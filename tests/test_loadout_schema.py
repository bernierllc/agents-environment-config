import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "docs" / "loadout" / "schema"
SCHEMA_FILES = ["plugin", "skill", "agent", "rule"]


@pytest.mark.parametrize("name", SCHEMA_FILES)
def test_schema_is_valid_json_schema(name: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"].startswith("https://json-schema.org/")


def _plugin_validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMA_DIR / "plugin.schema.json").read_text())
    return jsonschema.Draft202012Validator(schema)


def test_plugin_missing_install_type_fails() -> None:
    # Regression for the conditional `if` blocks: with `install_type` absent each
    # `if` must NOT vacuously pass. The instance should fail on the missing
    # required field, not surface spurious conditional errors.
    instance = {
        "schema": "loadout/v1",
        "item_type": "plugin",
        "name": "my-plugin",
        "version": "1.0.0",
        "description": "x",
        "source": "https://example.com",
        "install": {"marketplace": "example/my-plugin", "plugin": "my-plugin"},
    }
    assert not _plugin_validator().is_valid(instance)


def test_plugin_wrong_install_branch_fails() -> None:
    # marketplace install_type but an external-only install block: the
    # conditional must bind the marketplace branch and reject the missing fields.
    instance = {
        "schema": "loadout/v1",
        "item_type": "plugin",
        "name": "my-plugin",
        "version": "1.0.0",
        "description": "x",
        "source": "https://example.com",
        "install_type": "marketplace",
        "install": {"external": {"download": "https://example.com"}},
    }
    assert not _plugin_validator().is_valid(instance)


def test_plugin_valid_marketplace_passes() -> None:
    instance = {
        "schema": "loadout/v1",
        "item_type": "plugin",
        "name": "my-plugin",
        "version": "1.0.0",
        "description": "x",
        "source": "https://example.com",
        "install_type": "marketplace",
        "install": {"marketplace": "example/my-plugin", "plugin": "my-plugin"},
    }
    assert _plugin_validator().is_valid(instance)
