"""Tests for aec search command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def search_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")
    manifest = {"manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
                "global": {"skills": {"verification-writer": {"version": "2.0.0"}}, "rules": {}, "agents": {}},
                "repos": {}}
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    repo = temp_dir / "aec-repo"
    skills = repo / ".claude" / "skills"
    for name in ["verification-writer", "browser-verification", "commit"]:
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\nversion: 2.0.0\ndescription: {name} desc\n---\n")
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    return repo


class TestSearch:
    @patch("aec.commands.search.get_repo_root")
    def test_finds_matching_skills(self, mock_root, search_env, capsys):
        from aec.commands.search import run_search
        mock_root.return_value = search_env
        run_search("verification")
        output = capsys.readouterr().out
        assert "verification-writer" in output
        assert "browser-verification" in output
        assert "commit" not in output

    @patch("aec.commands.search.get_repo_root")
    def test_shows_install_status(self, mock_root, search_env, capsys):
        from aec.commands.search import run_search
        mock_root.return_value = search_env
        run_search("verification")
        output = capsys.readouterr().out
        assert "[global]" in output

    @patch("aec.commands.search.get_repo_root")
    def test_no_results_message(self, mock_root, search_env, capsys):
        from aec.commands.search import run_search
        mock_root.return_value = search_env
        run_search("zzzznonexistent")
        output = capsys.readouterr().out
        assert "No results" in output

    @patch("aec.commands.search.get_repo_root")
    def test_type_filter(self, mock_root, search_env, capsys):
        from aec.commands.search import run_search
        mock_root.return_value = search_env
        run_search("verification", type_filter="skill")
        output = capsys.readouterr().out
        assert "verification-writer" in output
