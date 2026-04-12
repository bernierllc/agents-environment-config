"""Lightweight Quick-scan notification for install/update operations.

Scans ~/.claude/agents/ and ~/.claude/skills/ for local items that match
AEC catalog names (Quick/Level 1 — name matching only). If untracked
matches are found, prints a one-line notification nudging the user to
run `aec discover -g`.

This module is informational only and must never break install/update.
All public functions are wrapped in try/except to guarantee silence on error.
"""

import json
import re
from pathlib import Path

from .console import Console
from .scope import Scope
from .sources import get_source_dirs, discover_available


def _normalize_name(name: str) -> str:
    """Normalize an item name for Quick/Level 1 comparison.

    Strips file extensions, common prefixes/suffixes, and lowercases.
    Example: 'engineering-backend-architect.md' -> 'backend-architect'
    """
    # Strip common extensions
    stem = re.sub(r"\.(md|txt|yaml|yml|json)$", "", name, flags=re.IGNORECASE)
    # Strip common prefixes
    stem = re.sub(r"^(engineering|custom|aec)-", "", stem)
    # Lowercase and strip whitespace
    return stem.strip().lower()


def _scan_local_items(base_dir: Path) -> list[str]:
    """List item names in a directory (files and subdirectories).

    Returns basenames of immediate children, skipping hidden files.
    """
    if not base_dir.is_dir():
        return []
    return [
        item.name
        for item in base_dir.iterdir()
        if not item.name.startswith(".")
    ]


def _is_dismissed(item_name: str, item_type: str) -> bool:
    """Check if an item has been dismissed in global dismissals.

    Reads from ~/.agents-environment-config/dismissed-{item_type}.json.
    Returns False if the file doesn't exist or can't be read.

    Note: For batch checks, prefer _get_dismissed_names() to avoid
    repeated file reads.
    """
    return item_name in _get_dismissed_names(item_type)


def _get_dismissed_names(item_type: str) -> set[str]:
    """Get names of globally dismissed items for a given type.

    Reads from ~/.agents-environment-config/dismissed-{item_type}.json.
    Returns empty set if file doesn't exist or can't be read.
    """
    dismissed_file = (
        Path.home()
        / ".agents-environment-config"
        / f"dismissed-{item_type}.json"
    )
    if not dismissed_file.is_file():
        return set()
    try:
        data = json.loads(dismissed_file.read_text(encoding="utf-8"))
        return set(data.get("items", {}).keys())
    except Exception:
        return set()


def _get_installed_names(item_type: str) -> set[str]:
    """Get names of globally installed items from the manifest.

    Reads from ~/.agents-environment-config/installed-manifest.json.
    Returns empty set if file doesn't exist or can't be read.
    """
    manifest_file = (
        Path.home()
        / ".agents-environment-config"
        / "installed-manifest.json"
    )
    if not manifest_file.is_file():
        return set()
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        global_scope = data.get("global", {})
        items = global_scope.get(item_type, {})
        return set(items.keys())
    except Exception:
        return set()


def quick_scan_notification(scope: Scope) -> None:
    """Show a notification if untracked items match AEC catalog names.

    Only runs for global scope. Uses Quick/Level 1 matching (name only).
    Wrapped in try/except — must never raise.
    """
    try:
        _quick_scan_notification_impl(scope)
    except Exception:
        pass


def _quick_scan_notification_impl(scope: Scope) -> None:
    """Internal implementation of quick_scan_notification."""
    if not scope.is_global:
        return

    source_dirs = get_source_dirs()
    if not source_dirs:
        return

    # Build catalog of normalized names per type
    catalog_normalized: dict[str, dict[str, str]] = {}  # type -> {normalized: original}
    for item_type in ("agents", "skills"):
        source_dir = source_dirs.get(item_type)
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        catalog_normalized[item_type] = {
            _normalize_name(name): name for name in available
        }

    # Scan local directories for untracked items
    match_count = 0
    scan_dirs = {
        "agents": scope.agents_dir,
        "skills": scope.skills_dir,
    }

    for item_type, local_dir in scan_dirs.items():
        if item_type not in catalog_normalized:
            continue

        installed = _get_installed_names(item_type)
        dismissed = _get_dismissed_names(item_type)
        local_items = _scan_local_items(local_dir)

        for local_name in local_items:
            if local_name in installed:
                continue
            if local_name in dismissed:
                continue

            normalized = _normalize_name(local_name)
            if normalized in catalog_normalized[item_type]:
                match_count += 1

    if match_count > 0:
        Console.info(
            f"Found {match_count} untracked item{'s' if match_count != 1 else ''} "
            f"matching AEC catalog names. Run `aec discover -g` to review."
        )
