"""Extra coverage for `aec.lib.org_config.parser` edge cases."""
from __future__ import annotations

import pytest

from aec.lib.org_config.errors import OrgConfigParseError
from aec.lib.org_config.parser import parse_org_config_text


def test_frontmatter_must_be_mapping_not_list():
    text = "---\n- a\n- b\n---\nfoo: bar\n"
    with pytest.raises(OrgConfigParseError, match="frontmatter must be a YAML mapping"):
        parse_org_config_text(text)


def test_body_must_be_mapping_not_list():
    text = "---\nschema_version: \"1.0\"\n---\n- one\n- two\n"
    with pytest.raises(OrgConfigParseError, match="body must be a YAML mapping"):
        parse_org_config_text(text)


def test_frontmatter_scalar_rejected():
    text = "---\njust-a-string\n---\nfoo: bar\n"
    with pytest.raises(OrgConfigParseError, match="frontmatter must be a YAML mapping"):
        parse_org_config_text(text)


def test_empty_body_yields_empty_dict():
    text = "---\nschema_version: \"1.0\"\n---\n"
    fm, body = parse_org_config_text(text)
    assert fm == {"schema_version": "1.0"}
    assert body == {}
