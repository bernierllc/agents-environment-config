"""Tests for aec.lib.viewers module."""

import pytest

from aec.lib.viewers import (
    REPORT_VIEWERS,
    get_platform_key,
    detect_viewers,
    get_viewer_command,
    format_viewer_command,
)


class TestReportViewersRegistry:
    """Test the REPORT_VIEWERS registry structure."""

    def test_has_all_platforms(self):
        """Registry must have entries for darwin, linux, and windows."""
        assert "darwin" in REPORT_VIEWERS
        assert "linux" in REPORT_VIEWERS
        assert "windows" in REPORT_VIEWERS

    def test_each_platform_has_at_least_one_viewer(self):
        """Every platform must have at least one viewer."""
        for platform_key, viewers in REPORT_VIEWERS.items():
            assert len(viewers) >= 1, f"{platform_key} has no viewers"

    def test_each_viewer_has_required_keys(self):
        """Every viewer entry must have display_name, command, and detect."""
        for platform_key, viewers in REPORT_VIEWERS.items():
            for viewer_key, config in viewers.items():
                assert "display_name" in config, (
                    f"{platform_key}/{viewer_key} missing display_name"
                )
                assert "command" in config, (
                    f"{platform_key}/{viewer_key} missing command"
                )
                assert "detect" in config, (
                    f"{platform_key}/{viewer_key} missing detect"
                )

    def test_all_commands_contain_file_placeholder(self):
        """Every viewer command must contain {file} placeholder."""
        for platform_key, viewers in REPORT_VIEWERS.items():
            for viewer_key, config in viewers.items():
                assert "{file}" in config["command"], (
                    f"{platform_key}/{viewer_key} command missing {{file}} placeholder"
                )


class TestGetPlatformKey:
    """Test platform key detection."""

    def test_returns_darwin_on_macos(self, monkeypatch):
        """Should return 'darwin' when platform.system() returns 'Darwin'."""
        import platform as plat

        monkeypatch.setattr(plat, "system", lambda: "Darwin")
        assert get_platform_key() == "darwin"

    def test_returns_linux_on_linux(self, monkeypatch):
        """Should return 'linux' when platform.system() returns 'Linux'."""
        import platform as plat

        monkeypatch.setattr(plat, "system", lambda: "Linux")
        assert get_platform_key() == "linux"

    def test_returns_windows_on_windows(self, monkeypatch):
        """Should return 'windows' when platform.system() returns 'Windows'."""
        import platform as plat

        monkeypatch.setattr(plat, "system", lambda: "Windows")
        assert get_platform_key() == "windows"

    def test_returns_linux_for_unknown_platform(self, monkeypatch):
        """Should return 'linux' as fallback for unknown platforms."""
        import platform as plat

        monkeypatch.setattr(plat, "system", lambda: "FreeBSD")
        assert get_platform_key() == "linux"


class TestDetectViewers:
    """Test viewer detection logic."""

    def test_always_includes_detect_none_viewers(self, monkeypatch):
        """Viewers with detect=None should always be returned."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        result = detect_viewers(platform_key="darwin")
        keys = [v["key"] for v in result]
        # "open" on darwin has detect=None
        assert "open" in keys

    def test_filters_by_shutil_which(self, monkeypatch):
        """Viewers should be included only when shutil.which finds them."""
        import shutil

        available_commands = {"code"}
        monkeypatch.setattr(
            shutil, "which", lambda cmd: f"/usr/bin/{cmd}" if cmd in available_commands else None
        )

        result = detect_viewers(platform_key="darwin")
        keys = [v["key"] for v in result]
        assert "vscode" in keys
        assert "cursor" not in keys  # "cursor" command not in available_commands
        assert "nano" not in keys
        assert "vim" not in keys

    def test_no_viewers_available_returns_only_always_available(self, monkeypatch):
        """When no commands are found, only detect=None viewers are returned."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        result = detect_viewers(platform_key="windows")
        keys = [v["key"] for v in result]
        # windows has notepad (detect=None) and start (detect=None)
        assert "notepad" in keys
        assert "start" in keys
        assert "vscode" not in keys

    def test_auto_detects_platform(self, monkeypatch):
        """When platform_key is None, should auto-detect via get_platform_key."""
        import platform as plat
        import shutil

        monkeypatch.setattr(plat, "system", lambda: "Linux")
        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        result = detect_viewers()
        # Linux has no detect=None viewers, so nothing should come back
        assert result == []

    def test_result_dict_shape(self, monkeypatch):
        """Each result dict should have key, display_name, and command."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda cmd: None)

        result = detect_viewers(platform_key="darwin")
        for viewer in result:
            assert "key" in viewer
            assert "display_name" in viewer
            assert "command" in viewer


class TestGetViewerCommand:
    """Test viewer command retrieval."""

    def test_returns_command_for_known_viewer(self, monkeypatch):
        """Should return the command string for a known viewer key."""
        import platform as plat

        monkeypatch.setattr(plat, "system", lambda: "Darwin")

        cmd = get_viewer_command("vscode")
        assert cmd == "code {file}"

    def test_returns_none_for_unknown_viewer(self, monkeypatch):
        """Should return None for an unrecognized viewer key."""
        import platform as plat

        monkeypatch.setattr(plat, "system", lambda: "Darwin")

        cmd = get_viewer_command("nonexistent-viewer")
        assert cmd is None

    def test_explicit_platform_key(self):
        """Should use the explicit platform_key when provided."""
        cmd = get_viewer_command("notepad", platform_key="windows")
        assert cmd == "notepad {file}"


class TestFormatViewerCommand:
    """Test command formatting with file path substitution."""

    def test_replaces_file_placeholder(self):
        """Should replace {file} with the actual file path."""
        result = format_viewer_command("code {file}", "/tmp/report.html")
        assert result == "code /tmp/report.html"

    def test_paths_with_spaces(self):
        """Should handle file paths containing spaces."""
        result = format_viewer_command(
            "open {file}", "/Users/test user/my report.html"
        )
        assert result == "open /Users/test user/my report.html"

    def test_preserves_rest_of_command(self):
        """Should not alter parts of the command outside the placeholder."""
        result = format_viewer_command("nano {file}", "/tmp/r.txt")
        assert result == "nano /tmp/r.txt"
