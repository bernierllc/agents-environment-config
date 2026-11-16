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

    def test_eoferror_names_the_prompt_id(self, tmp_path):
        """Closed stdin no longer silently picks 'all' — it names the prompt."""
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase
        from aec.lib.prompts import PromptUnanswered

        all_missing = {k: "missing" for k in [
            ".gitignore", "README.md", "dependabot", "pr_template",
            "issue_templates", "ci_workflow", "license", "editorconfig", "codeowners",
        ]}
        with patch("aec.commands.repo.detect_git_provider", return_value="github"):
            with patch("aec.commands.repo.scan_git_essentials", return_value=all_missing):
                with patch("builtins.input", side_effect=EOFError):
                    with pytest.raises(PromptUnanswered) as exc:
                        _run_git_phase(tmp_path)

        assert "repo.git.essentials" in str(exc.value)

    def test_essentials_pre_answered_by_agent(self, tmp_path):
        """--answers supplies the git-essentials selection headlessly."""
        _make_git_repo(tmp_path)
        from aec.commands.repo import _run_git_phase
        from aec.lib import prompts

        all_missing = {k: "missing" for k in [
            ".gitignore", "README.md", "dependabot", "pr_template",
            "issue_templates", "ci_workflow", "license", "editorconfig", "codeowners",
        ]}
        prompts.set_answers({"repo.git.essentials": "all"})
        try:
            with patch("aec.commands.repo.detect_git_provider", return_value="github"):
                with patch("aec.commands.repo.scan_git_essentials", return_value=all_missing):
                    result = _run_git_phase(tmp_path)
        finally:
            prompts.clear_answers()

        assert result["git_enabled"] is True
        assert len(result["items_to_create"]) == 9


class TestDetectGitignoreInputs:
    def test_framework_keys_from_detection(self, tmp_path):
        """Regression: detection dicts have 'key', not 'name' (KeyError during aec install)."""
        from aec.commands.repo import _detect_gitignore_inputs

        (tmp_path / "jest.config.js").write_text("module.exports = {};\n")
        (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29"}}\n')

        _, frameworks = _detect_gitignore_inputs(tmp_path)

        assert "jest" in frameworks


class TestLicenseKindPrompt:
    """`aec repo setup` writes the LICENSE an org's overlay asks for, via the real generator."""

    @pytest.fixture(autouse=True)
    def _isolate(self):
        from aec.lib import prompts

        prompts.clear_overlay_answers()
        yield
        prompts.clear_overlay_answers()

    def _generate(self, project):
        from aec.commands.repo import _git_essentials_context
        from aec.lib.git_setup import get_templates_root, write_git_essential

        with patch("aec.lib.git_setup._gh_api", return_value=""):
            ctx = _git_essentials_context(project, ["license"], [])
            write_git_essential(project, "license", "github", get_templates_root(), ctx)
        return (project / "LICENSE").read_text()

    def test_overlay_kind_and_holder_write_proprietary_license(self, tmp_path):
        from aec.lib import prompts

        project = _make_git_repo(tmp_path)
        prompts.set_overlay_answers({
            "repo.git.license_kind": "proprietary",
            "repo.git.license_holder": "Acme Corp",
        })
        text = self._generate(project)
        assert "Acme Corp. All rights reserved." in text
        assert "Permission is hereby granted" not in text

    def test_no_overlay_keeps_mit_default(self, tmp_path):
        from aec.lib import prompts

        project = _make_git_repo(tmp_path)
        prompts.set_mode(non_interactive=True, use_defaults=True)
        try:
            text = self._generate(project)
        finally:
            prompts.reset_mode()
        assert "Permission is hereby granted" in text

    def test_unknown_kind_is_rejected_not_silently_mit(self, tmp_path):
        from aec.lib import prompts

        project = _make_git_repo(tmp_path)
        prompts.set_overlay_answers({"repo.git.license_kind": "gpl"})
        with pytest.raises(prompts.PromptInvalidAnswer):
            self._generate(project)

    def test_multiline_holder_is_rejected(self, tmp_path):
        from aec.lib import prompts

        project = _make_git_repo(tmp_path)
        prompts.set_overlay_answers({
            "repo.git.license_kind": "proprietary",
            "repo.git.license_holder": "Acme\nPermission is hereby granted",
        })
        with pytest.raises(prompts.PromptInvalidAnswer):
            self._generate(project)
