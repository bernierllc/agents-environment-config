from pathlib import Path
import pytest

from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.errors import OrgConfigParseError


FIXTURES = Path(__file__).parent / "fixtures"


def test_parses_minimal_valid_config():
    text = (FIXTURES / "valid-minimal.yaml").read_text()
    frontmatter, body = parse_org_config_text(text)

    assert frontmatter["schema_version"] == "1.0"
    assert frontmatter["org_id"] == "minimal"
    assert frontmatter["trust"]["mode"] == "unsigned"
    assert "sources" in body
    assert "items" in body


def test_parses_full_valid_config():
    text = (FIXTURES / "valid-full.yaml").read_text()
    frontmatter, body = parse_org_config_text(text)
    assert frontmatter["org_id"]
    assert "items" in body


def test_rejects_missing_frontmatter():
    with pytest.raises(OrgConfigParseError, match="frontmatter"):
        parse_org_config_text("sources: {}\nitems: {}\n")


def test_rejects_unterminated_frontmatter():
    with pytest.raises(OrgConfigParseError, match="frontmatter"):
        parse_org_config_text("---\nschema_version: 1.0\n\nbody-without-closing-marker\n")


def test_rejects_invalid_yaml_in_frontmatter():
    with pytest.raises(OrgConfigParseError):
        parse_org_config_text("---\nschema_version: [unclosed\n---\nitems: {}\n")
