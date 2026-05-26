"""All docs/orgs/examples/*.yaml must parse and validate."""
from pathlib import Path

import pytest

from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.validator import validate_org_config

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "orgs" / "examples"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.yaml")))
def test_example_validates(path):
    fm, body = parse_org_config_text(path.read_text())
    validate_org_config(fm, body)
