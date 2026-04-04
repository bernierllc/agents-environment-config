# tests/test_deprecation.py
"""Tests for deprecation shims."""

import pytest


class TestDeprecationWarnings:
    def test_warns_on_old_command(self, capsys):
        from aec.commands.deprecation import deprecation_warning
        deprecation_warning("aec skills install X", "aec install skill X")
        captured = capsys.readouterr()
        assert "deprecated" in captured.err.lower()
        assert "aec install skill X" in captured.err

    def test_warning_includes_old_command(self, capsys):
        from aec.commands.deprecation import deprecation_warning
        deprecation_warning("aec repo list", "aec list --scope global")
        captured = capsys.readouterr()
        assert "aec repo list" in captured.err
        assert "aec list --scope global" in captured.err

    def test_warning_mentions_removal(self, capsys):
        from aec.commands.deprecation import deprecation_warning
        deprecation_warning("aec rules generate", "aec generate rules")
        captured = capsys.readouterr()
        assert "removed" in captured.err.lower()

    def test_warning_goes_to_stderr_not_stdout(self, capsys):
        from aec.commands.deprecation import deprecation_warning
        deprecation_warning("aec old", "aec new")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "deprecated" in captured.err.lower()
