"""`aec org` command group: manage organization configuration overlays.

Orgs enroll from a local file, an https URL, or a git repo
(``git+<url>#<ref>:<path>``), under unsigned, pinned_key, or dns_anchor trust.
"""
from __future__ import annotations

import dataclasses
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer

from ..lib.org_config import (
    OrgConfigCryptoUnavailable,
    OrgConfigError,
    OrgConfigFetchError,
    OrgConfigParseError,
    OrgConfigTrustError,
    OrgConfigUnknownSchemaError,
    OrgConfigValidationError,
    OrgPaths,
    discover_enrolled_orgs,
)
from ..lib.org_config import git_source
from ..lib.org_config.apply import apply_org_policy
from ..lib.org_config.crypto import decode_pubkey, fingerprint
from ..lib.org_config.discovery import migrate_state
from ..lib.org_config.fetch import fetch_bytes
from ..lib.org_config.hashing import hash_config_bytes
from ..lib.org_config.parser import parse_org_config_text
from ..lib.org_config.reconcile import open_conflicts
from ..lib.org_config.resolutions import Resolution, save_resolution
from ..lib.org_config.rotation import rotation_status
from ..lib.org_config.schema import ITEM_TYPES
from ..lib.org_config.state import OrgState, read_state, write_state
from ..lib.org_config.trust import UnsignedConsent, UnsignedConsentDeclined, verify_trust
from ..lib.org_config.validator import validate_org_config


app = typer.Typer(help="Manage organization configurations")


EXIT_TRUST = 10
EXIT_VALIDATION = 13
EXIT_PENDING = 14  # aec update: an org has a pending review, trust change, or failed refresh


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _looks_like_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _paths() -> OrgPaths:
    return OrgPaths.default()


def _pubkey_fetcher(url: str) -> bytes:
    """Fetch a well-known pubkey. Indirection point so tests can monkeypatch."""
    return fetch_bytes(url)


def _url_fetcher(url: str) -> bytes:
    """Fetch a remote config / signature / pubkey_url. Monkeypatched in tests."""
    return fetch_bytes(url)


def _fetch_config_bytes(url: str) -> bytes:
    try:
        return _url_fetcher(url)
    except OrgConfigFetchError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc


def _signature_for_url(config, url: str, signature_opt: Optional[str]) -> Optional[bytes]:
    """Acquire a detached signature for a url-fetched config.

    Precedence: explicit ``--signature`` local file, then the config's
    ``trust.signature_url``, then a ``<url>.sig`` sibling.
    """
    if signature_opt:
        sp = Path(signature_opt)
        return sp.read_bytes() if sp.exists() else None
    if config.trust_signature_url:
        return _url_fetcher(config.trust_signature_url)
    try:
        return _url_fetcher(url + ".sig")
    except OrgConfigFetchError:
        return None


def _load_signature(src_path: Path, signature_opt: Optional[str]) -> Optional[bytes]:
    """Locate a detached signature: explicit ``--signature`` or sidecar ``<config>.sig``."""
    if signature_opt:
        sp = Path(signature_opt)
        if not sp.exists():
            return None
        return sp.read_bytes()
    sidecar = src_path.with_name(src_path.name + ".sig")
    if sidecar.exists():
        return sidecar.read_bytes()
    return None


def _git_signature(dest: Path, src: "git_source.GitSource", signature_opt: Optional[str]):
    """Detached signature for a git-sourced config: ``--signature`` or ``<path>.sig`` in the checkout."""
    if signature_opt:
        sp = Path(signature_opt)
        return sp.read_bytes() if sp.exists() else None
    return git_source.read_file(dest, src.path + ".sig")


def _resolve_pubkey(config) -> Optional[str]:
    """The pinned_key public key: inline, or fetched once from ``trust.pubkey_url``."""
    if config.trust_pubkey or not config.trust_pubkey_url:
        return config.trust_pubkey
    return _url_fetcher(config.trust_pubkey_url).decode("utf-8").strip()


def _fingerprint_of(pubkey_b64: Optional[str]) -> Optional[str]:
    if not pubkey_b64:
        return None
    try:
        return fingerprint(decode_pubkey(pubkey_b64))
    except OrgConfigError:
        return None


def _anchor_of(trust_mode: str, pubkey_fingerprint: Optional[str], dns_domain: Optional[str]) -> dict:
    """The trust anchor: what a push must never change without a person consenting.

    A DNS key rotation is not part of it: that has its own path
    (``key_rotation_pending`` → ``aec org trust-rotate``).
    """
    anchor = {"trust_mode": trust_mode}
    if trust_mode == "pinned_key":
        anchor["pubkey_fingerprint"] = pubkey_fingerprint
    elif trust_mode == "dns_anchor":
        anchor["trust_dns_domain"] = dns_domain
    return anchor


def _recorded_anchor(st: OrgState) -> dict:
    return _anchor_of(st.trust_mode, st.pubkey_fingerprint, st.trust_dns_domain)


