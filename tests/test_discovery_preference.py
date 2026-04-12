"""Tests for the discovery_recompare preference and get_recompare_policy helper."""

import json
from unittest.mock import patch

from aec.lib.preferences import (
    OPTIONAL_FEATURES,
    get_recompare_policy,
)


class TestDiscoveryRecompareFeatureEntry:
    """Verify the OPTIONAL_FEATURES registry entry for discovery_recompare."""

    def test_entry_exists(self):
        """discovery_recompare must be registered in OPTIONAL_FEATURES."""
        assert "discovery_recompare" in OPTIONAL_FEATURES

    def test_has_required_keys(self):
        """Entry must have description, prompt, and default keys."""
        entry = OPTIONAL_FEATURES["discovery_recompare"]
        assert "description" in entry
        assert "prompt" in entry
        assert "default" in entry

    def test_default_is_true(self):
        """Default should be True (auto re-compare)."""
        assert OPTIONAL_FEATURES["discovery_recompare"]["default"] is True

    def test_prompt_contains_recompare_option(self):
        """Prompt text should describe the auto re-compare option."""
        prompt = OPTIONAL_FEATURES["discovery_recompare"]["prompt"]
        assert "re-compare automatically" in prompt

    def test_prompt_contains_manual_option(self):
        """Prompt text should mention the manual rediscover command."""
        prompt = OPTIONAL_FEATURES["discovery_recompare"]["prompt"]
        assert "aec discover --rediscover" in prompt

    def test_prompt_contains_numbered_choices(self):
        """Prompt should present numbered choices 1 and 2."""
        prompt = OPTIONAL_FEATURES["discovery_recompare"]["prompt"]
        assert "1)" in prompt
        assert "2)" in prompt


class TestGetRecomparePolicy:
    """Test the get_recompare_policy helper function."""

    def test_returns_auto_when_preference_is_true(self):
        """When user chose to re-compare (True), policy is 'auto'."""
        with patch("aec.lib.preferences.get_preference", return_value=True):
            assert get_recompare_policy() == "auto"

    def test_returns_manual_when_preference_is_false(self):
        """When user declined re-compare (False), policy is 'manual'."""
        with patch("aec.lib.preferences.get_preference", return_value=False):
            assert get_recompare_policy() == "manual"

    def test_returns_auto_when_preference_is_none(self):
        """When preference has not been answered yet (None), default to 'auto'."""
        with patch("aec.lib.preferences.get_preference", return_value=None):
            assert get_recompare_policy() == "auto"

    def test_calls_get_preference_with_correct_key(self):
        """get_recompare_policy must query the 'discovery_recompare' key."""
        with patch("aec.lib.preferences.get_preference", return_value=True) as mock_pref:
            get_recompare_policy()
            mock_pref.assert_called_once_with("discovery_recompare")


class TestGetRecomparePolicyIntegration:
    """Integration tests using the real preference loading path."""

    def test_returns_auto_with_enabled_preference(self, temp_dir, monkeypatch):
        """With a real preferences file where discovery_recompare is enabled."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.2",
            "optional_rules": {
                "discovery_recompare": {
                    "enabled": True,
                    "asked_at": "2026-04-08T00:00:00Z",
                }
            },
            "settings": {},
            "configurable_instructions": {},
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        assert get_recompare_policy() == "auto"

    def test_returns_manual_with_disabled_preference(self, temp_dir, monkeypatch):
        """With a real preferences file where discovery_recompare is disabled."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.2",
            "optional_rules": {
                "discovery_recompare": {
                    "enabled": False,
                    "asked_at": "2026-04-08T00:00:00Z",
                }
            },
            "settings": {},
            "configurable_instructions": {},
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        assert get_recompare_policy() == "manual"

    def test_returns_auto_with_no_preferences_file(self, temp_dir, monkeypatch):
        """With no preferences file at all, should default to 'auto'."""
        monkeypatch.setattr(
            "aec.lib.preferences.AEC_PREFERENCES",
            temp_dir / "nonexistent.json",
        )

        assert get_recompare_policy() == "auto"
