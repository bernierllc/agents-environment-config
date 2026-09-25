"""Tests for aec upgrade command."""

import json
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


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

    @patch("aec.commands.upgrade.is_stale", return_value=False)
    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_syncs_manifest_when_disk_already_matches_source(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, _stale, upgrade_env, capsys
    ):
        """Stale manifest + tree already at new release should not prompt."""
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = upgrade_env["repo"]
        mock_mp.return_value = upgrade_env["manifest_path"]
        mock_sd.return_value = _source_dirs(upgrade_env["repo"])

        src = upgrade_env["repo"] / ".claude" / "skills" / "test-skill"
        dst = upgrade_env["installed"]
        shutil.rmtree(dst)
        shutil.copytree(src, dst)

        m = json.loads(upgrade_env["manifest_path"].read_text())
        m["global"]["skills"]["test-skill"]["version"] = "1.0.0"
        upgrade_env["manifest_path"].write_text(json.dumps(m))

        run_upgrade(yes=False)

        m2 = json.loads(upgrade_env["manifest_path"].read_text())
        assert m2["global"]["skills"]["test-skill"]["version"] == "2.0.0"
        out = capsys.readouterr().out
        assert "manifest updated" in out.lower() or "matched source" in out.lower()


AGENT_V1 = "---\nname: test-agent\nversion: 1.0.0\ndescription: Old\nauthor: Test\n---\nOld"
AGENT_V2 = "---\nname: test-agent\nversion: 2.0.0\ndescription: New\nauthor: Test\n---\nNew"


@pytest.fixture
def agent_upgrade_env(temp_dir, monkeypatch):
    """Environment with an agent source at v2.0.0 and an installed v1.0.0 (with .md)."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    repo = temp_dir / "aec-repo"
    agents_src = repo / ".claude" / "agents"
    agents_src.mkdir(parents=True)
    (agents_src / "test-agent.md").write_text(AGENT_V2)
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    (repo / ".claude" / "skills").mkdir(parents=True)

    agents_dir = temp_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    installed_file = agents_dir / "test-agent.md"
    installed_file.write_text(AGENT_V1)

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": "2026-04-04T00:00:00Z",
        "global": {
            "skills": {},
            "rules": {},
            "agents": {
                "test-agent": {"version": "1.0.0", "contentHash": "", "installedAt": ""},
            },
        },
        "repos": {},
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return {"repo": repo, "aec_home": aec_home, "agents_dir": agents_dir, "manifest_path": manifest_path}


@pytest.fixture
def agent_upgrade_legacy_env(temp_dir, monkeypatch):
    """Environment with an agent installed without .md (legacy) and source at v2.0.0."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    repo = temp_dir / "aec-repo"
    agents_src = repo / ".claude" / "agents"
    agents_src.mkdir(parents=True)
    (agents_src / "test-agent.md").write_text(AGENT_V2)
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    (repo / ".claude" / "skills").mkdir(parents=True)

    agents_dir = temp_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    # Legacy: installed without .md extension
    (agents_dir / "test-agent").write_text(AGENT_V1)

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": "2026-04-04T00:00:00Z",
        "global": {
            "skills": {},
            "rules": {},
            "agents": {
                "test-agent": {"version": "1.0.0", "contentHash": "", "installedAt": ""},
            },
        },
        "repos": {},
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return {"repo": repo, "aec_home": aec_home, "agents_dir": agents_dir, "manifest_path": manifest_path}


def _agent_source_dirs(repo):
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
    }


class TestUpgradeAgent:
    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_upgrades_agent_file_with_md_extension(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, agent_upgrade_env
    ):
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = agent_upgrade_env["repo"]
        mock_mp.return_value = agent_upgrade_env["manifest_path"]
        mock_sd.return_value = _agent_source_dirs(agent_upgrade_env["repo"])

        run_upgrade(yes=True)

        upgraded = agent_upgrade_env["agents_dir"] / "test-agent.md"
        assert upgraded.exists()
        assert "2.0.0" in upgraded.read_text()

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_upgrades_legacy_agent_removes_bare_file(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, agent_upgrade_legacy_env
    ):
        """Upgrading a legacy (no .md) agent replaces the bare file with a .md one."""
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = agent_upgrade_legacy_env["repo"]
        mock_mp.return_value = agent_upgrade_legacy_env["manifest_path"]
        mock_sd.return_value = _agent_source_dirs(agent_upgrade_legacy_env["repo"])

        run_upgrade(yes=True)

        agents_dir = agent_upgrade_legacy_env["agents_dir"]
        assert not (agents_dir / "test-agent").exists(), "Legacy bare file must be removed"
        assert (agents_dir / "test-agent.md").exists(), "New .md file must be created"
        assert "2.0.0" in (agents_dir / "test-agent.md").read_text()


