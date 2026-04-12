"""Per-type installed file store -- separate JSON files for agents, rules, skills.

Replaces the monolithic installed-manifest.json with per-type files to avoid
write contention when multiple agents run in parallel. During the transition
period, callers dual-write to both the old manifest and per-type files.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .atomic_write import atomic_write_json
from .config import AEC_HOME, INSTALLED_MANIFEST_V2

SCHEMA_VERSION = 1
VALID_TYPES = ("agent", "rule", "skill")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _installed_path(item_type: str) -> Path:
    """Return the per-type installed file path (pluralised)."""
    if item_type not in VALID_TYPES:
        raise ValueError(f"Unknown item type: {item_type!r}. Must be one of {VALID_TYPES}")
    return AEC_HOME / f"installed-{item_type}s.json"


def _empty_store() -> dict:
    now = _now_iso()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "installedAt": now,
        "updatedAt": now,
        "items": {},
    }


def _migrate_v1_skills(data: dict) -> dict:
    """Convert v1 installed-skills.json format to per-type store format.

    V1 format: {"manifestVersion": 1, "skills": {name: {version, contentHash, installedAt, ...}}}
    Store format: {"schemaVersion": 1, "items": {name: {version, contentHash, installedAt}}}
    """
    store = _empty_store()
    for name, info in data.get("skills", {}).items():
        store["items"][name] = {
            "version": info.get("version", "0.0.0"),
            "contentHash": info.get("contentHash", ""),
            "installedAt": info.get("installedAt", _now_iso()),
        }
    if store["items"]:
        earliest = min(
            (v.get("installedAt", "") for v in store["items"].values()),
            default=_now_iso(),
        )
        store["installedAt"] = earliest or store["installedAt"]
    return store


def load_installed(item_type: str) -> dict:
    """Read a per-type installed file, returning an empty store on missing/corrupt.

    For skills, handles v1 format migration (existing installed-skills.json has
    {"manifestVersion": 1, "skills": {...}}).
    """
    path = _installed_path(item_type)
    if not path.exists():
        return _empty_store()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store()

    if not isinstance(data, dict):
        return _empty_store()

    # v1 skills migration: has "manifestVersion" and "skills" keys
    if item_type == "skill" and data.get("manifestVersion") == 1 and "skills" in data:
        store = _migrate_v1_skills(data)
        save_installed(item_type, store)
        return store

    # Normal per-type store format
    if data.get("schemaVersion") == SCHEMA_VERSION and "items" in data:
        data.setdefault("installedAt", _now_iso())
        data.setdefault("updatedAt", _now_iso())
        return data

    return _empty_store()


def save_installed(item_type: str, data: dict) -> None:
    """Atomically write the per-type installed file."""
    path = _installed_path(item_type)
    data["updatedAt"] = _now_iso()
    atomic_write_json(path, data)


def record_item_install(
    item_type: str,
    name: str,
    version: str,
    content_hash: str = "",
) -> None:
    """Add or update an item in the per-type installed file."""
    store = load_installed(item_type)
    store["items"][name] = {
        "version": version,
        "contentHash": content_hash,
        "installedAt": _now_iso(),
    }
    save_installed(item_type, store)


def remove_item_install(item_type: str, name: str) -> None:
    """Remove an item from the per-type installed file."""
    store = load_installed(item_type)
    store["items"].pop(name, None)
    save_installed(item_type, store)


def get_all_installed(item_type: str) -> dict:
    """Return all items from the per-type installed file."""
    store = load_installed(item_type)
    return dict(store.get("items", {}))


def seed_from_manifest() -> int:
    """Seed per-type files from the global section of installed-manifest.json.

    Called on first use if per-type files don't exist but the v2 manifest does.
    Returns the count of items migrated.
    """
    if not INSTALLED_MANIFEST_V2.exists():
        return 0

    try:
        manifest = json.loads(INSTALLED_MANIFEST_V2.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    if not isinstance(manifest, dict) or manifest.get("manifestVersion") != 2:
        return 0

    global_section = manifest.get("global", {})
    count = 0

    # Map plural keys in manifest to singular item_type
    type_map = {"skills": "skill", "rules": "rule", "agents": "agent"}

    for plural, item_type in type_map.items():
        items = global_section.get(plural, {})
        if not items:
            continue

        path = _installed_path(item_type)
        # Only seed if per-type file doesn't already exist
        if path.exists():
            continue

        store = _empty_store()
        for name, info in items.items():
            store["items"][name] = {
                "version": info.get("version", "0.0.0"),
                "contentHash": info.get("contentHash", ""),
                "installedAt": info.get("installedAt", _now_iso()),
            }
            count += 1

        if store["items"]:
            save_installed(item_type, store)

    return count
