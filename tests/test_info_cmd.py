"""Tests for aec info command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def info_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    repo = temp_dir / "aec-repo"
    skill = repo / ".claude" / "skills" / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 2.0.0\ndescription: A test skill\nauthor: Test Author\n---\n"
    )
    (skill / "references").mkdir()
    (skill / "references" / "ref.md").write_text("ref")
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()

    manifest = {
        "manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
        "global": {"skills": {"my-skill": {"version": "2.0.0", "contentHash": "sha256:abc", "installedAt": "2026-04-04"}}, "rules": {}, "agents": {}},
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
    return repo


class TestInfo:
    @patch("aec.commands.info.get_source_dirs")
    def test_shows_skill_info(self, mock_dirs, info_env, capsys):
        from aec.commands.info import run_info
        mock_dirs.return_value = {"skills": info_env / ".claude" / "skills", "rules": info_env / ".agent-rules", "agents": info_env / ".claude" / "agents"}
        run_info(item_type="skill", name="my-skill")
        output = capsys.readouterr().out
        assert "my-skill" in output
        assert "2.0.0" in output
        assert "Test Author" in output

    @patch("aec.commands.info.get_source_dirs")
    def test_shows_install_location(self, mock_dirs, info_env, capsys):
        from aec.commands.info import run_info
        mock_dirs.return_value = {"skills": info_env / ".claude" / "skills", "rules": info_env / ".agent-rules", "agents": info_env / ".claude" / "agents"}
        run_info(item_type="skill", name="my-skill")
        output = capsys.readouterr().out
        assert "global" in output

    @patch("aec.commands.info.get_source_dirs")
    def test_shows_not_installed(self, mock_dirs, info_env, capsys, temp_dir):
        from aec.commands.info import run_info
        # Clear manifest
        mp = temp_dir / ".agents-environment-config" / "installed-manifest.json"
        m = json.loads(mp.read_text())
        m["global"]["skills"] = {}
        mp.write_text(json.dumps(m))
        mock_dirs.return_value = {"skills": info_env / ".claude" / "skills", "rules": info_env / ".agent-rules", "agents": info_env / ".claude" / "agents"}
        run_info(item_type="skill", name="my-skill")
        output = capsys.readouterr().out
        assert "not installed" in output

    @patch("aec.commands.info.get_source_dirs")
    def test_error_for_unknown(self, mock_dirs, info_env, capsys):
        from aec.commands.info import run_info
        mock_dirs.return_value = {"skills": info_env / ".claude" / "skills", "rules": info_env / ".agent-rules", "agents": info_env / ".claude" / "agents"}
        run_info(item_type="skill", name="nonexistent")
        output = capsys.readouterr().out
        assert "not found" in output.lower()

    def test_error_for_invalid_type(self, info_env, capsys):
        from aec.commands.info import run_info
        run_info(item_type="widget", name="foo")
        output = capsys.readouterr().out
        assert "unknown type" in output.lower()

    @patch("aec.commands.info.get_source_dirs")
    def test_shows_file_count(self, mock_dirs, info_env, capsys):
        from aec.commands.info import run_info
        mock_dirs.return_value = {"skills": info_env / ".claude" / "skills", "rules": info_env / ".agent-rules", "agents": info_env / ".claude" / "agents"}
        run_info(item_type="skill", name="my-skill")
        output = capsys.readouterr().out
        # my-skill dir has SKILL.md + references/ref.md = 2 files
        assert "2 file(s)" in output

    @patch("aec.commands.info.get_source_dirs")
    def test_shows_description(self, mock_dirs, info_env, capsys):
        from aec.commands.info import run_info
        mock_dirs.return_value = {"skills": info_env / ".claude" / "skills", "rules": info_env / ".agent-rules", "agents": info_env / ".claude" / "agents"}
        run_info(item_type="skill", name="my-skill")
        output = capsys.readouterr().out
        assert "A test skill" in output
