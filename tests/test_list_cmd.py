"""Tests for aec list command."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def list_env(temp_dir, monkeypatch):
    """Set up a fake home with manifest and setup log for list command tests."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    manifest = {
        "manifestVersion": 2,
        "installedAt": "2026-04-01T00:00:00Z",
        "updatedAt": "2026-04-01T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {
            "skills": {
                "skill-a": {"version": "1.0.0", "contentHash": "", "installedAt": ""},
                "skill-b": {"version": "2.0.0", "contentHash": "", "installedAt": ""},
            },
            "rules": {
                "typescript/typing-standards": {"version": "1.0.0", "contentHash": "", "installedAt": ""},
            },
            "agents": {},
        },
        "repos": {},
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    # Monkeypatch the INSTALLED_MANIFEST_V2 used by list_cmd
    import aec.commands.list_cmd as list_mod
    monkeypatch.setattr(list_mod, "INSTALLED_MANIFEST_V2", manifest_path)

    return aec_home


@pytest.fixture
def list_env_with_repo(temp_dir, monkeypatch):
    """Set up environment with a tracked repo containing local installs."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    # Create a fake tracked repo
    repo = temp_dir / "my-project"
    repo.mkdir()
    (repo / ".claude").mkdir()

    repo_key = str(repo.resolve())

    # Write setup log with the repo
    (aec_home / "setup-repo-locations.txt").write_text(
        f"2026-04-01T00:00:00Z|2.0.0|{repo.resolve()}\n"
    )

    manifest = {
        "manifestVersion": 2,
        "installedAt": "2026-04-01T00:00:00Z",
        "updatedAt": "2026-04-01T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {
            "skills": {"skill-a": {"version": "1.0.0", "contentHash": "", "installedAt": ""}},
            "rules": {},
            "agents": {},
        },
        "repos": {
            repo_key: {
                "skills": {"local-skill": {"version": "0.5.0", "contentHash": "", "installedAt": ""}},
                "rules": {"local-rule": {"version": "0.1.0", "contentHash": "", "installedAt": ""}},
                "agents": {},
            }
        },
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    import aec.commands.list_cmd as list_mod
    monkeypatch.setattr(list_mod, "INSTALLED_MANIFEST_V2", manifest_path)

    # Monkeypatch cwd to be inside the repo so find_tracked_repo works
    monkeypatch.chdir(repo)

    return {"aec_home": aec_home, "repo": repo}


class TestListGlobal:
    def test_shows_global_items(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "skill-a" in output
        assert "skill-b" in output
        assert "typescript/typing-standards" in output

    def test_shows_versions(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "v1.0.0" in output
        assert "v2.0.0" in output

    def test_shows_tracked_repos_count(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "Tracked repos: 0" in output


class TestListTypeFilter:
    def test_filters_by_type_singular(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list(type_filter="skill")
        output = capsys.readouterr().out
        assert "skill-a" in output
        assert "skill-b" in output
        assert "typescript/typing-standards" not in output

    def test_filters_by_type_plural(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list(type_filter="rules")
        output = capsys.readouterr().out
        assert "typescript/typing-standards" in output
        assert "skill-a" not in output

    def test_shows_none_for_empty_type(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list(type_filter="agent")
        output = capsys.readouterr().out
        assert "(none)" in output


class TestListScopeFilter:
    def test_scope_global_only(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list(scope_filter="global")
        output = capsys.readouterr().out
        assert "Global:" in output
        assert "skill-a" in output

    def test_scope_local_shows_nothing_outside_repo(self, list_env, capsys):
        """When not in a tracked repo and scope=local, no local section appears."""
        from aec.commands.list_cmd import run_list
        run_list(scope_filter="local")
        output = capsys.readouterr().out
        # Global section should not appear when filtering for local
        assert "Global:" not in output


class TestListWithRepo:
    def test_shows_local_items(self, list_env_with_repo, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "local-skill" in output
        assert "local-rule" in output

    def test_shows_both_global_and_local(self, list_env_with_repo, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "Global:" in output
        assert "Local" in output
        assert "skill-a" in output
        assert "local-skill" in output

    def test_tracked_repos_count_with_repo(self, list_env_with_repo, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "Tracked repos: 1" in output


class TestListAll:
    def test_all_flag_shows_other_repos(self, list_env_with_repo, temp_dir, monkeypatch):
        """--all shows repos beyond the current local one."""
        # Add a second repo to setup log and manifest
        repo2 = temp_dir / "other-project"
        repo2.mkdir()
        (repo2 / ".claude").mkdir()

        aec_home = list_env_with_repo["aec_home"]
        repo1 = list_env_with_repo["repo"]

        # Rewrite setup log with both repos
        (aec_home / "setup-repo-locations.txt").write_text(
            f"2026-04-01T00:00:00Z|2.0.0|{repo1.resolve()}\n"
            f"2026-04-01T00:00:00Z|2.0.0|{repo2.resolve()}\n"
        )

        # Update manifest with second repo
        manifest_path = aec_home / "installed-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        repo2_key = str(repo2.resolve())
        manifest["repos"][repo2_key] = {
            "skills": {"other-skill": {"version": "3.0.0", "contentHash": "", "installedAt": ""}},
            "rules": {},
            "agents": {},
        }
        manifest_path.write_text(json.dumps(manifest))

        import aec.commands.list_cmd as list_mod
        monkeypatch.setattr(list_mod, "INSTALLED_MANIFEST_V2", manifest_path)

        from aec.commands.list_cmd import run_list
        import io, sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            run_list(show_all=True)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        assert "other-skill" in output
        assert "Tracked repos: 2" in output
