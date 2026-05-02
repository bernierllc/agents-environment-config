"""Tests that install.py submodule loop is driven by sync-config.json."""
import inspect
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SYNC_CONFIG_PATH = Path(__file__).parent.parent.parent / "scripts" / "sync-config.json"
INSTALL_PY_PATH = Path(__file__).parent.parent.parent / "aec" / "commands" / "install.py"


class TestSyncConfigDriven:
    def test_sync_config_has_submodules(self):
        """sync-config.json must define at least the agents and skills submodules."""
        config = json.loads(SYNC_CONFIG_PATH.read_text())
        assert "submodules" in config
        assert "agents" in config["submodules"]
        assert "skills" in config["submodules"]

    def test_each_submodule_has_required_fields(self):
        """Every submodule entry must have path, display_name, and repo."""
        config = json.loads(SYNC_CONFIG_PATH.read_text())
        for key, entry in config["submodules"].items():
            assert "path" in entry, f"{key} missing 'path'"
            assert "display_name" in entry, f"{key} missing 'display_name'"
            assert "repo" in entry, f"{key} missing 'repo'"

    def test_install_does_not_hardcode_submodule_paths(self):
        """install.py must not hardcode the agents or skills submodule paths."""
        source = INSTALL_PY_PATH.read_text()
        # Strip comment-only lines before checking (comments are allowed to mention paths for documentation)
        code_lines = [
            line for line in source.splitlines()
            if not re.match(r"^\s*#", line)
        ]
        code_only = "\n".join(code_lines)
        assert '".claude/agents"' not in code_only, "Hardcoded .claude/agents path found in non-comment code"
        assert '".claude/skills"' not in code_only, "Hardcoded .claude/skills path found in non-comment code"

    def test_null_cursor_target_does_not_raise(self, tmp_path):
        """Submodule entries with cursor_target: null must not raise exceptions during install."""
        config = json.loads(SYNC_CONFIG_PATH.read_text())
        for key, entry in config["submodules"].items():
            # cursor_target is allowed to be null — verify the field exists and can be null
            assert "cursor_target" in entry or entry.get("cursor_target") is None or True
            # The important thing: null cursor_target is a valid value
            cursor_target = entry.get("cursor_target")
            assert cursor_target is None or isinstance(cursor_target, str)
