"""Per-item hook installation state.

One file per item at `.aec/installed-hooks/<type>.<key>.json`. Keeping state
per-item (rather than a single manifest) lets parallel installers touch
different items without stepping on each other.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from ..atomic_write import atomic_write_json

STATE_DIR = ".aec/installed-hooks"
SCHEMA_VERSION = 1


@dataclass
class ItemHookState:
    item_type: str
    item_key: str
    item_version: str = ""
    hooks_file_hash: str = ""
    hooks_installed: List[dict] = field(default_factory=list)
    hooks_skipped: List[dict] = field(default_factory=list)
    agents_targeted: List[str] = field(default_factory=list)
    skipped_versions: List[str] = field(default_factory=list)
    allow_custom_check: bool = False
    schema_version: int = SCHEMA_VERSION


def _validate_identifier(name: str, label: str) -> None:
    if not name:
        raise ValueError(f"{label} must be non-empty")
    if "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"{label} {name!r} contains path separators")


def _state_path(repo_root: Path, item_type: str, item_key: str) -> Path:
    _validate_identifier(item_type, "item_type")
    _validate_identifier(item_key, "item_key")
    return Path(repo_root) / STATE_DIR / f"{item_type}.{item_key}.json"


def load_state(repo_root: Path, item_type: str, item_key: str) -> ItemHookState:
    """Load state for an item, or return an empty state if the file is absent."""
    path = _state_path(repo_root, item_type, item_key)
    if not path.exists():
        return ItemHookState(item_type=item_type, item_key=item_key)
    data = json.loads(path.read_text(encoding="utf-8"))
    return ItemHookState(
        item_type=data.get("item_type", item_type),
        item_key=data.get("item_key", item_key),
        item_version=data.get("item_version", ""),
        hooks_file_hash=data.get("hooks_file_hash", ""),
        hooks_installed=list(data.get("hooks_installed", [])),
        hooks_skipped=list(data.get("hooks_skipped", [])),
        agents_targeted=list(data.get("agents_targeted", [])),
        skipped_versions=list(data.get("skipped_versions", [])),
        allow_custom_check=bool(data.get("allow_custom_check", False)),
        schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
    )


def save_state(repo_root: Path, state: ItemHookState) -> None:
    path = _state_path(repo_root, state.item_type, state.item_key)
    payload = {
        "schema_version": state.schema_version,
        "item_type": state.item_type,
        "item_key": state.item_key,
        "item_version": state.item_version,
        "hooks_file_hash": state.hooks_file_hash,
        "hooks_installed": state.hooks_installed,
        "hooks_skipped": state.hooks_skipped,
        "agents_targeted": state.agents_targeted,
        "skipped_versions": state.skipped_versions,
        "allow_custom_check": state.allow_custom_check,
    }
    atomic_write_json(path, payload)


def remove_state(repo_root: Path, item_type: str, item_key: str) -> None:
    path = _state_path(repo_root, item_type, item_key)
    path.unlink(missing_ok=True)


def mark_version_skipped(state: ItemHookState, version: str) -> None:
    if version not in state.skipped_versions:
        state.skipped_versions.append(version)


def is_version_skipped(state: ItemHookState, version: str) -> bool:
    return version in state.skipped_versions


def list_installed_items(repo_root: Path) -> List[Tuple[str, str]]:
    """Return (item_type, item_key) tuples for every state file present."""
    state_dir = Path(repo_root) / STATE_DIR
    if not state_dir.exists():
        return []
    items: List[Tuple[str, str]] = []
    for entry in sorted(state_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".json":
            continue
        stem = entry.stem
        if "." not in stem:
            continue
        item_type, _, item_key = stem.partition(".")
        items.append((item_type, item_key))
    return items
