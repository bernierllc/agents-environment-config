"""Tests for OS-specific scheduler wrappers."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Dispatcher tests
# ---------------------------------------------------------------------------


class TestGetScheduler:
    """Test that get_scheduler returns the correct platform module."""

    def test_returns_module_with_required_interface(self):
        from aec.lib.schedulers import get_scheduler

        mod = get_scheduler()
        assert callable(getattr(mod, "register", None))
        assert callable(getattr(mod, "unregister", None))
        assert callable(getattr(mod, "is_registered", None))
        assert callable(getattr(mod, "get_next_run", None))

    def test_returns_macos_on_darwin(self, monkeypatch):
        monkeypatch.setattr("aec.lib.config.IS_MACOS", True)
        monkeypatch.setattr("aec.lib.config.IS_LINUX", False)
        monkeypatch.setattr("aec.lib.config.IS_WINDOWS", False)
        from aec.lib.schedulers import get_scheduler

        mod = get_scheduler()
        assert mod.__name__.endswith("macos")

    def test_returns_linux_on_linux(self, monkeypatch):
        monkeypatch.setattr("aec.lib.config.IS_MACOS", False)
        monkeypatch.setattr("aec.lib.config.IS_LINUX", True)
        monkeypatch.setattr("aec.lib.config.IS_WINDOWS", False)
        from aec.lib.schedulers import get_scheduler

        mod = get_scheduler()
        assert mod.__name__.endswith("linux")

    def test_returns_windows_on_windows(self, monkeypatch):
        monkeypatch.setattr("aec.lib.config.IS_MACOS", False)
        monkeypatch.setattr("aec.lib.config.IS_LINUX", False)
        monkeypatch.setattr("aec.lib.config.IS_WINDOWS", True)
        from aec.lib.schedulers import get_scheduler

        mod = get_scheduler()
        assert mod.__name__.endswith("windows")


# ---------------------------------------------------------------------------
# macOS tests
# ---------------------------------------------------------------------------


class TestMacOSScheduler:
    """Test macOS launchd scheduler wrapper."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch, tmp_path):
        """Redirect plist path to tmp and stub subprocess."""
        from aec.lib.schedulers import macos

        self.plist_path = tmp_path / "com.aec.test-runner.plist"
        monkeypatch.setattr(macos, "PLIST_PATH", self.plist_path)
        self.macos = macos
        self.runner_path = Path("/usr/local/bin/aec-runner.py")

        self.subprocess_calls = []

        def fake_run(cmd, **kwargs):
            self.subprocess_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

    def test_register_creates_plist(self):
        result = self.macos.register(self.runner_path, 3, 30)
        assert "03:30" in result
        assert self.plist_path.exists()

    def test_register_calls_launchctl_load(self):
        self.macos.register(self.runner_path, 3, 30)
        assert any("launchctl" in str(c) for c in self.subprocess_calls)
        load_call = [c for c in self.subprocess_calls if "launchctl" in str(c)][0]
        assert "load" in load_call

    def test_plist_xml_is_well_formed(self):
        self.macos.register(self.runner_path, 14, 5)
        import xml.etree.ElementTree as ET

        content = self.plist_path.read_text()
        # Remove DOCTYPE (ET doesn't handle it)
        clean = content.replace(
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            "",
        )
        ET.fromstring(clean)  # raises if malformed

    def test_plist_contains_correct_hour_minute(self):
        self.macos.register(self.runner_path, 14, 5)
        content = self.plist_path.read_text()
        assert "<integer>14</integer>" in content
        assert "<integer>5</integer>" in content

    def test_plist_contains_correct_runner_path(self):
        self.macos.register(self.runner_path, 0, 0)
        content = self.plist_path.read_text()
        assert str(self.runner_path) in content

    def test_unregister_deletes_plist(self):
        self.macos.register(self.runner_path, 3, 30)
        self.macos.unregister()
        assert not self.plist_path.exists()

    def test_unregister_calls_launchctl_unload(self):
        self.macos.register(self.runner_path, 3, 30)
        self.subprocess_calls.clear()
        self.macos.unregister()
        unload_call = [c for c in self.subprocess_calls if "launchctl" in str(c)][0]
        assert "unload" in unload_call

    def test_unregister_handles_missing_plist(self):
        result = self.macos.unregister()
        assert "Unregistered" in result

    def test_is_registered_true_when_plist_exists(self):
        self.macos.register(self.runner_path, 3, 30)
        assert self.macos.is_registered() is True

    def test_is_registered_false_when_no_plist(self):
        assert self.macos.is_registered() is False

    def test_get_next_run_returns_time_when_registered(self):
        self.macos.register(self.runner_path, 14, 5)
        result = self.macos.get_next_run()
        assert result == "14:05 daily"

    def test_get_next_run_returns_none_when_not_registered(self):
        assert self.macos.get_next_run() is None

    def test_register_handles_subprocess_error(self, monkeypatch):
        def failing_run(cmd, **kwargs):
            raise OSError("launchctl not found")

        monkeypatch.setattr(subprocess, "run", failing_run)
        result = self.macos.register(self.runner_path, 3, 30)
        assert "Failed" in result


# ---------------------------------------------------------------------------
# Linux tests
# ---------------------------------------------------------------------------


