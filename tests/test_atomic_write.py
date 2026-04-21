"""Tests for aec.lib.atomic_write."""

import json
from pathlib import Path

from aec.lib.atomic_write import atomic_write_json, atomic_write_text


class TestAtomicWriteJson:
    """Tests for atomic_write_json."""

    def test_round_trip(self, temp_dir: Path) -> None:
        """Write then read back -- content must match."""
        target = temp_dir / "config.json"
        data = {"name": "test", "version": 1, "nested": {"key": "value"}}

        atomic_write_json(target, data)

        result = json.loads(target.read_text(encoding="utf-8"))
        assert result == data

    def test_format_matches_convention(self, temp_dir: Path) -> None:
        """Output must use 2-space indent and trailing newline."""
        target = temp_dir / "fmt.json"
        data = {"a": 1}

        atomic_write_json(target, data)

        raw = target.read_text(encoding="utf-8")
        assert raw == json.dumps(data, indent=2) + "\n"

    def test_parent_dir_creation(self, temp_dir: Path) -> None:
        """Write to nested non-existent path -- dirs created automatically."""
        target = temp_dir / "deep" / "nested" / "dir" / "config.json"
        data = {"created": True}

        atomic_write_json(target, data)

        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == data

    def test_no_tmp_file_remains(self, temp_dir: Path) -> None:
        """After successful write, no .tmp file should exist."""
        target = temp_dir / "clean.json"

        atomic_write_json(target, {"key": "value"})

        tmp_path = target.with_suffix(".json.tmp")
        assert not tmp_path.exists()
        assert target.exists()

    def test_overwrite_existing_file(self, temp_dir: Path) -> None:
        """Overwrite an existing file -- new content must win."""
        target = temp_dir / "overwrite.json"
        target.write_text('{"old": true}\n', encoding="utf-8")

        new_data = {"old": False, "new": True}
        atomic_write_json(target, new_data)

        result = json.loads(target.read_text(encoding="utf-8"))
        assert result == new_data

    def test_empty_dict(self, temp_dir: Path) -> None:
        """Write empty dict -- must produce valid JSON."""
        target = temp_dir / "empty.json"

        atomic_write_json(target, {})

        raw = target.read_text(encoding="utf-8")
        assert raw == "{}\n"
        assert json.loads(raw) == {}


class TestAtomicWriteText:
    """Tests for atomic_write_text."""

    def test_round_trip(self, temp_dir: Path) -> None:
        """Write then read back -- content must match."""
        target = temp_dir / "notes.txt"
        content = "Hello, world!\nLine two.\n"

        atomic_write_text(target, content)

        assert target.read_text(encoding="utf-8") == content

    def test_parent_dir_creation(self, temp_dir: Path) -> None:
        """Write to nested path -- dirs created automatically."""
        target = temp_dir / "a" / "b" / "file.txt"

        atomic_write_text(target, "content")

        assert target.exists()
        assert target.read_text(encoding="utf-8") == "content"

    def test_no_tmp_file_remains(self, temp_dir: Path) -> None:
        """After successful write, no .tmp file should exist."""
        target = temp_dir / "clean.txt"

        atomic_write_text(target, "data")

        tmp_path = target.with_suffix(".txt.tmp")
        assert not tmp_path.exists()
