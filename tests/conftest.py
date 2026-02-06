"""Pytest fixtures for aec tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_home(temp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock the home directory for testing."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    return temp_dir


@pytest.fixture
def mock_repo_root(temp_dir: Path) -> Path:
    """Create a mock repository structure."""
    repo = temp_dir / "repo"
    repo.mkdir()

    # Create minimal repo structure
    (repo / ".git").mkdir()
    (repo / "CLAUDE.md").write_text("# Test")
    (repo / "aec").mkdir()

    # Create .cursor/rules structure
    cursor_rules = repo / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "test.mdc").write_text("""---
description: Test rule
---
# Test Rule
This is a test rule.
""")

    # Create .agent-rules structure
    agent_rules = repo / ".agent-rules"
    agent_rules.mkdir()
    (agent_rules / "test.md").write_text("""# Test Rule
This is a test rule.
""")

    # Create .claude directories
    (repo / ".claude" / "agents").mkdir(parents=True)
    (repo / ".claude" / "skills").mkdir(parents=True)

    # Create .cursor/commands
    (repo / ".cursor" / "commands").mkdir(parents=True)

    return repo


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove environment variables that might affect tests."""
    for var in ["PROJECTS_DIR", "GITHUB_ORGS", "NO_COLOR"]:
        monkeypatch.delenv(var, raising=False)
