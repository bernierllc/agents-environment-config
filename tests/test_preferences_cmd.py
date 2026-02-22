"""Tests for aec preferences CLI commands."""

import json
from pathlib import Path

import pytest


class TestPreferencesListCommand:
    """Test aec preferences list."""

    def test_shows_enabled_feature(self, temp_dir, monkeypatch, capsys):
        """Should display enabled features with checkmark."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-02-21T15:30:45Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.commands.preferences import list_preferences

        list_preferences()

        output = capsys.readouterr().out
        assert "leave-it-better" in output
        assert "enabled" in output.lower() or "\u2713" in output

    def test_shows_disabled_feature(self, temp_dir, monkeypatch, capsys):
        """Should display disabled features."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": False, "asked_at": "2026-02-21T15:30:45Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        from aec.commands.preferences import list_preferences

        list_preferences()

        output = capsys.readouterr().out
        assert "leave-it-better" in output
        assert "disabled" in output.lower() or "\u2717" in output

    def test_shows_not_set_feature(self, temp_dir, monkeypatch, capsys):
        """Should indicate features that haven't been configured."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        from aec.commands.preferences import list_preferences

        list_preferences()

        output = capsys.readouterr().out
        assert "leave-it-better" in output
        assert "not set" in output.lower() or "\u2014" in output


class TestPreferencesSetCommand:
    """Test aec preferences set."""

    def test_set_on(self, temp_dir, monkeypatch):
        """Should enable a feature."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.commands.preferences import set_pref
        from aec.lib.preferences import get_preference

        set_pref("leave-it-better", "on")
        assert get_preference("leave-it-better") is True

    def test_set_off(self, temp_dir, monkeypatch):
        """Should disable a feature."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.commands.preferences import set_pref
        from aec.lib.preferences import get_preference

        set_pref("leave-it-better", "off")
        assert get_preference("leave-it-better") is False

    def test_invalid_feature_name(self, temp_dir, monkeypatch, capsys):
        """Should error on unknown feature name."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        from aec.commands.preferences import set_pref

        with pytest.raises(SystemExit):
            set_pref("nonexistent", "on")


class TestPreferencesResetCommand:
    """Test aec preferences reset."""

    def test_reset_removes_preference(self, temp_dir, monkeypatch):
        """Should remove the preference so user is re-prompted."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-02-21T15:30:45Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.commands.preferences import reset_pref
        from aec.lib.preferences import get_preference

        reset_pref("leave-it-better")
        assert get_preference("leave-it-better") is None
