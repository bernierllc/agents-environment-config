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
