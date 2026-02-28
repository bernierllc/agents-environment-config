"""Tests for plans-dir-aware repo setup behavior."""

import json
import shutil
from pathlib import Path

import pytest


class TestCreateDirectoriesPlansDir:
    """Test _create_directories uses plans_dir setting."""

    def test_creates_default_plans_dir(self, temp_dir, monkeypatch):
        """Without setting, should create plans/ directory."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        from aec.commands.repo import _create_directories
        project = temp_dir / "myproject"
        project.mkdir()
        _create_directories(project)
        assert (project / "plans").is_dir()

    def test_creates_custom_plans_dir(self, temp_dir, monkeypatch):
        """With plans_dir='.plans', should create .plans/ directory."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        from aec.commands.repo import _create_directories
        project = temp_dir / "myproject"
        project.mkdir()
        _create_directories(project)
        assert (project / ".plans").is_dir()
        assert not (project / "plans").is_dir()
