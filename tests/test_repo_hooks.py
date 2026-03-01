"""Tests for lint hook setup during aec repo setup."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSetupLintHooks:
    """Test _setup_lint_hooks function in repo setup."""

    def _setup_project(self, temp_dir, languages=None):
        """Helper: create a project dir with optional language files."""
        project = temp_dir / "my-project"
        project.mkdir()
        if languages:
            for lang_file in languages:
                (project / lang_file).write_text("{}")
        return project

    def test_creates_claude_hooks_for_typescript(self, temp_dir, monkeypatch):
        """Should create .claude/settings.json with tsc hook."""
        project = self._setup_project(temp_dir, ["tsconfig.json"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "auto")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "claude": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        config = project / ".claude" / "settings.json"
        assert config.exists()
        data = json.loads(config.read_text())
        assert "tsc" in data["hooks"]["PostToolUse"][0]["hooks"][0]["command"]

    def test_creates_gemini_hooks(self, temp_dir, monkeypatch):
        """Should create .gemini/settings.json with hook config."""
        project = self._setup_project(temp_dir, ["Cargo.toml"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "auto")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "gemini": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        config = project / ".gemini" / "settings.json"
        assert config.exists()
        data = json.loads(config.read_text())
        assert data["tools"]["enableHooks"] is True

    def test_creates_cursor_hooks(self, temp_dir, monkeypatch):
        """Should create .cursor/hooks.json with hook config."""
        project = self._setup_project(temp_dir, ["tsconfig.json"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "auto")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "cursor": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        config = project / ".cursor" / "hooks.json"
        assert config.exists()

    def test_skips_when_hook_mode_never(self, temp_dir, monkeypatch):
        """Should not create any hook files when hook_mode is never."""
        project = self._setup_project(temp_dir, ["tsconfig.json"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "never")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "claude": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        assert not (project / ".claude" / "settings.json").exists()

    def test_skips_when_no_languages_detected(self, temp_dir, monkeypatch):
        """Should not create hooks when no languages detected."""
        project = self._setup_project(temp_dir)
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "auto")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "claude": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        assert not (project / ".claude" / "settings.json").exists()

    def test_skips_agent_without_hook_support(self, temp_dir, monkeypatch):
        """Should not create hooks for agents without supports_hooks."""
        project = self._setup_project(temp_dir, ["tsconfig.json"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "auto")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "codex": {"supports_hooks": False},
        }):
            _setup_lint_hooks(project)

        assert not (project / ".codex").exists()

    def test_multi_language_multi_agent(self, temp_dir, monkeypatch):
        """Should create hooks for all detected agents with all selected languages."""
        project = self._setup_project(temp_dir, ["tsconfig.json", "pyproject.toml"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "auto")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "claude": {"supports_hooks": True},
            "cursor": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        claude_data = json.loads((project / ".claude" / "settings.json").read_text())
        claude_hooks = claude_data["hooks"]["PostToolUse"][0]["hooks"]
        assert len(claude_hooks) == 2

        cursor_data = json.loads((project / ".cursor" / "hooks.json").read_text())
        cursor_hooks = cursor_data["hooks"]["afterFileEdit"]
        assert len(cursor_hooks) == 2

    def test_per_repo_mode_prompts_user_all(self, temp_dir, monkeypatch):
        """In per-repo mode, selecting all should install hooks."""
        project = self._setup_project(temp_dir, ["tsconfig.json"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "per-repo")

        # "2" = All detected (1 language + All option is 2, None is 3)
        monkeypatch.setattr("builtins.input", lambda _: "2")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "claude": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        assert (project / ".claude" / "settings.json").exists()

    def test_per_repo_mode_user_selects_none(self, temp_dir, monkeypatch):
        """In per-repo mode, selecting none should not create hooks."""
        project = self._setup_project(temp_dir, ["tsconfig.json"])
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        from aec.lib.preferences import set_setting
        set_setting("hook_mode", "per-repo")

        # "3" = None (1 language, 2 = All, 3 = None)
        monkeypatch.setattr("builtins.input", lambda _: "3")

        from aec.commands.repo import _setup_lint_hooks
        with patch("aec.commands.repo.detect_agents", return_value={
            "claude": {"supports_hooks": True},
        }):
            _setup_lint_hooks(project)

        assert not (project / ".claude" / "settings.json").exists()
