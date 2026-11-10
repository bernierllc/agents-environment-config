"""Pipeline post-install copies hook templates without tripping on subdirectories."""

from dataclasses import dataclass
from pathlib import Path

from aec.commands.install_cmd import _post_install_playwright_pipeline


@dataclass
class FakeScope:
    repo_path: Path
    skills_dir: Path
    is_global: bool = False


def test_hook_templates_with_tests_subdir_install(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs" / "verification").mkdir(parents=True)
    (repo / ".git" / "hooks").mkdir(parents=True)
    skills = tmp_path / "skills"
    hooks = skills / "playwright-test-generator" / "templates" / "hooks"
    (hooks / "__tests__").mkdir(parents=True)
    (hooks / "__tests__" / "pre-commit.test.sh").write_text("#!/bin/sh\n")
    (hooks / "pre-commit.sh").write_text("#!/bin/sh\n")
    (hooks / "pre-push.sh").write_text("#!/bin/sh\n")
    (skills / "playwright-test-generator" / "scripts").mkdir()

    _post_install_playwright_pipeline(
        "playwright-test-generator", FakeScope(repo, skills), yes=True
    )

    dst = repo / "scripts" / "verification-playwright" / "hooks"
    assert sorted(p.name for p in dst.iterdir()) == ["pre-commit.sh", "pre-push.sh"]
    assert (repo / ".git" / "hooks" / "pre-push").exists()
