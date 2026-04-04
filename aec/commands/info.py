"""aec info <type> <name> -- show detailed metadata for an item."""

from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.config import get_repo_root
from ..lib.manifest_v2 import load_manifest, get_installed, get_all_repo_scopes
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo

VALID_TYPES = ("skill", "rule", "agent")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def _manifest_path() -> Path:
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_info(item_type: str, name: str) -> None:
    if item_type not in VALID_TYPES:
        Console.error(f"Unknown type: {item_type}")
        return

    plural = TYPE_TO_PLURAL[item_type]
    source_dirs = get_source_dirs()
    manifest = load_manifest(_manifest_path())

    source_dir = source_dirs.get(plural)
    available = discover_available(source_dir, plural) if source_dir and source_dir.exists() else {}
    source_info = available.get(name, {})

    if not source_info:
        Console.error(f"{item_type.title()} not found: {name}")
        return

    version = source_info.get("version", "?")
    desc = source_info.get("description", "")
    author = source_info.get("author", "")

    Console.print(f"{name} v{version}")
    if author:
        Console.print(f"  Author:      {author}")
    if desc:
        Console.print(f"  Description: {desc}")

    # Show install locations
    installed_in = []
    global_items = get_installed(manifest, "global", plural)
    if name in global_items:
        installed_in.append(f"global ({global_items[name].get('installedAt', '?')})")

    local_repo = find_tracked_repo()
    if local_repo:
        local_items = get_installed(manifest, str(local_repo.resolve()), plural)
        if name in local_items:
            installed_in.append(f"local {local_repo} ({local_items[name].get('installedAt', '?')})")

    for repo_key in get_all_repo_scopes(manifest):
        if local_repo and repo_key == str(local_repo.resolve()):
            continue
        repo_items = get_installed(manifest, repo_key, plural)
        if name in repo_items:
            installed_in.append(f"{repo_key} ({repo_items[name].get('installedAt', '?')})")

    if installed_in:
        Console.print(f"  Installed:   {', '.join(installed_in)}")
    else:
        Console.print("  Installed:   (not installed)")

    if source_dir:
        src_path = source_dir / source_info.get("path", name)
        if src_path.exists() and src_path.is_dir():
            files = [f for f in src_path.rglob("*") if f.is_file()]
            Console.print(f"  Files:       {len(files)} file(s)")
