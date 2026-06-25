"""aec uninstall <type> <name> -- remove a skill, rule, agent, or MCP server."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.filesystem import resolve_installed_path
from ..lib.installed_store import remove_item_install
from ..lib.manifest_v2 import load_manifest, save_manifest, remove_install, get_installed
from ..lib.scope import resolve_scope, Scope, ScopeError
from ..lib.uninstall_scope import find_repos_with_install, resolve_repos_flag

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


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _prompt_repo_selection(item_type: str, name: str, candidates: list[str]) -> list[str]:
    """Aggregated prompt: a repo install owns its copy, so ask before reaping it."""
    n = len(candidates)
    Console.warning(f"{item_type} '{name}' is also installed in {n} repo(s).")
    while True:
        print(f"  Uninstall from repos? [a] all {n}  [e] each  "
              f"[s] show where  [g] only globally (default)")
        try:
            choice = input("  Choice [a/e/s/g]: ").strip().lower()
        except EOFError:
            return []
        if choice == "a":
            return list(candidates)
        if choice == "e":
            return [r for r in candidates if _confirm(f"    Also uninstall from {r}? [y/N]: ")]
        if choice == "s":
            for r in candidates:
                print(f"    - {r}")
            continue
        return []  # "g" or empty → only globally


def _purge_scope(item_type: str, name: str, plural: str, scope: Scope,
                 manifest: dict) -> None:
    """Remove the item dir, its hooks, and its manifest entry for one scope."""
    target_dir = getattr(scope, f"{plural}_dir")
    item_path = resolve_installed_path(target_dir, name)
    if item_path.exists():
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
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())
    remove_install(manifest, scope_key, plural, name)


def run_uninstall(
    item_type: str,
    name: str,
    global_flag: bool = False,
    yes: bool = False,
    repos: Optional[str] = None,
) -> None:
    """Remove an installed skill, rule, agent, or MCP server.

    A repo-scoped install overrides + is owned independently of the global one,
    so a global uninstall never reaps repo installs without permission. `repos`
    (all|none|<paths>) drives that selection non-interactively (default none).
    """
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

    mp = _manifest_path()
    manifest = load_manifest(mp)

    selected_repos: list[str] = []
    if scope.is_global:
        candidates = find_repos_with_install(manifest, plural, name)
        if yes:
            selected_repos = resolve_repos_flag(repos, candidates)
        elif candidates:
            selected_repos = _prompt_repo_selection(item_type, name, candidates)
        elif not _confirm(f"  Remove {name} from global? [y/N]: "):
            Console.info("Skipped.")
            return
    elif not yes and not _confirm(f"  Remove {name} from {scope.repo_path}? [y/N]: "):
        Console.info("Skipped.")
        return

    _purge_scope(item_type, name, plural, scope, manifest)
    for repo in selected_repos:
        _purge_scope(item_type, name, plural, Scope(False, Path(repo)), manifest)
        Console.success(f"Uninstalled {name} from {repo}")

    save_manifest(manifest, mp)

    # Dual-write to per-type installed file (best-effort during transition)
    remove_item_install(item_type, name)

    Console.success(f"Uninstalled {name}")
