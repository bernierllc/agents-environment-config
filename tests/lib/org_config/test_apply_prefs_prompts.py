"""Tests for applying org-policy preferences and prompts (A3)."""

import pytest

from aec.lib import preferences, prompts
from aec.lib.org_config.apply import apply_preferences, apply_prompts
from aec.lib.org_config.effective import EffectivePolicy


def _policy(*, preferences=None, prompts=None):
    return EffectivePolicy(
        items={},
        preferences=preferences or {},
        prompts=prompts or {},
        default_sources={},
        custom_sources=[],
        install_mode=None,
        held=(),
    )


@pytest.fixture
def prefs_file(tmp_path, monkeypatch):
    f = tmp_path / "preferences.json"
    monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", f)
    monkeypatch.setattr("aec.lib.preferences.AEC_HOME", tmp_path)
    return f


def test_setting_pref_routed_to_settings_section(prefs_file):
    apply_preferences(_policy(preferences={"projects_dir": "~/work/acme"}))
    data = preferences.load_preferences()
    assert data["settings"]["projects_dir"] == "~/work/acme"


def test_optional_feature_routed_to_optional_rules(prefs_file):
    # leave-it-better is an OPTIONAL_FEATURES key -> optional_rules section.
    apply_preferences(_policy(preferences={"leave-it-better": True}))
    data = preferences.load_preferences()
    assert data["optional_rules"]["leave-it-better"]["enabled"] is True


def test_apply_preferences_returns_applied_keys(prefs_file):
    applied = apply_preferences(_policy(preferences={"projects_dir": "~/w", "hook_mode": "auto"}))
    assert set(applied) == {"projects_dir", "hook_mode"}


def test_configurable_instruction_routed_to_dedicated_section(prefs_file):
    apply_preferences(
        _policy(
            preferences={
                "configurable_instructions.commit-style.claude": True,
                "configurable_instructions.commit-style.cursor": False,
            }
        )
    )
    data = preferences.load_preferences()
    agents = data["configurable_instructions"]["commit-style"]["agents"]
    assert agents == {"claude": True, "cursor": False}
    # Not leaked into settings.
    assert "configurable_instructions.commit-style.claude" not in data.get("settings", {})


def test_apply_prompts_registers_overlay_answers():
    prompts.clear_overlay_answers()
    try:
        apply_prompts(_policy(prompts={"setup.track_current_repo": True}))

        def boom(_t):
            raise AssertionError("should be pre-answered")

        import builtins

        orig = builtins.input
        builtins.input = boom
        try:
            assert prompts.prompt("setup.track_current_repo", "Q? ", type="bool") is True
        finally:
            builtins.input = orig
    finally:
        prompts.clear_overlay_answers()
