"""Tests for source management (fetch, discover available items)."""

import pytest
from pathlib import Path


@pytest.fixture
def skills_source(temp_dir):
    source = temp_dir / "skills"
    source.mkdir()
    skill = source / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 2.0.0\ndescription: A skill\nauthor: Test\n---\n# My Skill"
    )
    group = source / "doc-skills"
    group.mkdir()
    nested = group / "pdf"
    nested.mkdir()
    (nested / "SKILL.md").write_text(
        "---\nname: doc-skills:pdf\nversion: 1.0.0\ndescription: PDF skill\nauthor: Test\n---\n# PDF"
    )
    return source


@pytest.fixture
def rules_source(temp_dir):
    source = temp_dir / "rules"
    source.mkdir()
    ts_dir = source / "languages" / "typescript"
    ts_dir.mkdir(parents=True)
    (ts_dir / "typing-standards.md").write_text(
        "---\nname: typescript/typing-standards\nversion: 1.0.0\ndescription: TS typing rules\n---\n# TS Standards"
    )
    return source


@pytest.fixture
def agents_source(temp_dir):
    source = temp_dir / "agents"
    source.mkdir()
    (source / "code-reviewer.md").write_text(
        "---\nname: code-reviewer\nversion: 1.0.0\ndescription: Reviews code\n---\n# Reviewer"
    )
    return source


class TestDiscoverAvailable:
    def test_discovers_skills(self, skills_source):
        from aec.lib.sources import discover_available
        available = discover_available(skills_source, item_type="skills")
        assert "my-skill" in available
        assert available["my-skill"]["version"] == "2.0.0"

    def test_discovers_nested_skills(self, skills_source):
        from aec.lib.sources import discover_available
        available = discover_available(skills_source, item_type="skills")
        assert "doc-skills:pdf" in available

    def test_discovers_rules(self, rules_source):
        from aec.lib.sources import discover_available
        available = discover_available(rules_source, item_type="rules")
        assert "languages/typescript/typing-standards" in available

    def test_discovers_agents(self, agents_source):
        from aec.lib.sources import discover_available
        available = discover_available(agents_source, item_type="agents")
        assert "code-reviewer" in available
        assert available["code-reviewer"]["version"] == "1.0.0"

    def test_returns_empty_for_missing_dir(self, temp_dir):
        from aec.lib.sources import discover_available
        result = discover_available(temp_dir / "nonexistent", item_type="skills")
        assert result == {}

    def test_returns_empty_for_unknown_type(self, temp_dir):
        from aec.lib.sources import discover_available
        result = discover_available(temp_dir, item_type="unknown")
        assert result == {}


class TestStalenessCheck:
    def test_stale_when_never_checked(self):
        from aec.lib.sources import check_staleness
        assert check_staleness({"lastUpdateCheck": None}) is True

    def test_not_stale_when_recent(self):
        from aec.lib.sources import check_staleness
        from datetime import datetime, timezone
        assert check_staleness({"lastUpdateCheck": datetime.now(timezone.utc).isoformat()}) is False
