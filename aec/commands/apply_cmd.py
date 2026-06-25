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
        singular = PLURAL_TO_SINGULAR.get(plural)
        if singular is None:
            continue  # plugins handled separately (_collect_plugins / _apply_plugins)
        for entry in scope_data.get(plural, []):
            name = entry.get("name")
            if not name:
                continue
            version = "latest" if latest else entry.get("version", "latest")
            items.append(
                DesiredItem(
                    item_type=singular,
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


def _collect_plugins(portable: dict, tracked_repos: list) -> list:
    """Pull (scope_key, plugin_name) pairs out of a portable manifest.

    Plugins are reproduced by re-running the install handler, not via the
    declarative apply_core path, so they are collected separately here.
    """
    plugins = []
    for entry in portable.get("global", {}).get("plugins", []):
        name = entry.get("name")
        if name:
            plugins.append(("global", name))
    for repo_entry in portable.get("repos", []):
        resolved = resolve_repo_token(repo_entry.get("path", ""), tracked_repos=tracked_repos)
        if resolved is None or not resolved.exists():
            continue
        for entry in repo_entry.get("plugins", []):
            name = entry.get("name")
            if name:
                plugins.append((str(resolved.resolve()), name))
    return plugins


def _apply_plugins(plugins: list, *, source_dirs: dict, yes: bool) -> None:
    """Re-run the plugin install handler for each recorded plugin.

    A single up-front prompt gates the whole batch (skipped with ``--yes``);
    after approval, confirm-then-run plugins assume-yes. ``external`` plugins
    are always instructions-only — ``install_plugin`` enforces that regardless
    of the confirm callback or the execution preference.
    """
    import subprocess

    from ..lib.config import detect_agents
    from ..lib.installed_store import record_item_install
    from ..lib.loadout import LoadoutError, load_loadout
    from ..lib.manifest_v2 import load_manifest, record_plugin_install, save_manifest
    from ..lib.plugin_install import install_plugin
    from ..lib.preferences import get_setting

    if not yes:
        try:
            resp = input(f"Apply {len(plugins)} plugin(s)? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped plugins.")
            return

    source_dir = source_dirs.get("plugins")
    if not source_dir or not Path(source_dir).exists():
        Console.warning("No plugins source found; skipping plugins.")
        return

    available = discover_available(Path(source_dir), "plugins")
    pref = get_setting("plugins.execution")
    detected = detect_agents()
    manifest_path = _manifest_path()

    def runner(cmd):
        return subprocess.run(cmd)

    def confirm(*args) -> bool:
        # The batch was approved up front; external plugins never run regardless.
        return True

    for scope_key, name in plugins:
        if name not in available:
            Console.warning(f"Plugin not in catalog: {name}; skipping.")
            continue
        plugin_dir = Path(source_dir) / available[name]["path"]
        try:
            manifest_def = load_loadout(plugin_dir)
        except LoadoutError as exc:
            Console.warning(f"Invalid plugin '{name}': {exc}; skipping.")
            continue
        result = install_plugin(
            manifest_def, detected,
            runner=runner, confirm=confirm, printer=Console.print, pref=pref,
        )
        version = manifest_def.get("version", "0.0.0")
        manifest = load_manifest(manifest_path)
        record_plugin_install(
            manifest, scope_key, name, version,
            install_type=result["install_type"], targets=result["targets"],
        )
        save_manifest(manifest, manifest_path)
        record_item_install("plugin", name, version)
        Console.success(f"Applied plugin: {name} v{version}")


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


def _print_result(result) -> bool:
    """Print the apply result; return True if any item failed."""
    Console.success(f"Applied {len(result.applied)} item(s); {len(result.skipped)} skipped.")
    for entry, err in result.errors:
        Console.error(f"  {entry.item.name}: {err}")
    return bool(result.errors)


def run_apply(file: str, dry_run: bool = False, latest: bool = False, yes: bool = False) -> None:
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

    tracked_repos = get_all_tracked_repos()
    items = compile_desired_items(portable, latest=latest, tracked_repos=tracked_repos)
    plugins = _collect_plugins(portable, tracked_repos)
    if not items and not plugins:
        Console.info("Manifest contains no items to apply.")
        return

    manifest = load_manifest(_manifest_path())
    plan = plan_apply(items, manifest=manifest, available_by_type=available_by_type)
    _print_plan(plan)
    for scope_key, name in plugins:
        Console.print(f"  [plugin] {name} ({_scope_label(scope_key)})")
    if dry_run:
        Console.info("Dry run - no changes made.")
        return

    items_failed = False
    if plan:
        result = execute_apply(
            plan,
            source_dirs=source_dirs,
            available_by_type=available_by_type,
            manifest_path=_manifest_path(),
        )
        items_failed = _print_result(result)
    # Plugins are independent of the item pass — apply them even if items failed,
    # then surface the item-failure exit code afterward.
    if plugins:
        _apply_plugins(plugins, source_dirs=source_dirs, yes=yes)
    if items_failed:
        raise SystemExit(1)
