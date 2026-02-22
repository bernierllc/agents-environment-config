"""Tests for aec.lib.preferences module."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestAecPreferencesConstant:
    """Test that AEC_PREFERENCES path constant exists."""

    def test_aec_preferences_path_exists(self):
        """AEC_PREFERENCES should be defined in config."""
        from aec.lib.config import AEC_PREFERENCES

        assert AEC_PREFERENCES is not None
        assert isinstance(AEC_PREFERENCES, Path)
        assert AEC_PREFERENCES.name == "preferences.json"


class TestLoadPreferences:
    """Test load_preferences function."""

    def test_returns_empty_structure_when_file_missing(self, temp_dir, monkeypatch):
        """Should return default structure when preferences.json doesn't exist."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        from aec.lib.preferences import load_preferences

        result = load_preferences()
        assert result == {"schema_version": "1.0", "optional_rules": {}}

    def test_reads_existing_file(self, temp_dir, monkeypatch):
        """Should read and return existing preferences."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.lib.preferences import load_preferences

        result = load_preferences()
        assert result["optional_rules"]["leave-it-better"]["enabled"] is True

    def test_handles_corrupt_json(self, temp_dir, monkeypatch):
        """Should return default structure if JSON is corrupt."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text("not valid json {{{")
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.lib.preferences import load_preferences

        result = load_preferences()
        assert result == {"schema_version": "1.0", "optional_rules": {}}


class TestSavePreferences:
    """Test save_preferences function."""

    def test_creates_file(self, temp_dir, monkeypatch):
        """Should create preferences.json with given data."""
        prefs_file = temp_dir / "preferences.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import save_preferences

        data = {"schema_version": "1.0", "optional_rules": {"test": {"enabled": True, "asked_at": "now"}}}
        save_preferences(data)

        assert prefs_file.exists()
        loaded = json.loads(prefs_file.read_text())
        assert loaded["optional_rules"]["test"]["enabled"] is True

    def test_overwrites_existing(self, temp_dir, monkeypatch):
        """Should overwrite existing preferences file."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text('{"old": true}')
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import save_preferences

        save_preferences({"schema_version": "1.0", "optional_rules": {}})

        loaded = json.loads(prefs_file.read_text())
        assert "old" not in loaded


class TestGetPreference:
    """Test get_preference function."""

    def test_returns_none_when_not_set(self, temp_dir, monkeypatch):
        """Should return None for unset preference."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        from aec.lib.preferences import get_preference

        assert get_preference("leave-it-better") is None

    def test_returns_true_when_enabled(self, temp_dir, monkeypatch):
        """Should return True for enabled preference."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.lib.preferences import get_preference

        assert get_preference("leave-it-better") is True

    def test_returns_false_when_disabled(self, temp_dir, monkeypatch):
        """Should return False for disabled preference."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": False, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.lib.preferences import get_preference

        assert get_preference("leave-it-better") is False


class TestSetPreference:
    """Test set_preference function."""

    def test_sets_new_preference(self, temp_dir, monkeypatch):
        """Should create preference entry with timestamp."""
        prefs_file = temp_dir / "preferences.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_preference, load_preferences

        set_preference("leave-it-better", True)

        result = load_preferences()
        assert result["optional_rules"]["leave-it-better"]["enabled"] is True
        assert "asked_at" in result["optional_rules"]["leave-it-better"]

    def test_updates_existing_preference(self, temp_dir, monkeypatch):
        """Should update an existing preference."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_preference, load_preferences

        set_preference("leave-it-better", False)

        result = load_preferences()
        assert result["optional_rules"]["leave-it-better"]["enabled"] is False


class TestGetPendingPrompts:
    """Test get_pending_prompts function."""

    def test_returns_all_when_no_preferences(self, temp_dir, monkeypatch):
        """Should return all optional features when preferences.json is empty."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        from aec.lib.preferences import get_pending_prompts

        pending = get_pending_prompts()
        assert len(pending) > 0
        assert any(p["key"] == "leave-it-better" for p in pending)

    def test_returns_empty_when_all_answered(self, temp_dir, monkeypatch):
        """Should return empty list when all features have been answered."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.lib.preferences import get_pending_prompts

        pending = get_pending_prompts()
        assert len(pending) == 0

    def test_skips_disabled_features(self, temp_dir, monkeypatch):
        """Should NOT prompt for features the user has declined (enabled=False)."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": False, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.lib.preferences import get_pending_prompts

        pending = get_pending_prompts()
        assert len(pending) == 0


class TestOptionalFeaturesRegistry:
    """Test the OPTIONAL_FEATURES registry."""

    def test_leave_it_better_in_registry(self):
        """leave-it-better should be registered."""
        from aec.lib.preferences import OPTIONAL_FEATURES

        assert "leave-it-better" in OPTIONAL_FEATURES

    def test_features_have_required_keys(self):
        """Each feature must have description, prompt, and default."""
        from aec.lib.preferences import OPTIONAL_FEATURES

        for key, feature in OPTIONAL_FEATURES.items():
            assert "description" in feature, f"{key} missing description"
            assert "prompt" in feature, f"{key} missing prompt"
            assert "default" in feature, f"{key} missing default"


class TestResetPreference:
    """Test reset_preference function."""

    def test_removes_preference(self, temp_dir, monkeypatch):
        """Should remove a preference so it will be re-prompted."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import reset_preference, get_pending_prompts

        reset_preference("leave-it-better")

        pending = get_pending_prompts()
        assert any(p["key"] == "leave-it-better" for p in pending)

    def test_reset_nonexistent_is_noop(self, temp_dir, monkeypatch):
        """Resetting a nonexistent preference should not error."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import reset_preference

        # Should not raise
        reset_preference("nonexistent-feature")