class TestRepairExtensionlessAgents:
    """Tests for _repair_extensionless_agents — runs independently of version upgrades."""

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_repair_renames_bare_file_even_at_same_version(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, agent_upgrade_legacy_env
    ):
        """Bare agent file should be renamed to .md even if the version hasn't changed."""
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = agent_upgrade_legacy_env["repo"]
        mock_mp.return_value = agent_upgrade_legacy_env["manifest_path"]
        mock_sd.return_value = _agent_source_dirs(agent_upgrade_legacy_env["repo"])

        # Override the source version to match installed (so version_is_newer is False)
        src = agent_upgrade_legacy_env["repo"] / ".claude" / "agents" / "test-agent.md"
        src.write_text(AGENT_V1)  # same version as installed

        run_upgrade(yes=True)

        agents_dir = agent_upgrade_legacy_env["agents_dir"]
        assert not (agents_dir / "test-agent").exists(), "Bare file must be removed"
        assert (agents_dir / "test-agent.md").exists(), "File must now have .md extension"

    @patch("aec.commands.upgrade.find_tracked_repo", return_value=None)
    @patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[])
    @patch("aec.commands.upgrade.get_source_dirs")
    @patch("aec.commands.upgrade.get_repo_root")
    @patch("aec.commands.upgrade._manifest_path")
    def test_dry_run_reports_repair_without_renaming(
        self, mock_mp, mock_root, mock_sd, mock_all, mock_find, agent_upgrade_legacy_env, capsys
    ):
        """Dry run should report the extensionless file without actually renaming it."""
        from aec.commands.upgrade import run_upgrade

        mock_root.return_value = agent_upgrade_legacy_env["repo"]
        mock_mp.return_value = agent_upgrade_legacy_env["manifest_path"]
        mock_sd.return_value = _agent_source_dirs(agent_upgrade_legacy_env["repo"])

        src = agent_upgrade_legacy_env["repo"] / ".claude" / "agents" / "test-agent.md"
        src.write_text(AGENT_V1)

        run_upgrade(dry_run=True)

        agents_dir = agent_upgrade_legacy_env["agents_dir"]
        assert (agents_dir / "test-agent").exists(), "Bare file must NOT be renamed in dry run"
        assert not (agents_dir / "test-agent.md").exists()

        output = capsys.readouterr().out
        assert "test-agent" in output


def _skill_md(name: str, version: str, deps=None) -> str:
    """Build minimal SKILL.md content with optional dependencies block."""
    lines = ["---", f"name: {name}", f"version: {version}", "author: Test", "description: x"]
    if deps:
        lines += ["dependencies:", "  skills:"]
        for d in deps:
            lines += [
                f'    - name: {d["name"]}',
                f'      min_version: "{d["min_version"]}"',
                f'      reason: "{d["reason"]}"',
            ]
    lines += ["---", f"# {name}"]
    return "\n".join(lines) + "\n"


