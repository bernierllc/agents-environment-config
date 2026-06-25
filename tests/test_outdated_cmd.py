"""Tests for aec outdated command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def outdated_env(temp_dir, monkeypatch):
    """Set up a fake home with manifest and source skill for outdated tests."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    manifest = {
        "manifestVersion": 2,
        "installedAt": "",
        "updatedAt": "",
        "lastUpdateCheck": None,
        "global": {
            "skills": {"old-skill": {"version": "1.0.0", "contentHash": "", "installedAt": ""}},
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    # Create a fake AEC repo with a newer version of the skill
    repo = temp_dir / "aec-repo"
    skill = repo / ".claude" / "skills" / "old-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: old-skill\nversion: 2.0.0\ndescription: Updated\n---\n"
    )
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    return repo


def _make_source_dirs(repo):
    """Build source_dirs dict pointing at the fake repo."""
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
    }


class TestOutdated:
    @patch("aec.commands.outdated.get_source_dirs")
    @patch("aec.commands.outdated.get_repo_root")
    def test_shows_outdated_global(self, mock_root, mock_dirs, outdated_env, capsys):
        from aec.commands.outdated import run_outdated

        mock_root.return_value = outdated_env
        mock_dirs.return_value = _make_source_dirs(outdated_env)
        run_outdated()
        output = capsys.readouterr().out
        assert "old-skill" in output
        assert "1.0.0" in output
        assert "2.0.0" in output

    @patch("aec.commands.outdated.get_source_dirs")
    @patch("aec.commands.outdated.get_repo_root")
    def test_shows_up_to_date_when_current(self, mock_root, mock_dirs, outdated_env, capsys, temp_dir):
        from aec.commands.outdated import run_outdated

        mock_root.return_value = outdated_env
        mock_dirs.return_value = _make_source_dirs(outdated_env)
        # Update manifest to match available version
        mp = temp_dir / ".agents-environment-config" / "installed-manifest.json"
        m = json.loads(mp.read_text())
        m["global"]["skills"]["old-skill"]["version"] = "2.0.0"
        mp.write_text(json.dumps(m))
        run_outdated()
        output = capsys.readouterr().out
        assert "up to date" in output.lower()

    @patch("aec.commands.outdated.get_source_dirs")
    @patch("aec.commands.outdated.get_repo_root")
    def test_type_filter(self, mock_root, mock_dirs, outdated_env, capsys):
        from aec.commands.outdated import run_outdated

        mock_root.return_value = outdated_env
        mock_dirs.return_value = _make_source_dirs(outdated_env)
        run_outdated(type_filter="agent")
        output = capsys.readouterr().out
        # Filtering to agents should not show the outdated skill
        assert "old-skill" not in output

    @patch("aec.commands.outdated.get_repo_root")
    def test_no_repo_shows_error(self, mock_root, capsys):
        from aec.commands.outdated import run_outdated

        mock_root.return_value = None
        run_outdated()
        output = capsys.readouterr().out
        assert "not found" in output.lower() or "setup" in output.lower()

    @patch("aec.commands.outdated.get_source_dirs")
    @patch("aec.commands.outdated.get_repo_root")
    def test_type_filter_plural_form(self, mock_root, mock_dirs, outdated_env, capsys):
        from aec.commands.outdated import run_outdated

        mock_root.return_value = outdated_env
        mock_dirs.return_value = _make_source_dirs(outdated_env)
        # 'skills' (already plural) should still work
        run_outdated(type_filter="skills")
        output = capsys.readouterr().out
        assert "old-skill" in output
        assert "1.0.0" in output


def _add_plugin_to_manifest(temp_dir, name, fields):
    mp = temp_dir / ".agents-environment-config" / "installed-manifest.json"
    m = json.loads(mp.read_text())
    m["global"].setdefault("plugins", {})[name] = fields
    mp.write_text(json.dumps(m))


def _make_source_dirs_with_plugins(repo):
    dirs = _make_source_dirs(repo)
    dirs["plugins"] = repo / "plugins"
    return dirs


class TestOutdatedPlugins:
    @patch("aec.commands.outdated.get_source_dirs")
    @patch("aec.commands.outdated.get_repo_root")
    def test_registry_plugin_version_compare(self, mock_root, mock_dirs, outdated_env, capsys, temp_dir):
        from aec.commands.outdated import run_outdated

        # installed older than registry plugin.json -> shows upgrade
        plugin_dir = outdated_env / "plugins" / "old-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "schema": "loadout/v1", "item_type": "plugin", "name": "old-plugin",
            "version": "2.0.0", "description": "d", "source": "https://example.test",
            "install_type": "marketplace", "install": {"marketplace": {"id": "x"}},
        }))
        _add_plugin_to_manifest(temp_dir, "old-plugin", {"version": "1.0.0", "install_type": "marketplace", "installedAt": ""})

        mock_root.return_value = outdated_env
        mock_dirs.return_value = _make_source_dirs_with_plugins(outdated_env)
        run_outdated(type_filter="plugin")
        output = capsys.readouterr().out
        assert "old-plugin" in output
        assert "1.0.0" in output and "2.0.0" in output

    @patch("aec.commands.outdated.get_source_dirs")
    @patch("aec.commands.outdated.get_repo_root")
    def test_url_only_plugin_version_unknown(self, mock_root, mock_dirs, outdated_env, capsys, temp_dir):
        from aec.commands.outdated import run_outdated

        # plugin in manifest with no registry entry -> "version unknown"
        (outdated_env / "plugins").mkdir(parents=True)
        _add_plugin_to_manifest(temp_dir, "url-plugin", {"version": "0.0.0", "install_type": "external", "installedAt": ""})

        mock_root.return_value = outdated_env
        mock_dirs.return_value = _make_source_dirs_with_plugins(outdated_env)
        run_outdated(type_filter="plugin")
        output = capsys.readouterr().out
        assert "url-plugin" in output
        assert "version unknown" in output
