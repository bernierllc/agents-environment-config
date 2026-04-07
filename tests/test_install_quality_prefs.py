"""Tests for quality infrastructure install preferences."""

import json
from pathlib import Path

import pytest


class TestPromptQualitySettings:
    """Test the quality settings prompt flow during install."""

    def _enable_scheduled_tests(self, temp_dir, monkeypatch):
        """Helper: write prefs with scheduled_tests_enabled=True."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.2",
            "optional_rules": {
                "scheduled_tests_enabled": {
                    "enabled": True,
                    "asked_at": "2026-01-01T00:00:00Z",
                },
            },
            "settings": {},
            "configurable_instructions": {},
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

    def _disable_scheduled_tests(self, temp_dir, monkeypatch):
        """Helper: write prefs with scheduled_tests_enabled=False."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.2",
            "optional_rules": {
                "scheduled_tests_enabled": {
                    "enabled": False,
                    "asked_at": "2026-01-01T00:00:00Z",
                },
            },
            "settings": {},
            "configurable_instructions": {},
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

    def test_stores_viewer_when_scheduled_enabled(self, temp_dir, monkeypatch):
        """Should prompt for viewer and store it when scheduled tests are on."""
        self._enable_scheduled_tests(temp_dir, monkeypatch)

        # Pick viewer #1 from detected list, auto retention, 30 days
        inputs = iter([
            "1",   # first viewer in list
            "1",   # auto retention
            "30",  # 30 days
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_quality_settings
        _prompt_quality_settings()

        from aec.lib.preferences import get_setting
        # Should store a viewer key (string), not None
        assert get_setting("report_viewer") is not None

    def test_stores_retention_auto_with_days(self, temp_dir, monkeypatch):
        """Should store auto retention mode with custom day count."""
        self._enable_scheduled_tests(temp_dir, monkeypatch)

        # Pick "None" viewer (last option), auto retention, 14 days
        # detect_viewers returns N viewers; N+1 is "None"
        from aec.lib.viewers import detect_viewers
        n_viewers = len(detect_viewers())
        inputs = iter([
            str(n_viewers + 1),  # "None" option
            "1",                 # auto retention
            "14",                # 14 days
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_quality_settings
        _prompt_quality_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("report_viewer") is None
        assert get_setting("report_retention_mode") == "auto"
        assert get_setting("report_retention_days") == 14

    def test_stores_retention_manual(self, temp_dir, monkeypatch):
        """Should store manual retention mode without days."""
        self._enable_scheduled_tests(temp_dir, monkeypatch)

        from aec.lib.viewers import detect_viewers
        n_viewers = len(detect_viewers())
        inputs = iter([
            str(n_viewers + 1),  # "None" option
            "2",                 # manual retention
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_quality_settings
        _prompt_quality_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("report_retention_mode") == "manual"
        # report_retention_days should not be set
        assert get_setting("report_retention_days") is None

    def test_skips_when_scheduled_tests_disabled(self, temp_dir, monkeypatch):
        """Should skip viewer/retention prompts when scheduled tests off."""
        self._disable_scheduled_tests(temp_dir, monkeypatch)

        def should_not_be_called(_):
            raise AssertionError("Should not prompt when scheduled tests disabled")
        monkeypatch.setattr("builtins.input", should_not_be_called)

        from aec.commands.install import _prompt_quality_settings
        _prompt_quality_settings()  # Should not raise

    def test_handles_eof(self, temp_dir, monkeypatch):
        """Should use defaults when input raises EOFError."""
        self._enable_scheduled_tests(temp_dir, monkeypatch)

        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)

        from aec.commands.install import _prompt_quality_settings
        _prompt_quality_settings()

        from aec.lib.preferences import get_setting
        # Defaults: first viewer from detected list, auto retention, 30 days
        assert get_setting("report_viewer") is not None
        assert get_setting("report_retention_mode") == "auto"
        assert get_setting("report_retention_days") == 30

    def test_dry_run_does_not_write(self, temp_dir, monkeypatch):
        """Should not persist settings when dry_run=True."""
        self._enable_scheduled_tests(temp_dir, monkeypatch)

        inputs = iter([
            "1",   # first viewer
            "1",   # auto retention
            "30",  # 30 days
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_quality_settings
        _prompt_quality_settings(dry_run=True)

        from aec.lib.preferences import get_setting
        # Nothing should have been persisted
        assert get_setting("report_viewer") is None
        assert get_setting("report_retention_mode") is None
        assert get_setting("report_retention_days") is None


class TestOptionalFeaturesRegistry:
    """Test that new OPTIONAL_FEATURES entries are well-formed."""

    def test_port_registry_has_required_keys(self):
        """port_registry_enabled must have description, prompt, default."""
        from aec.lib.preferences import OPTIONAL_FEATURES
        entry = OPTIONAL_FEATURES["port_registry_enabled"]
        assert "description" in entry
        assert "prompt" in entry
        assert "default" in entry

    def test_scheduled_tests_has_required_keys(self):
        """scheduled_tests_enabled must have description, prompt, default."""
        from aec.lib.preferences import OPTIONAL_FEATURES
        entry = OPTIONAL_FEATURES["scheduled_tests_enabled"]
        assert "description" in entry
        assert "prompt" in entry
        assert "default" in entry

    def test_port_registry_default_true(self):
        """Port registry should default to enabled."""
        from aec.lib.preferences import OPTIONAL_FEATURES
        assert OPTIONAL_FEATURES["port_registry_enabled"]["default"] is True

    def test_scheduled_tests_default_false(self):
        """Scheduled tests should default to disabled."""
        from aec.lib.preferences import OPTIONAL_FEATURES
        assert OPTIONAL_FEATURES["scheduled_tests_enabled"]["default"] is False
