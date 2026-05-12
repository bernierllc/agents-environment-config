"""`aec configure-agent` — write/refresh/remove the agent blurb block."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

from aec import __version__
from aec.lib.agent_blurb.config import (
    load_config, save_config, new_skeleton, config_path,
)
from aec.lib.agent_blurb.drift import DriftState, compute_drift
from aec.lib.agent_blurb.markers import find_block, replace_block
from aec.lib.agent_blurb.profile import PROFILES, DEFAULT_PROFILE
from aec.lib.agent_blurb.render import (
    render_block, shipped_template_hash, sha256_short, extract_inner_body,
)
from aec.lib.agent_blurb.targets import (
    discover_targets, AgentTarget, resolve_path_for_agent_key,
)
from aec.lib.atomic_write import atomic_write_text
from aec.lib.console import Console


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_scopes(scope: Optional[str], interactive: bool) -> List[str]:
    if scope == "both":
        return ["project", "global"]
    if scope in ("project", "global"):
        return [scope]
    if not interactive:
        raise typer.BadParameter("--scope is required in non-interactive mode")
    return _prompt_scopes()


def _prompt_scopes() -> List[str]:
    in_repo = Path.cwd().joinpath(".git").exists()
    default = "project" if in_repo else "global"
    typer.echo("Where to install the blurb?")
    typer.echo("  1) project context")
    typer.echo("  2) global context")
    typer.echo("  3) both")
    raw = typer.prompt(f"Select (default: {default})", default=default)
    if raw in ("1", "project"):
        return ["project"]
    if raw in ("2", "global"):
        return ["global"]
    if raw in ("3", "both"):
        return ["project", "global"]
    raise typer.BadParameter(f"Invalid scope: {raw}")


def _prompt_profile() -> str:
    typer.echo("Choose a profile:")
    for name in ("conservative", "balanced", "permissive", "custom"):
        marker = " (default)" if name == DEFAULT_PROFILE else ""
        typer.echo(f"  - {name}{marker}")
    raw = typer.prompt("profile", default=DEFAULT_PROFILE)
    if raw not in PROFILES and raw != "custom":
        raise typer.BadParameter(f"Unknown profile: {raw}")
    return raw


def _resolve_targets(
    scope: str, root: Optional[Path], agent_files: Optional[str],
    interactive: bool = False,
) -> List[AgentTarget]:
    detected = discover_targets(scope=scope, root=root)
    if agent_files == "all":
        return detected
    if agent_files:
        wanted = {x.strip() for x in agent_files.split(",")}
        return [t for t in detected if t.path.name in wanted or t.agent_key in wanted]
    if not interactive:
        return detected
    return _prompt_agent_files(detected)


def _prompt_agent_files(detected: List[AgentTarget]) -> List[AgentTarget]:
    typer.echo("Apply blurb to which agent files?")
    typer.echo("  1) All detected")
    typer.echo("  2) Let me choose")
    raw = typer.prompt("Select", default="1")
    if raw in ("1", "all"):
        return detected
    selected: List[AgentTarget] = []
    typer.echo("Pick targets (y/n for each):")
    for t in detected:
        if typer.confirm(f"  include {t.path.name} ({t.agent_key})?", default=True):
            selected.append(t)
    return selected


def _scope_root(scope: str) -> Path:
    return Path.cwd() if scope == "project" else Path.home()


def _relpath_for(target: AgentTarget, scope: str) -> str:
    return str(target.path.relative_to(_scope_root(scope)))


def _resolve_target_path(record: dict, scope: str,
                        root: Optional[Path] = None) -> Path:
    project_root = root if scope == "project" else None
    if record.get("agent_key"):
        return resolve_path_for_agent_key(
            record["agent_key"], scope=scope, root=project_root,
        )
    base = project_root if scope == "project" else Path.home()
    return base / record["path"]


def _write_target(target: AgentTarget, block: str, content_hash: str,
                  tmpl_hash: str, scope: str) -> dict:
    original = target.path.read_text(encoding="utf-8")
    new_content = replace_block(original, block)
    atomic_write_text(target.path, new_content)
    return {
        "agent_key": target.agent_key,
        "path": _relpath_for(target, scope),
        "template_hash": tmpl_hash,
        "content_hash": content_hash,
        "written_at": _now_iso(),
    }


def _check_drift_for_scope(scope: str, root: Optional[Path]) -> int:
    cfg = load_config(scope=scope, root=root)
    if cfg is None:
        Console.error(f"No blurb config for scope={scope}")
        return 2
    shipped = shipped_template_hash()
    exit_code = 0
    for t in cfg.get("targets", []):
        target_path = _resolve_target_path(t, scope=scope, root=root)
        if not target_path.exists():
            Console.warning(f"Target missing: {target_path}")
            exit_code = max(exit_code, 1)
            continue
        on_disk = target_path.read_text(encoding="utf-8")
        state = compute_drift(
            on_disk_content=on_disk,
            stored_template_hash=t["template_hash"],
            stored_content_hash=t["content_hash"],
            shipped_template_hash=shipped,
        )
        if state == DriftState.CLEAN:
            Console.success(f"{target_path}: clean")
        else:
            Console.warning(f"{target_path}: {state.value}")
            exit_code = max(exit_code, 1)
    return exit_code


def run_configure_agent(
    scope: Optional[str],
    profile: Optional[str],
    agent_files: Optional[str],
    check: bool,
    refresh: bool,
    remove: bool,
    dry_run: bool,
    yes: bool,
) -> int:
    if check:
        scopes = ["project", "global"] if scope in (None, "both") else [scope]
        rc = 0
        for s in scopes:
            root = Path.cwd() if s == "project" else None
            rc = max(rc, _check_drift_for_scope(s, root))
        return rc

    interactive = not (yes or refresh or remove)
    scopes = _resolve_scopes(scope, interactive)

    if remove:
        return _do_remove(scopes, yes=yes)

    if refresh:
        return _do_refresh(scopes, yes=yes)

    scope_profiles = {}
    for s in scopes:
        if profile is not None:
            scope_profiles[s] = profile
        elif interactive:
            Console.info(f"Profile for scope={s}:")
            scope_profiles[s] = _prompt_profile()
        else:
            scope_profiles[s] = DEFAULT_PROFILE

    return _do_install(
        scopes=scopes,
        scope_profiles=scope_profiles,
        agent_files=agent_files,
        dry_run=dry_run,
        yes=yes,
        interactive=interactive,
    )


def _do_install(scopes, scope_profiles, agent_files, dry_run, yes, interactive) -> int:
    for s in scopes:
        root = Path.cwd() if s == "project" else None
        profile = scope_profiles[s]
        targets = _resolve_targets(s, root, agent_files, interactive=interactive)
        if not targets:
            Console.warning(f"No agent files detected for scope={s}; skipping")
            continue
        cfg = new_skeleton(scope=s, profile=profile, aec_version=__version__)
        if dry_run:
            Console.info(f"[dry-run] would write to: {[str(t.path) for t in targets]}")
            continue
        if not yes:
            Console.info(f"About to write to: {[str(t.path) for t in targets]}")
            if not typer.confirm("Proceed?", default=True):
                Console.info("Aborted.")
                return 1
        block = render_block(scope=s, profile=profile, matrix=cfg["matrix"],
                             aec_version=__version__)
        tmpl_hash = shipped_template_hash()
        content_hash = sha256_short(extract_inner_body(block))
        for t in targets:
            record = _write_target(t, block, content_hash, tmpl_hash, scope=s)
            cfg["targets"].append(record)
        save_config(cfg, scope=s, root=root)
        Console.success(f"Blurb installed for scope={s}")
    return 0


def _do_refresh(scopes, yes: bool = False) -> int:
    shipped = shipped_template_hash()
    for s in scopes:
        root = Path.cwd() if s == "project" else None
        cfg = load_config(scope=s, root=root)
        if cfg is None:
            Console.warning(f"No config for scope={s}; skipping")
            continue
        block = render_block(scope=s, profile=cfg["profile"],
                             matrix=cfg["matrix"], aec_version=__version__)
        tmpl_hash = shipped_template_hash()
        content_hash = sha256_short(extract_inner_body(block))
        new_targets = []
        for t in cfg["targets"]:
            target_path = _resolve_target_path(t, scope=s, root=root)
            if not target_path.exists():
                Console.warning(f"Skipping missing target: {target_path}")
                continue
            original = target_path.read_text(encoding="utf-8")
            state = compute_drift(
                on_disk_content=original,
                stored_template_hash=t["template_hash"],
                stored_content_hash=t["content_hash"],
                shipped_template_hash=shipped,
            )
            if state in (DriftState.MANUAL_EDIT, DriftState.CONFLICT):
                Console.warning(f"{target_path}: {state.value} — refresh would overwrite local edits")
                if not yes and not typer.confirm("Overwrite?", default=False):
                    Console.info(f"Skipped {target_path}")
                    new_targets.append(t)
                    continue
            atomic_write_text(target_path, replace_block(original, block))
            new_targets.append({**t, "template_hash": tmpl_hash,
                                "content_hash": content_hash,
                                "written_at": _now_iso()})
        cfg["targets"] = new_targets
        cfg["aec_version_last_write"] = __version__
        save_config(cfg, scope=s, root=root)
        Console.success(f"Refreshed scope={s}")
    return 0


def _do_remove(scopes, yes: bool) -> int:
    for s in scopes:
        root = Path.cwd() if s == "project" else None
        cfg = load_config(scope=s, root=root)
        if cfg is None:
            Console.info(f"No config for scope={s}; nothing to remove")
            continue
        if not yes and not typer.confirm(
                f"Remove blurb from {len(cfg['targets'])} files in scope={s}?",
                default=False):
            continue
        for t in cfg["targets"]:
            target_path = _resolve_target_path(t, scope=s, root=root)
            if not target_path.exists():
                continue
            original = target_path.read_text(encoding="utf-8")
            loc = find_block(original)
            if loc:
                atomic_write_text(target_path, original[:loc.start] + original[loc.end:])
        path = config_path(scope=s, root=root)
        if path.exists():
            path.unlink()
        Console.success(f"Removed blurb for scope={s}")
    return 0
