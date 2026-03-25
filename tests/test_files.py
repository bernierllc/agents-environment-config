"""Tests for aec files generate command."""

import pytest
from pathlib import Path
from unittest.mock import patch


class TestOrganizeRules:
    """Test rule organization from .cursor/rules/."""

    def test_organize_rules_returns_categories(self, tmp_path):
        """organize_rules returns dict with expected category keys."""
        from aec.lib.agent_files import organize_rules

        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)

        result = organize_rules(rules_dir)

        assert "general" in result
        assert "languages" in result
        assert "stacks" in result
        assert "frameworks" in result
        assert "topics" in result
        assert "packages" in result

    def test_organize_rules_finds_mdc_files(self, tmp_path):
        """organize_rules finds and categorizes .mdc files."""
        from aec.lib.agent_files import organize_rules

        rules_dir = tmp_path / ".cursor" / "rules"
        general_dir = rules_dir / "general"
        general_dir.mkdir(parents=True)

        rule_content = "---\ndescription: Test rule\nalwaysApply: true\n---\n# Test\n\nContent here."
        (general_dir / "test-rule.mdc").write_text(rule_content)

        result = organize_rules(rules_dir)

        assert len(result["general"]) == 1
        assert result["general"][0][0] == "general/test-rule.mdc"

    def test_organize_rules_skips_readme(self, tmp_path):
        """organize_rules skips README.mdc files."""
        from aec.lib.agent_files import organize_rules

        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)

        (rules_dir / "README.mdc").write_text("---\ndescription: Readme\n---\n# Readme")

        result = organize_rules(rules_dir)

        total = sum(len(v) for v in result.values())
        assert total == 0

    def test_organize_rules_empty_dir(self, tmp_path):
        """organize_rules handles empty rules directory."""
        from aec.lib.agent_files import organize_rules

        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)

        result = organize_rules(rules_dir)

        total = sum(len(v) for v in result.values())
        assert total == 0


class TestParseFrontmatter:
    """Test frontmatter parsing."""

    def test_parse_valid_frontmatter(self):
        """parse_frontmatter extracts YAML frontmatter."""
        from aec.lib.agent_files import parse_frontmatter

        content = "---\ndescription: My Rule\nalwaysApply: true\n---\n# Body\n\nContent."
        fm, body = parse_frontmatter(content)

        assert fm is not None
        assert fm["description"] == "My Rule"
        assert fm["alwaysApply"] is True
        assert body.startswith("# Body")

    def test_parse_no_frontmatter(self):
        """parse_frontmatter returns None for content without frontmatter."""
        from aec.lib.agent_files import parse_frontmatter

        content = "# No frontmatter\n\nJust content."
        fm, body = parse_frontmatter(content)

        assert fm is None
        assert body == content


class TestGenerateAgentFile:
    """Test agent file generation."""

    def test_generate_includes_agent_name(self):
        """Generated file includes agent name in title."""
        from aec.lib.agent_files import generate_agent_file

        content = generate_agent_file("Claude Code", {})

        assert "# Claude Code Agent Instructions" in content

    def test_generate_includes_agentinfo_reference(self):
        """Generated file references AGENTINFO.md."""
        from aec.lib.agent_files import generate_agent_file

        content = generate_agent_file("Test Agent", {})

        assert "AGENTINFO.md" in content

    def test_generate_includes_regeneration_command(self):
        """Generated file includes the CLI regeneration command."""
        from aec.lib.agent_files import generate_agent_file

        content = generate_agent_file("Test Agent", {})

        assert "aec files generate" in content

    def test_generate_with_agent_rules_references_home_dir(self):
        """When use_agent_rules=True, references ~/.agent-tools/ paths."""
        from aec.lib.agent_files import generate_agent_file

        content = generate_agent_file("Claude Code", {}, use_agent_rules=True)

        assert "~/.agent-tools/rules/agents-environment-config" in content

    def test_generate_without_agent_rules_references_cursor(self):
        """When use_agent_rules=False, references .cursor/rules/ paths."""
        from aec.lib.agent_files import generate_agent_file

        content = generate_agent_file("Cursor", {}, use_agent_rules=False)

        assert ".cursor/rules" in content


class TestGenerateAll:
    """Test full generation pipeline."""

    def test_generate_all_produces_files(self, tmp_path):
        """generate_all produces files for each agent in registry."""
        from aec.lib.agent_files import generate_all

        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)

        agents = {
            "CLAUDE.md": ("Claude Code", True),
            "AGENTS.md": ("Codex", True),
        }

        results = generate_all(tmp_path, agents=agents)

        assert "CLAUDE.md" in results
        assert "AGENTS.md" in results
        assert "Claude Code" in results["CLAUDE.md"]
        assert "Codex" in results["AGENTS.md"]

    def test_generate_all_raises_on_missing_rules_dir(self, tmp_path):
        """generate_all raises FileNotFoundError when rules dir missing."""
        from aec.lib.agent_files import generate_all

        with pytest.raises(FileNotFoundError):
            generate_all(tmp_path, agents={"CLAUDE.md": ("Claude", True)})


class TestGenerateCommand:
    """Test the CLI command integration."""

    def test_generate_command_writes_to_templates(self, tmp_path, monkeypatch):
        """generate() command writes files to templates/ directory."""
        from aec.commands.files import generate

        # Create minimal repo structure
        rules_dir = tmp_path / ".cursor" / "rules" / "general"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test.mdc").write_text(
            "---\ndescription: Test\nalwaysApply: true\n---\n# Test"
        )

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        monkeypatch.setattr("aec.commands.files.get_repo_root", lambda: tmp_path)

        # Mock the registry to return a simple agent set
        agents = {"TEST.md": ("Test Agent", True)}
        monkeypatch.setattr(
            "aec.lib.registry.get_generation_agents", lambda: agents
        )

        generate()

        output = templates_dir / "TEST.md"
        assert output.exists()
        content = output.read_text()
        assert "Test Agent" in content
