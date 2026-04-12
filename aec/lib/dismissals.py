"""CRUD for dismissed items — global dismissed-*.json files and per-repo .aec.json sections."""

import json
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from .aec_json import load_aec_json, save_aec_json
from .config import AEC_HOME

logger = logging.getLogger(__name__)


@runtime_checkable
class ScopeLike(Protocol):
    """Structural type for scope objects (avoids circular import of Scope)."""

    @property
    def is_global(self) -> bool: ...

    @property
    def repo_path(self) -> Path | None: ...


def _global_dismissed_path(item_type: str) -> Path:
    """Return path to the global dismissed file for the given type.

    Note: item_type is singular (agent, skill, rule) but file is plural.
    """
    return AEC_HOME / f"dismissed-{item_type}s.json"


def _load_global_dismissed(item_type: str) -> dict:
    """Read global dismissed file, returning empty structure on missing/corrupt."""
    path = _global_dismissed_path(item_type)
    if not path.exists():
        return {"schemaVersion": 1, "items": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "items" not in data:
            logger.warning("Malformed dismissed file %s — returning empty", path)
            return {"schemaVersion": 1, "items": {}}
        return data
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Corrupt dismissed file %s: %s — returning empty", path, exc)
        return {"schemaVersion": 1, "items": {}}


def _save_global_dismissed(item_type: str, data: dict) -> None:
    """Write global dismissed file atomically (write-tmp-then-rename)."""
    path = _global_dismissed_path(item_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def _load_repo_dismissed(item_type: str, repo_path: Path) -> dict:
    """Read .aec.json dismissed section for this type.

    Returns {} if section missing or .aec.json doesn't exist.
    """
    aec_data = load_aec_json(repo_path)
    if aec_data is None:
        return {}
    dismissed = aec_data.get("dismissed", {})
    # item_type is singular; the .aec.json section uses plural keys
    return dismissed.get(f"{item_type}s", {})


def _save_repo_dismissal(
    item_type: str, repo_path: Path, local_name: str, record: dict
) -> None:
    """Update .aec.json dismissed section for the given type and local name."""
    aec_data = load_aec_json(repo_path)
    if aec_data is None:
        aec_data = {}
    dismissed = aec_data.setdefault("dismissed", {})
    type_section = dismissed.setdefault(f"{item_type}s", {})
    type_section[local_name] = record
    save_aec_json(repo_path, aec_data)


def load_dismissed(item_type: str, scope: ScopeLike) -> dict:
    """Load dismissed items, dispatching to global or repo based on scope.

    For global scope: returns the 'items' dict from the global file.
    For repo scope: returns the type section from .aec.json dismissed.
    """
    if scope.is_global:
        data = _load_global_dismissed(item_type)
        return data.get("items", {})
    return _load_repo_dismissed(item_type, scope.repo_path)


def save_dismissal(
    item_type: str, scope: ScopeLike, local_name: str, record: dict
) -> None:
    """Save a dismissal record, dispatching to global or repo based on scope."""
    if scope.is_global:
        data = _load_global_dismissed(item_type)
        data["items"][local_name] = record
        _save_global_dismissed(item_type, data)
    else:
        _save_repo_dismissal(item_type, scope.repo_path, local_name, record)


def is_dismissed(item_type: str, scope: ScopeLike, local_name: str) -> bool:
    """Check if an item is dismissed in the given scope."""
    items = load_dismissed(item_type, scope)
    return local_name in items


def clear_dismissals(item_type: str, scope: ScopeLike) -> None:
    """Remove all dismissals for a type in the given scope (for --rediscover)."""
    if scope.is_global:
        data = _load_global_dismissed(item_type)
        data["items"] = {}
        _save_global_dismissed(item_type, data)
    else:
        aec_data = load_aec_json(scope.repo_path)
        if aec_data is None:
            return
        dismissed = aec_data.get("dismissed", {})
        plural_key = f"{item_type}s"
        if plural_key in dismissed:
            dismissed[plural_key] = {}
            save_aec_json(scope.repo_path, aec_data)


def prune_stale(item_type: str, scope: ScopeLike, catalog: dict) -> int:
    """Remove dismissals where matchedCatalogItem no longer exists in catalog.

    Args:
        item_type: 'agent', 'skill', or 'rule'
        scope: Scope object with is_global and repo_path
        catalog: dict of catalog item names (keys are catalog item identifiers)

    Returns:
        Count of pruned items.
    """
    if scope.is_global:
        data = _load_global_dismissed(item_type)
        items = data.get("items", {})
        stale_keys = [
            key
            for key, record in items.items()
            if record.get("matchedCatalogItem") not in catalog
        ]
        if not stale_keys:
            return 0
        for key in stale_keys:
            items.pop(key)
        _save_global_dismissed(item_type, data)
    else:
        aec_data = load_aec_json(scope.repo_path)
        if aec_data is None:
            return 0
        dismissed = aec_data.get("dismissed", {})
        type_section = dismissed.get(f"{item_type}s", {})
        stale_keys = [
            key
            for key, record in type_section.items()
            if record.get("matchedCatalogItem") not in catalog
        ]
        if not stale_keys:
            return 0
        for key in stale_keys:
            type_section.pop(key)
        save_aec_json(scope.repo_path, aec_data)

    return len(stale_keys)


def should_resurface(record: dict, catalog_hashes: dict, policy: str) -> bool:
    """Determine if a dismissed item should be resurfaced for re-comparison.

    Returns True if:
    - policy is "auto" AND
    - either the catalog hash changed (catalog item was updated) OR
      the local hash changed (user modified their file)

    Args:
        record: The dismissal record with matchedCatalogItem,
                matchedCatalogHash, localHash fields.
        catalog_hashes: Dict mapping catalog item names to their current
                        hash strings.
        policy: "auto" or "manual"
    """
    if policy != "auto":
        return False

    catalog_item = record.get("matchedCatalogItem")
    if catalog_item is None:
        return False

    recorded_catalog_hash = record.get("matchedCatalogHash")
    current_catalog_hash = catalog_hashes.get(catalog_item)

    # If catalog item no longer exists, don't resurface (prune_stale handles that)
    if current_catalog_hash is None:
        return False

    # Catalog hash changed => catalog item was updated
    if recorded_catalog_hash != current_catalog_hash:
        return True

    # Local hash changed => user modified their file
    recorded_local_hash = record.get("localHash")
    current_local_hash = record.get("currentLocalHash")
    if current_local_hash is not None and recorded_local_hash != current_local_hash:
        return True

    return False
