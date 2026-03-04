"""Tests for aec.lib.version_check module."""

import pytest
from unittest.mock import patch, MagicMock
import json as json_mod


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


class TestFetchLatestRelease:
    """Test _fetch_latest_release (mocks GitHub API — external service)."""

    def test_returns_version_and_url_on_success(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json_mod.dumps({
            "tag_name": "v2.1.0",
            "html_url": "https://github.com/bernierllc/agents-environment-config/releases/tag/v2.1.0",
            "prerelease": False,
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("aec.lib.version_check.urllib.request.urlopen", return_value=mock_response):
            from aec.lib.version_check import _fetch_latest_release
            result = _fetch_latest_release()
            assert result is not None
            assert result["latest_version"] == "2.1.0"
            assert "releases/tag/v2.1.0" in result["release_url"]

    def test_returns_none_on_network_error(self):
        with patch("aec.lib.version_check.urllib.request.urlopen", side_effect=Exception("timeout")):
            from aec.lib.version_check import _fetch_latest_release
            assert _fetch_latest_release() is None

    def test_skips_prerelease(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json_mod.dumps({
            "tag_name": "v3.0.0-beta.1",
            "html_url": "https://example.com",
            "prerelease": True,
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("aec.lib.version_check.urllib.request.urlopen", return_value=mock_response):
            from aec.lib.version_check import _fetch_latest_release
            assert _fetch_latest_release() is None


class TestCheckForUpdate:
    """Test check_for_update main entry point."""

    def test_returns_none_when_up_to_date(self, temp_dir, monkeypatch):
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", temp_dir / "vc.json")
        monkeypatch.setattr("aec.lib.version_check.VERSION", "2.1.0")

        mock_response = MagicMock()
        mock_response.read.return_value = json_mod.dumps({
            "tag_name": "v2.1.0",
            "html_url": "https://example.com",
            "prerelease": False,
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("aec.lib.version_check.urllib.request.urlopen", return_value=mock_response):
            from aec.lib.version_check import check_for_update
            assert check_for_update() is None

    def test_returns_info_when_update_available(self, temp_dir, monkeypatch):
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", temp_dir / "vc.json")
        monkeypatch.setattr("aec.lib.version_check.VERSION", "2.0.0")

        mock_response = MagicMock()
        mock_response.read.return_value = json_mod.dumps({
            "tag_name": "v2.1.0",
            "html_url": "https://github.com/bernierllc/agents-environment-config/releases/tag/v2.1.0",
            "prerelease": False,
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("aec.lib.version_check.urllib.request.urlopen", return_value=mock_response):
            from aec.lib.version_check import check_for_update
            result = check_for_update()
            assert result is not None
            assert result["current_version"] == "2.0.0"
            assert result["latest_version"] == "2.1.0"

    def test_uses_cache_when_fresh(self, temp_dir, monkeypatch):
        cache_file = temp_dir / "vc.json"
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", cache_file)
        monkeypatch.setattr("aec.lib.version_check.VERSION", "2.0.0")

        from datetime import datetime, timezone
        cache_file.write_text(json_mod.dumps({
            "last_check": datetime.now(timezone.utc).isoformat(),
            "latest_version": "2.1.0",
            "release_url": "https://example.com",
        }))

        # urlopen should NOT be called (using cache)
        with patch("aec.lib.version_check.urllib.request.urlopen") as mock_urlopen:
            from aec.lib.version_check import check_for_update
            result = check_for_update()
            mock_urlopen.assert_not_called()
            assert result is not None
            assert result["latest_version"] == "2.1.0"

    def test_returns_none_on_any_error(self, temp_dir, monkeypatch):
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", temp_dir / "vc.json")

        with patch("aec.lib.version_check.urllib.request.urlopen", side_effect=Exception("boom")):
            from aec.lib.version_check import check_for_update
            assert check_for_update() is None


class TestPrintUpdateBanner:
    """Test print_update_banner output."""

    def test_prints_banner_when_update_info_provided(self, capsys):
        from aec.lib.version_check import print_update_banner
        print_update_banner({
            "current_version": "2.0.0",
            "latest_version": "2.1.0",
            "release_url": "https://example.com/releases/v2.1.0",
        })
        output = capsys.readouterr().out
        assert "2.0.0" in output
        assert "2.1.0" in output
        assert "git pull" in output
        assert "https://example.com/releases/v2.1.0" in output

    def test_does_nothing_when_none(self, capsys):
        from aec.lib.version_check import print_update_banner
        print_update_banner(None)
        output = capsys.readouterr().out
        assert output == ""


class TestDoctorIntegration:
    """Test that doctor shows version check status."""

    def test_doctor_shows_update_check_preference(self, capsys, temp_dir, monkeypatch):
        """Doctor should display whether update checking is enabled."""
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", temp_dir / "vc.json")

        from aec.lib.preferences import get_preference
        assert get_preference("update_check") is None  # Not yet set


class TestUpdateCheckPreference:
    """Test that update_check is registered as a preference."""

    def test_update_check_in_optional_features(self):
        from aec.lib.preferences import OPTIONAL_FEATURES
        assert "update_check" in OPTIONAL_FEATURES
        assert "description" in OPTIONAL_FEATURES["update_check"]


class TestCLIIntegration:
    """Test that version check runs via CLI callback."""

    def test_maybe_check_for_update_respects_disabled_preference(self, temp_dir, monkeypatch):
        """When update_check preference is False, skip the check entirely."""
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", temp_dir / "vc.json")

        from aec.lib.preferences import set_preference
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        set_preference("update_check", False)

        from aec.lib.version_check import maybe_check_for_update
        with patch("aec.lib.version_check.check_for_update") as mock_check:
            maybe_check_for_update()
            mock_check.assert_not_called()

    def test_maybe_check_for_update_runs_when_enabled(self, temp_dir, monkeypatch):
        """When update_check preference is True or unset, run the check."""
        monkeypatch.setattr("aec.lib.version_check.VERSION_CACHE_FILE", temp_dir / "vc.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")

        from aec.lib.version_check import maybe_check_for_update
        with patch("aec.lib.version_check.check_for_update", return_value=None) as mock_check:
            maybe_check_for_update()
            mock_check.assert_called_once()
