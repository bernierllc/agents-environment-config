"""Tests for aec.lib.backup module."""

import re
from pathlib import Path
from unittest.mock import patch

from aec.lib.backup import (
    BACKUP_DIR_NAME,
    BACKUP_GITIGNORE_ENTRY,
    _timestamp_suffix,
    backup_item,
    ensure_backup_gitignore,
    list_backups,
)

TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}")


class TestTimestampSuffix:
    """Test _timestamp_suffix function."""

    def test_format_matches_pattern(self):
        """Should return YYYY-MM-DDTHH-MM-SS format."""
        result = _timestamp_suffix()
        assert TIMESTAMP_PATTERN.fullmatch(result), f"Unexpected format: {result}"

    def test_returns_utc_time(self):
        """Should use UTC, not local time."""
        from datetime import datetime, timezone

        utc_now = datetime.now(timezone.utc)
        result = _timestamp_suffix()
        # The date portion should match UTC
        assert result.startswith(utc_now.strftime("%Y-%m-%d"))


class TestBackupItem:
    """Test backup_item function."""

    def test_backup_single_file(self, tmp_path: Path):
        """Should copy file to .aec-backup/ with timestamp in name."""
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "engineering-backend-architect.md"
        source.write_text("# Agent definition\nSome content here.")

        result = backup_item(source, repo)

        assert result.exists()
        assert result.parent == repo / BACKUP_DIR_NAME
        assert result.read_text() == "# Agent definition\nSome content here."
        # Filename: <stem>.<timestamp>.<ext>
        assert result.name.startswith("engineering-backend-architect.")
        assert result.suffix == ".md"
        # Extract timestamp from between stem and extension
        name_without_ext = result.stem  # e.g. engineering-backend-architect.2026-04-10T18-00-00
        timestamp_part = name_without_ext.split(".", 1)[1]
        assert TIMESTAMP_PATTERN.fullmatch(timestamp_part), f"Bad timestamp: {timestamp_part}"

    def test_backup_directory(self, tmp_path: Path):
        """Should copytree directory to .aec-backup/ with timestamp in name."""
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "webapp-testing"
        source.mkdir()
        (source / "config.json").write_text('{"key": "value"}')
        (source / "runner.py").write_text("print('test')")

        result = backup_item(source, repo)

        assert result.exists()
        assert result.is_dir()
        assert result.parent == repo / BACKUP_DIR_NAME
        assert (result / "config.json").read_text() == '{"key": "value"}'
        assert (result / "runner.py").read_text() == "print('test')"
        # Name: <name>.<timestamp>
        parts = result.name.split(".", 1)
        assert parts[0] == "webapp-testing"
        assert TIMESTAMP_PATTERN.fullmatch(parts[1]), f"Bad timestamp: {parts[1]}"

    def test_creates_backup_dir_if_missing(self, tmp_path: Path):
        """Should create .aec-backup/ directory if it doesn't exist."""
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "test.md"
        source.write_text("content")

        backup_dir = repo / BACKUP_DIR_NAME
        assert not backup_dir.exists()

        backup_item(source, repo)

        assert backup_dir.exists()
        assert backup_dir.is_dir()

    def test_multiple_backups_no_overwrite(self, tmp_path: Path):
        """Multiple backups of the same file should each get a unique timestamp."""
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "agent.md"
        source.write_text("v1")

        # Use mocked timestamps to guarantee uniqueness
        with patch("aec.lib.backup._timestamp_suffix", return_value="2026-04-10T18-00-00"):
            result1 = backup_item(source, repo)

        source.write_text("v2")
        with patch("aec.lib.backup._timestamp_suffix", return_value="2026-04-10T18-00-01"):
            result2 = backup_item(source, repo)

        assert result1 != result2
        assert result1.exists()
        assert result2.exists()
        assert result1.read_text() == "v1"
        assert result2.read_text() == "v2"

    def test_preserves_file_metadata(self, tmp_path: Path):
        """Should use shutil.copy2 which preserves metadata."""
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "notes.txt"
        source.write_text("important notes")

        result = backup_item(source, repo)

        # copy2 preserves modification time (within filesystem precision)
        assert abs(source.stat().st_mtime - result.stat().st_mtime) < 2


