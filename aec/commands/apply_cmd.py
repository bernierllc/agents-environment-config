"""aec apply <file> -- reproduce a setup from a portable manifest."""

from pathlib import Path

from ..lib import Console
from ..lib.apply_core import DesiredItem, execute_apply, plan_apply
from ..lib.config import get_repo_root
from ..lib.manifest_v2 import load_manifest
from ..lib.portable_manifest import (
    ITEM_TYPES,
    PortableManifestError,
    load_portable_manifest,
    resolve_repo_token,
)
from ..lib.scope import get_all_tracked_repos
from ..lib.sources import discover_available, get_source_dirs

PLURAL_TO_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent", "mcps": "mcp"}


def _manifest_path() -> Path:
    """Compute manifest path dynamically so tests can monkeypatch Path.home()."""
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def _compile_scope(scope_key: str, scope_data: dict, latest: bool) -> list:
    items = []
    for plural in ITEM_TYPES:
        for entry in scope_data.get(plural, []):
            name = entry.get("name")
            if not name:
                continue
            version = "latest" if latest else entry.get("version", "latest")
            items.append(
                DesiredItem(
                    item_type=PLURAL_TO_SINGULAR[plural],
                    name=name,
                    scope=scope_key,
                    version_spec=version,
                    package=entry.get("package", ""),
                )
            )
    return items


def compile_desired_items(portable: dict, *, latest: bool, tracked_repos: list) -> list:
    """Compile a portable manifest into scope-qualified desired items."""
    items = list(_compile_scope("global", portable.get("global", {}), latest))
    for repo_entry in portable.get("repos", []):
        token = repo_entry.get("path", "")
        resolved = resolve_repo_token(token, tracked_repos=tracked_repos)
        if resolved is None or not resolved.exists():
            Console.warning(f"Skipping repo '{token}': not found on this machine.")
            continue
        items.extend(_compile_scope(str(resolved.resolve()), repo_entry, latest))
    return items


def _scope_label(scope_key: str) -> str:
    return "global" if scope_key == "global" else scope_key


def _print_plan(plan) -> None:
    Console.print("Apply plan:")
    for entry in plan:
        version = f" v{entry.to_version}" if entry.to_version else ""
        Console.print(
            f"  [{entry.action}] {entry.item.item_type} {entry.item.name}{version} "
            f"({_scope_label(entry.item.scope)}) - {entry.reason}"
        )


def _print_result(result) -> None:
    Console.success(f"Applied {len(result.applied)} item(s); {len(result.skipped)} skipped.")
    for entry, err in result.errors:
        Console.error(f"  {entry.item.name}: {err}")
    if result.errors:
        raise SystemExit(1)


def run_apply(file: str, dry_run: bool = False, latest: bool = False) -> None:
    """Read a portable manifest and reproduce its setup on this machine."""
    path = Path(file)
    if not path.exists():
        Console.error(f"Manifest file not found: {file}")
        raise SystemExit(1)
    try:
        portable = load_portable_manifest(path.read_text(encoding="utf-8"))
    except PortableManifestError as exc:
        Console.error(str(exc))
        raise SystemExit(1)

    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        raise SystemExit(1)

    source_dirs = get_source_dirs()
    available_by_type = {
        plural: discover_available(source_dirs[plural], plural)
        for plural in ITEM_TYPES
        if source_dirs.get(plural)
    }

    items = compile_desired_items(portable, latest=latest, tracked_repos=get_all_tracked_repos())
    if not items:
        Console.info("Manifest contains no items to apply.")
        return

    manifest = load_manifest(_manifest_path())
    plan = plan_apply(items, manifest=manifest, available_by_type=available_by_type)
    _print_plan(plan)
    if dry_run:
        Console.info("Dry run - no changes made.")
        return

    result = execute_apply(
        plan,
        source_dirs=source_dirs,
        available_by_type=available_by_type,
        manifest_path=_manifest_path(),
    )
    _print_result(result)
