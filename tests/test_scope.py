"""Tests for scope resolution."""

import pytest
from pathlib import Path


@pytest.fixture
def tracked_repo(temp_dir, monkeypatch):
    # Resolve to handle macOS /var -> /private/var symlink
    base = temp_dir.resolve()
    repo = base / "projects" / "my-app"
    repo.mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / ".agent-rules").mkdir()
    aec_home = base / ".agents-environment-config"
    aec_home.mkdir()
    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{repo}\n")
    monkeypatch.setattr(Path, "home", lambda: base)
    return repo


@pytest.fixture
def untracked_dir(temp_dir, monkeypatch):
    base = temp_dir.resolve()
    d = base / "random"
    d.mkdir()
    aec_home = base / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")
    monkeypatch.setattr(Path, "home", lambda: base)
    return d


class TestResolveScope:
    def test_local_scope_in_tracked_repo(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(tracked_repo)
        scope = resolve_scope(global_flag=False)
        assert scope.is_local
        assert scope.repo_path == tracked_repo

    def test_global_scope_with_flag(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(tracked_repo)
        scope = resolve_scope(global_flag=True)
        assert scope.is_global
        assert scope.repo_path is None

    def test_error_when_not_in_repo_without_flag(self, untracked_dir, monkeypatch):
        from aec.lib.scope import resolve_scope, ScopeError
        monkeypatch.chdir(untracked_dir)
        with pytest.raises(ScopeError, match="Not in a tracked repo"):
            resolve_scope(global_flag=False)

    def test_global_scope_when_not_in_repo_with_flag(self, untracked_dir, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(untracked_dir)
        scope = resolve_scope(global_flag=True)
        assert scope.is_global

    def test_detects_repo_from_subdirectory(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        subdir = tracked_repo / "src" / "lib"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        scope = resolve_scope(global_flag=False)
        assert scope.is_local
        assert scope.repo_path == tracked_repo


class TestFindTrackedRepo:
    def test_returns_none_for_untracked(self, untracked_dir, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        monkeypatch.chdir(untracked_dir)
        assert find_tracked_repo() is None

    def test_returns_repo_path(self, tracked_repo, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        monkeypatch.chdir(tracked_repo)
        assert find_tracked_repo() == tracked_repo


    def test_finds_repo_with_only_aec_json(self, temp_dir, monkeypatch):
        """Repos created by aec setup may only have .aec.json, not .claude/ or .agent-rules/."""
        from aec.lib.scope import find_tracked_repo
        base = temp_dir.resolve()
        repo = base / "projects" / "aec-json-only"
        repo.mkdir(parents=True)
        (repo / ".aec.json").write_text('{"version": "1.0.0"}')
        aec_home = base / ".agents-environment-config"
        aec_home.mkdir(exist_ok=True)
        log = aec_home / "setup-repo-locations.txt"
        log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{repo}\n")
        monkeypatch.setattr(Path, "home", lambda: base)
        monkeypatch.chdir(repo)
        assert find_tracked_repo() == repo


class TestGetAllTrackedRepos:
    def test_returns_existing_repos(self, tracked_repo):
        from aec.lib.scope import get_all_tracked_repos
        repos = get_all_tracked_repos()
        assert tracked_repo in repos

    def test_excludes_nonexistent_paths(self, temp_dir, monkeypatch):
        from aec.lib.scope import get_all_tracked_repos
        base = temp_dir.resolve()
        aec_home = base / ".agents-environment-config"
        aec_home.mkdir(exist_ok=True)
        log = aec_home / "setup-repo-locations.txt"
        log.write_text("2026-04-04T00:00:00Z|2.5.4|/nonexistent/path\n")
        monkeypatch.setattr(Path, "home", lambda: base)
        repos = get_all_tracked_repos()
        assert repos == []

    def test_empty_log_returns_empty(self, untracked_dir):
        from aec.lib.scope import get_all_tracked_repos
        repos = get_all_tracked_repos()
        assert repos == []


class TestScopeTargetPaths:
    def test_global_skill_path(self, temp_dir, monkeypatch):
        from aec.lib.scope import resolve_scope
        base = temp_dir.resolve()
        monkeypatch.setattr(Path, "home", lambda: base)
        scope = resolve_scope(global_flag=True)
        assert scope.skills_dir == base / ".claude" / "skills"
        assert scope.agents_dir == base / ".claude" / "agents"

    def test_global_rules_path(self, temp_dir, monkeypatch):
        from aec.lib.scope import resolve_scope
        base = temp_dir.resolve()
        monkeypatch.setattr(Path, "home", lambda: base)
        scope = resolve_scope(global_flag=True)
        assert scope.rules_dir == base / ".agent-tools" / "rules"

    def test_local_skill_path(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(tracked_repo)
        scope = resolve_scope(global_flag=False)
        assert scope.skills_dir == tracked_repo / ".claude" / "skills"
        assert scope.agents_dir == tracked_repo / ".claude" / "agents"
        assert scope.rules_dir == tracked_repo / ".agent-rules"


def _git(*args, cwd):
    import subprocess
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def tracked_git_repo(tracked_repo):
    """tracked_repo as a real git repo with a worktree at .worktrees/topic."""
    _git("init", "-q", "-b", "main", cwd=tracked_repo)
    (tracked_repo / ".claude" / "keep").write_text("")
    _git("add", ".", cwd=tracked_repo)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", cwd=tracked_repo)
    _git("worktree", "add", "-q", ".worktrees/topic", "-b", "topic", cwd=tracked_repo)
    return tracked_repo


class TestWorktrees:
    def test_worktree_of_tracked_repo_is_its_own_target(self, tracked_git_repo, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        wt = tracked_git_repo / ".worktrees" / "topic"
        (wt / "src").mkdir()
        monkeypatch.chdir(wt / "src")
        assert find_tracked_repo() == wt

    def test_marker_free_worktree_of_tracked_repo_is_tracked(self, tracked_git_repo, monkeypatch):
        import shutil
        from aec.lib.scope import find_tracked_repo
        wt = tracked_git_repo / ".worktrees" / "topic"
        shutil.rmtree(wt / ".claude")  # markers gitignored in the main checkout
        monkeypatch.chdir(wt)
        assert find_tracked_repo() == wt

    def test_directly_tracked_worktree_is_tracked(self, tracked_repo, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        other = tracked_repo.parent / "other"
        other.mkdir()
        (other / "f").write_text("")
        _git("init", "-q", "-b", "main", cwd=other)
        _git("add", ".", cwd=other)
        _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", cwd=other)
        wt = tracked_repo.parent / "other-wt"
        _git("worktree", "add", "-q", str(wt), "-b", "wt", cwd=other)
        log = Path.home() / ".agents-environment-config" / "setup-repo-locations.txt"
        log.write_text(log.read_text() + f"2026-04-04T00:00:00Z|2.5.4|{wt}\n")
        monkeypatch.chdir(wt)
        assert find_tracked_repo() == wt

    def test_worktree_of_untracked_repo_never_resolves_to_its_parent(self, tracked_repo, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        other = tracked_repo / "vendor" / "other"
        other.mkdir(parents=True)
        (other / ".claude").mkdir()
        (other / ".claude" / "keep").write_text("")
        _git("init", "-q", "-b", "main", cwd=other)
        _git("add", ".", cwd=other)
        _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", cwd=other)
        _git("worktree", "add", "-q", str(tracked_repo / "wt"), "-b", "wt", cwd=other)
        monkeypatch.chdir(tracked_repo / "wt")
        assert find_tracked_repo() is None

    def test_submodule_still_resolves_to_parent_repo(self, tracked_repo, monkeypatch):
        from aec.lib.scope import find_tracked_repo, main_checkout
        sub = tracked_repo / ".claude" / "skills"
        sub.mkdir()
        (sub / ".git").write_text("gitdir: ../../.git/modules/skills\n")  # no commondir
        assert main_checkout(sub) == sub
        monkeypatch.chdir(sub)
        assert find_tracked_repo() == tracked_repo

    def test_worktree_of_catalog_is_catalog(self, tracked_git_repo):
        from unittest.mock import patch
        from aec.lib.scope import is_catalog_repo
        wt = tracked_git_repo / ".worktrees" / "topic"
        with patch("aec.lib.config.get_repo_root", return_value=tracked_git_repo):
            assert is_catalog_repo(wt)
            assert is_catalog_repo(tracked_git_repo)
        with patch("aec.lib.config.get_repo_root", return_value=wt):
            assert is_catalog_repo(tracked_git_repo)
