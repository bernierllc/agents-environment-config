"""Tests for aec.commands.rules module."""

import json
from pathlib import Path

import pytest

from aec.commands.rules import _strip_frontmatter


class TestStripFrontmatter:
    """Test frontmatter stripping."""

    def test_strips_yaml_frontmatter(self):
        """Should strip YAML frontmatter from content."""
        content = """---
description: Test rule
globs: ["*.py"]
---
# Rule Title

This is the rule content.
"""
        result = _strip_frontmatter(content)

        assert "---" not in result
        assert "description:" not in result
        assert "# Rule Title" in result
        assert "This is the rule content." in result

    def test_handles_no_frontmatter(self):
        """Should return content unchanged if no frontmatter."""
        content = """# Rule Title

This is the rule content.
"""
        result = _strip_frontmatter(content)

        assert result == content

    def test_handles_unclosed_frontmatter(self):
        """Should return original if frontmatter is not closed."""
        content = """---
description: Test rule

# Rule Title

This is missing the closing ---.
"""
        result = _strip_frontmatter(content)

        # Should return original since frontmatter is not properly closed
        assert result == content

    def test_handles_empty_content(self):
        """Should handle empty content."""
        result = _strip_frontmatter("")
        assert result == ""

    def test_handles_only_frontmatter(self):
        """Should handle content that is only frontmatter."""
        content = """---
description: Test
---
"""
        result = _strip_frontmatter(content)

        # Should return empty or whitespace
        assert result.strip() == ""

    def test_preserves_content_after_frontmatter(self):
        """Should preserve all content after frontmatter."""
        content = """---
key: value
---
Line 1
Line 2

Line 4 (after blank)
"""
        result = _strip_frontmatter(content)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 4" in result
        assert "key: value" not in result


class TestRulesPlansSubstitution:
    """Test that rules.generate() substitutes plans dir references."""

    def test_substitutes_plans_dir(self, mock_repo_root, monkeypatch, temp_dir):
        """Should replace ./plans/ with user's chosen dir in generated rules."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        cursor_rules = mock_repo_root / ".cursor" / "rules" / "general"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        (cursor_rules / "test-plans.mdc").write_text(
            "---\ndescription: test\n---\n"
            "Store plans in `./plans/` directory\n"
            "Use `./plans/**/*.md` for organization\n"
        )

        monkeypatch.setattr("aec.commands.rules.get_repo_root", lambda: mock_repo_root)
        from aec.commands.rules import generate
        generate()

        output = (mock_repo_root / ".agent-rules" / "general" / "test-plans.md").read_text()
        assert "./.plans/" in output
        assert "./.plans/**/*.md" in output
        assert "./plans/" not in output

    def test_no_substitution_when_plans_dir_is_plans(self, mock_repo_root, monkeypatch, temp_dir):
        """Should not change anything when user chose plans/ (the default)."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": "plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        cursor_rules = mock_repo_root / ".cursor" / "rules" / "general"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        (cursor_rules / "test-plans.mdc").write_text(
            "---\ndescription: test\n---\n"
            "Store plans in `./plans/` directory\n"
        )

        monkeypatch.setattr("aec.commands.rules.get_repo_root", lambda: mock_repo_root)
        from aec.commands.rules import generate
        generate()

        output = (mock_repo_root / ".agent-rules" / "general" / "test-plans.md").read_text()
        assert "./plans/" in output


class TestRulesCompletionBehavior:
    """Test that rules.generate() applies plans completion behavior."""

    def test_archive_behavior(self, mock_repo_root, monkeypatch, temp_dir):
        """Should change completed to archive when user chose archive."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans", "plans_completion": "archive"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        cursor_rules = mock_repo_root / ".cursor" / "rules" / "general"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        (cursor_rules / "plans-checklists.mdc").write_text(
            "---\ndescription: test\n---\n"
            "### File Completion Process\n"
            "1. When ALL tasks in a plan file are completed `- [x]`:\n"
            "   - **Move file** to `./plans/completed/` directory (if applicable)\n"
        )

        monkeypatch.setattr("aec.commands.rules.get_repo_root", lambda: mock_repo_root)
        from aec.commands.rules import generate
        generate()

        output = (mock_repo_root / ".agent-rules" / "general" / "plans-checklists.md").read_text()
        assert "./.plans/archive/" in output
        assert "Move file" in output
        assert "(if applicable)" not in output

    def test_delete_behavior(self, mock_repo_root, monkeypatch, temp_dir):
        """Should replace with delete instruction when user chose delete."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans", "plans_completion": "delete"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        cursor_rules = mock_repo_root / ".cursor" / "rules" / "general"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        (cursor_rules / "plans-checklists.mdc").write_text(
            "---\ndescription: test\n---\n"
            "### File Completion Process\n"
            "1. When ALL tasks in a plan file are completed `- [x]`:\n"
            "   - **Move file** to `./plans/completed/` directory (if applicable)\n"
        )

        monkeypatch.setattr("aec.commands.rules.get_repo_root", lambda: mock_repo_root)
        from aec.commands.rules import generate
        generate()

        output = (mock_repo_root / ".agent-rules" / "general" / "plans-checklists.md").read_text()
        assert "**Delete the completed plan file**" in output
        assert "Move file" not in output

    def test_no_completion_setting_leaves_original(self, mock_repo_root, monkeypatch, temp_dir):
        """When no plans_completion setting, should leave original text."""
        prefs_file = temp_dir / "preferences.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": "plans"}
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)

        cursor_rules = mock_repo_root / ".cursor" / "rules" / "general"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        (cursor_rules / "plans-checklists.mdc").write_text(
            "---\ndescription: test\n---\n"
            "   - **Move file** to `./plans/completed/` directory (if applicable)\n"
        )

        monkeypatch.setattr("aec.commands.rules.get_repo_root", lambda: mock_repo_root)
        from aec.commands.rules import generate
        generate()

        output = (mock_repo_root / ".agent-rules" / "general" / "plans-checklists.md").read_text()
        assert "completed/" in output
        assert "(if applicable)" in output
