# tests/test_config_cmd.py
"""Tests for aec config command."""

import pytest
from pathlib import Path


@pytest.fixture
def config_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    return aec_home


class TestConfig:
    def test_list_does_not_crash(self, config_env, capsys):
        from aec.commands.config_cmd import run_config_list
        run_config_list()
        # Should complete without error

    def test_functions_are_importable(self):
        from aec.commands.config_cmd import run_config_list, run_config_set, run_config_reset
        assert callable(run_config_list)
        assert callable(run_config_set)
        assert callable(run_config_reset)


@pytest.fixture
def prefs_env(temp_dir, monkeypatch):
    """Isolate preferences storage to a temp file."""
    monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
    monkeypatch.setattr(
        "aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json"
    )
    return temp_dir


class TestPluginsExecutionSetting:
    def test_set_persists_string_value(self, prefs_env):
        from aec.commands.preferences import set_pref
        from aec.lib.preferences import get_setting

        set_pref("plugins.execution", "instructions-only")
        assert get_setting("plugins.execution") == "instructions-only"

    def test_invalid_value_exits_nonzero(self, prefs_env):
        from aec.commands.preferences import set_pref
        from aec.lib.preferences import get_setting

        with pytest.raises(SystemExit):
            set_pref("plugins.execution", "bogus")
        assert get_setting("plugins.execution") is None

    def test_reset_returns_to_default(self, prefs_env):
        from aec.commands.preferences import set_pref, reset_pref
        from aec.lib.preferences import get_setting

        set_pref("plugins.execution", "instructions-only")
        reset_pref("plugins.execution")
        value = get_setting("plugins.execution")
        assert value in (None, "default")

    def test_list_shows_string_setting(self, prefs_env, capsys):
        from aec.commands.preferences import list_preferences, set_pref

        # Unset shows "default"
        list_preferences()
        out = capsys.readouterr().out
        assert "plugins.execution" in out
        assert "default" in out

        # Set value is rendered
        set_pref("plugins.execution", "instructions-only")
        list_preferences()
        out = capsys.readouterr().out
        assert "instructions-only" in out
