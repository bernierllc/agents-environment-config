"""Tests for aec update command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def aec_env(temp_dir, monkeypatch):
    """Set up a fake AEC environment with a repo, manifest, and skill source."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    # AEC home directory with setup log
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    # Fake AEC repo with a skill source at version 2.0.0
    repo = temp_dir / "aec-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    skills = repo / ".claude" / "skills"
    skills.mkdir(parents=True)
    skill_dir = skills / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 2.0.0\ndescription: A test\nauthor: Test\n---\n"
    )

    # Manifest with skill installed at version 1.0.0
    manifest_path = aec_home / "installed-manifest.json"
    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {
            "skills": {
                "test-skill": {
                    "version": "1.0.0",
                    "contentHash": "",
                    "installedAt": "2026-04-04T00:00:00Z",
                }
            },
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    manifest_path.write_text(json.dumps(manifest))

    return {"repo": repo, "aec_home": aec_home, "manifest_path": manifest_path}


def _patch_update(**overrides):
    """Return a list of patch context managers for update command dependencies.

    Always patches _get_manifest_path, get_repo_root, and fetch_latest.
    Pass keyword args to override defaults.
    """
    patches = {
        "fetch_latest": True,
        "get_repo_root": None,
        "find_tracked_repo": None,
        "get_all_tracked_repos": [],
    }
    patches.update(overrides)
    return patches


class TestUpdateCommand:
    @patch("aec.commands.update.find_tracked_repo", return_value=None)
    @patch("aec.commands.update.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.update.fetch_latest", return_value=True)
    @patch("aec.commands.update.get_repo_root")
    @patch("aec.commands.update.get_source_dirs")
    @patch("aec.commands.update._get_manifest_path")
    def test_reports_outdated_global_skills(
        self, mock_manifest_path, mock_source_dirs, mock_root, mock_fetch,
        mock_all_repos, mock_find_repo, aec_env, capsys
    ):
        from aec.commands.update import run_update

        mock_root.return_value = aec_env["repo"]
        mock_manifest_path.return_value = aec_env["manifest_path"]
        mock_source_dirs.return_value = {
            "skills": aec_env["repo"] / ".claude" / "skills",
            "rules": aec_env["repo"] / ".agent-rules",
            "agents": aec_env["repo"] / ".claude" / "agents",
        }

        run_update()
        output = capsys.readouterr().out
        assert "test-skill" in output
        assert "1.0.0" in output
        assert "2.0.0" in output
        assert "upgrade" in output.lower()

    @patch("aec.commands.update.fetch_latest", return_value=False)
    @patch("aec.commands.update.get_repo_root")
    def test_handles_fetch_failure(self, mock_root, mock_fetch, aec_env, capsys):
        from aec.commands.update import run_update

        mock_root.return_value = aec_env["repo"]
        run_update()
        output = capsys.readouterr().out
        assert "fail" in output.lower()

    @patch("aec.commands.update.find_tracked_repo", return_value=None)
    @patch("aec.commands.update.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.update.fetch_latest", return_value=True)
    @patch("aec.commands.update.get_repo_root")
    @patch("aec.commands.update.get_source_dirs")
    @patch("aec.commands.update._get_manifest_path")
    def test_reports_up_to_date_when_versions_match(
        self, mock_manifest_path, mock_source_dirs, mock_root, mock_fetch,
        mock_all_repos, mock_find_repo, aec_env, capsys
    ):
        from aec.commands.update import run_update

        mock_root.return_value = aec_env["repo"]
        mock_manifest_path.return_value = aec_env["manifest_path"]
        mock_source_dirs.return_value = {
            "skills": aec_env["repo"] / ".claude" / "skills",
            "rules": aec_env["repo"] / ".agent-rules",
            "agents": aec_env["repo"] / ".claude" / "agents",
        }

        # Update manifest so installed version matches source version
        m = json.loads(aec_env["manifest_path"].read_text())
        m["global"]["skills"]["test-skill"]["version"] = "2.0.0"
        aec_env["manifest_path"].write_text(json.dumps(m))

        run_update()
        output = capsys.readouterr().out
        assert "up to date" in output.lower()
        assert "test-skill" not in output

    @patch("aec.commands.update.get_repo_root", return_value=None)
    def test_handles_missing_repo(self, mock_root, capsys):
        from aec.commands.update import run_update

        run_update()
        output = capsys.readouterr().out
        assert "not found" in output.lower() or "setup" in output.lower()

    @patch("aec.commands.update.find_tracked_repo", return_value=None)
    @patch("aec.commands.update.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.update.fetch_latest", return_value=True)
    @patch("aec.commands.update.get_repo_root")
    @patch("aec.commands.update.get_source_dirs")
    @patch("aec.commands.update._get_manifest_path")
    def test_records_update_check_timestamp(
        self, mock_manifest_path, mock_source_dirs, mock_root, mock_fetch,
        mock_all_repos, mock_find_repo, aec_env, capsys
    ):
        from aec.commands.update import run_update

        mock_root.return_value = aec_env["repo"]
        mock_manifest_path.return_value = aec_env["manifest_path"]
        mock_source_dirs.return_value = {
            "skills": aec_env["repo"] / ".claude" / "skills",
            "rules": aec_env["repo"] / ".agent-rules",
            "agents": aec_env["repo"] / ".claude" / "agents",
        }

        run_update()

        # Verify that lastUpdateCheck was set in the saved manifest
        updated = json.loads(aec_env["manifest_path"].read_text())
        assert updated["lastUpdateCheck"] is not None

    @patch("aec.commands.update.find_tracked_repo")
    @patch("aec.commands.update.get_all_tracked_repos")
    @patch("aec.commands.update.fetch_latest", return_value=True)
    @patch("aec.commands.update.get_repo_root")
    @patch("aec.commands.update.get_source_dirs")
    @patch("aec.commands.update._get_manifest_path")
    def test_mentions_other_tracked_repos(
        self, mock_manifest_path, mock_source_dirs, mock_root, mock_fetch,
        mock_all_repos, mock_find_repo, aec_env, capsys
    ):
        from aec.commands.update import run_update

        mock_root.return_value = aec_env["repo"]
        mock_manifest_path.return_value = aec_env["manifest_path"]
        mock_source_dirs.return_value = {
            "skills": aec_env["repo"] / ".claude" / "skills",
            "rules": aec_env["repo"] / ".agent-rules",
            "agents": aec_env["repo"] / ".claude" / "agents",
        }
        mock_find_repo.return_value = None
        mock_all_repos.return_value = [Path("/fake/repo1"), Path("/fake/repo2")]

        run_update()
        output = capsys.readouterr().out
        assert "2 other tracked repo(s)" in output
        assert "outdated" in output.lower()
