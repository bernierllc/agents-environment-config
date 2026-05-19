"""Tests for the hooks lifecycle helpers (install_hooks_for_item /
remove_hooks_for_item) and their integration into install/uninstall commands.
"""

import json
from pathlib import Path


def _write_skill(item_dir: Path, *, version: str = "1.0.0", hooks=None) -> None:
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "SKILL.md").write_text(
        f"---\nname: demo-skill\ndescription: x\nversion: {version}\n---\nbody\n"
    )
    if hooks is not None:
        (item_dir / "hooks.json").write_text(
            json.dumps({"$schema": "x", "version": version, "hooks": hooks})
        )


class TestLifecycleHelpers:
    def test_install_noop_when_no_hooks_json(self, tmp_path):
        from aec.lib.hooks.lifecycle import install_hooks_for_item

        item_dir = tmp_path / "item"
        _write_skill(item_dir)
        repo = tmp_path / "repo"
        repo.mkdir()
        ok = install_hooks_for_item(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo,
        )
        assert ok is False
        assert not (repo / ".claude/settings.json").exists()
        assert not (repo / ".aec/installed-hooks").exists()

    def test_install_then_remove_round_trip(self, tmp_path):
        from aec.lib.hooks.lifecycle import (
            install_hooks_for_item, remove_hooks_for_item,
        )

        item_dir = tmp_path / "item"
        _write_skill(item_dir, hooks=[{
            "id": "h1", "event": "on_file_edit",
            "command": "echo hi", "description": "d",
        }])
        repo = tmp_path / "repo"
        repo.mkdir()

        installed = install_hooks_for_item(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo, agents=["claude"],
        )
        assert installed is True
        state_path = repo / ".aec/installed-hooks/skill.demo.json"
        assert state_path.exists()
        settings = json.loads((repo / ".claude/settings.json").read_text())
        assert settings["hooks"]["PostToolUse"]

        removed = remove_hooks_for_item(
            item_type="skill", item_key="demo", repo_root=repo,
        )
        assert removed is True
        assert not state_path.exists()
        settings = json.loads((repo / ".claude/settings.json").read_text())
        assert settings.get("hooks", {}).get("PostToolUse", []) == []

    def test_remove_noop_when_no_state(self, tmp_path):
        from aec.lib.hooks.lifecycle import remove_hooks_for_item

        repo = tmp_path / "repo"
        repo.mkdir()
        assert remove_hooks_for_item(
            item_type="skill", item_key="never-installed", repo_root=repo,
        ) is False


class TestRunScriptCommand:
    def test_run_script_executes_script(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app

        # Fake a tracked repo with a skill that owns scripts/echo.sh
        repo = tmp_path / "repo"
        skill_dir = repo / ".claude/skills/demo"
        scripts = skill_dir / "scripts"
        scripts.mkdir(parents=True)
        marker = tmp_path / "marker.txt"
        script = scripts / "echo.sh"
        script.write_text(f"#!/usr/bin/env bash\necho hello-$1 > {marker}\n")
        script.chmod(0o755)

        monkeypatch.setattr(
            "aec.commands.run_script_cmd.find_tracked_repo",
            lambda: repo,
        )

        result = CliRunner().invoke(app, ["run-script", "skill:demo", "echo.sh", "world"])
        assert result.exit_code == 0, result.output
        assert marker.read_text().strip() == "hello-world"

    def test_run_script_errors_when_item_missing(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app

        repo = tmp_path / "repo"
        repo.mkdir()
        monkeypatch.setattr(
            "aec.commands.run_script_cmd.find_tracked_repo",
            lambda: repo,
        )
        result = CliRunner().invoke(app, ["run-script", "skill:missing", "x.sh"])
        assert result.exit_code != 0

    def test_run_script_rejects_bad_item_form(self):
        from typer.testing import CliRunner
        from aec.cli import app

        result = CliRunner().invoke(app, ["run-script", "no-colon", "x.sh"])
        assert result.exit_code != 0
