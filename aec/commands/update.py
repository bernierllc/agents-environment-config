"""aec update -- fetch latest sources and report what's outdated."""

from pathlib import Path

from ..lib.console import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, save_manifest, record_update_check, get_installed
from ..lib.sources import fetch_latest, discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import version_is_newer


def _get_manifest_path() -> Path:
    """Return the manifest path. Separated for testability."""
    return INSTALLED_MANIFEST_V2


def run_update() -> None:
    """Fetch latest AEC repo + submodules, report what's outdated."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    Console.print("Pulling latest...", end=" ")
    if not fetch_latest(repo):
        Console.print("failed!")
        Console.error("Could not pull latest. Check your network and git status.")
        return
    Console.print("done.")

    manifest_path = _get_manifest_path()
    manifest = load_manifest(manifest_path)
    record_update_check(manifest)
    save_manifest(manifest, manifest_path)

    source_dirs = get_source_dirs()
    any_outdated = False

    Console.print("\nGlobal:")
    global_outdated = _report_scope_outdated(manifest, "global", source_dirs)
    if global_outdated:
        any_outdated = True
    else:
        Console.print("  (up to date)")

    local_repo = find_tracked_repo()
    if local_repo:
        Console.print(f"\nLocal ({local_repo}):")
        repo_key = str(local_repo.resolve())
        local_outdated = _report_scope_outdated(manifest, repo_key, source_dirs)
        if local_outdated:
            any_outdated = True
        else:
            Console.print("  (up to date)")

    all_repos = get_all_tracked_repos()
    other_repos = [r for r in all_repos if r != local_repo]
    if other_repos:
        Console.print(
            f"\n{len(other_repos)} other tracked repo(s) may have updates. "
            "Run `aec outdated --all` to check."
        )

    if any_outdated:
        Console.print("\nRun `aec upgrade` to apply.")
    else:
        Console.print("\nEverything is up to date.")


def _report_scope_outdated(manifest: dict, scope: str, source_dirs: dict) -> int:
    """Report outdated items for a scope. Returns count of outdated items."""
    count = 0
    for item_type, source_dir in source_dirs.items():
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        installed = get_installed(manifest, scope, item_type)
        for name, info in installed.items():
            if name in available:
                avail_v = available[name].get("version", "0.0.0")
                inst_v = info.get("version", "0.0.0")
                if version_is_newer(avail_v, inst_v):
                    Console.print(f"  {item_type[:-1]}  {name}  {inst_v} -> {avail_v}")
                    count += 1
    return count
