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


class TestMigratePlansDir:
    """Test legacy plans directory migration."""

    def test_migrates_plans_to_dotplans(self, temp_dir, monkeypatch):
        """Should move files from plans/ to .plans/ when setting is .plans."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        from aec.commands.repo import _migrate_plans_dir
        project = temp_dir / "myproject"
        project.mkdir()
        old_plans = project / "plans"
        old_plans.mkdir()
        (old_plans / "feature.md").write_text("# Feature Plan")
        _migrate_plans_dir(project)
        assert (project / ".plans" / "feature.md").exists()
        assert (project / ".plans" / "feature.md").read_text() == "# Feature Plan"
        assert not (project / "plans" / "feature.md").exists()

    def test_migrates_docs_plans(self, temp_dir, monkeypatch):
        """Should move files from docs/plans/ to chosen plans dir."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        from aec.commands.repo import _migrate_plans_dir
        project = temp_dir / "myproject"
        project.mkdir()
        docs_plans = project / "docs" / "plans"
        docs_plans.mkdir(parents=True)
        (docs_plans / "design.md").write_text("# Design")
        _migrate_plans_dir(project)
        assert (project / ".plans" / "design.md").exists()
        assert not (project / "docs" / "plans" / "design.md").exists()

    def test_noop_when_no_legacy_dirs(self, temp_dir, monkeypatch):
        """Should do nothing when no legacy plans directories exist."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        from aec.commands.repo import _migrate_plans_dir
        project = temp_dir / "myproject"
        project.mkdir()
        _migrate_plans_dir(project)  # Should not raise

    def test_noop_when_plans_dir_matches(self, temp_dir, monkeypatch):
        """Should not migrate when user chose plans/ (same as legacy)."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": "plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        from aec.commands.repo import _migrate_plans_dir
        project = temp_dir / "myproject"
        project.mkdir()
        old_plans = project / "plans"
        old_plans.mkdir()
        (old_plans / "feature.md").write_text("# Feature Plan")
        _migrate_plans_dir(project)
        assert (project / "plans" / "feature.md").exists()

    def test_skips_existing_files_in_target(self, temp_dir, monkeypatch):
        """Should not overwrite files that already exist in target."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        from aec.commands.repo import _migrate_plans_dir
        project = temp_dir / "myproject"
        project.mkdir()
        # Create legacy with a file
        old_plans = project / "plans"
        old_plans.mkdir()
        (old_plans / "feature.md").write_text("old version")
        # Create target with same filename
        new_plans = project / ".plans"
        new_plans.mkdir()
        (new_plans / "feature.md").write_text("new version")
        _migrate_plans_dir(project)
        # Should keep the target version
        assert (project / ".plans" / "feature.md").read_text() == "new version"
