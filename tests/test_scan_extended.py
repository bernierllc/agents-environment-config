"""Tests for scan_extended_test_commands."""

import json
from pathlib import Path


class TestScanExtendedTestCommands:
    """Extended hooks beyond package.json / pyproject."""

    def test_deno(self, tmp_path: Path) -> None:
        (tmp_path / "deno.json").write_text("{}", encoding="utf-8")
        from aec.lib.test_detection import scan_extended_test_commands

        r = scan_extended_test_commands(tmp_path)
        names = [x["name"] for x in r]
        assert "deno:test" in names
        assert any(x["command"] == "deno test" for x in r)

    def test_turbo(self, tmp_path: Path) -> None:
        (tmp_path / "turbo.json").write_text("{}", encoding="utf-8")
        from aec.lib.test_detection import scan_extended_test_commands

        r = scan_extended_test_commands(tmp_path)
        assert any(x["name"] == "turbo:test" for x in r)

    def test_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        from aec.lib.test_detection import scan_extended_test_commands

        r = scan_extended_test_commands(tmp_path)
        assert any(x["name"] == "gradle:test" for x in r)

    def test_makefile_only_with_test_target(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("all:\n\techo\n", encoding="utf-8")
        from aec.lib.test_detection import scan_extended_test_commands

        assert scan_extended_test_commands(tmp_path) == []
