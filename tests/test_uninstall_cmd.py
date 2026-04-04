"""Tests for aec uninstall <type> <name> command."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def uninstall_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    skill_dir = temp_dir / ".claude" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\nversion: 1.0.0\n---\n")

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "",
        "lastUpdateCheck": None,
        "global": {
            "skills": {
                "my-skill": {
                    "version": "1.0.0",
                    "contentHash": "",
                    "installedAt": "",
                }
            },
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
    return {"aec_home": aec_home, "skill_dir": skill_dir}


class TestUninstall:
    def test_removes_global_skill(self, uninstall_env):
        from aec.commands.uninstall import run_uninstall

        run_uninstall(item_type="skill", name="my-skill", global_flag=True, yes=True)
        assert not uninstall_env["skill_dir"].exists()

    def test_removes_from_manifest(self, uninstall_env):
        from aec.commands.uninstall import run_uninstall
        from aec.lib.manifest_v2 import load_manifest

        run_uninstall(item_type="skill", name="my-skill", global_flag=True, yes=True)
        m = load_manifest(uninstall_env["aec_home"] / "installed-manifest.json")
        assert "my-skill" not in m["global"]["skills"]

    def test_warning_for_nonexistent(self, uninstall_env, capsys):
        from aec.commands.uninstall import run_uninstall

        run_uninstall(item_type="skill", name="nope", global_flag=True, yes=True)
        output = capsys.readouterr().out
        assert "not found" in output.lower()

    def test_rejects_unknown_type(self, uninstall_env):
        from aec.commands.uninstall import run_uninstall

        with pytest.raises(SystemExit):
            run_uninstall(item_type="widget", name="x", global_flag=True, yes=True)
