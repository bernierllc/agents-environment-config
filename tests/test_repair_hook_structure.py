"""Tests for repair_hook_structure and detect_hook_structure_issues.

These cover the legacy flat-shape repair: entries under a Claude matcher
event (PostToolUse, PreToolUse, ...) that have a top-level "command"
instead of a nested "hooks" array. Claude Code refuses to load any
settings file containing this shape, so aec repairs it on update.
"""

import json
from pathlib import Path

from aec.lib.hooks import (
    detect_hook_structure_issues,
    repair_hook_structure,
)


def _write_claude_config(project_dir: Path, config: dict) -> Path:
    config_path = project_dir / ".claude" / "settings.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return config_path


class TestRepairHookStructure:
    def test_fixes_flat_shape_with_command_only(self, temp_dir):
        """Entry with top-level command and no hooks[] should be normalized."""
        project = temp_dir / "project"
        project.mkdir()

        bad = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "command": "npx tsc --noEmit",
                    }
                ]
            }
        }
        config_path = _write_claude_config(project, bad)

        results = repair_hook_structure(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        entry = fixed["hooks"]["PostToolUse"][0]
        assert entry["matcher"] == "Edit|Write"
        assert entry["hooks"] == [
            {"type": "command", "command": "npx tsc --noEmit"}
        ]
        assert "command" not in entry

    def test_fixes_flat_shape_with_type_and_command(self, temp_dir):
        """Flat entry with both 'type' and 'command' at top level."""
        project = temp_dir / "project"
        project.mkdir()

        bad = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Bash",
                        "type": "command",
                        "command": "echo done",
                    }
                ]
            }
        }
        config_path = _write_claude_config(project, bad)

        results = repair_hook_structure(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        entry = fixed["hooks"]["PostToolUse"][0]
        assert entry["hooks"] == [{"type": "command", "command": "echo done"}]
        assert "command" not in entry
        assert "type" not in entry

    def test_real_world_formexpert_two_sibling_entries(self, temp_dir):
        """The exact formexpert.co bug: two flat entries sharing a matcher.

        Standalone normalization: each entry gets its own nested hooks[].
        Duplicate-matcher entries are valid in Claude Code; we don't merge.
        """
        project = temp_dir / "project"
        project.mkdir()

        bad = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "command": "npx tsc --noEmit --pretty 2>&1 | head -20",
                    },
                    {
                        "matcher": "Edit|Write",
                        "command": (
                            'if echo "$CLAUDE_FILE_PATH" | grep -q '
                            '"docs/verification/"; then echo sync; fi'
                        ),
                    },
                ]
            }
        }
        config_path = _write_claude_config(project, bad)

        results = repair_hook_structure(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        entries = fixed["hooks"]["PostToolUse"]
        assert len(entries) == 2
        for entry in entries:
            assert entry["matcher"] == "Edit|Write"
            assert isinstance(entry["hooks"], list)
            assert len(entry["hooks"]) == 1
            assert entry["hooks"][0]["type"] == "command"
            assert "command" not in entry  # top-level command removed

    def test_preserves_extra_inner_keys(self, temp_dir):
        """Unknown keys at the entry level should move into the inner hook.

        e.g. 'name' or 'timeout' that the user added — don't drop them.
        """
        project = temp_dir / "project"
        project.mkdir()

        bad = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit",
                        "command": "echo hi",
                        "name": "greet",
                        "timeout": 5,
                    }
                ]
            }
        }
        config_path = _write_claude_config(project, bad)

        results = repair_hook_structure(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        inner = fixed["hooks"]["PostToolUse"][0]["hooks"][0]
        assert inner["name"] == "greet"
        assert inner["timeout"] == 5
        assert inner["command"] == "echo hi"

    def test_already_correct_returns_ok_and_no_write(self, temp_dir):
        """A correctly-nested config should not be rewritten."""
        project = temp_dir / "project"
        project.mkdir()

        good = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {"type": "command", "command": "npx tsc --noEmit"}
                        ],
                    }
                ]
            }
        }
        config_path = _write_claude_config(project, good)
        original = config_path.read_text()

        results = repair_hook_structure(project)
        assert results["claude"] == "ok"
        assert config_path.read_text() == original

    def test_idempotent_two_passes(self, temp_dir):
        """Running repair twice should be a no-op the second time."""
        project = temp_dir / "project"
        project.mkdir()

        bad = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit", "command": "echo a"},
                ]
            }
        }
        _write_claude_config(project, bad)

        first = repair_hook_structure(project)
        second = repair_hook_structure(project)
        assert first["claude"] == "fixed"
        assert second["claude"] == "ok"

    def test_no_file_returns_no_file(self, temp_dir):
        project = temp_dir / "project"
        project.mkdir()
        results = repair_hook_structure(project)
        assert results["claude"] == "no_file"

    def test_invalid_json_returns_error(self, temp_dir):
        project = temp_dir / "project"
        project.mkdir()
        config_path = project / ".claude" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("{ not json")

        results = repair_hook_structure(project)
        assert results["claude"].startswith("error:")

    def test_ignores_non_matcher_events(self, temp_dir):
        """Notification/Stop events don't use matchers — leave them alone."""
        project = temp_dir / "project"
        project.mkdir()

        config = {
            "hooks": {
                "Notification": [
                    {"command": "echo hi"},
                ],
                "Stop": [
                    {"command": "echo bye"},
                ],
            }
        }
        config_path = _write_claude_config(project, config)
        original = config_path.read_text()

        results = repair_hook_structure(project)
        assert results["claude"] == "ok"
        assert config_path.read_text() == original

    def test_preserves_unrelated_hook_events(self, temp_dir):
        """Repairing PostToolUse must not touch other events."""
        project = temp_dir / "project"
        project.mkdir()

        config = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit", "command": "echo a"},
                ],
                "Notification": [
                    {"command": "echo notify"},
                ],
            }
        }
        config_path = _write_claude_config(project, config)

        results = repair_hook_structure(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        # PostToolUse normalized
        assert fixed["hooks"]["PostToolUse"][0]["hooks"] == [
            {"type": "command", "command": "echo a"}
        ]
        # Notification untouched
        assert fixed["hooks"]["Notification"] == [{"command": "echo notify"}]

    def test_preserves_other_top_level_keys(self, temp_dir):
        """permissions, env, etc. must survive the repair."""
        project = temp_dir / "project"
        project.mkdir()

        config = {
            "permissions": {"allow": ["Bash"]},
            "env": {"FOO": "bar"},
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit", "command": "echo a"},
                ]
            },
        }
        config_path = _write_claude_config(project, config)

        results = repair_hook_structure(project)
        assert results["claude"] == "fixed"

        fixed = json.loads(config_path.read_text())
        assert fixed["permissions"] == {"allow": ["Bash"]}
        assert fixed["env"] == {"FOO": "bar"}

    def test_handles_hooks_not_dict(self, temp_dir):
        """If hooks is somehow a string/list, return ok and don't crash."""
        project = temp_dir / "project"
        project.mkdir()
        _write_claude_config(project, {"hooks": "not a dict"})
        results = repair_hook_structure(project)
        assert results["claude"] == "ok"

    def test_handles_entry_without_command_or_hooks(self, temp_dir):
        """An entry missing both command and hooks[] is left alone.

        We don't invent content — the validator in Claude Code can flag it.
        """
        project = temp_dir / "project"
        project.mkdir()

        config = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit"},  # no command, no hooks
                ]
            }
        }
        config_path = _write_claude_config(project, config)

        results = repair_hook_structure(project)
        assert results["claude"] == "ok"
        fixed = json.loads(config_path.read_text())
        # File should not be rewritten — leave the bad entry visible.
        assert fixed == config


