"""aec outdated — show items with available upgrades."""

from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.config import get_repo_root
from ..lib.manifest_v2 import load_manifest, get_installed
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import version_is_newer

ITEM_TYPES = ("skills", "rules", "agents")
TYPE_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent"}


def _manifest_path() -> Path:
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_outdated(type_filter: Optional[str] = None, show_all: bool = False) -> None:
    """Check for items with available upgrades across scopes."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    source_dirs = get_source_dirs()
    manifest = load_manifest(_manifest_path())

    types_to_check = ITEM_TYPES
    if type_filter:
        plural = type_filter + "s" if not type_filter.endswith("s") else type_filter
        if plural in ITEM_TYPES:
            types_to_check = (plural,)

    any_outdated = False

    Console.print("Global:")
    if _print_outdated(manifest, "global", source_dirs, types_to_check):
        any_outdated = True
    else:
        Console.print("  (up to date)")

    local_repo = find_tracked_repo()
    if local_repo:
        repo_key = str(local_repo.resolve())
        Console.print(f"\nLocal ({local_repo}):")
        if _print_outdated(manifest, repo_key, source_dirs, types_to_check):
            any_outdated = True
        else:
            Console.print("  (up to date)")

    if show_all:
        for repo_path in get_all_tracked_repos():
            if repo_path == local_repo:
                continue
            repo_key = str(repo_path.resolve())
            Console.print(f"\n{repo_path}:")
            if not _print_outdated(manifest, repo_key, source_dirs, types_to_check):
                Console.print("  (up to date)")

    if not any_outdated:
        Console.print("\nEverything is up to date.")


def _print_outdated(
    manifest: dict,
    scope: str,
    source_dirs: dict,
    types: tuple,
) -> bool:
    """Print outdated items for a single scope. Returns True if any found."""
    found = False
    for item_type in types:
        source_dir = source_dirs.get(item_type)
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        installed = get_installed(manifest, scope, item_type)
        singular = TYPE_SINGULAR[item_type]
        for name, info in sorted(installed.items()):
            if name in available:
                avail_v = available[name].get("version", "0.0.0")
                inst_v = info.get("version", "0.0.0")
                if version_is_newer(avail_v, inst_v):
                    Console.print(f"  {singular:<8} {name:<32} {inst_v} → {avail_v}")
                    found = True
    return found
