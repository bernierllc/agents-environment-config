"""aec list — show installed items."""

from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.config import INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, get_installed, get_all_repo_scopes
from ..lib.scope import find_tracked_repo, get_all_tracked_repos

ITEM_TYPES = ("skills", "rules", "agents")
TYPE_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent"}


def run_list(
    type_filter: Optional[str] = None,
    scope_filter: Optional[str] = None,
    show_all: bool = False,
) -> None:
    """Show installed items across applicable scopes.

    Always shows global. If in a tracked repo, also shows local.
    Supports --type and --scope filtering, and --all to scan all tracked repos.
    """
    manifest = load_manifest(INSTALLED_MANIFEST_V2)

    types_to_show = ITEM_TYPES
    if type_filter:
        plural = type_filter + "s" if not type_filter.endswith("s") else type_filter
        if plural in ITEM_TYPES:
            types_to_show = (plural,)

    # Global scope
    if scope_filter in (None, "global"):
        Console.print("Global:")
        count = _print_scope(manifest, "global", types_to_show)
        if count == 0:
            Console.print("  (none)")

    # Local scope (current repo)
    local_repo = find_tracked_repo()
    if local_repo and scope_filter in (None, "local"):
        repo_key = str(local_repo.resolve())
        Console.print(f"\nLocal ({local_repo}):")
        count = _print_scope(manifest, repo_key, types_to_show)
        if count == 0:
            Console.print("  (none)")

    # --all: show all other tracked repos
    if show_all:
        all_repos = get_all_tracked_repos()
        for repo_path in all_repos:
            if repo_path == local_repo:
                continue
            repo_key = str(repo_path.resolve())
            Console.print(f"\n{repo_path}:")
            count = _print_scope(manifest, repo_key, types_to_show)
            if count == 0:
                Console.print("  (none)")

    tracked = get_all_tracked_repos()
    Console.print(f"\nTracked repos: {len(tracked)}")


def _print_scope(manifest: dict, scope: str, types: tuple) -> int:
    """Print installed items for a scope, return count of items printed."""
    count = 0
    for item_type in types:
        items = get_installed(manifest, scope, item_type)
        singular = TYPE_SINGULAR[item_type]
        for name, info in sorted(items.items()):
            version = info.get("version", "?")
            Console.print(f"  {singular:<8} {name:<32} v{version}")
            count += 1
    return count
