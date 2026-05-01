"""Tests for aec doctor extensionless-agent detection."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def doctor_env(temp_dir, monkeypatch):
    """Minimal AEC environment for doctor tests."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    agents_dir = temp_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": "2026-04-04T00:00:00Z",
        "global": {"skills": {}, "rules": {}, "agents": {}},
        "repos": {},
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    return {"aec_home": aec_home, "agents_dir": agents_dir, "manifest_path": manifest_path}


def _run_doctor_patched(temp_dir):
    """Run doctor with repo root, agent-tools, and cursor patched out."""
    from aec.commands.doctor import run_doctor

    with (
        patch("aec.commands.doctor.get_repo_root", return_value=temp_dir / "aec-repo"),
        patch("aec.commands.doctor.AGENT_TOOLS_DIR", temp_dir / ".agent-tools"),
        patch("aec.commands.doctor.CURSOR_DIR", temp_dir / ".cursor"),
        patch("aec.commands.doctor.AEC_HOME", temp_dir / ".agents-environment-config"),
        patch("aec.commands.doctor.CLAUDE_DIR", temp_dir / ".claude"),
        patch("aec.commands.doctor.AEC_SETUP_LOG", temp_dir / ".agents-environment-config" / "setup-repo-locations.txt"),
        patch("aec.lib.config.INSTALLED_MANIFEST_V2", temp_dir / ".agents-environment-config" / "installed-manifest.json"),
    ):
        return run_doctor()


class TestDoctorExtensionlessAgents:
    def test_no_issue_when_agents_have_md_extension(self, doctor_env, capsys):
        agents_dir = doctor_env["agents_dir"]
        (agents_dir / "my-agent.md").write_text("---\nname: my-agent\n---\n")

        _, issues = _run_doctor_patched(doctor_env["aec_home"].parent)

        output = capsys.readouterr().out
        assert not any("missing .md" in i for i in issues)
        assert "missing .md" not in output

    def test_flags_bare_agent_file_as_issue(self, doctor_env, capsys):
        agents_dir = doctor_env["agents_dir"]
        (agents_dir / "my-agent").write_text("---\nname: my-agent\n---\n")

        _, issues = _run_doctor_patched(doctor_env["aec_home"].parent)

        output = capsys.readouterr().out
        assert any("missing .md" in i.lower() or ".md extension" in i.lower() for i in issues), \
            f"Expected .md extension issue in: {issues}"
        assert "my-agent" in output

    def test_suggests_aec_upgrade_for_bare_agents(self, doctor_env, capsys):
        agents_dir = doctor_env["agents_dir"]
        (agents_dir / "broken-agent").write_text("---\nname: broken-agent\n---\n")

        _run_doctor_patched(doctor_env["aec_home"].parent)

        output = capsys.readouterr().out
        assert "aec upgrade" in output

    def test_counts_multiple_bare_agents(self, doctor_env, capsys):
        agents_dir = doctor_env["agents_dir"]
        (agents_dir / "agent-one").write_text("---\nname: agent-one\n---\n")
        (agents_dir / "agent-two").write_text("---\nname: agent-two\n---\n")
        (agents_dir / "good-agent.md").write_text("---\nname: good-agent\n---\n")

        _, issues = _run_doctor_patched(doctor_env["aec_home"].parent)

        assert any("2" in i for i in issues if ".md extension" in i.lower() or "missing .md" in i.lower())
