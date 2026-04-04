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