class TestDetectHookStructureIssues:
    def test_reports_flat_shape(self, temp_dir):
        project = temp_dir / "project"
        project.mkdir()
        _write_claude_config(
            project,
            {
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Edit", "command": "echo a"},
                    ]
                }
            },
        )

        issues = detect_hook_structure_issues(project)
        assert "claude" in issues
        assert len(issues["claude"]) == 1
        assert "PostToolUse[0]" in issues["claude"][0]
        assert "flat shape" in issues["claude"][0]

    def test_no_issues_for_correct_config(self, temp_dir):
        project = temp_dir / "project"
        project.mkdir()
        _write_claude_config(
            project,
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Edit",
                            "hooks": [{"type": "command", "command": "x"}],
                        }
                    ]
                }
            },
        )
        assert detect_hook_structure_issues(project) == {}

    def test_no_issues_when_no_file(self, temp_dir):
        project = temp_dir / "project"
        project.mkdir()
        assert detect_hook_structure_issues(project) == {}

    def test_does_not_modify_file(self, temp_dir):
        """Detect must be read-only."""
        project = temp_dir / "project"
        project.mkdir()
        config_path = _write_claude_config(
            project,
            {
                "hooks": {
                    "PostToolUse": [
                        {"matcher": "Edit", "command": "echo a"},
                    ]
                }
            },
        )
        original = config_path.read_text()
        detect_hook_structure_issues(project)
        assert config_path.read_text() == original
