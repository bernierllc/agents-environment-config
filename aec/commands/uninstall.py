"""aec uninstall <type> <name> -- remove a skill, rule, agent, or MCP server."""

import shutil
import subprocess
from pathlib import Path

from ..lib.console import Console
from ..lib.filesystem import resolve_installed_path
from ..lib.installed_store import remove_item_install
from ..lib.manifest_v2 import load_manifest, save_manifest, remove_install, get_installed
from ..lib.scope import resolve_scope, ScopeError

VALID_TYPES = ("skill", "rule", "agent", "mcp", "plugin")
TYPE_TO_PLURAL = {
    "skill": "skills", "rule": "rules", "agent": "agents",
    "mcp": "mcps", "plugin": "plugins",
}


def _manifest_path() -> Path:
    """Return manifest path dynamically so monkeypatch can redirect Path.home()."""
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def _uninstall_mcp(name: str, global_flag: bool, yes: bool) -> None:
    """Remove an MCP server: remove mcpServers entry from settings.json."""
    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    manifest_file = _manifest_path()
    manifest = load_manifest(manifest_file)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())

    installed = get_installed(manifest, scope_key, "mcps")
    if name not in installed:
        Console.warning(f"MCP server not found in manifest: {name}")
        return

    item_meta = installed[name]
    pip_package = item_meta.get("package", "")

    if not yes:
        try:
            resp = input(f"  Remove {name} mcpServers entry? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    from ..lib.mcp_settings import get_settings_path, remove_mcp_server
    settings_path = get_settings_path(scope)
    removed = remove_mcp_server(settings_path, name)
    if removed:
        Console.success(f"Removed {name} from mcpServers in {settings_path}")
    else:
        Console.warning(f"mcpServers entry for {name} not found in {settings_path}")

    # Offer pip uninstall (default no — user may have installed it independently)
    if pip_package and not yes:
        try:
            resp = input(f"  Also pip uninstall {pip_package}? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp == "y":
            subprocess.run(["pip", "uninstall", "-y", pip_package])

    remove_install(manifest, scope_key, "mcps", name)
    save_manifest(manifest, manifest_file)
    remove_item_install("mcp", name)

    Console.success(f"Uninstalled MCP server: {name}")


def _uninstall_plugin(name: str, global_flag: bool, yes: bool) -> None:
    """Remove a plugin: run its loadout uninstall block under the execution policy.

    Mirrors ``_uninstall_mcp`` and ``_install_plugin``: resolve scope, read the
    recorded entry, re-load the registry loadout for the uninstall block, delegate
    to ``uninstall_plugin`` (which never auto-runs ``external`` plugins), then drop
    the record.
    """
    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    manifest_file = _manifest_path()
    manifest = load_manifest(manifest_file)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())

    installed = get_installed(manifest, scope_key, "plugins")
    if name not in installed:
        Console.warning(f"Plugin not found in manifest: {name}")
        return

    if not yes:
        scope_label = "global" if scope.is_global else str(scope.repo_path)
        try:
            resp = input(f"  Remove {name} from {scope_label}? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    from ..lib.loadout import LoadoutError, load_loadout
    from ..lib.plugin_install import uninstall_plugin
    from ..lib.config import detect_agents
    from ..lib.preferences import get_setting
    from ..lib.sources import get_source_dirs

    # Re-load the registry loadout to get the uninstall block.
    manifest_def = None
    source_dir = get_source_dirs().get("plugins")
    if source_dir and source_dir.exists():
        plugin_dir = source_dir / name
        try:
            manifest_def = load_loadout(plugin_dir)
        except LoadoutError:
            manifest_def = None

    if manifest_def is None:
        # ponytail: registry loadout gone — drop the record and warn; no documented
        # command to fabricate. Add a stored-uninstall-block fallback if one ships.
        Console.warning(f"Plugin manifest not found in registry; manual cleanup may be required: {name}")
    else:
        def runner(cmd):
            return subprocess.run(cmd)

        def confirm(*args) -> bool:
            if yes:
                return True
            cmds = args[-1] if args else []
            if cmds and isinstance(cmds[0], list):
                shown = "; ".join(" ".join(c) for c in cmds)
            else:
                shown = " ".join(cmds)
            prompt = f"  Run: {shown}? [y/N]: " if shown else "  Proceed? [y/N]: "
            try:
                return input(prompt).strip().lower() == "y"
            except EOFError:
                return False

        uninstall_plugin(
            manifest_def, detect_agents(),
            runner=runner, confirm=confirm, printer=Console.print,
            pref=get_setting("plugins.execution"),
        )

    remove_install(manifest, scope_key, "plugins", name)
    save_manifest(manifest, manifest_file)
    remove_item_install("plugin", name)

    Console.success(f"Uninstalled plugin: {name}")


def run_uninstall(
    item_type: str,
    name: str,
    global_flag: bool = False,
    yes: bool = False,
) -> None:
    """Remove an installed skill, rule, agent, or MCP server."""
    if item_type not in VALID_TYPES:
        Console.error(
            f"Unknown type: {item_type}. Must be one of: {', '.join(VALID_TYPES)}"
        )
        raise SystemExit(1)

    if item_type == "mcp":
        _uninstall_mcp(name, global_flag, yes)
        return

    if item_type == "plugin":
        _uninstall_plugin(name, global_flag, yes)
        return

    plural = TYPE_TO_PLURAL[item_type]

    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    target_dir = getattr(scope, f"{plural}_dir")
    item_path = resolve_installed_path(target_dir, name)

    if not item_path.exists():
        Console.warning(f"{item_type.title()} not found: {name}")
        return

    if not yes:
        scope_label = "global" if scope.is_global else str(scope.repo_path)
        try:
            resp = input(f"  Remove {name} from {scope_label}? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    if scope.repo_path is not None:
        try:
            from ..lib.hooks.lifecycle import remove_hooks_for_item
            remove_hooks_for_item(
                item_type=item_type, item_key=name, repo_root=scope.repo_path,
            )
        except Exception as e:  # noqa: BLE001 — never block uninstall on hook removal
            Console.warning(f"hooks removal failed for {name}: {e}")

    if item_path.is_dir():
        shutil.rmtree(item_path)
    else:
        item_path.unlink()

    mp = _manifest_path()
    manifest = load_manifest(mp)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())
    remove_install(manifest, scope_key, plural, name)
    save_manifest(manifest, mp)

    # Dual-write to per-type installed file (best-effort during transition)
    remove_item_install(item_type, name)

    Console.success(f"Uninstalled {name}")
