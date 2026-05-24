"""`aec org` command group: manage organization configuration overlays.

Phase 1 supports a single enrolled org loaded from a local YAML file with
``trust_mode: unsigned``. Signed trust modes and URL-based enrollment are
deferred to Phase 2. Multi-org coexistence is deferred to Phase 3.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from ..lib.org_config import (
    OrgConfigCryptoUnavailable,
    OrgConfigFetchError,
    OrgConfigParseError,
    OrgConfigTrustError,
    OrgConfigUnknownSchemaError,
    OrgConfigValidationError,
    OrgPaths,
    discover_enrolled_orgs,
)
from ..lib.org_config.fetch import fetch_bytes
from ..lib.org_config.hashing import hash_config_bytes
from ..lib.org_config.parser import parse_org_config_text
from ..lib.org_config.reconcile import open_conflicts
from ..lib.org_config.resolutions import Resolution, save_resolution
from ..lib.org_config.rotation import rotation_status
from ..lib.org_config.state import OrgState, read_state, write_state
from ..lib.org_config.trust import UnsignedConsent, UnsignedConsentDeclined, verify_trust
from ..lib.org_config.validator import validate_org_config


app = typer.Typer(help="Manage organization configurations")


EXIT_TRUST = 10
EXIT_VALIDATION = 13


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


def _verify_pinned_key_enroll(config, raw_bytes, sig_bytes, trust_fingerprint, yes):
    """Verify a pinned_key config and return (fingerprint, pubkey_source).

    Raises ``typer.Exit`` with the appropriate exit code on any failure.
    """
    if sig_bytes is None:
        typer.echo(
            "trust error: pinned_key config needs a detached signature "
            "(<config>.sig sidecar, signature_url, or --signature)",
            err=True,
        )
        raise typer.Exit(code=EXIT_TRUST)

    pubkey_b64 = config.trust_pubkey
    if not pubkey_b64 and config.trust_pubkey_url:
        try:
            pubkey_b64 = _url_fetcher(config.trust_pubkey_url).decode("utf-8").strip()
        except OrgConfigFetchError as exc:
            typer.echo(f"trust error: {exc}", err=True)
            raise typer.Exit(code=EXIT_TRUST) from exc

    prior = read_state(_paths(), config.org_id)
    pinned_fp = prior.pubkey_fingerprint if prior else None
    try:
        result = verify_trust(
            trust_mode="pinned_key",
            config_bytes=raw_bytes,
            consent=UnsignedConsent(acknowledged=True),
            pubkey_b64=pubkey_b64,
            signature=sig_bytes,
            pinned_fingerprint=pinned_fp,
        )
    except OrgConfigCryptoUnavailable as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc
    except OrgConfigTrustError as exc:
        typer.echo(f"trust error: {exc}", err=True)
        raise typer.Exit(code=EXIT_TRUST) from exc

    fp = result.pubkey_fingerprint
    if pinned_fp is None and not (trust_fingerprint or yes):
        typer.echo(f"public key fingerprint: {fp}")
        typer.echo("you should have received this fingerprint from your IT/security team.")
        if not typer.confirm("does this fingerprint match?", default=False):
            typer.echo("trust error: fingerprint not confirmed; enrollment aborted", err=True)
            raise typer.Exit(code=EXIT_TRUST)
    return fp, "inline"


def _verify_dns_anchor_enroll(config, raw_bytes, sig_bytes, trust_fingerprint, yes):
    """Verify a dns_anchor config and return (fingerprint, pubkey_source).

    Raises ``typer.Exit`` with the appropriate exit code on any failure.
    """
    if sig_bytes is None:
        typer.echo(
            "trust error: dns_anchor config needs a detached signature "
            "(<config>.sig sidecar, signature_url, or --signature)",
            err=True,
        )
        raise typer.Exit(code=EXIT_TRUST)

    prior = read_state(_paths(), config.org_id)
    pinned_fp = prior.pubkey_fingerprint if prior else None
    try:
        result = verify_trust(
            trust_mode="dns_anchor",
            config_bytes=raw_bytes,
            consent=UnsignedConsent(acknowledged=True),
            signature=sig_bytes,
            dns_domain=config.trust_dns_domain,
            pinned_fingerprint=pinned_fp,
            pubkey_fetcher=_pubkey_fetcher,
        )
    except OrgConfigCryptoUnavailable as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc
    except (OrgConfigTrustError, OrgConfigFetchError) as exc:
        typer.echo(f"trust error: {exc}", err=True)
        raise typer.Exit(code=EXIT_TRUST) from exc

    fp = result.pubkey_fingerprint
    if pinned_fp is None and not (trust_fingerprint or yes):
        typer.echo(f"public key fingerprint: {fp}")
        typer.echo(
            f"fetched from https://{config.trust_dns_domain}/.well-known/aec-pubkey"
        )
        if not typer.confirm("does this fingerprint match?", default=False):
            typer.echo("trust error: fingerprint not confirmed; enrollment aborted", err=True)
            raise typer.Exit(code=EXIT_TRUST)
    return fp, "dns_anchor"


@app.command("enroll")
def enroll_cmd(
    source: str = typer.Argument(..., help="Local path or https URL to an org config YAML"),
    allow_unsigned: bool = typer.Option(False, "--allow-unsigned", help="Bypass the unsigned-config consent prompt"),
    signature: Optional[str] = typer.Option(None, "--signature", help="Path to a detached signature file (signed modes)"),
    trust_fingerprint: bool = typer.Option(False, "--trust-fingerprint", help="Accept the pubkey fingerprint without prompting (signed modes)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts"),
):
    """Enroll an org configuration from a local YAML file or an https URL."""
    perform_enroll(
        source,
        allow_unsigned=allow_unsigned,
        signature=signature,
        trust_fingerprint=trust_fingerprint,
        yes=yes,
    )


def perform_enroll(
    source: str,
    *,
    allow_unsigned: bool = False,
    signature: Optional[str] = None,
    trust_fingerprint: bool = False,
    yes: bool = False,
) -> str:
    """Fetch/read, verify, and persist an org config. Returns the org_id.

    Shared by ``aec org enroll`` and ``aec install --org-config``.
    """
    is_url = _looks_like_url(source)
    src_path: Optional[Path] = None

    if is_url:
        if not source.startswith("https://"):
            typer.echo("error: only https:// URLs are supported for org configs", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
        raw_bytes = _fetch_config_bytes(source)
        source_of_record = "url"
        source_url: Optional[str] = source
    else:
        src_path = Path(source)
        if not src_path.exists() or not src_path.is_file():
            typer.echo(f"error: file not found: {source}", err=True)
            raise typer.Exit(code=EXIT_VALIDATION)
        try:
            raw_bytes = src_path.read_bytes()
        except OSError as exc:
            typer.echo(f"error: could not read {source}: {exc}", err=True)
            raise typer.Exit(code=EXIT_VALIDATION) from exc
        source_of_record = "local"
        source_url = None

    try:
        frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
        config = validate_org_config(frontmatter, body)
    except (OrgConfigParseError, OrgConfigValidationError, OrgConfigUnknownSchemaError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc

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
            sig_bytes = (
                _signature_for_url(config, source, signature)
                if is_url
                else _load_signature(src_path, signature)
            )
        except OrgConfigFetchError as exc:
            typer.echo(f"trust error: {exc}", err=True)
            raise typer.Exit(code=EXIT_TRUST) from exc
        if config.trust_mode == "pinned_key":
            pubkey_fingerprint, pubkey_source = _verify_pinned_key_enroll(
                config, raw_bytes, sig_bytes, trust_fingerprint, yes
            )
        else:
            pubkey_fingerprint, pubkey_source = _verify_dns_anchor_enroll(
                config, raw_bytes, sig_bytes, trust_fingerprint, yes
            )

    paths = _paths()
    paths.orgs_dir.mkdir(parents=True, exist_ok=True)

    dest = paths.config_for(config.org_id)
    dest.write_bytes(raw_bytes)

    now = _now_iso_utc()
    state = OrgState(
        org_id=config.org_id,
        config_version=config.config_version,
        config_hash=hash_config_bytes(raw_bytes),
        trust_mode=config.trust_mode,
        pubkey_fingerprint=pubkey_fingerprint,
        pubkey_source=pubkey_source,
        last_verified_at=now,
        last_applied_at=now,
        source_of_record=source_of_record,
        unsigned_warning_acknowledged_at=now if config.trust_mode == "unsigned" else None,
        key_rotation_pending=None,
        source_url=source_url,
    )
    write_state(paths, state)

    typer.echo(f"enrolled org '{config.org_id}'")
    return config.org_id


def refresh_url_sourced_orgs(paths: OrgPaths) -> list[tuple[str, str]]:
    """Re-fetch url-sourced org configs (used by ``aec update``).

    Returns a list of ``(org_id, status)`` where status is one of
    ``unchanged`` / ``updated`` / a failure message. Unchanged configs are
    left untouched so their applied-state timestamps are preserved.
    """
    results: list[tuple[str, str]] = []
    for enrolled in discover_enrolled_orgs(paths):
        st = read_state(paths, enrolled.config.org_id)
        if not (st and st.source_of_record == "url" and st.source_url):
            continue
        try:
            fetched = _url_fetcher(st.source_url)
        except OrgConfigFetchError as exc:
            results.append((st.org_id, f"fetch failed: {exc}"))
            continue
        if hash_config_bytes(fetched) == st.config_hash:
            results.append((st.org_id, "unchanged"))
            continue
        try:
            perform_enroll(st.source_url, allow_unsigned=True, yes=True)
            results.append((st.org_id, "updated"))
        except typer.Exit as exc:
            results.append((st.org_id, f"refresh blocked (exit {exc.exit_code})"))
    return results


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
        last_applied = state.last_applied_at if state else "(never)"
        trust_mode = state.trust_mode if state else cfg.trust_mode
        typer.echo(
            f"{cfg.org_id}\tconfig_version={cfg.config_version}\t"
            f"trust_mode={trust_mode}\tlast_applied_at={last_applied}"
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
        typer.echo(f"  last_applied_at: {state.last_applied_at}")
        typer.echo(f"  source_of_record: {state.source_of_record}")
        if state.pubkey_fingerprint:
            typer.echo(f"  pubkey_fingerprint: {state.pubkey_fingerprint}")
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
    for item_type in ("skills", "rules", "agents", "mcps"):
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
                dns_domain=config.trust_dns_domain,
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
    prior = read_state(paths, org_id)
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
            last_applied_at=now,
            source_of_record="local",
            unsigned_warning_acknowledged_at=None,
            key_rotation_pending=None,
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


# Public alias matching the registration convention used elsewhere in cli.py.
org_app = app
