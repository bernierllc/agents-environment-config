"""Tests for conflict-resolution persistence and input-hash invalidation."""

from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.resolutions import (
    Resolution,
    input_hash_for,
    is_valid,
    load_history,
    load_resolutions,
    prune_invalid,
    save_resolution,
)


def _res(conflict_id="conf-abcd1234", decision="honor:acme", input_hash="sha256:aaa"):
    return Resolution(
        conflict_id=conflict_id,
        decision=decision,
        input_hash=input_hash,
        decided_at="2026-05-24T00:00:00Z",
        decided_by="matt@bernierllc.com",
    )


def test_round_trip(tmp_path):
    paths = OrgPaths(home_dir=tmp_path)
    save_resolution(paths, _res())
    loaded = load_resolutions(paths)
    assert loaded["conf-abcd1234"].decision == "honor:acme"


def test_input_hash_is_order_independent():
    h1 = input_hash_for(["acme", "globex"], {"acme": "sha256:a", "globex": "sha256:b"})
    h2 = input_hash_for(["globex", "acme"], {"globex": "sha256:b", "acme": "sha256:a"})
    assert h1 == h2


def test_input_hash_changes_with_config_hash():
    h1 = input_hash_for(["acme"], {"acme": "sha256:a"})
    h2 = input_hash_for(["acme"], {"acme": "sha256:CHANGED"})
    assert h1 != h2


def test_is_valid_detects_stale_inputs():
    res = _res(input_hash="sha256:original")
    assert is_valid(res, "sha256:original") is True
    assert is_valid(res, "sha256:different") is False


def test_superseded_resolution_moves_to_history(tmp_path):
    paths = OrgPaths(home_dir=tmp_path)
    save_resolution(paths, _res(decision="honor:acme", input_hash="sha256:v1"))
    # Same conflict, new decision/inputs -> prior goes to history.
    save_resolution(paths, _res(decision="honor:globex", input_hash="sha256:v2"))

    live = load_resolutions(paths)
    assert live["conf-abcd1234"].decision == "honor:globex"
    history = load_history(paths)
    assert len(history) == 1
    assert history[0]["decision"] == "honor:acme"
    assert history[0]["reason"] == "superseded"


def test_prune_invalid_removes_stale_and_keeps_valid(tmp_path):
    paths = OrgPaths(home_dir=tmp_path)
    save_resolution(paths, _res(conflict_id="conf-keep", input_hash="sha256:good"))
    save_resolution(paths, _res(conflict_id="conf-drop", input_hash="sha256:old"))

    pruned = prune_invalid(paths, {"conf-keep": "sha256:good", "conf-drop": "sha256:new"})

    assert pruned == ["conf-drop"]
    live = load_resolutions(paths)
    assert "conf-keep" in live
    assert "conf-drop" not in live
    assert any(h["conflict_id"] == "conf-drop" for h in load_history(paths))


def test_missing_file_loads_empty(tmp_path):
    paths = OrgPaths(home_dir=tmp_path)
    assert load_resolutions(paths) == {}
