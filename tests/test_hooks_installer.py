"""Tests for aec.lib.hooks.installer end-to-end install/remove."""

import json
from pathlib import Path


def _write_item(item_dir: Path, *, hooks: list) -> None:
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "hooks.json").write_text(json.dumps({
        "$schema": "x", "version": "1.0.0", "hooks": hooks,
    }))


class TestInstallItemHooksClaude:
    def test_installs_generic_claude_hook_end_to_end(self, tmp_path):
        from aec.lib.hooks.installer import install_item_hooks
        item_dir = tmp_path / "item"
        _write_item(item_dir, hooks=[{
            "id": "lint", "event": "on_file_edit",
            "command": "echo hi", "description": "lint",
        }])
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["claude"],
        )

        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert settings["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write|MultiEdit"
        assert settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == "echo hi"

        state_path = repo_root / ".aec/installed-hooks/skill.demo.json"
        state = json.loads(state_path.read_text())
        assert state["item_version"] == "1.0.0"
        assert state["agents_targeted"] == ["claude"]
        assert len(state["hooks_installed"]) == 1
        assert state["hooks_installed"][0]["hook_id"] == "lint"
        assert state["hooks_installed"][0]["agent"] == "claude"
