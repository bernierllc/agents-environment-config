"""Tests for install settings prompts."""

import json
from pathlib import Path

import pytest


class TestPromptSettings:
    """Test the settings prompt flow during install."""

    def test_prompts_for_all_settings(self, temp_dir, monkeypatch):
        """Should ask for all settings and store them."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter([
            "/Users/test/projects",  # projects_dir
            "1",                     # .plans/
            "n",                     # not tracked in git (= gitignored)
            "1",                     # archive
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("projects_dir") == "/Users/test/projects"
        assert get_setting("plans_dir") == ".plans"
        assert get_setting("plans_gitignored") is True
        assert get_setting("plans_completion") == "archive"

    def test_skips_when_already_set(self, temp_dir, monkeypatch):
        """Should not prompt when all settings already exist."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {
                "projects_dir": "/Users/test/projects",
                "plans_dir": ".plans",
                "plans_gitignored": True,
                "plans_completion": "archive",
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        def should_not_be_called(_):
            raise AssertionError("Should not prompt when settings exist")
        monkeypatch.setattr("builtins.input", should_not_be_called)

        from aec.commands.install import _prompt_settings
        _prompt_settings()  # Should not raise

    def test_default_projects_dir(self, temp_dir, monkeypatch):
        """Should use ~/projects as default when user presses Enter."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["", "1", "n", "1"])  # empty = accept default
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        result = get_setting("projects_dir")
        assert "projects" in result

    def test_plans_dir_option_2(self, temp_dir, monkeypatch):
        """Should set plans/ when user picks option 2."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "2", "y", "2"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "plans"
        assert get_setting("plans_gitignored") is False  # tracked = not gitignored
        assert get_setting("plans_completion") == "delete"

    def test_handles_eof(self, temp_dir, monkeypatch):
        """Should use defaults when input raises EOFError (non-interactive)."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("projects_dir") is not None
        assert get_setting("plans_dir") == ".plans"
        assert get_setting("plans_gitignored") is True  # default: not tracked
        assert get_setting("plans_completion") == "archive"

    def test_plans_dir_custom_option_3(self, temp_dir, monkeypatch):
        """Should prompt for custom name when user picks option 3."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "3", "docs", "n", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "docs"

    def test_plans_dir_direct_name(self, temp_dir, monkeypatch):
        """Should accept a direct name typed instead of 1/2/3."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "my-plans", "n", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "my-plans"

    def test_plans_gitignored_yes_means_tracked(self, temp_dir, monkeypatch):
        """Should set plans_gitignored=False when user says yes to tracking."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "1", "yes", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_gitignored") is False


class TestFindProjects:
    """Test _find_projects directory scanning."""

    def test_finds_git_dirs_only(self, temp_dir):
        """When git_only=True, should only return dirs with .git."""
        projects = temp_dir / "projects"
        projects.mkdir()

        git_project = projects / "my-app"
        git_project.mkdir()
        (git_project / ".git").mkdir()

        other_dir = projects / "notes"
        other_dir.mkdir()

        from aec.commands.install import _find_projects
        result = _find_projects(projects, git_only=True)

        assert git_project in result
        assert other_dir not in result

    def test_finds_all_dirs(self, temp_dir):
        """When git_only=False, should return all subdirectories."""
        projects = temp_dir / "projects"
        projects.mkdir()

        (projects / "my-app").mkdir()
        (projects / "notes").mkdir()

        from aec.commands.install import _find_projects
        result = _find_projects(projects, git_only=False)

        assert len(result) == 2

    def test_skips_hidden_dirs(self, temp_dir):
        """Should skip directories starting with a dot."""
        projects = temp_dir / "projects"
        projects.mkdir()

        (projects / ".hidden").mkdir()
        visible = projects / "visible"
        visible.mkdir()

        from aec.commands.install import _find_projects
        result = _find_projects(projects, git_only=False)

        assert len(result) == 1
        assert visible in result

    def test_skips_files(self, temp_dir):
        """Should skip regular files."""
        projects = temp_dir / "projects"
        projects.mkdir()

        (projects / "README.md").write_text("hi")
        proj = projects / "my-app"
        proj.mkdir()

        from aec.commands.install import _find_projects
        result = _find_projects(projects, git_only=False)

        assert len(result) == 1

    def test_returns_sorted(self, temp_dir):
        """Should return results sorted alphabetically."""
        projects = temp_dir / "projects"
        projects.mkdir()

        (projects / "zebra").mkdir()
        (projects / "alpha").mkdir()
        (projects / "middle").mkdir()

        from aec.commands.install import _find_projects
        result = _find_projects(projects, git_only=False)

        assert result == [projects / "alpha", projects / "middle", projects / "zebra"]

    def test_nonexistent_dir(self):
        """Should return empty list for nonexistent directory."""
        from aec.commands.install import _find_projects
        result = _find_projects(Path("/nonexistent/path"), git_only=False)
        assert result == []
