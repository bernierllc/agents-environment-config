"""aec search <term> — search available items."""

from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.config import get_repo_root
from ..lib.manifest_v2 import load_manifest, get_installed
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo

ITEM_TYPES = ("skills", "rules", "agents")
TYPE_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent"}


def _manifest_path() -> Path:
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_search(term: str, type_filter: Optional[str] = None) -> None:
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    source_dirs = get_source_dirs()
    manifest = load_manifest(_manifest_path())
    local_repo = find_tracked_repo()
    term_lower = term.lower()

    types_to_search = ITEM_TYPES
    if type_filter:
        plural = type_filter + "s" if not type_filter.endswith("s") else type_filter
        if plural in ITEM_TYPES:
            types_to_search = (plural,)

    found = False
    for item_type in types_to_search:
        source_dir = source_dirs.get(item_type)
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        singular = TYPE_SINGULAR[item_type]
        for name, info in sorted(available.items()):
            if term_lower not in name.lower() and term_lower not in info.get("description", "").lower():
                continue
            version = info.get("version", "?")
            desc = info.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."

            scopes = []
            global_items = get_installed(manifest, "global", item_type)
            if name in global_items:
                scopes.append("global")
            if local_repo:
                local_items = get_installed(manifest, str(local_repo.resolve()), item_type)
                if name in local_items:
                    scopes.append("local")

            scope_tag = f"  [{', '.join(scopes)}]" if scopes else ""
            Console.print(f"{singular:<8} {name:<32} v{version}  {desc}{scope_tag}")
            found = True

    if not found:
        Console.print(f"No results for '{term}'")
