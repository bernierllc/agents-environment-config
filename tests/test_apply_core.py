"""Tests for the shared declarative install-execution core."""

import json
from pathlib import Path

import pytest

from aec.lib.apply_core import (
    ApplyPlanEntry,
    DesiredItem,
    execute_apply,
    plan_apply,
)
from aec.lib.manifest_v2 import load_manifest

AVAIL = {"skills": {"my-skill": {"version": "1.0.0", "path": "my-skill"}}}


def _manifest(skills_global=None):
    return {
        "manifestVersion": 2,
        "installedAt": "x",
        "updatedAt": "x",
        "lastUpdateCheck": None,
        "global": {"skills": skills_global or {}, "rules": {}, "agents": {}, "mcps": {}},
        "repos": {},
    }


class TestPlanApply:
    def test_install_when_absent(self):
        plan = plan_apply(
            [DesiredItem("skill", "my-skill", "global")],
            manifest=_manifest(),
            available_by_type=AVAIL,
        )
        assert plan[0].action == "install"
        assert plan[0].to_version == "1.0.0"

    def test_noop_when_up_to_date(self):
        m = _manifest({"my-skill": {"version": "1.0.0"}})
        plan = plan_apply([DesiredItem("skill", "my-skill", "global")], manifest=m, available_by_type=AVAIL)
        assert plan[0].action == "noop"

    def test_upgrade_when_catalog_newer(self):
        m = _manifest({"my-skill": {"version": "0.9.0"}})
        plan = plan_apply([DesiredItem("skill", "my-skill", "global")], manifest=m, available_by_type=AVAIL)
        assert plan[0].action == "upgrade"
        assert plan[0].from_version == "0.9.0"
        assert plan[0].to_version == "1.0.0"

    def test_skip_missing_when_not_in_catalog(self):
        plan = plan_apply([DesiredItem("skill", "ghost", "global")], manifest=_manifest(), available_by_type=AVAIL)
        assert plan[0].action == "skip-missing"

    def test_skip_unknown_type(self):
        plan = plan_apply([DesiredItem("widget", "x", "global")], manifest=_manifest(), available_by_type=AVAIL)
        assert plan[0].action == "skip-missing"


@pytest.fixture
def exec_env(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aec_home = tmp_path / ".agents-environment-config"
    aec_home.mkdir()
    repo = tmp_path / "aec-repo"
    skill = repo / ".claude" / "skills" / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: my-skill\nversion: 1.0.0\ndescription: d\n---\n# s")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(_manifest()))
    return {
        "manifest_path": manifest_path,
        "source_dirs": {"skills": repo / ".claude" / "skills"},
    }


class TestExecuteApply:
    def test_installs_skill_globally(self, exec_env):
        plan = [ApplyPlanEntry(DesiredItem("skill", "my-skill", "global"), "install", None, "1.0.0", "x")]
        result = execute_apply(
            plan,
            source_dirs=exec_env["source_dirs"],
            available_by_type=AVAIL,
            manifest_path=exec_env["manifest_path"],
        )
        assert len(result.applied) == 1
        assert not result.errors
        assert (Path.home() / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()
        m = load_manifest(exec_env["manifest_path"])
        assert "my-skill" in m["global"]["skills"]

    def test_noop_entries_are_skipped(self, exec_env):
        plan = [ApplyPlanEntry(DesiredItem("skill", "my-skill", "global"), "noop", "1.0.0", "1.0.0", "up to date")]
        result = execute_apply(
            plan,
            source_dirs=exec_env["source_dirs"],
            available_by_type=AVAIL,
            manifest_path=exec_env["manifest_path"],
        )
        assert not result.applied
        assert len(result.skipped) == 1

    def test_idempotent_second_run_is_all_noop(self, exec_env):
        item = DesiredItem("skill", "my-skill", "global")
        first = execute_apply(
            plan_apply([item], manifest=load_manifest(exec_env["manifest_path"]), available_by_type=AVAIL),
            source_dirs=exec_env["source_dirs"],
            available_by_type=AVAIL,
            manifest_path=exec_env["manifest_path"],
        )
        assert len(first.applied) == 1

        second_plan = plan_apply(
            [item], manifest=load_manifest(exec_env["manifest_path"]), available_by_type=AVAIL
        )
        assert second_plan[0].action == "noop"
        second = execute_apply(
            second_plan,
            source_dirs=exec_env["source_dirs"],
            available_by_type=AVAIL,
            manifest_path=exec_env["manifest_path"],
        )
        assert not second.applied
        assert not second.errors
