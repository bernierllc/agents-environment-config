"""Tests for aec.lib.hooks.git_hooks_path — husky-aware hooks-dir resolution."""

import subprocess


def _git_init(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)


class TestResolveHooksDir:
    def test_default_repo_uses_git_hooks(self, tmp_path):
        from aec.lib.hooks.git_hooks_path import resolve_hooks_dir
        repo = tmp_path / "repo"
        _git_init(repo)
        r = resolve_hooks_dir(repo)
        assert r.hooks_dir == repo / ".git" / "hooks"
        assert r.husky_version is None
        assert r.needs_v8_bootstrap is False

    def test_husky_v8_layout(self, tmp_path):
        from aec.lib.hooks.git_hooks_path import resolve_hooks_dir
        repo = tmp_path / "repo"
        _git_init(repo)
        (repo / ".husky" / "_").mkdir(parents=True)
        (repo / ".husky" / "_" / "husky.sh").write_text("#!/bin/sh\n# husky v8\n")
        subprocess.run(
            ["git", "-C", str(repo), "config", "core.hooksPath", ".husky"],
            check=True,
        )
        r = resolve_hooks_dir(repo)
        assert r.hooks_dir == repo / ".husky"
        assert r.husky_version == "v8"
        assert r.needs_v8_bootstrap is True

    def test_husky_v9_layout(self, tmp_path):
        from aec.lib.hooks.git_hooks_path import resolve_hooks_dir
        repo = tmp_path / "repo"
        _git_init(repo)
        (repo / ".husky" / "_").mkdir(parents=True)
        (repo / ".husky" / "_" / "pre-commit").write_text("#!/usr/bin/env sh\n")
        (repo / ".husky" / "_" / "h").write_text("#!/usr/bin/env sh\n")
        subprocess.run(
            ["git", "-C", str(repo), "config", "core.hooksPath", ".husky/_"],
            check=True,
        )
        r = resolve_hooks_dir(repo)
        assert r.hooks_dir == repo / ".husky"
        assert r.husky_version == "v9"
        assert r.needs_v8_bootstrap is False

    def test_husky_dir_without_underscore_treated_as_v8(self, tmp_path):
        from aec.lib.hooks.git_hooks_path import resolve_hooks_dir
        repo = tmp_path / "repo"
        _git_init(repo)
        (repo / ".husky").mkdir()
        r = resolve_hooks_dir(repo)
        assert r.hooks_dir == repo / ".husky"
        assert r.husky_version == "v8"
        assert r.needs_v8_bootstrap is True

    def test_custom_core_hooks_path_non_husky(self, tmp_path):
        from aec.lib.hooks.git_hooks_path import resolve_hooks_dir
        repo = tmp_path / "repo"
        _git_init(repo)
        subprocess.run(
            ["git", "-C", str(repo), "config", "core.hooksPath", ".githooks"],
            check=True,
        )
        r = resolve_hooks_dir(repo)
        assert r.hooks_dir == repo / ".githooks"
        assert r.husky_version is None
        assert r.needs_v8_bootstrap is False

    def test_no_git_repo_falls_back_to_git_hooks(self, tmp_path):
        from aec.lib.hooks.git_hooks_path import resolve_hooks_dir
        repo = tmp_path / "repo"
        repo.mkdir()
        r = resolve_hooks_dir(repo)
        assert r.hooks_dir == repo / ".git" / "hooks"
        assert r.husky_version is None
