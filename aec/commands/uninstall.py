"""aec uninstall <type> <name> -- remove a skill, rule, agent, or MCP server."""

import shutil
import subprocess
from pathlib import Path

from ..lib.console import Console
from ..lib.filesystem import resolve_installed_path
from ..lib.installed_store import remove_item_install
from ..lib.manifest_v2 import load_manifest, save_manifest, remove_install, get_installed
from ..lib.scope import resolve_scope, ScopeError

VALID_TYPES = ("skill", "rule", "agent", "mcp")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents", "mcp": "mcps"}


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
