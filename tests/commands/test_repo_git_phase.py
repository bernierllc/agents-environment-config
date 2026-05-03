"""Tests for _run_git_phase and _create_git_essentials in repo.py."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def _make_git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


class TestRunGitPhase:
    def test_returns_git_disabled_when_user_declines_github(self, tmp_path):
        from aec.commands.repo import _run_git_phase

        with patch("builtins.input", return_value="n"):
            result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is False
        assert result["provider"] is None
        assert result["items_to_create"] == []

    def test_returns_unknown_provider_with_git_disabled(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.commands.repo import _run_git_phase

        with patch("aec.commands.repo.detect_git_provider", return_value="unknown"):
            result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is False
        assert result["provider"] == "unknown"

    def test_git_init_failure_returns_git_disabled(self, tmp_path):
        from aec.commands.repo import _run_git_phase

        failed = MagicMock()
        failed.returncode = 1
        failed.stderr = "not a git repository"

        with patch("builtins.input", side_effect=["y", "y"]):
            with patch("subprocess.run", return_value=failed):
                result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is False

    def test_multi_select_parses_comma_separated_numbers(self, tmp_path):
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase

        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value={
                ".gitignore": "missing",
                "README.md": "missing",
                "dependabot": "missing",
                "pr_template": "found",
                "issue_templates": "found",
                "ci_workflow": "found",
                "license": "found",
                "editorconfig": "found",
                "codeowners": "found",
            }):
                with patch("builtins.input", return_value="1,2"):
                    result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is True
        assert ".gitignore" in result["items_to_create"]
        assert "README.md" in result["items_to_create"]
        assert len(result["items_to_create"]) == 2

    def test_multi_select_all_selects_everything_missing(self, tmp_path):
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase

        all_missing = {k: "missing" for k in [
            ".gitignore", "README.md", "dependabot", "pr_template",
            "issue_templates", "ci_workflow", "license", "editorconfig", "codeowners",
        ]}
        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value=all_missing):
                with patch("builtins.input", return_value="all"):
                    result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is True
        assert len(result["items_to_create"]) == 9

    def test_eoferror_on_input_defaults_to_all(self, tmp_path):
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase

        all_missing = {k: "missing" for k in [
            ".gitignore", "README.md", "dependabot", "pr_template",
            "issue_templates", "ci_workflow", "license", "editorconfig", "codeowners",
        ]}
        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value=all_missing):
                with patch("builtins.input", side_effect=EOFError):
                    result = _run_git_phase(tmp_path)

        assert result["git_enabled"] is True
        assert len(result["items_to_create"]) == 9