class TestLinuxScheduler:
    """Test Linux crontab scheduler wrapper."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        from aec.lib.schedulers import linux

        self.linux = linux
        self.runner_path = Path("/usr/local/bin/aec-runner.py")
        self.current_crontab = ""
        self.subprocess_calls = []

        def fake_run(cmd, **kwargs):
            self.subprocess_calls.append((cmd, kwargs))
            if cmd == ["crontab", "-l"]:
                if self.current_crontab:
                    return subprocess.CompletedProcess(
                        cmd, 0, stdout=self.current_crontab, stderr=""
                    )
                else:
                    return subprocess.CompletedProcess(
                        cmd, 1, stdout="", stderr="no crontab"
                    )
            elif cmd == ["crontab", "-"]:
                self.current_crontab = kwargs.get("input", "")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

    def test_register_adds_cron_entry(self):
        result = self.linux.register(self.runner_path, 3, 30)
        assert "03:30" in result
        assert "# AEC test runner" in self.current_crontab

    def test_crontab_entry_format_is_correct(self):
        self.linux.register(self.runner_path, 3, 30)
        lines = [l for l in self.current_crontab.splitlines() if "AEC" in l]
        assert len(lines) == 1
        entry = lines[0]
        assert entry.startswith("30 3 * * *")
        assert f"python3 {self.runner_path}" in entry

    def test_existing_entries_are_replaced_not_duplicated(self):
        self.linux.register(self.runner_path, 3, 30)
        self.linux.register(self.runner_path, 5, 0)
        lines = [l for l in self.current_crontab.splitlines() if "AEC" in l]
        assert len(lines) == 1
        assert "0 5 * * *" in lines[0]

    def test_handles_empty_crontab(self):
        self.current_crontab = ""
        result = self.linux.register(self.runner_path, 3, 30)
        assert "03:30" in result
        assert "# AEC test runner" in self.current_crontab

    def test_unregister_removes_entry(self):
        self.linux.register(self.runner_path, 3, 30)
        self.linux.unregister()
        assert "# AEC test runner" not in self.current_crontab

    def test_unregister_preserves_other_entries(self):
        self.current_crontab = "0 * * * * /usr/bin/other-job\n"
        self.linux.register(self.runner_path, 3, 30)
        self.linux.unregister()
        assert "other-job" in self.current_crontab
        assert "# AEC test runner" not in self.current_crontab

    def test_is_registered_true(self):
        self.linux.register(self.runner_path, 3, 30)
        assert self.linux.is_registered() is True

    def test_is_registered_false(self):
        assert self.linux.is_registered() is False

    def test_get_next_run_returns_time(self):
        self.linux.register(self.runner_path, 14, 5)
        result = self.linux.get_next_run()
        assert result == "14:05 daily"

    def test_get_next_run_returns_none(self):
        assert self.linux.get_next_run() is None

    def test_register_handles_subprocess_error(self, monkeypatch):
        def failing_run(cmd, **kwargs):
            raise OSError("crontab not found")

        monkeypatch.setattr(subprocess, "run", failing_run)
        result = self.linux.register(self.runner_path, 3, 30)
        assert "Failed" in result


# ---------------------------------------------------------------------------
# Windows tests
# ---------------------------------------------------------------------------


class TestWindowsScheduler:
    """Test Windows Task Scheduler wrapper."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        from aec.lib.schedulers import windows

        self.windows = windows
        self.runner_path = Path("C:/aec/runner.py")
        self.subprocess_calls = []
        self.registered = False

        def fake_run(cmd, **kwargs):
            self.subprocess_calls.append((cmd, kwargs))
            if "/Create" in cmd:
                self.registered = True
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            elif "/Delete" in cmd:
                self.registered = False
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            elif "/Query" in cmd:
                if self.registered:
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout="TaskName: AEC_TestRunner\nNext Run Time: 03:30\n",
                        stderr="",
                    )
                return subprocess.CompletedProcess(
                    cmd, 1, stdout="", stderr="not found"
                )
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

    def test_register_returns_status(self):
        result = self.windows.register(self.runner_path, 3, 30)
        assert "03:30" in result

    def test_schtasks_command_format(self):
        self.windows.register(self.runner_path, 3, 30)
        create_call = [c for c, _ in self.subprocess_calls if "/Create" in c][0]
        assert "schtasks" in create_call
        assert "/SC" in create_call
        assert "DAILY" in create_call
        assert "/TN" in create_call
        assert "AEC_TestRunner" in create_call
        assert "/ST" in create_call
        assert "03:30" in create_call
        assert "/F" in create_call

    def test_unregister_returns_status(self):
        result = self.windows.unregister()
        assert "Unregistered" in result

    def test_is_registered_true(self):
        self.windows.register(self.runner_path, 3, 30)
        assert self.windows.is_registered() is True

    def test_is_registered_false(self):
        assert self.windows.is_registered() is False

    def test_get_next_run_returns_time(self):
        self.windows.register(self.runner_path, 3, 30)
        result = self.windows.get_next_run()
        assert result is not None
        assert "03:30" in result

    def test_get_next_run_returns_none_when_not_registered(self):
        assert self.windows.get_next_run() is None

    def test_register_handles_subprocess_error(self, monkeypatch):
        def failing_run(cmd, **kwargs):
            raise OSError("schtasks not found")

        monkeypatch.setattr(subprocess, "run", failing_run)
        result = self.windows.register(self.runner_path, 3, 30)
        assert "Failed" in result
