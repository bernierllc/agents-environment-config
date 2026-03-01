"""Tests for Console section-replace UX."""

import io
import os
import sys

import pytest

from aec.lib.console import Console, _LineCountingStream


class TestLineCountingStream:
    """Tests for _LineCountingStream."""

    def test_counts_newlines_single_line(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        stream.write("hello\n")
        assert stream.line_count == 1
        assert real.getvalue() == "hello\n"

    def test_counts_newlines_multiple(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        stream.write("a\nb\nc\n")
        assert stream.line_count == 3

    def test_counts_newlines_no_trailing(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        stream.write("no newline")
        assert stream.line_count == 0

    def test_counts_across_multiple_writes(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        stream.write("a\n")
        stream.write("b\n")
        stream.write("c\n")
        assert stream.line_count == 3

    def test_delegates_flush(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        # Should not raise
        stream.flush()

    def test_delegates_attribute_access(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        # StringIO has getvalue — should be accessible via delegation
        stream.write("test")
        assert stream.getvalue() == "test"

    def test_write_returns_char_count(self):
        real = io.StringIO()
        stream = _LineCountingStream(real)
        result = stream.write("hello\n")
        assert result == 6


class TestShouldUseSections:
    """Tests for Console._should_use_sections()."""

    def setup_method(self):
        # Reset cached value before each test
        Console._sections_enabled = None

    def test_false_when_not_tty(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("AEC_NO_SECTIONS", raising=False)
        monkeypatch.delenv("TERM", raising=False)
        assert Console._should_use_sections() is False

    def test_false_when_no_color_set(self, monkeypatch):
        # Use a fake TTY stream
        fake_tty = io.StringIO()
        fake_tty.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", fake_tty)
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("AEC_NO_SECTIONS", raising=False)
        monkeypatch.delenv("TERM", raising=False)
        assert Console._should_use_sections() is False

    def test_false_when_aec_no_sections_set(self, monkeypatch):
        fake_tty = io.StringIO()
        fake_tty.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", fake_tty)
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("AEC_NO_SECTIONS", "1")
        monkeypatch.delenv("TERM", raising=False)
        assert Console._should_use_sections() is False

    def test_false_when_term_dumb(self, monkeypatch):
        fake_tty = io.StringIO()
        fake_tty.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", fake_tty)
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("AEC_NO_SECTIONS", raising=False)
        monkeypatch.setenv("TERM", "dumb")
        assert Console._should_use_sections() is False

    def test_true_when_tty_and_no_blockers(self, monkeypatch):
        fake_tty = io.StringIO()
        fake_tty.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", fake_tty)
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.delenv("AEC_NO_SECTIONS", raising=False)
        monkeypatch.delenv("TERM", raising=False)
        assert Console._should_use_sections() is True

    def test_caches_result(self, monkeypatch):
        Console._sections_enabled = True
        # Even with non-TTY stdout, cached value wins
        monkeypatch.setattr(sys, "stdout", io.StringIO())
        assert Console._should_use_sections() is True


class TestConsoleSection:
    """Tests for Console.section() context manager."""

    def setup_method(self):
        Console._sections_enabled = None
        Console._use_colors = None

    def test_collapse_false_no_ansi_cursor(self, monkeypatch, capsys):
        """collapse=False should not emit ANSI cursor movement."""
        Console._sections_enabled = True
        Console._use_colors = False

        with Console.section("Test Section", collapse=False):
            print("detail line 1")
            print("detail line 2")

        captured = capsys.readouterr()
        assert "\033[A" not in captured.out  # No cursor up
        assert "detail line 1" in captured.out
        assert "detail line 2" in captured.out

    def test_collapse_true_non_tty_degrades(self, monkeypatch, capsys):
        """collapse=True on non-TTY should degrade to plain output (no ANSI)."""
        Console._sections_enabled = False  # Simulates non-TTY
        Console._use_colors = False

        with Console.section("Test Section", collapse=True):
            print("detail line")

        captured = capsys.readouterr()
        assert "\033[A" not in captured.out
        assert "detail line" in captured.out

    def test_collapse_true_tty_emits_ansi(self, monkeypatch):
        """collapse=True on TTY emits cursor-up + clear-line and summary."""
        Console._sections_enabled = True
        Console._use_colors = False

        buf = io.StringIO()
        buf.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", buf)

        with Console.section("Test Section", collapse=True, delay=0):
            print("detail line 1")
            print("detail line 2")

        output = buf.getvalue()
        assert "\033[A" in output  # Cursor up
        assert "\033[2K" in output  # Clear line
        assert "✓ Test Section" in output  # Summary line

    def test_exception_does_not_collapse(self, monkeypatch):
        """Exception inside section should NOT collapse — error output preserved."""
        Console._sections_enabled = True
        Console._use_colors = False

        buf = io.StringIO()
        buf.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", buf)

        with pytest.raises(ValueError, match="boom"):
            with Console.section("Failing Section", collapse=True, delay=0):
                print("error context")
                raise ValueError("boom")

        output = buf.getvalue()
        assert "error context" in output
        # Should NOT have collapsed
        assert "✓ Failing Section" not in output

    def test_stdout_restored_after_section(self, monkeypatch):
        """sys.stdout should be restored after section exits."""
        Console._sections_enabled = True
        Console._use_colors = False

        original = sys.stdout
        buf = io.StringIO()
        buf.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", buf)

        with Console.section("Restore Test", collapse=True, delay=0):
            print("inside")

        # After section, stdout should be buf (the monkeypatched "real" stdout)
        assert sys.stdout is buf

    def test_stdout_restored_after_exception(self, monkeypatch):
        """sys.stdout should be restored even after exception."""
        Console._sections_enabled = True
        Console._use_colors = False

        buf = io.StringIO()
        buf.isatty = lambda: True
        monkeypatch.setattr(sys, "stdout", buf)

        with pytest.raises(RuntimeError):
            with Console.section("Exception Test", collapse=True, delay=0):
                raise RuntimeError("fail")

        assert sys.stdout is buf

    def test_subheader_printed_for_section(self, capsys):
        """Section name should appear as subheader."""
        Console._sections_enabled = False
        Console._use_colors = False

        with Console.section("My Section", collapse=False):
            pass

        captured = capsys.readouterr()
        assert "My Section" in captured.out
