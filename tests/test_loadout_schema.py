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