@pytest.fixture
def dep_upgrade_env(temp_dir, monkeypatch):
    """Environment: main-skill v1→v2 (v2 now requires dep-skill >=2.0.0), dep-skill installed at 1.5.0."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    repo = temp_dir / "aec-repo"
    skills_src = repo / ".claude" / "skills"

    # Source: main-skill v2.0.0 with dep on dep-skill >=2.0.0
    main_src = skills_src / "main-skill"
    main_src.mkdir(parents=True)
    (main_src / "SKILL.md").write_text(
        _skill_md("main-skill", "2.0.0", [{"name": "dep-skill", "min_version": "2.0.0", "reason": "Needs v2"}])
    )

    # Source: dep-skill v2.0.0
    dep_src = skills_src / "dep-skill"
    dep_src.mkdir(parents=True)
    (dep_src / "SKILL.md").write_text(_skill_md("dep-skill", "2.0.0"))

    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    (repo / ".claude" / "agents").mkdir(parents=True)

    # Installed: main-skill v1.0.0 (no deps declared), dep-skill v1.5.0
    installed_skills = temp_dir / ".claude" / "skills"

    main_installed = installed_skills / "main-skill"
    main_installed.mkdir(parents=True)
    (main_installed / "SKILL.md").write_text(_skill_md("main-skill", "1.0.0"))

    dep_installed = installed_skills / "dep-skill"
    dep_installed.mkdir(parents=True)
    (dep_installed / "SKILL.md").write_text(_skill_md("dep-skill", "1.5.0"))

    from aec.lib.skills_manifest import hash_skill_directory
    main_hash = hash_skill_directory(main_installed)
    dep_hash = hash_skill_directory(dep_installed)

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-05-01T00:00:00Z",
        "lastUpdateCheck": "2026-05-01T00:00:00Z",
        "global": {
            "skills": {
                "main-skill": {"version": "1.0.0", "contentHash": main_hash, "installedAt": ""},
                "dep-skill": {"version": "1.5.0", "contentHash": dep_hash, "installedAt": ""},
            },
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    return {
        "repo": repo,
        "aec_home": aec_home,
        "manifest_path": manifest_path,
        "installed_skills": installed_skills,
        "dep_installed": dep_installed,
    }


class TestUpgradeWithDepConflicts:
    def _patches(self, env):
        from unittest.mock import patch
        return [
            patch("aec.commands.upgrade.get_repo_root", return_value=env["repo"]),
            patch("aec.commands.upgrade._manifest_path", return_value=env["manifest_path"]),
            patch("aec.commands.upgrade.get_source_dirs", return_value=_source_dirs(env["repo"])),
            patch("aec.commands.upgrade.find_tracked_repo", return_value=None),
            patch("aec.commands.upgrade.get_all_tracked_repos", return_value=[]),
        ]

    def test_conflict_prompts_user_to_upgrade_dep(self, dep_upgrade_env, monkeypatch):
        """When new version tightens a dep constraint, user is prompted to upgrade the dep."""
        from aec.commands.upgrade import run_upgrade

        prompts_seen = []
        def capture(msg):
            prompts_seen.append(msg)
            return "y"
        monkeypatch.setattr("builtins.input", capture)

        with self._patches(dep_upgrade_env)[0], self._patches(dep_upgrade_env)[1], \
             self._patches(dep_upgrade_env)[2], self._patches(dep_upgrade_env)[3], \
             self._patches(dep_upgrade_env)[4]:
            run_upgrade(yes=False)

        assert any("dep-skill" in p for p in prompts_seen), "Should prompt about dep-skill"

    def test_conflict_declined_skips_main_skill_upgrade(self, dep_upgrade_env, monkeypatch, capsys):
        """When user declines dep upgrade, the main skill is not upgraded."""
        from aec.commands.upgrade import run_upgrade

        monkeypatch.setattr("builtins.input", lambda _: "n")

        with self._patches(dep_upgrade_env)[0], self._patches(dep_upgrade_env)[1], \
             self._patches(dep_upgrade_env)[2], self._patches(dep_upgrade_env)[3], \
             self._patches(dep_upgrade_env)[4]:
            run_upgrade(yes=False)

        # main-skill should still be at v1.0.0
        installed = dep_upgrade_env["installed_skills"] / "main-skill" / "SKILL.md"
        assert "1.0.0" in installed.read_text()

    def test_conflict_approved_upgrades_dep_and_main_skill(self, dep_upgrade_env, monkeypatch):
        """When user approves dep upgrade, both dep and main skill are upgraded."""
        from aec.commands.upgrade import run_upgrade

        monkeypatch.setattr("builtins.input", lambda _: "y")

        with self._patches(dep_upgrade_env)[0], self._patches(dep_upgrade_env)[1], \
             self._patches(dep_upgrade_env)[2], self._patches(dep_upgrade_env)[3], \
             self._patches(dep_upgrade_env)[4]:
            run_upgrade(yes=False)

        dep_md = dep_upgrade_env["dep_installed"] / "SKILL.md"
        main_md = dep_upgrade_env["installed_skills"] / "main-skill" / "SKILL.md"
        assert "2.0.0" in dep_md.read_text(), "dep-skill should be upgraded to 2.0.0"
        assert "2.0.0" in main_md.read_text(), "main-skill should be upgraded to 2.0.0"

    def test_assume_yes_upgrades_dep_and_main_skill_silently(self, dep_upgrade_env):
        """With -y flag, dep and main skill are both upgraded without any prompts."""
        from aec.commands.upgrade import run_upgrade

        with self._patches(dep_upgrade_env)[0], self._patches(dep_upgrade_env)[1], \
             self._patches(dep_upgrade_env)[2], self._patches(dep_upgrade_env)[3], \
             self._patches(dep_upgrade_env)[4]:
            run_upgrade(yes=True)

        dep_md = dep_upgrade_env["dep_installed"] / "SKILL.md"
        main_md = dep_upgrade_env["installed_skills"] / "main-skill" / "SKILL.md"
        assert "2.0.0" in dep_md.read_text()
        assert "2.0.0" in main_md.read_text()

    def test_dry_run_reports_dep_conflict_without_upgrading(self, dep_upgrade_env, capsys):
        """Dry run reports both the skill upgrade and the dep constraint change."""
        from aec.commands.upgrade import run_upgrade

        with self._patches(dep_upgrade_env)[0], self._patches(dep_upgrade_env)[1], \
             self._patches(dep_upgrade_env)[2], self._patches(dep_upgrade_env)[3], \
             self._patches(dep_upgrade_env)[4]:
            run_upgrade(dry_run=True)

        output = capsys.readouterr().out
        assert "dep-skill" in output

        # Nothing should be modified
        dep_md = dep_upgrade_env["dep_installed"] / "SKILL.md"
        assert "1.5.0" in dep_md.read_text()


class TestUpgradePlugins:
    """Plugins upgrade through their installer; never copied like rule files.

    Claude Code marketplace plugins go through `claude plugin update --json`
    (Claude decides what is newer); older per-tool records are re-installed.
    """

    CATALOG = Path(__file__).resolve().parent.parent / "plugins"

    def _run(self, tmp_path, recorded, *, update=None, yes=True, agents=None, pref=None,
             answer="n", fail=False, dry_run=False):
        import json as _json
        from aec.commands.upgrade import _upgrade_scope
        from aec.lib.manifest_v2 import record_plugin_install

        manifest = {"global": {"plugins": {}}, "repos": {}}
        record_plugin_install(manifest, "global", "ponytail", recorded["version"],
                              install_type=recorded["install_type"], targets=["claude"],
                              plugin_id=recorded.get("pluginId", ""))
        update = update or {"updateOutcome": "updated", "oldVersion": recorded["version"], "newVersion": "9.9.9"}
        calls = []

        def fake_run(cmd, *a, **kw):
            calls.append(cmd)
            out = ""
            if cmd[:3] == ["claude", "plugin", "update"]:
                out = _json.dumps({"command": "update", "outcome": "ok", **update})
            elif cmd[:3] == ["claude", "plugin", "list"]:
                out = _json.dumps([{"id": "ponytail@ponytail", "version": "9.9.9"}])
            return MagicMock(returncode=1 if fail else 0, stdout=out, stderr="")

        with patch("subprocess.run", side_effect=fake_run), \
             patch("aec.lib.config.detect_agents", return_value={"claude": {}} if agents is None else agents), \
             patch("aec.lib.preferences.get_setting", return_value=pref), \
             patch("aec.commands.upgrade.prompt", return_value=answer), \
             patch("aec.commands.upgrade.record_item_install_pertype"), \
             patch("aec.commands.upgrade._target_base", return_value=tmp_path / "rules"):
            upgraded = _upgrade_scope(manifest, "global", {"plugins": self.CATALOG},
                                      yes=yes, dry_run=dry_run)
        return manifest["global"]["plugins"]["ponytail"], calls, upgraded

    MANAGED = {"version": "4.10.0", "install_type": "marketplace", "pluginId": "ponytail@ponytail"}

    def test_managed_plugin_asks_claude_even_when_catalog_is_not_newer(self, tmp_path):
        entry, calls, upgraded = self._run(tmp_path, self.MANAGED)
        assert ["claude", "plugin", "marketplace", "update", "ponytail"] in calls
        assert ["claude", "plugin", "update", "ponytail@ponytail", "--json"] in calls
        assert upgraded and entry["version"] == "9.9.9" and entry["pluginId"] == "ponytail@ponytail"
        assert not (tmp_path / "rules").exists(), "plugin must not be copied as a rule"

    def test_up_to_date_is_the_only_current_result(self, tmp_path):
        """Only a confirmed up_to_date lets the caller report "up to date"."""
        entry, _, not_current = self._run(tmp_path, self.MANAGED, update={
            "updateOutcome": "up_to_date", "oldVersion": "4.10.0", "newVersion": "4.10.0"})
        assert not not_current and entry["version"] == "4.10.0"

    def test_record_without_plugin_id_resolves_it_from_catalog(self, tmp_path):
        entry, calls, _ = self._run(tmp_path, {"version": "4.10.0", "install_type": "marketplace"})
        assert ["claude", "plugin", "update", "ponytail@ponytail", "--json"] in calls
        assert entry["pluginId"] == "ponytail@ponytail"

    def test_failed_update_keeps_recorded_version(self, tmp_path):
        """A failed check keeps the record, and is not reported as "up to date"."""
        entry, _, not_known_current = self._run(tmp_path, self.MANAGED, fail=True)
        assert entry["version"] == "4.10.0" and not_known_current

    def test_instructions_only_preference_never_runs(self, tmp_path):
        entry, calls, not_current = self._run(tmp_path, self.MANAGED, pref="instructions-only")
        assert calls == [] and entry["version"] == "4.10.0"
        assert not_current, "an unchecked plugin is never reported current"

    def test_missing_claude_is_not_run(self, tmp_path):
        entry, calls, not_current = self._run(tmp_path, self.MANAGED, agents={})
        assert calls == [] and entry["version"] == "4.10.0" and not_current

    def test_dry_run_runs_nothing(self, tmp_path):
        entry, calls, upgraded = self._run(tmp_path, self.MANAGED, dry_run=True)
        assert calls == [] and upgraded and entry["version"] == "4.10.0"

    def test_old_per_tool_record_reinstalls_from_marketplace(self, tmp_path):
        entry, calls, upgraded = self._run(tmp_path, {"version": "1.0.0", "install_type": "per-tool"})
        assert calls[:2] == [
            ["claude", "plugin", "marketplace", "add", "DietrichGebert/ponytail"],
            ["claude", "plugin", "install", "ponytail@ponytail"],
        ]
        assert upgraded and entry["install_type"] == "marketplace"
        assert entry["version"] == "9.9.9", "records what Claude Code installed"
        assert entry["pluginId"] == "ponytail@ponytail"

    def test_reinstall_without_yes_declining_runs_nothing(self, tmp_path):
        entry, calls, not_current = self._run(tmp_path, {"version": "1.0.0", "install_type": "per-tool"},
                                              yes=False, answer="n")
        assert calls == [] and entry["version"] == "1.0.0"
        assert not_current, "a declined re-install leaves the plugin outdated"

    def test_managed_update_needs_no_extra_confirmation(self, tmp_path):
        """`aec upgrade` is the request; Claude Code's own update runs without a prompt."""
        # Every prompt would answer "no"; the update still runs.
        _, calls, upgraded = self._run(tmp_path, self.MANAGED, yes=False, answer="n")
        assert ["claude", "plugin", "update", "ponytail@ponytail", "--json"] in calls and upgraded

    def test_dry_run_under_instructions_only_says_manual(self, tmp_path, capsys):
        _, calls, not_current = self._run(tmp_path, self.MANAGED, dry_run=True, pref="instructions-only")
        out = capsys.readouterr().out
        assert calls == [] and not_current and "run manually" in out and "would run" not in out

    def test_failed_update_shows_claudes_message(self, tmp_path, capsys):
        self._run(tmp_path, self.MANAGED, fail=True)
        assert "failed" in capsys.readouterr().out



