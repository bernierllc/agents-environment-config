"""Tests for aec.lib.git_setup orchestration."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent


class TestBuildCompositeGitignore:
    def test_aec_section_always_present(self, tmp_path):
        from aec.lib.git_setup import build_composite_gitignore
        result = build_composite_gitignore([], [], tmp_path)
        assert "# AEC" in result

    def test_falls_back_gracefully_when_submodule_missing(self, tmp_path):
        from aec.lib.git_setup import build_composite_gitignore
        result = build_composite_gitignore(["python"], [], tmp_path)
        assert "# AEC" in result
        assert result  # non-empty

    def test_deduplicates_lines(self):
        """When two languages share templates, lines must not be duplicated."""
        templates_dir = REPO_ROOT / "aec" / "templates"
        if not (templates_dir / "gitignore" / "Python.gitignore").exists():
            pytest.skip("gitignore submodule not initialized")
        from aec.lib.git_setup import build_composite_gitignore
        result = build_composite_gitignore(["typescript"], ["jest"], templates_dir)
        lines = [l for l in result.splitlines() if l and not l.startswith("#")]
        assert len(lines) == len(set(lines)), "non-comment lines must be deduplicated"


class TestWriteGitEssentials:
    def test_creates_readme_from_template(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "README.md", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "README.md").read_text()

    def test_creates_github_dir_structure(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "dependabot", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / ".github" / "dependabot.yml").exists()

    def test_creates_issue_template_dir(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "issue_templates", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / ".github" / "ISSUE_TEMPLATE").is_dir()

    def test_does_not_overwrite_existing_file(self, tmp_path):
        existing_content = "# My existing README\n"
        (tmp_path / "README.md").write_text(existing_content)
        from aec.lib.git_setup import write_git_essential
        write_git_essential(tmp_path, "README.md", "github", REPO_ROOT / "aec" / "templates")
        assert (tmp_path / "README.md").read_text() == existing_content


class TestExecuteCommitStrategy:
    def _make_git_repo(self, tmp_path):
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

    def test_one_commit_strategy_creates_single_commit(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        (repo / ".gitignore").write_text("*.pyc")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md", ".gitignore"], strategy="one_commit")
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
        )
        assert len(log.stdout.strip().splitlines()) == 1

    def test_incremental_strategy_creates_one_commit_per_file(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        (repo / ".gitignore").write_text("*.pyc")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md", ".gitignore"], strategy="incremental")
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
        )
        assert len(log.stdout.strip().splitlines()) == 2

    def test_stage_only_strategy_stages_but_does_not_commit(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md"], strategy="stage_only")
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
        )
        assert "A  README.md" in status.stdout
        log = subprocess.run(
            ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
        )
        assert log.stdout.strip() == ""

    def test_none_strategy_makes_no_git_changes(self, tmp_path):
        repo = self._make_git_repo(tmp_path)
        (repo / "README.md").write_text("# Test")
        from aec.lib.git_setup import execute_commit_strategy
        execute_commit_strategy(repo, ["README.md"], strategy="none")
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
        )
        assert "README.md" in status.stdout
        assert status.stdout.startswith("??"), "file should be untracked, not staged"
