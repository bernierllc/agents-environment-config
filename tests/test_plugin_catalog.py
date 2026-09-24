"""Every plugin shipped in the catalog (plugins/*/plugin.json) is a valid loadout."""

import json
from pathlib import Path

import pytest

from aec.lib.loadout import validate_loadout

CATALOG = Path(__file__).resolve().parent.parent / "plugins"
MANIFESTS = sorted(CATALOG.glob("*/plugin.json"))


def test_catalog_is_not_empty():
    assert MANIFESTS


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.parent.name)
def test_manifest_validates(path):
    data = json.loads(path.read_text())
    validate_loadout(data)
    assert data["name"] == path.parent.name


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.parent.name)
def test_manifest_matches_json_schema(path):
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = CATALOG.parent / "docs" / "loadout" / "schema" / "plugin.schema.json"
    jsonschema.validate(json.loads(path.read_text()), json.loads(schema_path.read_text()))


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.parent.name)
def test_marketplace_plugins_uninstall_with_claude(path):
    """A marketplace plugin is removable by `aec uninstall`, not "manual cleanup"."""
    data = json.loads(path.read_text())
    if data["install_type"] != "marketplace":
        pytest.skip("not a marketplace plugin")
    run = data["uninstall"]["tools"]["claude"]["run"]
    assert run == ["claude", "plugin", "uninstall", data["install"]["plugin"]]
