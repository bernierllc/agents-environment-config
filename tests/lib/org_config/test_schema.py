import pytest

from aec.lib.org_config.schema import (
    Stance,
    RESERVED_SOURCE_IDS,
    ItemPolicy,
    CustomSource,
    OrgConfig,
    SCHEMA_VERSION_SUPPORTED,
)


def test_stance_is_closed_set():
    assert {s.value for s in Stance} == {"required", "recommended", "blocked", "pinned", "silent"}


def test_reserved_source_ids():
    assert RESERVED_SOURCE_IDS == frozenset({
        "aec.default.skills",
        "aec.default.rules",
        "aec.default.agents",
        "aec.default.mcps",
    })


def test_supported_schema_version_is_1_0():
    assert "1.0" in SCHEMA_VERSION_SUPPORTED


def test_item_policy_requires_source():
    pol = ItemPolicy(source="aec.default.skills", stance=Stance.REQUIRED, version=">=2.0.0")
    assert pol.source == "aec.default.skills"


def test_item_policy_time_bounds_default_none():
    pol = ItemPolicy(source="aec.default.skills", stance=Stance.REQUIRED)
    assert pol.required_after is None
    assert pol.expires_at is None


def test_item_policy_carries_time_bounds():
    pol = ItemPolicy(
        source="aec.default.skills",
        stance=Stance.REQUIRED,
        required_after="2026-06-01",
        expires_at="2026-12-01",
    )
    assert pol.required_after == "2026-06-01"
    assert pol.expires_at == "2026-12-01"


def test_org_config_construct():
    cfg = OrgConfig(
        schema_version="1.0",
        org_id="acme",
        org_name="Acme",
        config_version="1.0.0",
        description=None,
        trust_mode="unsigned",
        default_sources={"skills": "keep", "rules": "keep", "agents": "keep", "mcps": "keep"},
        custom_sources=[],
        items={"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
        install_preferences={},
        install_prompts={},
        install_agents_enabled=[],
        install_agents_disabled=[],
    )
    assert cfg.org_id == "acme"