def test_other_repo_with_only_managed_plugins_is_offered(tmp_path):
    """Codex P2 on #87: a repo whose only plugins are Claude-managed still needs an upgrade pass."""
    from aec.commands.upgrade import _find_outdated_repos

    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = {"global": {}, "repos": {str(repo.resolve()): {
        "plugins": {"p": {"install_type": "marketplace", "version": "1.0.0", "pluginId": "p@m"}}}}}
    catalog = tmp_path / "plugins"
    catalog.mkdir()
    assert _find_outdated_repos(manifest, [repo], {"plugins": catalog}) == [(repo, 1)]


def test_yes_upgrades_discovered_other_repos(tmp_path, capsys):
    """Codex P2 on #87: --yes skips the other-repos confirmation instead of skipping the repos."""
    from aec.commands import upgrade

    other = tmp_path / "other"
    other.mkdir()
    manifest = {"global": {}, "repos": {str(other): {}}}
    scopes = []
    with patch.object(upgrade, "get_repo_root", return_value=tmp_path), \
         patch.object(upgrade, "get_source_dirs", return_value={}), \
         patch.object(upgrade, "load_manifest", return_value=manifest), \
         patch.object(upgrade, "save_manifest"), \
         patch.object(upgrade, "find_tracked_repo", return_value=None), \
         patch.object(upgrade, "get_all_tracked_repos", return_value=[other]), \
         patch.object(upgrade, "_find_outdated_repos", return_value=[(other, 1)]), \
         patch.object(upgrade, "_upgrade_scope", side_effect=lambda m, s, *a, **k: scopes.append(s) or False), \
         patch.object(upgrade, "prompt") as asked:
        upgrade.run_upgrade(yes=True)
    assert str(other) in scopes and not asked.called
    assert "Everything is up to date" not in capsys.readouterr().out

