"""Pytest fixtures for aec tests."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

# Point HOME at a throwaway directory before anything imports aec.
# aec.lib.config derives every state path (~/.agents-environment-config,
# ~/.agent-tools, ~/.claude, ...) from Path.home() at import time and 17
# modules import those paths by value, so this must happen here, first.
# Without it, tests wrote fixtures such as "dep-skill" into the developer's
# real installed-*.json, and concurrent runs raced on the same temp files.
_REAL_HOME = os.environ.get("HOME", "")
# realpath: on macOS /var is a symlink to /private/var, and code that resolves
# paths must agree with Path.home().
_TEST_HOME = os.path.realpath(tempfile.mkdtemp(prefix="aec-test-home-"))
os.environ["HOME"] = _TEST_HOME
os.environ["USERPROFILE"] = _TEST_HOME  # Windows equivalent

import pytest  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_HOME, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_preferences(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read the developer's real ~/.agents-environment-config/preferences.json.

    Tests that need specific preferences monkeypatch AEC_PREFERENCES themselves.
    """
    monkeypatch.setattr(
        "aec.lib.preferences.AEC_PREFERENCES", tmp_path / "preferences.json"
    )


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
