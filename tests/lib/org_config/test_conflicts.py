"""Tests for cross-org conflict detection."""

from aec.lib.org_config.conflicts import detect_conflicts
from aec.lib.org_config.schema import ItemPolicy, OrgConfig, Stance


def _cfg(org_id, *, items=None, default_sources=None, preferences=None, install_mode=None):
    return OrgConfig(
        schema_version="1.0",
        org_id=org_id,
        org_name=org_id.title(),
        config_version="1.0.0",
        description=None,
        trust_mode="unsigned",
        default_sources=default_sources or {},
        custom_sources=[],
        items=items or {"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
        install_preferences=preferences or {},
        install_prompts={},
        install_agents_enabled=[],
        install_agents_disabled=[],
        install_mode=install_mode,
    )


def _skill(name, stance, source="aec.default.skills", version=None):
    return {"skills": {name: ItemPolicy(source=source, stance=Stance(stance), version=version)}}


def test_no_conflicts_when_single_org():
    a = _cfg("acme", items=_skill("foo", "required"))
    assert detect_conflicts([a]) == []


def test_stance_conflict_required_vs_blocked():
    a = _cfg("acme", items=_skill("foo", "required"))
    b = _cfg("globex", items=_skill("foo", "blocked"))
    conflicts = detect_conflicts([a, b])
    kinds = [c.kind for c in conflicts]
    assert "stance" in kinds
    stance = next(c for c in conflicts if c.kind == "stance")
    assert stance.subject == "skills/foo"
    assert {p.org_id: p.value for p in stance.participants} == {
        "acme": "required",
        "globex": "blocked",
    }


def test_no_stance_conflict_when_both_install():
    a = _cfg("acme", items=_skill("foo", "required"))
    b = _cfg("globex", items=_skill("foo", "recommended"))
    assert [c for c in detect_conflicts([a, b]) if c.kind == "stance"] == []


def test_silent_stance_is_not_a_conflict():
    a = _cfg("acme", items=_skill("foo", "blocked"))
    b = _cfg("globex", items=_skill("foo", "silent"))
    assert [c for c in detect_conflicts([a, b]) if c.kind == "stance"] == []


def test_version_conflict_on_differing_pins():
    a = _cfg("acme", items=_skill("foo", "required", version=">=2.0.0"))
    b = _cfg("globex", items=_skill("foo", "pinned", version="1.0.0"))
    versions = [c for c in detect_conflicts([a, b]) if c.kind == "version"]
    assert len(versions) == 1
    assert versions[0].subject == "skills/foo"


def test_no_version_conflict_when_pins_match():
    a = _cfg("acme", items=_skill("foo", "required", version=">=2.0.0"))
    b = _cfg("globex", items=_skill("foo", "required", version=">=2.0.0"))
    assert [c for c in detect_conflicts([a, b]) if c.kind == "version"] == []


def test_different_sources_are_not_the_same_item():
    a = _cfg("acme", items=_skill("foo", "required", source="aec.default.skills"))
    b = _cfg("globex", items=_skill("foo", "blocked", source="aec.default.skills"))
    # same source -> conflict
    assert any(c.kind == "stance" for c in detect_conflicts([a, b]))


def test_source_replacement_conflict():
    a = _cfg("acme", default_sources={"skills": "keep"})
    b = _cfg("globex", default_sources={"skills": "replace"})
    conflicts = [c for c in detect_conflicts([a, b]) if c.kind == "source_replacement"]
    assert len(conflicts) == 1
    assert conflicts[0].subject == "sources.default.skills"


def test_preference_conflict():
    a = _cfg("acme", preferences={"projects_dir": "~/work/acme"})
    b = _cfg("globex", preferences={"projects_dir": "~/code"})
    conflicts = [c for c in detect_conflicts([a, b]) if c.kind == "preference"]
    assert len(conflicts) == 1
    assert conflicts[0].subject == "preference.projects_dir"


def test_no_preference_conflict_when_values_match():
    a = _cfg("acme", preferences={"projects_dir": "~/work"})
    b = _cfg("globex", preferences={"projects_dir": "~/work"})
    assert [c for c in detect_conflicts([a, b]) if c.kind == "preference"] == []


def test_install_mode_conflict():
    a = _cfg("acme", install_mode="managed")
    b = _cfg("globex", install_mode="guided")
    conflicts = [c for c in detect_conflicts([a, b]) if c.kind == "install_mode"]
    assert len(conflicts) == 1
    assert conflicts[0].subject == "install.mode"


def test_conflict_id_is_stable_and_order_independent():
    a = _cfg("acme", items=_skill("foo", "required"))
    b = _cfg("globex", items=_skill("foo", "blocked"))
    id1 = detect_conflicts([a, b])[0].conflict_id
    id2 = detect_conflicts([b, a])[0].conflict_id
    assert id1 == id2
    assert id1.startswith("conf-")
