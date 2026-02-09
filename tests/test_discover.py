"""Tests for aec discover command and discover_from_scripts function."""

import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------


@pytest.fixture
def raycast_dir(tmp_path: Path) -> Path:
    """Create a temporary raycast_scripts directory."""
    d = tmp_path / "raycast_scripts"
    d.mkdir()
    return d


@pytest.fixture
def project_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create a set of fake project directories for testing."""
    projects = {}
    for name in ["tools", "mbernier.com", "earnlearn", "radium", "missing-project"]:
        if name != "missing-project":
            d = tmp_path / "projects" / name
            d.mkdir(parents=True)
            projects[name] = d
        else:
            # This one does not exist on disk
            projects[name] = tmp_path / "projects" / name
    return projects


def _write_claude_script(raycast_dir: Path, name: str, project_path: str) -> Path:
    """Write a Claude-style Raycast launcher script."""
    script = raycast_dir / f"claude-{name}.sh"
    script.write_text(
        f"""#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title claude {name}
# @raycast.mode compact

# Optional parameters:
# @raycast.icon x

# Documentation:
# @raycast.description open claude {name} project
# @raycast.author test

osascript -e 'tell application "Terminal" to do script "cd {project_path}/; claude --dangerously-skip-permissions"'
"""
    )
    return script


def _write_claude_resume_script(
    raycast_dir: Path, name: str, project_path: str
) -> Path:
    """Write a Claude resume-style Raycast launcher script."""
    script = raycast_dir / f"claude-{name}-resume.sh"
    script.write_text(
        f"""#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title claude {name} resume
# @raycast.mode compact

# Optional parameters:
# @raycast.icon x

osascript -e 'tell application "Terminal" to do script "cd {project_path}/; claude --dangerously-skip-permissions --resume"'
"""
    )
    return script


def _write_cursor_script(raycast_dir: Path, name: str, project_path: str) -> Path:
    """Write a Cursor-style Raycast launcher script."""
    script = raycast_dir / f"cursor-{name}.sh"
    script.write_text(
        f"""#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title cursor {name}
# @raycast.mode compact

# Optional parameters:
# @raycast.icon x

cursor {project_path}/
"""
    )
    return script


def _write_utility_script(raycast_dir: Path, name: str) -> Path:
    """Write a non-agent utility script (no project path)."""
    script = raycast_dir / f"{name}.sh"
    script.write_text(
        f"""#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title {name}
# @raycast.mode fullOutput

