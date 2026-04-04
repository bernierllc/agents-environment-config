"""Tests for aec upgrade command."""

import json
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def upgrade_env(temp_dir, monkeypatch):
    """Set up a fake AEC environment with source at v2.0.0, installed at v1.0.0."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    # Source skill (v2.0.0) in the AEC repo
    repo = temp_dir / "aec-repo"
    skills_src = repo / ".claude" / "skills" / "test-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 2.0.0\ndescription: Updated\nauthor: Test\n---\nNew content"
    )
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    (repo / ".claude" / "agents").mkdir(parents=True)

    # Installed skill (v1.0.0, global)
    installed = temp_dir / ".claude" / "skills" / "test-skill"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 1.0.0\ndescription: Old\nauthor: Test\n---\nOld content"
    )

    from aec.lib.skills_manifest import hash_skill_directory
    old_hash = hash_skill_directory(installed)

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": "2026-04-04T00:00:00Z",
        "global": {
            "skills": {
                "test-skill": {
                    "version": "1.0.0",
                    "contentHash": old_hash,
                    "installedAt": "",
                },
            },
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
    return {
        "repo": repo,
        "aec_home": aec_home,
        "installed": installed,
        "manifest_path": aec_home / "installed-manifest.json",
    }


def _source_dirs(repo):
    """Build source_dirs dict pointing at the fake repo."""
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
    }


class TestUpgradeCommand:
    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_upgrades_global_skill(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, upgrade_env
    ):
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = upgrade_env["repo"]
        mock_mp.return_value = upgrade_env["manifest_path"]
        mock_sd.return_value = _source_dirs(upgrade_env["repo"])

        run_upgrade(yes=True)

        skill_md = upgrade_env["installed"] / "SKILL.md"
        assert "2.0.0" in skill_md.read_text()

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_dry_run_does_not_modify(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, upgrade_env
    ):
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = upgrade_env["repo"]
        mock_mp.return_value = upgrade_env["manifest_path"]
        mock_sd.return_value = _source_dirs(upgrade_env["repo"])

        run_upgrade(dry_run=True)

        skill_md = upgrade_env["installed"] / "SKILL.md"
        assert "1.0.0" in skill_md.read_text()

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_reports_nothing_when_up_to_date(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, upgrade_env, capsys
    ):
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = upgrade_env["repo"]
        mock_mp.return_value = upgrade_env["manifest_path"]
        mock_sd.return_value = _source_dirs(upgrade_env["repo"])

        # Make installed match source version
        src = upgrade_env["repo"] / ".claude" / "skills" / "test-skill"
        dst = upgrade_env["installed"]
        shutil.rmtree(dst)
        shutil.copytree(src, dst)

        m = json.loads(upgrade_env["manifest_path"].read_text())
        m["global"]["skills"]["test-skill"]["version"] = "2.0.0"
        upgrade_env["manifest_path"].write_text(json.dumps(m))

        run_upgrade(yes=True)

        output = capsys.readouterr().out
        assert "up to date" in output.lower()

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_dry_run_reports_what_would_change(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, upgrade_env, capsys
    ):
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = upgrade_env["repo"]
        mock_mp.return_value = upgrade_env["manifest_path"]
        mock_sd.return_value = _source_dirs(upgrade_env["repo"])

        run_upgrade(dry_run=True)

        output = capsys.readouterr().out
        assert "would upgrade" in output.lower()
        assert "test-skill" in output

    @patch("aec.commands.upgrade.get_repo_root", return_value=None)
    def test_handles_missing_repo(self, mock_root, capsys):
        from aec.commands.upgrade import run_upgrade

        run_upgrade()

        output = capsys.readouterr().out
        assert "not found" in output.lower() or "setup" in output.lower()

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_manifest_updated_after_upgrade(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, upgrade_env
    ):
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = upgrade_env["repo"]
        mock_mp.return_value = upgrade_env["manifest_path"]
        mock_sd.return_value = _source_dirs(upgrade_env["repo"])

        run_upgrade(yes=True)

        m = json.loads(upgrade_env["manifest_path"].read_text())
        assert m["global"]["skills"]["test-skill"]["version"] == "2.0.0"
        assert m["global"]["skills"]["test-skill"]["contentHash"] != ""
