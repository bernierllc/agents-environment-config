"""Tests for repair_hook_keys in aec.lib.hooks."""

import json
from pathlib import Path

import pytest

from aec.lib.hooks import repair_hook_keys, HOOK_KEY_FIXES, AGENT_HOOK_CONFIGS


class TestRepairHookKeys:
    """Test the repair_hook_keys function."""

    def _create_claude_config(self, project_dir: Path, config: dict) -> Path:
        """Helper: write a .claude/settings.json with given config."""
        config_path = project_dir / ".claude" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return config_path

    def test_fixes_camel_case_post_tool_use(self, temp_dir):
        """Should rename postToolUse to PostToolUse."""
        project = temp_dir / "project"
        project.mkdir()

        bad_config = {
            "hooks": {
                "postToolUse": [{
                    "matcher": "Edit|Write",
                    "hooks": [{"type": "command", "command": "npx tsc --noEmit"}],
                }],
            },
        }
        config_path = self._create_claude_config(project, bad_config)

        results = repair_hook_keys(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        assert "PostToolUse" in fixed["hooks"]
        assert "postToolUse" not in fixed["hooks"]
        # Verify content was preserved
        assert fixed["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"

    def test_no_change_when_already_correct(self, temp_dir):
        """Should return 'ok' when keys are already PascalCase."""
        project = temp_dir / "project"
        project.mkdir()

        good_config = {
            "hooks": {
                "PostToolUse": [{
                    "matcher": "Edit|Write",
                    "hooks": [{"type": "command", "command": "npx tsc --noEmit"}],
                }],
            },
        }
        config_path = self._create_claude_config(project, good_config)
        original_content = config_path.read_text()

        results = repair_hook_keys(project)
        assert results["claude"] == "ok"

        # File should be unchanged
        assert config_path.read_text() == original_content

    def test_no_file_returns_no_file(self, temp_dir):
        """Should return 'no_file' when config doesn't exist."""
        project = temp_dir / "project"
        project.mkdir()

        results = repair_hook_keys(project)
        assert results["claude"] == "no_file"

    def test_preserves_other_keys(self, temp_dir):
        """Should preserve non-hook keys in the config."""
        project = temp_dir / "project"
        project.mkdir()

        config = {
            "permissions": {"allow": ["Bash", "Read"]},
            "hooks": {
                "postToolUse": [{
                    "matcher": "Edit|Write",
                    "hooks": [{"type": "command", "command": "npx tsc --noEmit"}],
                }],
            },
        }
        config_path = self._create_claude_config(project, config)

        results = repair_hook_keys(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        assert fixed["permissions"] == {"allow": ["Bash", "Read"]}
        assert "PostToolUse" in fixed["hooks"]

    def test_fixes_multiple_bad_keys(self, temp_dir):
        """Should fix multiple camelCase keys in one pass."""
        project = temp_dir / "project"
        project.mkdir()

        config = {
            "hooks": {
                "postToolUse": [{"matcher": "Edit|Write", "hooks": []}],
                "preToolUse": [{"matcher": "Bash", "hooks": []}],
            },
        }
        config_path = self._create_claude_config(project, config)

        results = repair_hook_keys(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        assert "PostToolUse" in fixed["hooks"]
        assert "PreToolUse" in fixed["hooks"]
        assert "postToolUse" not in fixed["hooks"]
        assert "preToolUse" not in fixed["hooks"]

    def test_handles_invalid_json(self, temp_dir):
        """Should return error status for invalid JSON."""
        project = temp_dir / "project"
        project.mkdir()

        config_path = project / ".claude" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("not valid json {{{")

        results = repair_hook_keys(project)
        assert results["claude"].startswith("error:")

    def test_handles_no_hooks_key(self, temp_dir):
        """Should return 'ok' when config has no hooks key."""
        project = temp_dir / "project"
        project.mkdir()

        config = {"permissions": {"allow": ["Bash"]}}
        self._create_claude_config(project, config)

        results = repair_hook_keys(project)
        assert results["claude"] == "ok"

    def test_handles_hooks_not_dict(self, temp_dir):
        """Should return 'ok' when hooks value is not a dict."""
        project = temp_dir / "project"
        project.mkdir()

        config = {"hooks": "not a dict"}
        self._create_claude_config(project, config)

        results = repair_hook_keys(project)
        assert results["claude"] == "ok"

    def test_real_world_barevents_config(self, temp_dir):
        """Test with the exact config that caused the original bug."""
        project = temp_dir / "project"
        project.mkdir()

        # This is the exact config from the barevents repo
        bad_config = {
            "hooks": {
                "postToolUse": [{
                    "matcher": "Edit|Write",
                    "hooks": [{
                        "type": "command",
                        "command": (
                            'file="$CLAUDE_FILE_PATH"; '
                            'if echo "$file" | grep -qE \'\\.(ts|tsx|js|jsx)$\'; '
                            'then cd venues && npx tsc --noEmit --pretty 2>&1 | head -20; '
                            'elif echo "$file" | grep -qE \'\\.py$\'; '
                            'then cd admin && python -m py_compile "$file" 2>&1 | head -20; fi'
                        ),
                    }],
                }],
            },
        }
        config_path = self._create_claude_config(project, bad_config)

        results = repair_hook_keys(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        assert "PostToolUse" in fixed["hooks"]
        assert "postToolUse" not in fixed["hooks"]
        # Verify the complex command survived
        assert "CLAUDE_FILE_PATH" in fixed["hooks"]["PostToolUse"][0]["hooks"][0]["command"]


class TestHookKeyFixesMatchesTemplate:
    """Verify HOOK_KEY_FIXES covers all keys generated by templates.

    This ensures the fix map stays in sync with what we actually generate.
    """

    def test_claude_template_key_is_pascal_case(self):
        """The claude template must use PascalCase PostToolUse."""
        config = AGENT_HOOK_CONFIGS["claude"]["template"](["echo test"])
        hook_keys = list(config["hooks"].keys())
        for key in hook_keys:
            assert key[0].isupper(), f"Template key '{key}' should be PascalCase"

    def test_fix_map_contains_pascal_case_values(self):
        """All fix values should be PascalCase."""
        for agent_key, fixes in HOOK_KEY_FIXES.items():
            for bad, good in fixes.items():
                assert good[0].isupper(), f"Fix value '{good}' should be PascalCase"
                assert bad[0].islower(), f"Fix key '{bad}' should be camelCase"
