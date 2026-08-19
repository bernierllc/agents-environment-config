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


# --- headless batch driver (aec test schedule --do / --list) ---------------

from aec.lib.test_schedule_repo import run_repo_schedule_batch  # noqa: E402


def _load(repo):
    return json.loads((repo / ".aec.json").read_text())["test"]


def test_batch_applies_every_verb_and_saves(tmp_path):
    rc = run_repo_schedule_batch(
        tmp_path,
        ["n unit :: npm test", "n e2e :: npm run e2e", "o e2e,unit", "mv 1 2"],
    )
    assert rc == 0
    test = _load(tmp_path)
    assert test["scheduled"] == ["unit", "e2e"]
    assert test["suites"]["e2e"]["command"] == "npm run e2e"


def test_batch_removes_by_position(tmp_path):
    run_repo_schedule_batch(tmp_path, ["n unit :: npm test", "n e2e :: npm run e2e"])
    assert run_repo_schedule_batch(tmp_path, ["r 1"]) == 0
    assert _load(tmp_path)["scheduled"] == ["e2e"]


def test_batch_writes_nothing_when_a_verb_fails(tmp_path):
    run_repo_schedule_batch(tmp_path, ["n unit :: npm test"])
    before = (tmp_path / ".aec.json").read_text()
    assert run_repo_schedule_batch(tmp_path, ["n e2e :: npm run e2e", "+ nope"]) == 1
    assert (tmp_path / ".aec.json").read_text() == before


def test_batch_list_does_not_save(tmp_path):
    run_repo_schedule_batch(tmp_path, ["n unit :: npm test"])
    before = (tmp_path / ".aec.json").read_text()
    assert run_repo_schedule_batch(tmp_path, ["list"], save=False) == 0
    assert (tmp_path / ".aec.json").read_text() == before


def test_batch_never_prompts(tmp_path, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("headless batch must not call input()")

    monkeypatch.setattr("builtins.input", boom)
    assert run_repo_schedule_batch(tmp_path, ["n unit :: npm test"]) == 0


def test_command_routes_to_the_batch_driver(tmp_path, monkeypatch):
    from aec.commands import test_cmd

    monkeypatch.setattr("aec.lib.scope.find_tracked_repo", lambda: tmp_path)
    assert test_cmd.run_test_schedule(commands=["n unit :: npm test"]) == 0
    assert _load(tmp_path)["scheduled"] == ["unit"]


def test_command_errors_outside_a_tracked_repo(monkeypatch):
    from aec.commands import test_cmd

    monkeypatch.setattr("aec.lib.scope.find_tracked_repo", lambda: None)
    assert test_cmd.run_test_schedule(list_only=True) == 1