class TestEnsureBackupGitignore:
    """Test ensure_backup_gitignore function."""

    def test_creates_gitignore_when_missing(self, tmp_path: Path):
        """Should create .gitignore with .aec-backup/ entry."""
        repo = tmp_path / "repo"
        repo.mkdir()
        gitignore = repo / ".gitignore"
        assert not gitignore.exists()

        ensure_backup_gitignore(repo)

        assert gitignore.exists()
        assert BACKUP_GITIGNORE_ENTRY in gitignore.read_text().splitlines()

    def test_appends_to_existing_gitignore(self, tmp_path: Path):
        """Should append entry to existing .gitignore."""
        repo = tmp_path / "repo"
        repo.mkdir()
        gitignore = repo / ".gitignore"
        gitignore.write_text("node_modules/\n.env\n")

        ensure_backup_gitignore(repo)

        content = gitignore.read_text()
        lines = content.splitlines()
        assert "node_modules/" in lines
        assert ".env" in lines
        assert BACKUP_GITIGNORE_ENTRY in lines

    def test_appends_newline_before_entry_if_missing(self, tmp_path: Path):
        """Should add newline before entry if file doesn't end with one."""
        repo = tmp_path / "repo"
        repo.mkdir()
        gitignore = repo / ".gitignore"
        gitignore.write_text("node_modules/")  # No trailing newline

        ensure_backup_gitignore(repo)

        content = gitignore.read_text()
        assert content == "node_modules/\n.aec-backup/\n"

    def test_idempotent_no_duplicate(self, tmp_path: Path):
        """Should not add duplicate entry if already present."""
        repo = tmp_path / "repo"
        repo.mkdir()
        gitignore = repo / ".gitignore"
        gitignore.write_text("node_modules/\n.aec-backup/\n")

        ensure_backup_gitignore(repo)

        content = gitignore.read_text()
        count = content.splitlines().count(BACKUP_GITIGNORE_ENTRY)
        assert count == 1

    def test_idempotent_after_multiple_calls(self, tmp_path: Path):
        """Calling multiple times should not duplicate the entry."""
        repo = tmp_path / "repo"
        repo.mkdir()

        ensure_backup_gitignore(repo)
        ensure_backup_gitignore(repo)
        ensure_backup_gitignore(repo)

        content = (repo / ".gitignore").read_text()
        count = content.splitlines().count(BACKUP_GITIGNORE_ENTRY)
        assert count == 1


class TestListBackups:
    """Test list_backups function."""

    def test_returns_sorted_paths(self, tmp_path: Path):
        """Should return all items in .aec-backup/ sorted by name."""
        repo = tmp_path / "repo"
        backup_dir = repo / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)
        # Create items in non-alphabetical order
        (backup_dir / "charlie.2026-04-10T18-00-02.md").write_text("c")
        (backup_dir / "alpha.2026-04-10T18-00-00.md").write_text("a")
        (backup_dir / "bravo.2026-04-10T18-00-01.md").write_text("b")

        result = list_backups(repo)

        assert len(result) == 3
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_returns_empty_list_when_no_backup_dir(self, tmp_path: Path):
        """Should return empty list when .aec-backup/ doesn't exist."""
        repo = tmp_path / "repo"
        repo.mkdir()

        result = list_backups(repo)

        assert result == []

    def test_includes_both_files_and_directories(self, tmp_path: Path):
        """Should list both file and directory backups."""
        repo = tmp_path / "repo"
        backup_dir = repo / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)
        (backup_dir / "agent.2026-04-10T18-00-00.md").write_text("content")
        skill_dir = backup_dir / "skill.2026-04-10T18-00-00"
        skill_dir.mkdir()
        (skill_dir / "main.py").write_text("code")

        result = list_backups(repo)

        assert len(result) == 2
        types = {p.is_file() for p in result}
        assert types == {True, False}  # One file, one directory
