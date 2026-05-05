"""Tests for aec.lib.debug — error capture, redaction, and the global handler."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture
def fresh_debug(monkeypatch, tmp_path):
    """Reload the debug module against a temp HOME so each test is isolated."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Reload config first so AEC_HOME picks up the patched home,
    # then reload debug so LOG_DIR/LOG_FILE rebind to the new path.
    from aec.lib import config as _config
    importlib.reload(_config)
    from aec.lib import debug as _debug
    importlib.reload(_debug)
    # Reset module-level state explicitly.
    _debug._debug_enabled = False
    _debug._logger = None
    # The stdlib logging registry is global — drop any handlers from prior
    # tests so the RotatingFileHandler is rebuilt against the current tmp HOME.
    import logging as _logging
    _stale = _logging.getLogger(_debug._LOGGER_NAME)
    for h in list(_stale.handlers):
        h.close()
        _stale.removeHandler(h)
    return _debug


class TestRedaction:
    def test_redacts_unix_user_paths(self, fresh_debug):
        d = fresh_debug
        assert "/Users/USER" in d.redact("/Users/alice/projects/foo.py")
        assert "/home/USER" in d.redact("/home/bob/repos/x")

    def test_redacts_windows_user_paths(self, fresh_debug):
        d = fresh_debug
        assert "C:\\Users\\USER" in d.redact("C:\\Users\\carol\\Desktop")

    def test_redacts_home_directory(self, fresh_debug, tmp_path):
        d = fresh_debug
        sample = f"error at {tmp_path}/some/file"
        assert str(tmp_path) not in d.redact(sample)
        assert "~" in d.redact(sample)

    def test_redacts_secretlike_long_tokens(self, fresh_debug):
        d = fresh_debug
        token = "A" * 40
        assert "<REDACTED>" in d.redact(f"token={token}")

    def test_does_not_blank_short_strings(self, fresh_debug):
        d = fresh_debug
        assert d.redact("hello world") == "hello world"


class TestEnableAndDetect:
    def test_disabled_by_default(self, fresh_debug):
        assert fresh_debug.is_debug() is False

    def test_enable_debug_sets_flag(self, fresh_debug):
        fresh_debug.enable_debug()
        assert fresh_debug.is_debug() is True

    def test_detects_argv_flag(self, fresh_debug):
        assert fresh_debug.debug_from_env_or_argv(["upgrade", "--debug"]) is True
        assert fresh_debug.debug_from_env_or_argv(["upgrade"]) is False

    def test_detects_env_var(self, fresh_debug, monkeypatch):
        monkeypatch.setenv("AEC_DEBUG", "1")
        assert fresh_debug.debug_from_env_or_argv([]) is True
        monkeypatch.setenv("AEC_DEBUG", "off")
        assert fresh_debug.debug_from_env_or_argv([]) is False


class TestLogException:
    def test_writes_traceback_to_log_file(self, fresh_debug):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            log_path = fresh_debug.log_exception(exc, command="aec upgrade")
        assert log_path.exists()
        content = log_path.read_text()
        assert "RuntimeError: boom" in content
        assert "aec upgrade" in content
        assert "==== aec error ====" in content

    def test_log_redacts_paths(self, fresh_debug, tmp_path):
        try:
            raise RuntimeError(f"failed in {tmp_path}/secret")
        except RuntimeError as exc:
            log_path = fresh_debug.log_exception(exc)
        content = log_path.read_text()
        assert str(tmp_path) not in content
        assert "~" in content or "/Users/USER" in content or "/home/USER" in content

    def test_secret_env_values_redacted(self, fresh_debug, monkeypatch):
        monkeypatch.setenv("AEC_API_KEY", "super-secret-value-1234")
        try:
            raise RuntimeError("nope")
        except RuntimeError as exc:
            log_path = fresh_debug.log_exception(exc)
        content = log_path.read_text()
        assert "super-secret-value-1234" not in content
        assert "<REDACTED>" in content


class TestSubprocessFailureLogging:
    def test_skips_when_debug_disabled(self, fresh_debug):
        result = fresh_debug.log_subprocess_failure(
            cmd=["git", "pull"], returncode=1, stderr="bad"
        )
        assert result is None
        assert not fresh_debug.LOG_FILE.exists()

    def test_writes_when_debug_enabled(self, fresh_debug):
        fresh_debug.enable_debug()
        result = fresh_debug.log_subprocess_failure(
            cmd=["git", "pull", "--ff-only"],
            returncode=1,
            stderr="fatal: refusing to merge unrelated histories",
            note="fetch_latest",
        )
        assert result is not None and result.exists()
        content = result.read_text()
        assert "git pull --ff-only" in content
        assert "returncode: 1" in content
        assert "refusing to merge" in content
        assert "fetch_latest" in content

    def test_redacts_user_path_in_note(self, fresh_debug, tmp_path):
        fresh_debug.enable_debug()
        result = fresh_debug.log_subprocess_failure(
            cmd=["git", "pull"],
            returncode=1,
            note=f"fetch_latest in {tmp_path}",
        )
        assert result is not None
        content = result.read_text()
        assert str(tmp_path) not in content


class TestFriendlyMessages:
    def test_friendly_message_points_to_issue_url(self, fresh_debug):
        msg = fresh_debug.friendly_error_message()
        assert "github.com/mattbernier/agents-environment-config" in msg
        assert "--debug" in msg

    def test_debug_message_includes_log_path(self, fresh_debug, tmp_path):
        msg = fresh_debug.debug_error_message(tmp_path / "foo.log")
        assert "foo.log" in msg
        assert "github.com/mattbernier/agents-environment-config" in msg


class TestCLIIntegration:
    """In-process: call aec.cli.main() with a command monkeypatched to raise."""

    def _invoke_main(self, argv, monkeypatch, capsys):
        from aec import cli as _cli
        from aec.commands import doctor as _doctor
        from aec.lib import preferences as _prefs
        from aec.lib import version_check as _vc

        def _boom():
            raise RuntimeError("synthetic crash for tests")

        # Bypass interactive callback work that would block on stdin.
        monkeypatch.setattr(_prefs, "check_pending_preferences", lambda: None)
        monkeypatch.setattr(_vc, "maybe_check_for_update", lambda: None)
        monkeypatch.setattr(_doctor, "run_doctor", _boom)
        monkeypatch.setattr(sys, "argv", ["aec"] + argv)
        with pytest.raises(SystemExit) as exc_info:
            _cli.main()
        return exc_info.value.code, capsys.readouterr()

    def test_friendly_message_without_debug(self, fresh_debug, monkeypatch, capsys):
        code, captured = self._invoke_main(["doctor"], monkeypatch, capsys)
        assert code == 1
        combined = captured.out + captured.err
        assert "aec encountered an error" in combined
        assert "--debug" in combined
        assert "github.com/mattbernier/agents-environment-config" in combined
        assert "Traceback (most recent call last)" not in combined
        assert "synthetic crash for tests" not in combined

    def test_debug_writes_log_and_shows_traceback(
        self, fresh_debug, monkeypatch, capsys, tmp_path
    ):
        code, captured = self._invoke_main(["doctor", "--debug"], monkeypatch, capsys)
        assert code == 1
        combined = captured.out + captured.err
        assert "Traceback" in combined
        assert "synthetic crash for tests" in combined
        log_file = fresh_debug.LOG_FILE
        assert log_file.exists(), f"expected log at {log_file}"
        content = log_file.read_text()
        assert "synthetic crash for tests" in content
        assert "==== aec error ====" in content
