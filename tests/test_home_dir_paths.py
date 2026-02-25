"""Tests for home directory path references in agent files and repo setup."""

import importlib.util
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


HOME_RULES_DIR = "~/.agent-tools/rules/agents-environment-config"

# Import generate_agent_files from scripts/ (not a Python package)
_script_path = Path(__file__).parent.parent / "scripts" / "generate-agent-files.py"
_spec = importlib.util.spec_from_file_location("generate_agent_files", _script_path)
generate_agent_files_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_agent_files_mod)


class TestGenerateReferenceOnlyContent:
    """Test that generate_reference_only_content produces home dir paths."""

    def test_uses_home_dir_paths_when_use_agent_rules(self):
        """Generated content should reference ~/.agent-tools/... not .agent-rules/."""
        generate_reference_only_content = generate_agent_files_mod.generate_reference_only_content

        # Minimal organized_rules with one category
        organized_rules = {
            "general": [("general/architecture.mdc", {}, "body")],
            "languages": [],
            "stacks": [],
            "frameworks": [("frameworks/testing/standards.mdc", {}, "body")],
            "topics": [],
            "packages": [],
        }

        content = generate_reference_only_content(organized_rules, use_agent_rules=True)

        assert HOME_RULES_DIR in content
        assert ".agent-rules/" not in content

    def test_essential_rules_use_home_dir_paths(self):
        """Essential rules section should have full home dir paths."""
        generate_reference_only_content = generate_agent_files_mod.generate_reference_only_content

        organized_rules = {
            "general": [],
            "languages": [],
            "stacks": [],
            "frameworks": [],
            "topics": [],
            "packages": [],
        }

        content = generate_reference_only_content(organized_rules, use_agent_rules=True)

        # Check specific essential rule paths
        assert f"`{HOME_RULES_DIR}/frameworks/testing/standards.md`" in content
        assert f"`{HOME_RULES_DIR}/languages/typescript/typing-standards.md`" in content
        assert f"`{HOME_RULES_DIR}/general/architecture.md`" in content
        assert f"`{HOME_RULES_DIR}/topics/git/workflow.md`" in content
        assert f"`{HOME_RULES_DIR}/topics/quality/gates.md`" in content

    def test_how_to_use_rules_uses_home_dir_paths(self):
        """How to Use Rules section should reference home dir paths."""
        generate_reference_only_content = generate_agent_files_mod.generate_reference_only_content

        organized_rules = {
            "general": [],
            "languages": [],
            "stacks": [],
            "frameworks": [],
            "topics": [],
            "packages": [],
        }

        content = generate_reference_only_content(organized_rules, use_agent_rules=True)

        assert f"`{HOME_RULES_DIR}/languages/typescript/typing-standards.md`" in content
        assert f"`{HOME_RULES_DIR}/frameworks/database/connection-management.md`" in content

    def test_cursor_mode_still_uses_cursor_paths(self):
        """When use_agent_rules=False, should still use .cursor/rules/ paths."""
        generate_reference_only_content = generate_agent_files_mod.generate_reference_only_content

        organized_rules = {
            "general": [],
            "languages": [],
            "stacks": [],
            "frameworks": [],
            "topics": [],
            "packages": [],
        }

        content = generate_reference_only_content(organized_rules, use_agent_rules=False)

        assert ".cursor/rules/" in content
        assert HOME_RULES_DIR not in content


class TestGenerateAgentFile:
    """Test that generate_agent_file uses correct paths."""

    def test_quick_start_uses_home_dir_glob(self):
        """Quick Start section should reference ~/.agent-tools/... glob."""
        generate_agent_file = generate_agent_files_mod.generate_agent_file

        organized_rules = {
            "general": [],
            "languages": [],
            "stacks": [],
            "frameworks": [],
            "topics": [],
            "packages": [],
        }

        content = generate_agent_file(
            "Test Agent",
            organized_rules,
            Path("/tmp/fake"),
            use_agent_rules=True,
        )

        assert f"`{HOME_RULES_DIR}/*.md`" in content
        assert ".agent-rules/*.md" not in content


