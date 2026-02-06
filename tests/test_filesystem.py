"""Tests for aec.lib.filesystem module."""

import os
import platform
from pathlib import Path

import pytest

from aec.lib.filesystem import (
    ensure_directory,
    create_symlink,
    remove_symlink,
    is_symlink,
    get_symlink_target,
    copy_file,
)


class TestEnsureDirectory:
    """Test ensure_directory function."""

    def test_creates_directory(self, temp_dir):
        """Should create a directory that doesn't exist."""
        new_dir = temp_dir / "new" / "nested" / "dir"
        assert not new_dir.exists()

        ensure_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_handles_existing_directory(self, temp_dir):
        """Should not fail if directory already exists."""
        existing = temp_dir / "existing"
        existing.mkdir()

        # Should not raise
        ensure_directory(existing)

        assert existing.exists()

    def test_returns_none(self, temp_dir):
        """Should return None (creates in place)."""
        new_dir = temp_dir / "test"

        result = ensure_directory(new_dir)

        assert result is None
        assert new_dir.exists()


class TestSymlinks:
    """Test symlink operations."""

    def test_create_symlink_to_file(self, temp_dir):
        """Should create a symlink to a file."""
        source = temp_dir / "source.txt"
        source.write_text("test content")
        target = temp_dir / "link.txt"

        result = create_symlink(source, target)

        assert result is True
        assert target.exists()
        assert is_symlink(target)
        assert target.read_text() == "test content"

    def test_create_symlink_to_directory(self, temp_dir):
        """Should create a symlink to a directory."""
        source = temp_dir / "source_dir"
        source.mkdir()
        (source / "file.txt").write_text("content")
        target = temp_dir / "link_dir"

        result = create_symlink(source, target, is_directory=True)

        assert result is True
        assert target.exists()
        assert is_symlink(target)
        assert (target / "file.txt").read_text() == "content"

    def test_remove_symlink(self, temp_dir):
        """Should remove a symlink."""
        source = temp_dir / "source.txt"
        source.write_text("test")
        target = temp_dir / "link.txt"
        create_symlink(source, target)

        assert is_symlink(target)

        result = remove_symlink(target)

        assert result is True
        assert not target.exists()
        # Source should still exist
        assert source.exists()

    def test_get_symlink_target(self, temp_dir):
        """Should return the target of a symlink."""
        source = temp_dir / "source.txt"
        source.write_text("test")
        target = temp_dir / "link.txt"
        create_symlink(source, target)

        result = get_symlink_target(target)

        # Use resolve() to handle /var -> /private/var on macOS
        assert result.resolve() == source.resolve()

    def test_is_symlink_false_for_regular_file(self, temp_dir):
        """Should return False for regular files."""
        regular_file = temp_dir / "regular.txt"
        regular_file.write_text("test")

        assert is_symlink(regular_file) is False

    def test_is_symlink_false_for_nonexistent(self, temp_dir):
        """Should return False for nonexistent paths."""
        nonexistent = temp_dir / "nonexistent"

        assert is_symlink(nonexistent) is False


class TestCopyFile:
    """Test copy_file function."""

    def test_copies_file(self, temp_dir):
        """Should copy a file."""
        source = temp_dir / "source.txt"
        source.write_text("test content")
        target = temp_dir / "target.txt"

        result = copy_file(source, target)

        assert result is True
        assert target.exists()
        assert target.read_text() == "test content"

    def test_creates_parent_directory(self, temp_dir):
        """Should create parent directories if needed."""
        source = temp_dir / "source.txt"
        source.write_text("test")
        target = temp_dir / "nested" / "dir" / "target.txt"

        result = copy_file(source, target)

        assert result is True
        assert target.exists()

    def test_returns_false_for_nonexistent_source(self, temp_dir):
        """Should return False if source doesn't exist."""
        source = temp_dir / "nonexistent.txt"
        target = temp_dir / "target.txt"

        result = copy_file(source, target)

        assert result is False


class TestWindowsJunctions:
    """Test Windows-specific junction behavior."""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_directory_uses_junction(self, temp_dir):
        """On Windows, directory symlinks should use junctions."""
        source = temp_dir / "source_dir"
        source.mkdir()
        target = temp_dir / "link_dir"

        create_symlink(source, target, is_directory=True)

        # Junction should work like a directory
        assert target.is_dir()
        # But os.path.islink returns False for junctions
        # (junctions are not symlinks in the traditional sense)
