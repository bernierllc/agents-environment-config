"""Tests for optional rule installation during repo setup."""

import json
from pathlib import Path

import pytest


class TestCopyOptionalRules:
    """Test that enabled optional rules are copied to projects."""

    def test_copies_enabled_rule_mdc(self, temp_dir, monkeypatch):
        """Should copy .mdc file to project .cursor/rules/ when rule is enabled."""
        # Setup: preferences with leave-it-better enabled
        prefs_file = temp_dir / "prefs" / "preferences.json"
        prefs_file.parent.mkdir(parents=True)
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": True, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        # Setup: mock repo root with the rule file
        repo_root = temp_dir / "repo"
        rule_src = repo_root / ".cursor" / "rules" / "general" / "leave-it-better.mdc"
        rule_src.parent.mkdir(parents=True)
        rule_src.write_text("---\nalwaysApply: true\n---\n# Leave It Better\nContent here.")

        # Setup: project directory
        project_dir = temp_dir / "my-project"
        cursor_rules_dir = project_dir / ".cursor" / "rules" / "general"
        cursor_rules_dir.mkdir(parents=True)

        from aec.commands.repo import _copy_optional_rules

        _copy_optional_rules(project_dir, repo_root)

        target = cursor_rules_dir / "leave-it-better.mdc"
        assert target.exists()
        assert "Leave It Better" in target.read_text()

    def test_skips_disabled_rule(self, temp_dir, monkeypatch):
        """Should NOT copy .mdc file when rule is disabled."""
        prefs_file = temp_dir / "prefs" / "preferences.json"
        prefs_file.parent.mkdir(parents=True)
        prefs_file.write_text(json.dumps({
            "schema_version": "1.0",
            "optional_rules": {
                "leave-it-better": {"enabled": False, "asked_at": "2026-01-01T00:00:00Z"}
            }
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        repo_root = temp_dir / "repo"
        rule_src = repo_root / ".cursor" / "rules" / "general" / "leave-it-better.mdc"
        rule_src.parent.mkdir(parents=True)
        rule_src.write_text("# Leave It Better")

        project_dir = temp_dir / "my-project"
        cursor_rules_dir = project_dir / ".cursor" / "rules" / "general"
        cursor_rules_dir.mkdir(parents=True)

        from aec.commands.repo import _copy_optional_rules

        _copy_optional_rules(project_dir, repo_root)

        target = cursor_rules_dir / "leave-it-better.mdc"
        assert not target.exists()

    def test_skips_when_not_asked(self, temp_dir, monkeypatch):
        """Should NOT copy when user hasn't been asked yet."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        repo_root = temp_dir / "repo"
        rule_src = repo_root / ".cursor" / "rules" / "general" / "leave-it-better.mdc"
        rule_src.parent.mkdir(parents=True)
        rule_src.write_text("# Leave It Better")

        project_dir = temp_dir / "my-project"
        cursor_rules_dir = project_dir / ".cursor" / "rules" / "general"
        cursor_rules_dir.mkdir(parents=True)

        from aec.commands.repo import _copy_optional_rules

        _copy_optional_rules(project_dir, repo_root)

        target = cursor_rules_dir / "leave-it-better.mdc"
        assert not target.exists()