echo "utility script"
"""
    )
    return script


# -------------------------------------------------------------------
# Tests for discover_from_scripts
# -------------------------------------------------------------------


class TestDiscoverFromScripts:
    """Tests for the discover_from_scripts library function."""

    def test_empty_directory(self, raycast_dir: Path):
        """Returns empty list when directory has no scripts."""
        from aec.lib.tracking import discover_from_scripts

        result = discover_from_scripts(raycast_dir)
        assert result == []

    def test_nonexistent_directory(self, tmp_path: Path):
        """Returns empty list when directory does not exist."""
        from aec.lib.tracking import discover_from_scripts

        result = discover_from_scripts(tmp_path / "nonexistent")
        assert result == []

    def test_extracts_claude_path(self, raycast_dir: Path, project_dirs: dict):
        """Extracts path from claude-style osascript cd command."""
        from aec.lib.tracking import discover_from_scripts

        _write_claude_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 1
        assert result[0] == project_dirs["tools"].resolve()

    def test_extracts_cursor_path(self, raycast_dir: Path, project_dirs: dict):
        """Extracts path from cursor-style direct launch command."""
        from aec.lib.tracking import discover_from_scripts

        _write_cursor_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 1
        assert result[0] == project_dirs["tools"].resolve()

    def test_deduplicates_same_project(
        self, raycast_dir: Path, project_dirs: dict
    ):
        """Same project from claude + cursor + resume scripts is deduplicated."""
        from aec.lib.tracking import discover_from_scripts

        path = str(project_dirs["tools"])
        _write_claude_script(raycast_dir, "tools", path)
        _write_claude_resume_script(raycast_dir, "tools", path)
        _write_cursor_script(raycast_dir, "tools", path)

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 1
        assert result[0] == project_dirs["tools"].resolve()

    def test_discovers_multiple_projects(
        self, raycast_dir: Path, project_dirs: dict
    ):
        """Finds paths from multiple different projects."""
        from aec.lib.tracking import discover_from_scripts

        _write_claude_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )
        _write_cursor_script(
            raycast_dir, "earnlearn", str(project_dirs["earnlearn"])
        )
        _write_claude_script(
            raycast_dir, "radium", str(project_dirs["radium"])
        )

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 3
        resolved = {p.resolve() for p in result}
        assert project_dirs["tools"].resolve() in resolved
        assert project_dirs["earnlearn"].resolve() in resolved
        assert project_dirs["radium"].resolve() in resolved

    def test_ignores_utility_scripts(
        self, raycast_dir: Path, project_dirs: dict
    ):
        """Utility scripts without cd/cursor commands produce no paths."""
        from aec.lib.tracking import discover_from_scripts

        _write_utility_script(raycast_dir, "cleanup-hung-processes")

        result = discover_from_scripts(raycast_dir)
        assert result == []

    def test_handles_tilde_paths(self, raycast_dir: Path):
        """Handles ~ in paths by expanding to home directory."""
        from aec.lib.tracking import discover_from_scripts

        script = raycast_dir / "claude-test.sh"
        script.write_text(
            'osascript -e \'tell application "Terminal" to do script '
            '"cd ~/projects/test/; claude --dangerously-skip-permissions"\'\n'
        )

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 1
        assert str(result[0]).startswith(str(Path.home()))
        assert "~" not in str(result[0])

    def test_handles_trailing_slash_variations(
        self, raycast_dir: Path, project_dirs: dict
    ):
        """Path with or without trailing slash resolves to same path."""
        from aec.lib.tracking import discover_from_scripts

        path = str(project_dirs["tools"])

        # One with trailing slash, one without
        script1 = raycast_dir / "claude-tools.sh"
        script1.write_text(
            f'osascript -e \'tell application "Terminal" to do script '
            f'"cd {path}/; claude"\'\n'
        )
        script2 = raycast_dir / "cursor-tools.sh"
        script2.write_text(f"cursor {path}/\n")

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 1

    def test_returns_sorted_paths(self, raycast_dir: Path, project_dirs: dict):
        """Result is sorted by path for consistent output."""
        from aec.lib.tracking import discover_from_scripts

        # Write in reverse order
        _write_claude_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )
        _write_claude_script(
            raycast_dir, "earnlearn", str(project_dirs["earnlearn"])
        )

        result = discover_from_scripts(raycast_dir)
        assert result == sorted(result)

    def test_only_scans_sh_files(self, raycast_dir: Path, project_dirs: dict):
        """Only .sh files are scanned, not other file types."""
        from aec.lib.tracking import discover_from_scripts

        # Create a .txt file with a path pattern
        txt_file = raycast_dir / "notes.txt"
        txt_file.write_text(f"cd {project_dirs['tools']}/; claude\n")

        result = discover_from_scripts(raycast_dir)
        assert result == []

    def test_handles_code_launch_pattern(self, raycast_dir: Path, tmp_path: Path):
        """Handles 'code /path' pattern for VS Code."""
        from aec.lib.tracking import discover_from_scripts

        project = tmp_path / "projects" / "vscode-project"
        project.mkdir(parents=True)

        script = raycast_dir / "code-test.sh"
        script.write_text(f"code {project}/\n")

        result = discover_from_scripts(raycast_dir)
        assert len(result) == 1
        assert result[0] == project.resolve()

    def test_ignores_shell_script_cd_internals(self, raycast_dir: Path):
        """Does not match cd commands that are shell internals (variables, subshells)."""
        from aec.lib.tracking import discover_from_scripts

        # This mimics setup-repo.sh which has:
        # SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        # REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
        script = raycast_dir / "setup-repo.sh"
        script.write_text(
            '#!/bin/bash\n'
            'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
            'REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"\n'
            'echo "done"\n'
        )

        result = discover_from_scripts(raycast_dir)
        assert result == []

    def test_ignores_cd_with_variable_path(self, raycast_dir: Path):
        """Does not match cd $VARIABLE; patterns (only literal paths)."""
        from aec.lib.tracking import discover_from_scripts

        # This mimics sync-cursor-commands.sh which has:
        # cd $REPO_DIR/; claude ...
        script = raycast_dir / "sync-commands.sh"
        script.write_text(
            '#!/bin/bash\n'
            'REPO_DIR="$HOME/projects/test"\n'
            'cd $REPO_DIR/; claude --dangerously-skip-permissions\n'
        )

        result = discover_from_scripts(raycast_dir)
        assert result == []


# -------------------------------------------------------------------
# Tests for the discover CLI command
# -------------------------------------------------------------------


class TestDiscoverCLI:
    """Test the discover CLI command."""

    def test_discover_help(self):
        """Discover command should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "discover", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "discover" in result.stdout.lower()
        assert "--dry-run" in result.stdout
        assert "--auto" in result.stdout

    def test_discover_runs_without_crash(self):
        """Discover command should run without crashing."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "discover", "--dry-run"],
            capture_output=True,
            text=True,
        )

        # Should complete - either finds scripts or reports none
        assert result.returncode == 0
        assert "Repo Discovery" in result.stdout


# -------------------------------------------------------------------
# Tests verifying the discover function integration with tracking
# -------------------------------------------------------------------


class TestDiscoverIntegration:
    """Test discover function integration with the tracking system."""

    def test_discover_identifies_untracked_paths(
        self, tmp_path: Path, raycast_dir: Path, project_dirs: dict, monkeypatch
    ):
        """Discovered paths not in tracking log are identified as new."""
        from aec.lib.tracking import discover_from_scripts, is_logged

        _write_claude_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )

        discovered = discover_from_scripts(raycast_dir)
        assert len(discovered) == 1

        # Not yet tracked
        assert not is_logged(discovered[0])

    def test_discover_identifies_tracked_paths(
        self, tmp_path: Path, raycast_dir: Path, project_dirs: dict, monkeypatch
    ):
        """Paths already in tracking log are identified as tracked."""
        from aec.lib import config
        from aec.lib.tracking import (
            discover_from_scripts,
            is_logged,
            log_setup,
            init_aec_home,
        )

        # Point AEC_HOME to temp directory
        aec_home = tmp_path / ".agents-environment-config"
        monkeypatch.setattr(config, "AEC_HOME", aec_home)
        monkeypatch.setattr(config, "AEC_SETUP_LOG", aec_home / "setup-repo-locations.txt")
        monkeypatch.setattr(config, "AEC_README", aec_home / "README.md")

        # Also patch the tracking module's imported references
        from aec.lib import tracking
        monkeypatch.setattr(tracking, "AEC_HOME", aec_home)
        monkeypatch.setattr(tracking, "AEC_SETUP_LOG", aec_home / "setup-repo-locations.txt")
        monkeypatch.setattr(tracking, "AEC_README", aec_home / "README.md")

        init_aec_home()

        # Track a project
        log_setup(project_dirs["tools"])

        _write_claude_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )

        discovered = discover_from_scripts(raycast_dir)
        assert len(discovered) == 1
        assert is_logged(discovered[0])

    def test_log_setup_adds_discovered_path(
        self, tmp_path: Path, raycast_dir: Path, project_dirs: dict, monkeypatch
    ):
        """log_setup correctly adds a discovered path to the tracking log."""
        from aec.lib import config
        from aec.lib.tracking import (
            discover_from_scripts,
            is_logged,
            log_setup,
            init_aec_home,
            list_repos,
        )

        # Point AEC_HOME to temp directory
        aec_home = tmp_path / ".agents-environment-config"
        monkeypatch.setattr(config, "AEC_HOME", aec_home)
        monkeypatch.setattr(config, "AEC_SETUP_LOG", aec_home / "setup-repo-locations.txt")
        monkeypatch.setattr(config, "AEC_README", aec_home / "README.md")

        from aec.lib import tracking
        monkeypatch.setattr(tracking, "AEC_HOME", aec_home)
        monkeypatch.setattr(tracking, "AEC_SETUP_LOG", aec_home / "setup-repo-locations.txt")
        monkeypatch.setattr(tracking, "AEC_README", aec_home / "README.md")

        init_aec_home()

        _write_claude_script(
            raycast_dir, "tools", str(project_dirs["tools"])
        )

        discovered = discover_from_scripts(raycast_dir)
        assert len(discovered) == 1

        # Add to tracking
        log_setup(discovered[0])

        # Now it should be tracked
        assert is_logged(discovered[0])
        repos = list_repos()
        assert len(repos) == 1
        assert repos[0].path == discovered[0].resolve()


# -------------------------------------------------------------------
# Tests for real Raycast scripts in the repo
# -------------------------------------------------------------------


class TestDiscoverRealScripts:
    """Test discover_from_scripts against the actual raycast_scripts/ directory."""

    def test_discovers_paths_from_real_scripts(self):
        """Verify discover works against the real raycast_scripts/ in this repo."""
        from aec.lib.tracking import discover_from_scripts
        from aec.lib.config import get_repo_root

        repo_root = get_repo_root()
        if repo_root is None:
            pytest.skip("Not running from within the aec repo")

        raycast_dir = repo_root / "raycast_scripts"
        if not raycast_dir.is_dir():
            pytest.skip("No raycast_scripts/ directory in repo")

        result = discover_from_scripts(raycast_dir)

        # We know there are scripts in the repo, so we should find paths
        assert len(result) > 0

        # All returned paths should be absolute
        for path in result:
            assert path.is_absolute(), f"Path should be absolute: {path}"

        # All returned paths should have ~ expanded
        for path in result:
            assert "~" not in str(path), f"Tilde not expanded: {path}"

    def test_no_duplicates_in_real_scripts(self):
        """Verify no duplicate paths are returned from real scripts."""
        from aec.lib.tracking import discover_from_scripts
        from aec.lib.config import get_repo_root

        repo_root = get_repo_root()
        if repo_root is None:
            pytest.skip("Not running from within the aec repo")

        raycast_dir = repo_root / "raycast_scripts"
        if not raycast_dir.is_dir():
            pytest.skip("No raycast_scripts/ directory in repo")

        result = discover_from_scripts(raycast_dir)

        # Check for duplicates
        path_strings = [str(p) for p in result]
        assert len(path_strings) == len(set(path_strings)), (
            f"Duplicate paths found: {path_strings}"
        )