class TestSetupPrerequisiteCheck:
    """Test that repo setup checks for aec install prerequisite."""

    def test_fails_when_rules_not_installed(self, temp_dir, monkeypatch):
        """Setup should fail early when ~/.agent-tools/rules/... doesn't exist."""
        from aec.commands.repo import setup

        # Mock get_repo_root to return a valid path
        repo_root = temp_dir / "repo"
        repo_root.mkdir()
        (repo_root / ".agent-rules").mkdir()
        (repo_root / "aec").mkdir()
        monkeypatch.setattr("aec.commands.repo.get_repo_root", lambda: repo_root)

        # AGENT_TOOLS_DIR points to a non-existent dir
        fake_tools = temp_dir / "nonexistent-agent-tools"
        monkeypatch.setattr("aec.commands.repo.AGENT_TOOLS_DIR", fake_tools)

        project_dir = temp_dir / "my-project"
        project_dir.mkdir()

        with pytest.raises(SystemExit):
            setup(str(project_dir))

    def test_succeeds_when_rules_installed(self, temp_dir, monkeypatch):
        """Setup should proceed when prerequisite directory exists."""
        from aec.commands.repo import setup

        # Mock get_repo_root
        repo_root = temp_dir / "repo"
        repo_root.mkdir()
        (repo_root / ".agent-rules").mkdir()
        (repo_root / "aec").mkdir()
        (repo_root / ".git").mkdir()
        (repo_root / "CLAUDE.md").write_text("# Test")
        monkeypatch.setattr("aec.commands.repo.get_repo_root", lambda: repo_root)

        # Create the prerequisite directory
        fake_tools = temp_dir / "agent-tools"
        rules_dir = fake_tools / "rules" / "agents-environment-config"
        rules_dir.mkdir(parents=True)
        monkeypatch.setattr("aec.commands.repo.AGENT_TOOLS_DIR", fake_tools)

        # Mock is_logged to avoid "already set up" flow
        monkeypatch.setattr("aec.commands.repo.is_logged", lambda p: False)

        # Mock input to avoid interactive prompts
        monkeypatch.setattr("builtins.input", lambda _: "n")

        project_dir = temp_dir / "my-project"
        project_dir.mkdir()

        # Should not raise SystemExit for the prerequisite check
        # (may raise for other reasons like skipping raycast, but that's fine)
        try:
            setup(str(project_dir), skip_raycast=True)
        except SystemExit:
            pytest.fail("setup() raised SystemExit despite rules being installed")


class TestMigrateAgentFiles:
    """Test migration from old path formats to home dir paths."""

    def test_migrates_agent_rules_to_home_dir(self, temp_dir):
        """Should migrate .agent-rules/ paths to ~/.agent-tools/... paths."""
        from aec.commands.repo import _migrate_agent_files

        # Create a file with old .agent-rules/ paths
        project_dir = temp_dir / "project"
        project_dir.mkdir()

        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text(
            "Read `.agent-rules/frameworks/testing/standards.md`\n"
            "Rules are organized in `.agent-rules/` and read on demand.\n"
            "Read relevant `.agent-rules/*.md` files.\n"
        )

        # Patch get_migration_files to return our test file
        with patch("aec.commands.repo.get_migration_files", return_value=["CLAUDE.md"]):
            changes = _migrate_agent_files(project_dir)

        content = claude_md.read_text()
        assert HOME_RULES_DIR in content
        assert ".agent-rules/" not in content or "~/.agent-tools/" in content
        assert changes == 1

    def test_migrates_cursor_rules_to_home_dir(self, temp_dir):
        """Should migrate .cursor/rules/*.mdc paths to ~/.agent-tools/... paths."""
        from aec.commands.repo import _migrate_agent_files

        project_dir = temp_dir / "project"
        project_dir.mkdir()

        agents_md = project_dir / "AGENTS.md"
        agents_md.write_text(
            "Read `.cursor/rules/frameworks/testing/standards.mdc`\n"
            "Rules are organized in `.cursor/rules/` and read on demand.\n"
        )

        with patch("aec.commands.repo.get_migration_files", return_value=["AGENTS.md"]):
            changes = _migrate_agent_files(project_dir)

        content = agents_md.read_text()
        assert HOME_RULES_DIR in content
        assert ".cursor/rules/" not in content
        assert ".mdc" not in content
        assert changes == 1

    def test_no_migration_when_already_current(self, temp_dir):
        """Should report no changes when paths already use home dir."""
        from aec.commands.repo import _migrate_agent_files

        project_dir = temp_dir / "project"
        project_dir.mkdir()

        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text(
            f"Read `{HOME_RULES_DIR}/frameworks/testing/standards.md`\n"
        )

        with patch("aec.commands.repo.get_migration_files", return_value=["CLAUDE.md"]):
            changes = _migrate_agent_files(project_dir)

        assert changes == 0


class TestNeedsMigration:
    """Test _needs_migration detection."""

    def test_detects_agent_rules_paths(self, temp_dir):
        """Should detect .agent-rules/ paths as needing migration."""
        from aec.commands.repo import _needs_migration

        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "CLAUDE.md").write_text(
            "Read `.agent-rules/frameworks/testing/standards.md`"
        )

        with patch("aec.commands.repo.get_migration_files", return_value=["CLAUDE.md"]):
            assert _needs_migration(project_dir) is True

    def test_detects_cursor_rules_paths(self, temp_dir):
        """Should detect .cursor/rules/*.mdc paths as needing migration."""
        from aec.commands.repo import _needs_migration

        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "CLAUDE.md").write_text(
            "Read `.cursor/rules/testing/standards.mdc`"
        )

        with patch("aec.commands.repo.get_migration_files", return_value=["CLAUDE.md"]):
            assert _needs_migration(project_dir) is True

    def test_no_migration_needed_for_home_dir_paths(self, temp_dir):
        """Should not flag migration when already using home dir paths."""
        from aec.commands.repo import _needs_migration

        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "CLAUDE.md").write_text(
            f"Read `{HOME_RULES_DIR}/frameworks/testing/standards.md`"
        )

        with patch("aec.commands.repo.get_migration_files", return_value=["CLAUDE.md"]):
            assert _needs_migration(project_dir) is False
