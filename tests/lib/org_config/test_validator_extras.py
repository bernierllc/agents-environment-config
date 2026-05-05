"""Extra coverage for `aec.lib.org_config.validator` edge cases."""
from __future__ import annotations

import pytest

from aec.lib.org_config.errors import OrgConfigValidationError
from aec.lib.org_config.validator import validate_org_config


def _fm(**overrides):
    base = {
        "schema_version": "1.0",
        "org_id": "x",
        "org_name": "X",
        "config_version": "1.0.0",
        "trust": {"mode": "unsigned"},
    }
    base.update(overrides)
    return base


def _body(**overrides):
    base = {
        "sources": {"default": {}, "custom": []},
        "items": {"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
    }
    base.update(overrides)
    return base


def test_missing_required_org_id_raises_with_field_path():
    fm = _fm()
    fm.pop("org_id")
    with pytest.raises(OrgConfigValidationError) as excinfo:
        validate_org_config(fm, _body())
    assert excinfo.value.field_path == "org_id"


def test_required_field_present_but_explicit_none_raises():
    fm = _fm(org_name=None)
    with pytest.raises(OrgConfigValidationError, match="org_name"):
        validate_org_config(fm, _body())


def test_missing_trust_mode_raises():
    fm = _fm(trust={})
    with pytest.raises(OrgConfigValidationError, match="trust.mode is required"):
        validate_org_config(fm, _body())


def test_item_policy_must_be_a_mapping():
    body = _body(items={"skills": {"my-skill": "not-a-mapping"}, "rules": {}, "agents": {}, "mcps": {}})
    with pytest.raises(OrgConfigValidationError, match="item policy must be a mapping"):
        validate_org_config(_fm(), body)


def test_install_preferences_dynamic_namespace_is_accepted():
    """Keys that match a PREFERENCES_DYNAMIC_NAMESPACES prefix are allowed."""
    from aec.lib.org_config.allow_lists import PREFERENCES_DYNAMIC_NAMESPACES

    assert PREFERENCES_DYNAMIC_NAMESPACES, "preconditions: at least one dynamic ns"
    ns = next(iter(PREFERENCES_DYNAMIC_NAMESPACES))
    body = _body(install={"preferences": {f"{ns}.some_runtime_key": "v"}})
    cfg = validate_org_config(_fm(), body)
    assert cfg.install_preferences == {f"{ns}.some_runtime_key": "v"}


def test_install_prompts_dynamic_prefix_is_accepted():
    """Keys that match a PROMPTS_DYNAMIC_PREFIXES prefix are allowed."""
    from aec.lib.org_config.allow_lists import PROMPTS_DYNAMIC_PREFIXES

    assert PROMPTS_DYNAMIC_PREFIXES, "preconditions: at least one dynamic prefix"
    prefix = next(iter(PROMPTS_DYNAMIC_PREFIXES))
    body = _body(install={"prompts": {f"{prefix}.runtime.id": True}})
    cfg = validate_org_config(_fm(), body)
    assert f"{prefix}.runtime.id" in cfg.install_prompts
