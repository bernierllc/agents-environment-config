"""Tests for aec.lib.version_check module."""

import pytest


class TestParseVersion:
    """Test parse_version function."""

    def test_parses_plain_version(self):
        from aec.lib.version_check import parse_version
        assert parse_version("2.0.0") == (2, 0, 0)

    def test_parses_v_prefix(self):
        from aec.lib.version_check import parse_version
        assert parse_version("v2.1.0") == (2, 1, 0)

    def test_parses_two_part_version(self):
        from aec.lib.version_check import parse_version
        assert parse_version("2.1") == (2, 1)

    def test_comparison_newer(self):
        from aec.lib.version_check import parse_version
        assert parse_version("2.1.0") > parse_version("2.0.0")

    def test_comparison_equal(self):
        from aec.lib.version_check import parse_version
        assert parse_version("v2.0.0") == parse_version("2.0.0")

    def test_comparison_older(self):
        from aec.lib.version_check import parse_version
        assert parse_version("1.9.9") < parse_version("2.0.0")

    def test_comparison_patch(self):
        from aec.lib.version_check import parse_version
        assert parse_version("2.0.1") > parse_version("2.0.0")


class TestCache:
    """Test version check caching."""

    def test_read_cache_returns_none_when_missing(self, temp_dir, monkeypatch):
        cache_file = temp_dir / "version-check.json"
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", cache_file)

        from aec.lib.version_check import _read_cache
        assert _read_cache() is None

    def test_read_cache_returns_none_when_stale(self, temp_dir, monkeypatch):
        cache_file = temp_dir / "version-check.json"
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", cache_file)

        import json
        from datetime import datetime, timezone, timedelta
        stale_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        cache_file.write_text(json.dumps({
            "last_check": stale_time,
            "latest_version": "2.1.0",
            "release_url": "https://example.com",
        }))

        from aec.lib.version_check import _read_cache
        assert _read_cache() is None

    def test_read_cache_returns_data_when_fresh(self, temp_dir, monkeypatch):
        cache_file = temp_dir / "version-check.json"
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", cache_file)

        import json
        from datetime import datetime, timezone
        fresh_time = datetime.now(timezone.utc).isoformat()
        cache_file.write_text(json.dumps({
            "last_check": fresh_time,
            "latest_version": "2.1.0",
            "release_url": "https://example.com",
        }))

        from aec.lib.version_check import _read_cache
        result = _read_cache()
        assert result is not None
        assert result["latest_version"] == "2.1.0"

    def test_write_cache_creates_file(self, temp_dir, monkeypatch):
        cache_file = temp_dir / "version-check.json"
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", cache_file)

        from aec.lib.version_check import _write_cache
        _write_cache("2.1.0", "https://example.com")

        assert cache_file.exists()
        import json
        data = json.loads(cache_file.read_text())
        assert data["latest_version"] == "2.1.0"
        assert data["release_url"] == "https://example.com"
        assert "last_check" in data

    def test_read_cache_returns_none_on_corrupt_json(self, temp_dir, monkeypatch):
        cache_file = temp_dir / "version-check.json"
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", cache_file)
        cache_file.write_text("not json{{{")

        from aec.lib.version_check import _read_cache
        assert _read_cache() is None
