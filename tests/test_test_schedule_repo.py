"""Tests for per-repo test scheduling (aec.lib.test_schedule_repo)."""

import json
from pathlib import Path


class TestMergeDiscoveryIntoSuites:
    """Tests for merge_discovery_into_suites."""

    def test_merge_adds_package_json_scripts(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"test": "jest", "build": "tsc"}}),
            encoding="utf-8",
        )
        from aec.lib.test_schedule_repo import merge_discovery_into_suites

        suites: dict = {}
        added = merge_discovery_into_suites(tmp_path, suites)
        assert "test" in suites
        assert "test" in added
        assert suites["test"]["command"] == "npm run test"

    def test_merge_adds_makefile_target(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("test:\n\tpytest\n", encoding="utf-8")
        from aec.lib.test_schedule_repo import merge_discovery_into_suites

        suites = {}
        added = merge_discovery_into_suites(tmp_path, suites)
        assert "make:test" in suites
        assert "make:test" in added
        assert suites["make:test"]["command"] == "make test"

    def test_merge_idempotent(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"scripts": {"test": "jest"}}),
            encoding="utf-8",
        )
        from aec.lib.test_schedule_repo import merge_discovery_into_suites

        suites = {"test": {"command": "npm run test", "cleanup": None}}
        added = merge_discovery_into_suites(tmp_path, suites)
        assert added == []


class TestMoveScheduledItem:
    """move_scheduled_item (REPL ``mv``)."""

    def test_moves_and_preserves_order(self) -> None:
        from aec.lib.test_schedule_repo import move_scheduled_item

        scheduled = ["a", "b", "c"]
        assert move_scheduled_item(scheduled, 1, 3) is True
        assert scheduled == ["b", "c", "a"]

    def test_invalid_returns_false(self) -> None:
        from aec.lib.test_schedule_repo import move_scheduled_item

        one = ["only"]
        assert move_scheduled_item(one, 1, 2) is False
        assert one == ["only"]

        three = ["a", "b", "c"]
        assert move_scheduled_item(three, 0, 2) is False
        assert move_scheduled_item(three, 1, 5) is False
        assert three == ["a", "b", "c"]


class TestNormalizeScheduled:
    """Scheduled list normalization via merge + save path."""

    def test_drops_unknown_and_dedupes(self, tmp_path: Path) -> None:
        from aec.lib import test_schedule_repo as tsr

        suites = {"a": {"command": "x"}, "b": {"command": "y"}}
        raw = ["a", "ghost", "a", "b"]
        out = tsr._normalize_scheduled(raw, suites)
        assert out == ["a", "b"]
