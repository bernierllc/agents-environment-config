"""End-to-end: export on machine 1 -> apply on machine 2 reproduces the setup."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from aec.commands.apply_cmd import run_apply
from aec.commands.export_cmd import run_export
from aec.lib.manifest_v2 import load_manifest


def _make_source_repo(root: Path) -> Path:
    repo = root / "aec-repo"
    skill = repo / ".claude" / "skills" / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 1.0.0\ndescription: d\nauthor: t\n---\n# s"
    )
    rules = repo / ".agent-rules"
    rules.mkdir(parents=True)
    (rules / "my-rule.md").write_text("---\nname: my-rule\nversion: 1.0.0\ndescription: d\n---\n# r")
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "my-agent.md").write_text(
        "---\nname: my-agent\nversion: 1.0.0\ndescription: d\nauthor: t\n---\n# a"
    )
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    return repo


def _source_dirs(repo: Path) -> dict:
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
        "mcps": repo / "mcp-servers",
    }


def _machine1_manifest(project: Path) -> dict:
    item = {"version": "1.0.0", "contentHash": "", "installedAt": "x"}
    return {
        "manifestVersion": 2,
        "installedAt": "x",
        "updatedAt": "x",
        "lastUpdateCheck": None,
        "global": {
            "skills": {"my-skill": dict(item)},
            "rules": {"my-rule": dict(item)},
            "agents": {"my-agent": dict(item)},
            "mcps": {},
        },
        "repos": {
            str(project.resolve()): {
                "skills": {"my-skill": dict(item)},
                "rules": {},
                "agents": {},
                "mcps": {},
            }
        },
    }


def test_export_then_apply_reproduces_setup(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    manifest_file = tmp_path / "shared" / "my.aec.json"
    manifest_file.parent.mkdir()

    # ---- machine 1: export ----
    home1 = tmp_path / "home1"
    (home1 / ".agents-environment-config").mkdir(parents=True)
    project1 = home1 / "projects" / "my-app"
    project1.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home1)
    monkeypatch.setenv("PROJECTS_DIR", str(home1 / "projects"))
    (home1 / ".agents-environment-config" / "installed-manifest.json").write_text(
        json.dumps(_machine1_manifest(project1))
    )

    run_export(out=str(manifest_file))

    text = manifest_file.read_text()
    assert str(home1) not in text  # no machine-1 absolute paths leaked
    assert "${PROJECTS}/my-app" in text

    # ---- machine 2: apply (different home dir) ----
    home2 = tmp_path / "home2"
    (home2 / ".agents-environment-config").mkdir(parents=True)
    project2 = home2 / "projects" / "my-app"
    project2.mkdir(parents=True)
    repo = _make_source_repo(home2)
    monkeypatch.setattr(Path, "home", lambda: home2)
    monkeypatch.setenv("PROJECTS_DIR", str(home2 / "projects"))

    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=_source_dirs(repo)
    ):
        run_apply(file=str(manifest_file))

    # global items reproduced on machine 2
    assert (home2 / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()
    assert (home2 / ".agent-tools" / "rules" / "my-rule.md").exists()
    assert (home2 / ".claude" / "agents" / "my-agent.md").exists()
    # repo-scoped item reproduced at machine-2's path
    assert (project2 / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()

    m2 = load_manifest(home2 / ".agents-environment-config" / "installed-manifest.json")
    assert "my-skill" in m2["global"]["skills"]
    assert "my-rule" in m2["global"]["rules"]
    assert "my-agent" in m2["global"]["agents"]
    assert "my-skill" in m2["repos"][str(project2.resolve())]["skills"]


def test_apply_dry_run_makes_no_changes(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    home = tmp_path / "home"
    (home / ".agents-environment-config").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    repo = _make_source_repo(home)
    manifest_file = tmp_path / "m.json"
    manifest_file.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "generatedBy": "aec test",
                "global": {"skills": [{"name": "my-skill", "version": "1.0.0"}]},
            }
        )
    )

    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=_source_dirs(repo)
    ):
        run_apply(file=str(manifest_file), dry_run=True)

    assert not (home / ".claude" / "skills" / "my-skill").exists()


def test_apply_missing_file_errors(tmp_path):
    with pytest.raises(SystemExit):
        run_apply(file=str(tmp_path / "nope.json"))
