#!/usr/bin/env python3
"""Pre-commit hook: incrementally update catalog-hashes.json when item versions change."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Allow imports from aec/ regardless of how the script is invoked
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from aec.lib.catalog_hashes import generate_catalog_hashes, load_catalog_hashes
from aec.lib.sources import get_source_dirs


def incremental_update(catalog_path: Path, source_dirs: Optional[dict] = None) -> bool:
    """Incrementally update catalog-hashes.json, recomputing only changed items.

    Args:
        catalog_path: Path to the catalog-hashes.json file.
        source_dirs: Optional dict of item_type -> Path. If None, auto-discovered.

    Returns:
        True if the file was modified, False if no changes needed.
    """
    if source_dirs is None:
        source_dirs = get_source_dirs()

    existing = load_catalog_hashes(catalog_path)

    # Generate a full fresh catalog to get current state of all items
    fresh = generate_catalog_hashes(source_dirs)

    changed = False

    for item_type in ("agents", "skills", "rules"):
        if changed:
            break
        old_items = existing.get(item_type, {})
        new_items = fresh.get(item_type, {})

        # Check for removed items
        if old_items.keys() - new_items.keys():
            changed = True
            break

        # Check for new or version-changed items
        for name, new_entry in new_items.items():
            old_entry = old_items.get(name)
            if old_entry is None:
                changed = True
                break
            elif old_entry.get("version") != new_entry.get("version"):
                changed = True
                break
            elif old_entry.get("contentHash") != new_entry.get("contentHash"):
                changed = True
                break

    if not changed:
        return False

    # Write the fresh catalog (which already has all correct hashes)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(fresh, indent=2) + "\n", encoding="utf-8")
    return True


def git_add(path: Path) -> None:
    """Stage a file with git add."""
    try:
        subprocess.run(
            ["git", "add", str(path)],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # Best effort; don't block commits


def main() -> int:
    """Entry point for pre-commit hook usage."""
    catalog_path = REPO_ROOT / "catalog-hashes.json"

    try:
        modified = incremental_update(catalog_path)
        if modified:
            git_add(catalog_path)
            print("catalog-hashes.json updated and staged.")
        else:
            print("catalog-hashes.json is up to date.")
    except Exception as exc:
        # Never block commits
        print(f"Warning: catalog hash update failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