def _verify_signed_enroll(config, raw_bytes, sig_bytes, pubkey_b64, pinned_fp, confirm_fp):
    """Verify a pinned_key / dns_anchor config. Returns (fingerprint, pubkey_source).

    ``confirm_fp`` asks the person to confirm the fingerprint (first enroll or
    a trust-anchor change). Raises ``typer.Exit`` on any failure.
    """
    mode = config.trust_mode
    if sig_bytes is None:
        typer.echo(
            f"trust error: {mode} config needs a detached signature "
            "(<config>.sig sidecar, signature_url, or --signature)",
            err=True,
        )
        raise typer.Exit(code=EXIT_TRUST)
    try:
        result = verify_trust(
            trust_mode=mode,
            config_bytes=raw_bytes,
            consent=UnsignedConsent(acknowledged=True),
            pubkey_b64=pubkey_b64,
            signature=sig_bytes,
            dns_domain=config.trust_dns_domain,
            pinned_fingerprint=pinned_fp,
            pubkey_fetcher=_pubkey_fetcher,
        )
    except OrgConfigCryptoUnavailable as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc
    except OrgConfigError as exc:  # trust, fetch, malformed signature
        typer.echo(f"trust error: {exc}", err=True)
        raise typer.Exit(code=EXIT_TRUST) from exc

    fp = result.pubkey_fingerprint
    if confirm_fp:
        typer.echo(f"public key fingerprint: {fp}")
        if mode == "dns_anchor":
            typer.echo(f"fetched from https://{config.trust_dns_domain}/.well-known/aec-pubkey")
        else:
            typer.echo("you should have received this fingerprint from your IT/security team.")
        if not typer.confirm("does this fingerprint match?", default=False):
            typer.echo("trust error: fingerprint not confirmed; enrollment aborted", err=True)
            raise typer.Exit(code=EXIT_TRUST)
    return fp, ("inline" if mode == "pinned_key" else "dns_anchor")


@app.command("enroll")
def enroll_cmd(
    source: str = typer.Argument(
        ..., help="Local path, https URL, or git+<url>#<ref>:<path> to an org config YAML"
    ),
    allow_unsigned: bool = typer.Option(False, "--allow-unsigned", help="Bypass the unsigned-config consent prompt"),
    signature: Optional[str] = typer.Option(None, "--signature", help="Path to a detached signature file (signed modes)"),
    trust_fingerprint: bool = typer.Option(False, "--trust-fingerprint", help="Accept the pubkey fingerprint without prompting (signed modes)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts"),
    replace: Annotated[Optional[str], typer.Option(
        "--replace", metavar="ORG_ID",
        help="Swap an enrolled org's source, keeping its conflict resolutions",
    )] = None,
):
    """Enroll an org configuration from a local file, an https URL, or a git repo."""
    perform_enroll(
        source,
        allow_unsigned=allow_unsigned,
        signature=signature,
        trust_fingerprint=trust_fingerprint,
        yes=yes,
        replace=replace,
    )


