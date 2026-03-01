"""Tests for cross-platform compatibility.

These tests verify that path handling, config detection, and core logic
work correctly on both Unix and Windows. They can run on any platform.
"""

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest


class TestResolveProjectPath:
    """Test _resolve_project_path handles all path formats."""

    def test_home_relative_path(self, monkeypatch):
        """Resolves ~/projects/foo correctly."""
        from aec.commands.repo import _resolve_project_path

        result = _resolve_project_path("~/some-project")
        assert result.is_absolute()
        assert "some-project" in str(result)

    def test_absolute_path(self, tmp_path, monkeypatch):
        """Resolves absolute paths directly."""
        from aec.commands.repo import _resolve_project_path

        result = _resolve_project_path(str(tmp_path / "my-project"))
        assert result.is_absolute()
        assert "my-project" in str(result)

    def test_project_name_uses_projects_dir(self, tmp_path, monkeypatch):
        """Bare project names resolve under projects_dir."""
        from aec.commands.repo import _resolve_project_path

        monkeypatch.setattr("aec.commands.repo.get_projects_dir", lambda: tmp_path)

        result = _resolve_project_path("my-project")
        assert result == tmp_path / "my-project"


class TestGetRepoRoot:
    """Test get_repo_root() works cross-platform."""

    def test_finds_repo_by_templates_marker(self, tmp_path, monkeypatch):
        """get_repo_root() finds repo via templates/ directory marker."""
        import aec.lib.config as config_mod

        # Create the expected markers
        (tmp_path / ".git").mkdir()
        (tmp_path / "templates").mkdir()
        (tmp_path / "aec").mkdir()
        (tmp_path / ".agent-rules").mkdir()

        # Clear cached result and simulate __file__ inside the repo
        monkeypatch.setattr(config_mod, "_repo_root", None)
        monkeypatch.setattr(
            config_mod,
            "__file__",
            str(tmp_path / "aec" / "lib" / "config.py"),
        )

        result = config_mod.get_repo_root()
        assert result is not None
        assert result.resolve() == tmp_path.resolve()


class TestConsoleAnsi:
    """Test console output handles platform differences."""

    def test_console_colorize_returns_string(self):
        """Console._colorize always returns a string."""
        from aec.lib.console import Console

        result = Console._colorize(Console.GREEN, "test")
        assert isinstance(result, str)
        assert "test" in result

    def test_console_path_returns_string(self):
        """Console.path() works with Path objects and strings."""
        from aec.lib.console import Console

        result = Console.path("/some/path")
        assert isinstance(result, str)
        assert "path" in result


class TestFilesystemCrossPlatform:
    """Test filesystem operations work cross-platform."""

    def test_ensure_directory_creates_nested(self, tmp_path):
        """ensure_directory creates nested dirs on any platform."""
        from aec.lib.filesystem import ensure_directory

        target = tmp_path / "a" / "b" / "c"
        ensure_directory(target)
        assert target.is_dir()

    def test_copy_file_works(self, tmp_path):
        """copy_file works on any platform."""
        from aec.lib.filesystem import copy_file

        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("hello")

        result = copy_file(src, dst)
        assert result is True
        assert dst.read_text() == "hello"

    def test_is_symlink_returns_false_for_regular_file(self, tmp_path):
        """is_symlink returns False for a regular file."""
        from aec.lib.filesystem import is_symlink

        f = tmp_path / "regular.txt"
        f.write_text("not a link")
        assert is_symlink(f) is False


class TestPathHandling:
    """Test that Path operations handle platform differences."""

    def test_gitignore_patterns_use_forward_slashes(self):
        """Gitignore patterns always use forward slashes (git convention)."""
        from aec.lib.registry import get_gitignore_patterns

        patterns = get_gitignore_patterns()
        for pattern in patterns:
            # Gitignore patterns should use / not \
            assert "\\" not in pattern, f"Pattern uses backslash: {pattern}"
