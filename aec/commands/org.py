"""`aec org` command group: manage organization configuration overlays.

Phase 1 supports a single enrolled org loaded from a local YAML file with
``trust_mode: unsigned``. Signed trust modes and URL-based enrollment are
deferred to Phase 2. Multi-org coexistence is deferred to Phase 3.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from ..lib.org_config import (
    OrgConfigMultiOrgRejectedError,
    OrgConfigParseError,
    OrgConfigTrustError,
    OrgConfigUnknownSchemaError,
    OrgConfigValidationError,
    OrgPaths,
    discover_enrolled_orgs,
)
from ..lib.org_config.hashing import hash_config_bytes
from ..lib.org_config.parser import parse_org_config_text
from ..lib.org_config.state import OrgState, read_state, write_state
from ..lib.org_config.trust import UnsignedConsent, UnsignedConsentDeclined, verify_trust
from ..lib.org_config.validator import validate_org_config


app = typer.Typer(help="Manage organization configurations")


EXIT_TRUST = 10
EXIT_MULTI_ORG = 12
EXIT_VALIDATION = 13


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _looks_like_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _paths() -> OrgPaths:
    return OrgPaths.default()


@app.command("enroll")
def enroll_cmd(
    source: str = typer.Argument(..., help="Local path to org config YAML (URL support arrives in phase 2)"),
    allow_unsigned: bool = typer.Option(False, "--allow-unsigned", help="Bypass the unsigned-config consent prompt"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive prompts"),
):
    """Enroll an org configuration from a local YAML file."""
    if _looks_like_url(source):
        typer.echo("url fetch added in phase 2")
        raise typer.Exit(code=1)

    src_path = Path(source)
    if not src_path.exists() or not src_path.is_file():
        typer.echo(f"error: file not found: {source}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION)

    try:
        raw_bytes = src_path.read_bytes()
    except OSError as exc:
        typer.echo(f"error: could not read {source}: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc

    try:
        frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
        config = validate_org_config(frontmatter, body)
    except (OrgConfigParseError, OrgConfigValidationError, OrgConfigUnknownSchemaError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_VALIDATION) from exc

    # Trust check.
    acknowledged = allow_unsigned or yes
    if not acknowledged and config.trust_mode == "unsigned":
        typer.echo(
            "WARNING: this org config is unsigned. An attacker who controls the "
            "config file can change which skills, rules, agents, and MCPs are "
            "applied to your environment.",
            err=True,
        )
        acknowledged = typer.confirm("acknowledge unsigned-config risk and continue?", default=False)

    consent = UnsignedConsent(acknowledged=acknowledged)
    try:
        verify_trust(trust_mode=config.trust_mode, config_bytes=raw_bytes, consent=consent)
    except (OrgConfigTrustError, UnsignedConsentDeclined) as exc:
        typer.echo(f"trust error: {exc}", err=True)
        raise typer.Exit(code=EXIT_TRUST) from exc

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
        pubkey_fingerprint=None,
        pubkey_source=None,
        last_verified_at=now,
        last_applied_at=now,
        source_of_record="local",
        unsigned_warning_acknowledged_at=now if config.trust_mode == "unsigned" else None,
        key_rotation_pending=None,
    )
    write_state(paths, state)

    typer.echo(f"enrolled org '{config.org_id}'")


@app.command("list")
def list_cmd():
    """List enrolled organizations."""
    paths = _paths()
    try:
        orgs = discover_enrolled_orgs(paths)
    except OrgConfigMultiOrgRejectedError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_MULTI_ORG) from exc

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
    else:
        typer.echo("  state: (no state file)")


@app.command("status")
def status_cmd(
    org_id: Optional[str] = typer.Argument(None, help="Limit to a single org id"),
):
    """Show detailed status for enrolled organizations."""
    paths = _paths()
    try:
        orgs = discover_enrolled_orgs(paths)
    except OrgConfigMultiOrgRejectedError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=EXIT_MULTI_ORG) from exc

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


# Public alias matching the registration convention used elsewhere in cli.py.
org_app = app