def _read_source(source: str, signature: Optional[str], tmp_dir: Path):
    """Read a config from its source. Returns (raw_bytes, sig_loader, source_fields, clone).

    ``sig_loader(config)`` returns the detached signature, or None. ``clone`` is
    the temporary git checkout to keep, or None.
    """
    if git_source.is_git_source(source):
        try:
            src = git_source.parse_git_source(source)
            clone = tmp_dir / "repo"
            commit = git_source.clone(src, clone)
            raw = git_source.read_file(clone, src.path)
        except (OrgConfigValidationError, OrgConfigFetchError) as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=EXIT_VALIDATION) from exc
        if raw is None:
            typer.echo(f"error: {src.path} not found in {src.url}@{src.ref}", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
        fields = dict(
            source_of_record="git", source_repo=src.url, source_ref=src.ref,
            source_path=src.path, resolved_commit=commit,
        )
        return raw, lambda _cfg: _git_signature(clone, src, signature), fields, clone
    if _looks_like_url(source):
        if not source.startswith("https://"):
            typer.echo("error: only https:// URLs are supported for org configs", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
        raw = _fetch_config_bytes(source)
        sig_loader = lambda cfg: _signature_for_url(cfg, source, signature)  # noqa: E731
        return raw, sig_loader, dict(source_of_record="url", source_url=source), None
    src_path = Path(source)
    if not src_path.is_file():
        typer.echo(f"error: file not found: {source}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION)
    try:
        raw = src_path.read_bytes()
    except OSError as exc:
        typer.echo(f"error: could not read {source}: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc
    return raw, lambda _cfg: _load_signature(src_path, signature), dict(source_of_record="local"), None


def perform_enroll(
    source: str,
    *,
    allow_unsigned: bool = False,
    signature: Optional[str] = None,
    trust_fingerprint: bool = False,
    yes: bool = False,
    replace: Optional[str] = None,
) -> str:
    """Read, verify, and persist an org config. Returns the org_id.

    Shared by ``aec org enroll`` and ``aec install --org-config``. Re-enrolling
    an org re-verifies trust from scratch; a trust-anchor change (mode, pinned
    key, dns domain) needs a person at a prompt, so ``--yes`` refuses it.
    """
    paths = _paths()
    if replace is not None:
        if read_state(paths, replace) is None and not paths.config_for(replace).exists():
            typer.echo(f"error: org '{replace}' is not enrolled; --replace needs an enrolled org", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
        # Persist any legacy-state migration before the source is read.
        migrate_state(paths, replace)

    paths.orgs_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=".tmp-enroll-", dir=paths.orgs_dir))
    try:
        return _enroll_from(paths, source, tmp_dir, allow_unsigned, signature, trust_fingerprint, yes, replace)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _enroll_from(paths, source, tmp_dir, allow_unsigned, signature, trust_fingerprint, yes, replace) -> str:
    raw_bytes, sig_loader, source_fields, clone = _read_source(source, signature, tmp_dir)

    try:
        frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
        config = validate_org_config(frontmatter, body)
    except (OrgConfigParseError, OrgConfigValidationError, OrgConfigUnknownSchemaError, UnicodeDecodeError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc
    if replace is not None and config.org_id != replace:
        typer.echo(
            f"error: {source} is org '{config.org_id}', not '{replace}'; --replace refuses a different org",
            err=True,
        )
        raise typer.Exit(code=EXIT_VALIDATION)

    prior = migrate_state(paths, config.org_id)
    pubkey_b64 = None
    if config.trust_mode == "pinned_key":
        try:
            pubkey_b64 = _resolve_pubkey(config)
        except OrgConfigFetchError as exc:
            typer.echo(f"trust error: {exc}", err=True)
            raise typer.Exit(code=EXIT_TRUST) from exc

    anchor_changed = prior is not None and (
        _recorded_anchor(prior)
        != _anchor_of(config.trust_mode, _fingerprint_of(pubkey_b64), config.trust_dns_domain)
        or bool(prior.pending and prior.pending.get("kind") == "trust_change")
    )
    if anchor_changed:
        if yes:
            typer.echo(
                f"trust error: the trust anchor of '{config.org_id}' changed "
                f"({_recorded_anchor(prior)} -> {config.trust_mode}); "
                "re-run without --yes to confirm it at the prompt",
                err=True,
            )
            raise typer.Exit(code=EXIT_TRUST)
        typer.echo(f"the trust anchor of '{config.org_id}' changed; confirm it as on a first enroll.")
        allow_unsigned = trust_fingerprint = False
    first_trust = prior is None or anchor_changed

    pubkey_fingerprint: Optional[str] = None
    pubkey_source: Optional[str] = None
    if config.trust_mode == "unsigned":
        acknowledged = allow_unsigned or yes
        if not acknowledged:
            typer.echo(
                "WARNING: this org config is unsigned. An attacker who controls the "
                "config file can change which skills, rules, agents, and MCPs are "
                "applied to your environment.",
                err=True,
            )
            acknowledged = typer.confirm("acknowledge unsigned-config risk and continue?", default=False)
        try:
            verify_trust(
                trust_mode="unsigned",
                config_bytes=raw_bytes,
                consent=UnsignedConsent(acknowledged=acknowledged),
            )
        except (OrgConfigTrustError, UnsignedConsentDeclined) as exc:
            typer.echo(f"trust error: {exc}", err=True)
            raise typer.Exit(code=EXIT_TRUST) from exc
    else:  # pinned_key or dns_anchor
        try:
            sig_bytes = sig_loader(config)
        except (OrgConfigFetchError, OrgConfigValidationError) as exc:
            typer.echo(f"trust error: {exc}", err=True)
            raise typer.Exit(code=EXIT_TRUST) from exc
        pubkey_fingerprint, pubkey_source = _verify_signed_enroll(
            config, raw_bytes, sig_bytes, pubkey_b64,
            pinned_fp=None if first_trust else prior.pubkey_fingerprint,
            confirm_fp=first_trust and not (trust_fingerprint or yes),
        )

    org_dir = paths.org_dir_for(config.org_id)
    repo_dir = org_dir / "repo"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    if clone is not None:
        org_dir.mkdir(parents=True, exist_ok=True)
        clone.rename(repo_dir)
    (org_dir / STAGED_NAME).unlink(missing_ok=True)
    paths.config_for(config.org_id).write_bytes(raw_bytes)

    now = _now_iso_utc()
    write_state(paths, OrgState(
        org_id=config.org_id,
        config_version=config.config_version,
        config_hash=hash_config_bytes(raw_bytes),
        trust_mode=config.trust_mode,
        pubkey_fingerprint=pubkey_fingerprint,
        pubkey_source=pubkey_source,
        last_verified_at=now,
        last_applied_at=prior.last_applied_at if prior else None,
        unsigned_warning_acknowledged_at=now if config.trust_mode == "unsigned" else None,
        key_rotation_pending=None,
        trust_dns_domain=config.trust_dns_domain if config.trust_mode == "dns_anchor" else None,
        **source_fields,
    ))

    typer.echo(f"enrolled org '{config.org_id}'")
    return config.org_id


# --------------------------------------------------------------------------- #
#  Refresh (aec update): fetch, evaluate against recorded trust, then        #
#  promote (signed + managed), stage for review, or record a pending.       #
# --------------------------------------------------------------------------- #

STAGED_NAME = "staged.yaml"


def _staged_path(paths: OrgPaths, org_id: str) -> Path:
    return paths.org_dir_for(org_id) / STAGED_NAME


def _set_pending(paths: OrgPaths, st: OrgState, pending: dict) -> OrgState:
    """Record ``pending``. A ``trust_change`` is never downgraded to a lesser kind."""
    current = st.pending or {}
    if current.get("kind") == "trust_change" and pending["kind"] != "trust_change":
        return st
    st = dataclasses.replace(st, pending=pending)
    write_state(paths, st)
    return st


def _fetch_remote(paths: OrgPaths, st: OrgState):
    """Fetch a url / git org's config. Returns (raw_bytes, sig_loader, commit)."""
    if st.source_of_record == "url":
        raw = _url_fetcher(st.source_url)
        return raw, (lambda cfg: _signature_for_url(cfg, st.source_url, None)), hash_config_bytes(raw)
    src = git_source.validate_git_source(st.source_repo, st.source_ref, st.source_path)
    dest = paths.org_dir_for(st.org_id) / "repo"
    commit = git_source.refresh(src, dest) if dest.exists() else git_source.clone(src, dest)
    raw = git_source.read_file(dest, src.path)
    if raw is None:
        raise OrgConfigFetchError(f"{src.path} not found at {src.url}@{src.ref} ({commit[:12]})")
    return raw, (lambda _cfg: _git_signature(dest, src, None)), commit


def _review_summary(paths: OrgPaths, org_id: str, new_cfg) -> str:
    """One line for the pending record; prints the full policy diff."""
    from ..lib.org_config.propagation import policy_diff

    old_cfg = next((e.config for e in discover_enrolled_orgs(paths) if e.config.org_id == org_id), None)
    if old_cfg is None:
        return f"config_version {new_cfg.config_version}"
    diff = policy_diff(old_cfg, new_cfg)
    for label, values in (
        ("added", diff.items_added), ("removed", diff.items_removed),
        ("changed", diff.items_changed), ("sources", diff.source_changes),
        ("preferences", diff.preference_changes),
    ):
        for v in values:
            typer.echo(f"    {label}: {v}")
    if diff.install_mode_change:
        typer.echo(f"    install_mode: {diff.install_mode_change}")
    return (
        f"config_version {old_cfg.config_version}->{new_cfg.config_version}: "
        f"+{len(diff.items_added)} -{len(diff.items_removed)} ~{len(diff.items_changed)} items"
    )


def _refresh_one(paths: OrgPaths, st: OrgState) -> tuple[str, bool]:
    """Refresh one remote org. Returns (status, promoted)."""
    try:
        raw, sig_loader, commit = _fetch_remote(paths, st)
    except (OrgConfigFetchError, OrgConfigValidationError) as exc:
        _set_pending(paths, st, {"kind": "verify_failed", "reason": f"fetch failed: {exc}"})
        return f"verify_failed: fetch failed: {exc}", False

    def failed(reason: str) -> tuple[str, bool]:
        _set_pending(paths, st, {"kind": "verify_failed", "commit": commit, "reason": reason})
        return f"verify_failed: {reason}", False

    has_trust_change = bool(st.pending and st.pending.get("kind") == "trust_change")
    if hash_config_bytes(raw) == st.config_hash and not has_trust_change:
        # Back to the applied content: a stale review or verify failure no longer applies.
        if st.pending:
            write_state(paths, dataclasses.replace(st, pending=None))
        _staged_path(paths, st.org_id).unlink(missing_ok=True)
        return "unchanged", False

    try:
        frontmatter, body = parse_org_config_text(raw.decode("utf-8"))
        cfg = validate_org_config(frontmatter, body)
    except (OrgConfigParseError, OrgConfigValidationError, OrgConfigUnknownSchemaError, UnicodeDecodeError) as exc:
        return failed(str(exc))
    if cfg.org_id != st.org_id:
        return failed(f"fetched config is org '{cfg.org_id}', not '{st.org_id}'")

    pubkey_b64 = None
    if cfg.trust_mode == "pinned_key":
        try:
            pubkey_b64 = _resolve_pubkey(cfg)
        except OrgConfigFetchError as exc:
            return failed(f"pubkey fetch failed: {exc}")
    new_anchor = _anchor_of(cfg.trust_mode, _fingerprint_of(pubkey_b64), cfg.trust_dns_domain)
    if has_trust_change or new_anchor != _recorded_anchor(st):
        previous = st.pending["from"] if has_trust_change else _recorded_anchor(st)
        _set_pending(paths, st, {"kind": "trust_change", "from": previous, "to": new_anchor})
        return "trust_change", False

    # The anchor matches the recorded one, so "signed" is the recorded trust_mode.
    if st.trust_mode != "unsigned":
        try:
            verify_trust(
                trust_mode=st.trust_mode,
                config_bytes=raw,
                consent=UnsignedConsent(acknowledged=True),
                pubkey_b64=pubkey_b64,
                signature=sig_loader(cfg),
                dns_domain=st.trust_dns_domain,
                pinned_fingerprint=st.pubkey_fingerprint,
                pubkey_fetcher=_pubkey_fetcher,
            )
        except OrgConfigError as exc:  # trust, fetch, malformed signature, crypto missing
            return failed(str(exc))

    now = _now_iso_utc()
    if st.trust_mode != "unsigned" and cfg.install_mode == "managed":
        _promote(paths, st, raw, cfg, commit, now)
        _staged_path(paths, st.org_id).unlink(missing_ok=True)
        return "updated", True

    staged = _staged_path(paths, st.org_id)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(raw)
    typer.echo(f"org '{st.org_id}' changed upstream; review it, then run `aec org apply`:")
    summary = _review_summary(paths, st.org_id, cfg)
    _set_pending(paths, st, {"kind": "review", "commit": commit, "summary": summary})
    return "pending review", False


def _promote(paths: OrgPaths, st: OrgState, raw: bytes, cfg, commit: str, now: str) -> OrgState:
    """Make verified bytes the enrolled config and clear any pending."""
    paths.config_for(st.org_id).write_bytes(raw)
    st = dataclasses.replace(
        st,
        config_version=cfg.config_version,
        config_hash=hash_config_bytes(raw),
        last_verified_at=now,
        resolved_commit=commit if st.source_of_record == "git" else st.resolved_commit,
        pending=None,
    )
    write_state(paths, st)
    return st


def refresh_remote_orgs(paths: OrgPaths) -> list[tuple[str, str]]:
    """Refresh url- and git-sourced orgs (used by ``aec update``; never prompts).

    Returns ``(org_id, status)`` pairs. Local orgs are never fetched. Signed +
    managed + verified changes are applied; everything else lands in
    ``pending`` for a person.
    """
    results: list[tuple[str, str]] = []
    promoted = False
    for enrolled in discover_enrolled_orgs(paths):
        org_id = enrolled.config.org_id
        st = read_state(paths, org_id)
        if st is None or st.source_of_record not in ("url", "git"):
            continue
        st = migrate_state(paths, org_id)
        status, did_promote = _refresh_one(paths, st)
        results.append((org_id, status))
        promoted = promoted or did_promote
    if promoted:
        apply_org_policy(paths, mode_override="managed")
    return results


def pending_orgs(paths: OrgPaths) -> list[OrgState]:
    """Enrolled orgs whose state records a ``pending`` for a person."""
    out = []
    for enrolled in discover_enrolled_orgs(paths):
        st = read_state(paths, enrolled.config.org_id)
        if st is not None and st.pending:
            out.append(st)
    return out


def pending_fix(st: OrgState) -> str:
    """One line naming an org's pending item and the command that clears it."""
    kind = st.pending.get("kind")
    if kind == "review":
        return (
            f"org '{st.org_id}' has an unreviewed change ({st.pending.get('summary')}): "
            f"run `aec org apply`, or `aec org apply --decline {str(st.pending.get('commit'))[:12]}`"
        )
    if kind == "trust_change":
        return (
            f"org '{st.org_id}' trust anchor changed: run `aec org enroll --replace {st.org_id} <source>`"
        )
    return f"org '{st.org_id}' refresh failed ({st.pending.get('reason')}): fix the source, then `aec update`"


@app.command("list")
def list_cmd():
    """List enrolled organizations."""
    paths = _paths()
    orgs = discover_enrolled_orgs(paths)

    if not orgs:
        typer.echo("no orgs enrolled")
        return

    for enrolled in orgs:
        cfg = enrolled.config
        state = read_state(paths, cfg.org_id)
        last_applied = (state.last_applied_at if state else None) or "never applied"
        trust_mode = state.trust_mode if state else cfg.trust_mode
        pending = f"\tpending={state.pending.get('kind')}" if state and state.pending else ""
        typer.echo(
            f"{cfg.org_id}\tconfig_version={cfg.config_version}\t"
            f"trust_mode={trust_mode}\tlast_applied_at={last_applied}{pending}"
        )


def _print_status_for(paths: OrgPaths, enrolled) -> None:
    cfg = enrolled.config
    state = read_state(paths, cfg.org_id)
    typer.echo(f"org_id: {cfg.org_id}")
    typer.echo(f"  org_name: {cfg.org_name}")
    typer.echo(f"  schema_version: {cfg.schema_version}")
    typer.echo(f"  config_version: {cfg.config_version}")
    typer.echo(f"  trust_mode: {cfg.trust_mode}")
    if cfg.trust_mode == "unsigned":
        typer.echo("  WARNING: unsigned config — integrity is not cryptographically verified")
    typer.echo(f"  config_hash: {enrolled.content_hash}")
    typer.echo(f"  source_path: {enrolled.source_path}")
    if state is not None:
        typer.echo(f"  last_verified_at: {state.last_verified_at}")
        typer.echo(f"  last_applied_at: {state.last_applied_at or 'never applied'}")
        typer.echo(f"  source_of_record: {state.source_of_record}")
        if state.source_of_record == "git":
            typer.echo(f"  source: git+{state.source_repo}#{state.source_ref}:{state.source_path}")
            typer.echo(f"  resolved_commit: {state.resolved_commit}")
        if state.pubkey_fingerprint:
            typer.echo(f"  pubkey_fingerprint: {state.pubkey_fingerprint}")
        if state.trust_mode == "dns_anchor":
            typer.echo(f"  trust_dns_domain: {state.trust_dns_domain or 'not recorded'}")
        if state.pending:
            typer.echo(f"  pending: {pending_fix(state)}")
        rs = rotation_status(
            pending=state.key_rotation_pending, now=_now_iso_utc(), org_id=cfg.org_id
        )
        if rs.state == "warn":
            typer.echo(f"  key_rotation: PENDING ({rs.days_remaining} days remaining) — {rs.message}")
        elif rs.state == "locked":
            typer.echo(f"  key_rotation: LOCKED — {rs.message}")
    else:
        typer.echo("  state: (no state file)")


@app.command("status")
def status_cmd(
    org_id: Optional[str] = typer.Argument(None, help="Limit to a single org id"),
):
    """Show detailed status for enrolled organizations."""
    paths = _paths()
    orgs = discover_enrolled_orgs(paths)

    if org_id is not None:
        matches = [e for e in orgs if e.config.org_id == org_id]
        if not matches:
            typer.echo(f"error: org '{org_id}' is not enrolled", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
        _print_status_for(paths, matches[0])
        return

    if not orgs:
        typer.echo("no orgs enrolled")
        return

    for enrolled in orgs:
        _print_status_for(paths, enrolled)


@app.command("show")
def show_cmd(
    org_id: str = typer.Argument(..., help="Org id to show"),
    raw: bool = typer.Option(False, "--raw", help="Print the on-disk config file verbatim"),
):
    """Print the resolved (or raw) config for an enrolled org."""
    paths = _paths()
    cfg_path = paths.config_for(org_id)
    if not cfg_path.exists():
        typer.echo(f"error: org '{org_id}' is not enrolled (no file at {cfg_path})", err=True)
        raise typer.Exit(code=EXIT_VALIDATION)

    raw_bytes = cfg_path.read_bytes()

    if raw:
        typer.echo(raw_bytes.decode("utf-8"))
        return

    try:
        frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
        config = validate_org_config(frontmatter, body)
    except (OrgConfigParseError, OrgConfigValidationError, OrgConfigUnknownSchemaError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc

    typer.echo(f"schema_version: {config.schema_version}")
    typer.echo(f"org_id: {config.org_id}")
    typer.echo(f"org_name: {config.org_name}")
    typer.echo(f"config_version: {config.config_version}")
    if config.description:
        typer.echo(f"description: {config.description}")
    typer.echo(f"trust_mode: {config.trust_mode}")
    typer.echo("default_sources:")
    for k, v in sorted(config.default_sources.items()):
        typer.echo(f"  {k}: {v}")
    typer.echo(f"custom_sources: {len(config.custom_sources)}")
    typer.echo("items:")
    for item_type in ITEM_TYPES:
        count = len(config.items.get(item_type, {}))
        typer.echo(f"  {item_type}: {count}")


@app.command("remove")
def remove_cmd(
    org_id: str = typer.Argument(..., help="Org id to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Remove an enrolled org's config and state."""
    paths = _paths()
    cfg_path = paths.config_for(org_id)
    state_path = paths.state_for(org_id)
    lock_path = paths.state_lock_for(org_id)

    if not cfg_path.exists() and not state_path.exists():
        typer.echo(f"error: org '{org_id}' is not enrolled", err=True)
        raise typer.Exit(code=EXIT_VALIDATION)

    if not yes:
        confirmed = typer.confirm(f"remove org '{org_id}' (config + state)?", default=False)
        if not confirmed:
            typer.echo("aborted")
            raise typer.Exit(code=1)

    for p in (cfg_path, state_path, lock_path):
        try:
            if p.exists():
                p.unlink()
        except OSError as exc:
            typer.echo(f"warning: could not remove {p}: {exc}", err=True)
    shutil.rmtree(paths.org_dir_for(org_id), ignore_errors=True)  # git clone + staged review

    typer.echo(f"removed org '{org_id}'")


@app.command("trust-rotate")
def trust_rotate_cmd(
    org_id: str = typer.Argument(..., help="Org id whose signing key to rotate"),
    signature: Optional[str] = typer.Option(None, "--signature", help="Detached signature for the current config"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the fingerprint confirmation prompt"),
):
    """Acknowledge a rotated public key for a signed org (pinned_key or dns_anchor)."""
    paths = _paths()
    cfg_path = paths.config_for(org_id)
    if not cfg_path.exists():
        typer.echo(f"error: org '{org_id}' is not enrolled", err=True)
        raise typer.Exit(code=EXIT_VALIDATION)
    prior = migrate_state(paths, org_id)
    if prior is not None and prior.pending and prior.pending.get("kind") == "trust_change":
        typer.echo(
            f"trust error: '{org_id}' has a pending trust-anchor change; a key rotation "
            f"cannot confirm it. Run `aec org enroll --replace {org_id} <source>`.",
            err=True,
        )
        raise typer.Exit(code=EXIT_TRUST)

    raw_bytes = cfg_path.read_bytes()
    try:
        frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
        config = validate_org_config(frontmatter, body)
    except (OrgConfigParseError, OrgConfigValidationError, OrgConfigUnknownSchemaError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc

    if config.trust_mode not in ("pinned_key", "dns_anchor"):
        typer.echo(
            f"error: org '{org_id}' is not a signed org (trust_mode={config.trust_mode})",
            err=True,
        )
        raise typer.Exit(code=EXIT_VALIDATION)

    sig_bytes = _load_signature(cfg_path, signature)
    if sig_bytes is None:
        typer.echo(
            "error: need a detached signature for the current config "
            "(<config>.sig sidecar or --signature)",
            err=True,
        )
        raise typer.Exit(code=EXIT_VALIDATION)

    # Verify the config against its new key (no pinned comparison — that is the
    # whole point of a rotation), then require explicit acknowledgment.
    try:
        if config.trust_mode == "pinned_key":
            result = verify_trust(
                trust_mode="pinned_key",
                config_bytes=raw_bytes,
                consent=UnsignedConsent(acknowledged=True),
                pubkey_b64=config.trust_pubkey,
                signature=sig_bytes,
                pinned_fingerprint=None,
            )
            pubkey_source = "inline"
        else:  # dns_anchor
            result = verify_trust(
                trust_mode="dns_anchor",
                config_bytes=raw_bytes,
                consent=UnsignedConsent(acknowledged=True),
                signature=sig_bytes,
                # The recorded domain, never the on-disk yaml's: a rotation
                # changes the key, not where the key comes from.
                dns_domain=prior.trust_dns_domain if prior else config.trust_dns_domain,
                pinned_fingerprint=None,
                pubkey_fetcher=_pubkey_fetcher,
            )
            pubkey_source = "dns_anchor"
    except OrgConfigCryptoUnavailable as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc
    except (OrgConfigTrustError, OrgConfigFetchError) as exc:
        typer.echo(f"trust error: {exc}", err=True)
        raise typer.Exit(code=EXIT_TRUST) from exc

    new_fp = result.pubkey_fingerprint
    old_fp = prior.pubkey_fingerprint if prior else None
    if old_fp == new_fp:
        typer.echo(f"no rotation needed: key fingerprint unchanged ({new_fp})")
        return

    if not yes:
        typer.echo(f"old fingerprint: {old_fp}")
        typer.echo(f"new fingerprint: {new_fp}")
        if not typer.confirm("acknowledge the rotated key?", default=False):
            typer.echo("aborted")
            raise typer.Exit(code=1)

    now = _now_iso_utc()
    if prior is not None:
        new_state = dataclasses.replace(
            prior,
            config_version=config.config_version,
            config_hash=hash_config_bytes(raw_bytes),
            pubkey_fingerprint=new_fp,
            pubkey_source=pubkey_source,
            last_verified_at=now,
            key_rotation_pending=None,
        )
    else:
        new_state = OrgState(
            org_id=org_id,
            config_version=config.config_version,
            config_hash=hash_config_bytes(raw_bytes),
            trust_mode=config.trust_mode,
            pubkey_fingerprint=new_fp,
            pubkey_source=pubkey_source,
            last_verified_at=now,
            last_applied_at=None,
            source_of_record="local",
            unsigned_warning_acknowledged_at=None,
            key_rotation_pending=None,
            trust_dns_domain=config.trust_dns_domain if config.trust_mode == "dns_anchor" else None,
        )
    write_state(paths, new_state)
    typer.echo(f"rotated pinned key for '{org_id}' to {new_fp}")


def _format_conflict(conflict) -> str:
    parts = ", ".join(f"{p.org_id}={p.value}" for p in conflict.participants)
    return f"[{conflict.conflict_id}] {conflict.kind} on {conflict.subject}: {parts}"


def _resolve_one(paths: OrgPaths, oc) -> None:
    conflict = oc.conflict
    typer.echo("")
    typer.echo(f"Conflict ({conflict.kind}) on {conflict.subject}:")
    options: list[tuple[str, str]] = [
        (f"honor:{p.org_id}", f"honor {p.org_id} ({p.value})") for p in conflict.participants
    ]
    options.append(("skip", "skip — apply nobody's choice for this item"))
    options.append(("defer", "defer — ask me again next time"))
    for i, (_, label) in enumerate(options, start=1):
        typer.echo(f"  {i}. {label}")

    choice = typer.prompt(f"Choice [1-{len(options)}]", default=str(len(options)))
    try:
        decision = options[int(choice) - 1][0]
    except (ValueError, IndexError):
        typer.echo("invalid choice; deferring", err=True)
        return

    if decision == "defer":
        typer.echo(f"deferred {conflict.subject}")
        return

    save_resolution(
        paths,
        Resolution(
            conflict_id=conflict.conflict_id,
            decision=decision,
            input_hash=oc.input_hash,
            decided_at=_now_iso_utc(),
        ),
    )
    typer.echo(f"resolved {conflict.subject}: {decision}")


@app.command("resolve")
def resolve_cmd(
    conflict_id: Optional[str] = typer.Argument(None, help="Resolve a single conflict by id"),
    list_only: bool = typer.Option(False, "--list", help="List open conflicts without prompting"),
):
    """Resolve conflicts between multiple enrolled org configs."""
    paths = _paths()
    opens = open_conflicts(paths)

    if not opens:
        typer.echo("no unresolved org conflicts")
        return

    if list_only:
        for oc in opens:
            typer.echo(_format_conflict(oc.conflict))
        return

    if conflict_id is not None:
        targets = [oc for oc in opens if oc.conflict.conflict_id == conflict_id]
        if not targets:
            typer.echo(f"error: no open conflict with id '{conflict_id}'", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
    else:
        targets = opens

    for oc in targets:
        _resolve_one(paths, oc)


@app.command("apply")
def apply_cmd(
    enroll: Optional[str] = typer.Option(
        None, "--enroll", help="Enroll a config (local path or https url) before applying"
    ),
    allow_unsigned: bool = typer.Option(False, "--allow-unsigned", help="Allow an unsigned --enroll source"),
    managed: bool = typer.Option(False, "--managed", help="Force silent (managed) apply"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan without applying"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without confirmation (guided mode)"),
    decline: Optional[str] = typer.Option(
        None, "--decline", metavar="COMMIT",
        help="Discard a pending upstream change (commit prefix, 7+ chars) instead of applying it",
    ),
):
    """Apply enrolled org policy to this environment (preferences, prompts, items).

    A change ``aec update`` staged for review is part of what this applies;
    ``--decline <commit>`` discards it instead.
    """
    paths = _paths()
    if decline is not None:
        _decline_review(paths, decline)
        return
    if enroll:
        perform_enroll(enroll, allow_unsigned=allow_unsigned, yes=yes)

    # Promote staged reviews first so the propagation gate sees them as the
    # enrolled content; roll back if the apply does not happen.
    backups = _promote_staged_reviews(paths)
    confirm = (lambda _policy: True) if yes else None
    outcome = apply_org_policy(
        paths,
        mode_override="managed" if managed else None,
        dry_run=dry_run,
        confirm=confirm,
    )
    for org_id, (old_bytes, old_state) in backups.items():
        if outcome.skipped_reason is None:
            _staged_path(paths, org_id).unlink(missing_ok=True)
        else:
            paths.config_for(org_id).write_bytes(old_bytes)
            write_state(paths, old_state)
    if outcome.skipped_reason == "locked":
        raise typer.Exit(code=EXIT_TRUST)


def _promote_staged_reviews(paths: OrgPaths) -> dict:
    """Promote every staged review. Returns ``{org_id: (old_yaml_bytes, old_state)}``."""
    backups = {}
    for st in pending_orgs(paths):
        staged = _staged_path(paths, st.org_id)
        if st.pending.get("kind") != "review" or not staged.exists():
            continue
        raw = staged.read_bytes()
        frontmatter, body = parse_org_config_text(raw.decode("utf-8"))
        cfg = validate_org_config(frontmatter, body)
        backups[st.org_id] = (paths.config_for(st.org_id).read_bytes(), st)
        _promote(paths, st, raw, cfg, st.pending.get("commit"), _now_iso_utc())
    return backups


def _decline_review(paths: OrgPaths, commit_prefix: str) -> None:
    if len(commit_prefix) < 7:
        typer.echo("error: --decline needs at least 7 characters of the commit", err=True)
        raise typer.Exit(code=EXIT_VALIDATION)
    pending = pending_orgs(paths)
    matches = [st for st in pending if str(st.pending.get("commit", "")).startswith(commit_prefix)]
    if not matches:
        # A trust_change has no commit to name; say what clears it instead.
        trust = [st for st in pending if st.pending.get("kind") == "trust_change"]
        typer.echo(f"error: no pending review matches '{commit_prefix}'", err=True)
        for st in trust:
            typer.echo(f"  {pending_fix(st)}", err=True)
        raise typer.Exit(code=EXIT_TRUST if trust else EXIT_VALIDATION)
    for st in matches:
        if st.pending.get("kind") != "review":
            typer.echo(
                f"error: '{st.org_id}' pending is {st.pending.get('kind')}, not a review; "
                f"{pending_fix(st)}",
                err=True,
            )
            raise typer.Exit(code=EXIT_TRUST if st.pending.get("kind") == "trust_change" else EXIT_VALIDATION)
        _staged_path(paths, st.org_id).unlink(missing_ok=True)
        write_state(paths, dataclasses.replace(st, pending=None))
        typer.echo(f"declined {st.pending.get('commit')} for org '{st.org_id}'")


# Public alias matching the registration convention used elsewhere in cli.py.
org_app = app
