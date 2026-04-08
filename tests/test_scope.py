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
