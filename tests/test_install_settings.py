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
            "1",                     # PRs ready for review
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

        inputs = iter(["", "1", "n", "1", "1"])  # empty = accept default
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

        inputs = iter(["/tmp/projects", "2", "y", "2", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "plans"
        assert get_setting("plans_gitignored") is False  # tracked = not gitignored
        assert get_setting("plans_completion") == "delete"

    def test_eof_raises_instead_of_silently_defaulting(self, temp_dir, monkeypatch):
        """No human and no supplied answer is an error, not a silent default."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)

        from aec.commands.install import _prompt_settings
        from aec.lib.prompts import PromptUnanswered

        with pytest.raises(PromptUnanswered):
            _prompt_settings()

    def test_defaults_flag_applies_declared_defaults(self, temp_dir, monkeypatch):
        """`--defaults` is the explicit opt-in to the old EOF behaviour."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)

        from aec.commands.install import _prompt_settings
        from aec.lib.prompts import reset_mode, set_mode

        set_mode(use_defaults=True)
        try:
            _prompt_settings()
        finally:
            reset_mode()

        from aec.lib.preferences import get_setting
        assert get_setting("projects_dir") is not None
        assert get_setting("plans_dir") == ".plans"
        assert get_setting("plans_gitignored") is True  # default: not tracked
        assert get_setting("plans_completion") == "archive"

    def test_plans_dir_custom_option_3(self, temp_dir, monkeypatch):
        """Should prompt for custom name when user picks option 3."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "3", "docs", "n", "1", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "docs"

    def test_plans_dir_off_menu_digit_reasks(self, temp_dir, monkeypatch):
        """A digit typo like '4' is re-asked, never saved as a directory."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "4", "2", "n", "1", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "plans"

    def test_plans_dir_direct_name(self, temp_dir, monkeypatch):
        """A directory name answered at the menu is accepted (org-config contract)."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "my-plans", "n", "1", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings()

        from aec.lib.preferences import get_setting
        assert get_setting("plans_dir") == "my-plans"

    @pytest.mark.parametrize("answer,expected", [
        ("1", "1"), ("dotplans", "1"), ("plans", "2"), ("CUSTOM", "3"), ("docs", "docs"),
    ])
    def test_plans_dir_answer_forms(self, answer, expected):
        from aec.commands.install import _plans_dir_answer
        assert _plans_dir_answer(answer) == expected

    @pytest.mark.parametrize("bad", ["4", "a/b", "..", "", "/abs"])
    def test_plans_dir_answer_rejects(self, bad):
        from aec.commands.install import _plans_dir_answer
        with pytest.raises(ValueError):
            _plans_dir_answer(bad)

    def test_plans_gitignored_yes_means_tracked(self, temp_dir, monkeypatch):
        """Should set plans_gitignored=False when user says yes to tracking."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        inputs = iter(["/tmp/projects", "1", "yes", "1", "1"])
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


class TestPrOpenModeSetting:
    def _run(self, temp_dir, monkeypatch, answer):
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        inputs = iter(["/tmp/projects", "1", "n", "1", answer])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        from aec.commands.install import _prompt_settings
        _prompt_settings()
        from aec.lib.preferences import get_setting
        return get_setting("pr_open_mode")

    def test_enter_means_ready(self, temp_dir, monkeypatch):
        assert self._run(temp_dir, monkeypatch, "") == "ready"

    def test_option_2_means_draft(self, temp_dir, monkeypatch):
        assert self._run(temp_dir, monkeypatch, "2") == "draft"

