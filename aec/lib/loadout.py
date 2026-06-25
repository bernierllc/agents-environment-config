"""Locate, parse, and validate a loadout item-manifest (plugin.json / plugin.yaml)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
    HAS_YAML = True
    _PARSE_ERRORS: tuple = (json.JSONDecodeError, ValueError, yaml.YAMLError)
except ImportError:
    HAS_YAML = False
    _PARSE_ERRORS = (json.JSONDecodeError, ValueError)

SCHEMA_VERSION = "loadout/v1"
ITEM_TYPES = ("plugin", "skill", "agent", "rule")
INSTALL_TYPES = ("marketplace", "per-tool", "external")
_BASE_REQUIRED = ("schema", "item_type", "name", "version", "description", "source")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# install sub-keys each install_type's consumers index (mirrors plugin.schema.json allOf)
_INSTALL_REQUIRED = {
    "marketplace": ("marketplace", "plugin"),
    "per-tool": ("tools",),
    "external": ("external",),
}
# filename stems searched, in priority order, at dir root then .loadout/
_STEMS = ("plugin", "skill", "agent", "rule")


class LoadoutError(Exception):
    """Raised when a loadout manifest is missing, unparseable, or invalid."""


def validate_loadout(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise LoadoutError("loadout manifest must be a mapping")
    for field in _BASE_REQUIRED:
        if field not in data:
            raise LoadoutError(f"loadout manifest missing required field: {field}")
    if data["schema"] != SCHEMA_VERSION:
        raise LoadoutError(
            f"unsupported loadout schema {data['schema']!r}; expected {SCHEMA_VERSION!r}"
        )
    if data["item_type"] not in ITEM_TYPES:
        raise LoadoutError(f"invalid item_type: {data['item_type']!r}")
    if not _NAME_RE.match(str(data["name"])):
        raise LoadoutError(f"invalid name {data['name']!r}; must match {_NAME_RE.pattern}")
    if data["item_type"] == "plugin":
        it = data.get("install_type")
        if it not in INSTALL_TYPES:
            raise LoadoutError(f"invalid install_type: {it!r}")
        install = data.get("install")
        if not isinstance(install, dict):
            raise LoadoutError("plugin loadout missing install block")
        for key in _INSTALL_REQUIRED[it]:
            if key not in install:
                raise LoadoutError(f"{it} install block missing required key: {key}")


def _parse(path: Path) -> Dict[str, Any]:
    try:
        # read inside the try: UnicodeDecodeError (a ValueError) is in _PARSE_ERRORS,
        # so an undecodable manifest surfaces as LoadoutError and discovery skips it.
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            return json.loads(text)
        if not HAS_YAML:
            raise LoadoutError(
                f"{path.name} is YAML but PyYAML is not installed; "
                "install PyYAML or provide a .json manifest"
            )
        return yaml.safe_load(text)
    except _PARSE_ERRORS as e:
        raise LoadoutError(f"failed to parse {path.name}: {e}") from e


def find_loadout_file(directory: Path) -> Path | None:
    for base in (directory, directory / ".loadout"):
        for stem in _STEMS:
            for ext in (".json", ".yaml", ".yml"):
                candidate = base / f"{stem}{ext}"
                if candidate.is_file():
                    return candidate
    return None


def load_loadout(directory: Path) -> Dict[str, Any]:
    path = find_loadout_file(directory)
    if path is None:
        raise LoadoutError(f"no loadout manifest found in {directory}")
    data = _parse(path)
    validate_loadout(data)
    return data
