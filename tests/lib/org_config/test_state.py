from pathlib import Path

import pytest

from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.state import (
    OrgState,
    OrgStateCorruptError,
    read_state,
    write_state,
)


def _make_state(**overrides) -> OrgState:
    base = dict(
        org_id="acme",
        config_version="1.0.0",
        config_hash="sha256:abc",
        trust_mode="unsigned",
        pubkey_fingerprint=None,
        pubkey_source=None,
        last_verified_at="2026-05-04T12:00:00Z",
        last_applied_at="2026-05-04T12:00:01Z",
        source_of_record="local",
        unsigned_warning_acknowledged_at="2026-05-04T12:00:00Z",
        key_rotation_pending=None,
    )
    base.update(overrides)
    return OrgState(**base)


def test_write_and_read_state_roundtrip(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)

    state = _make_state()
    write_state(paths, state)
    loaded = read_state(paths, "acme")
    assert loaded == state


def test_read_state_returns_none_for_unknown_org(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    assert read_state(paths, "ghost") is None


def test_write_state_is_atomic(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)

    write_state(paths, _make_state(unsigned_warning_acknowledged_at=None))

    tmp_files = list(paths.orgs_dir.glob("acme.state.json.tmp*"))
    assert tmp_files == []


def test_read_state_raises_on_corrupt_json(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    paths.state_for("acme").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(OrgStateCorruptError):
        read_state(paths, "acme")


def test_write_state_creates_orgs_dir_if_missing(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    # Note: orgs_dir intentionally not pre-created
    write_state(paths, _make_state())
    assert paths.state_for("acme").exists()


# --- StateSnapshot / all_or_nothing ----------------------------------------

import os
import subprocess
import sys

import aec.lib.org_config.state as state_mod
from aec.lib.org_config.state import OrgConfigError, StateSnapshot, all_or_nothing


def _two_orgs(tmp_path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    for org in ("acme", "beta"):
        write_state(paths, _make_state(org_id=org))
    return paths


def _leftovers(paths):
    return sorted(p.name for p in paths.orgs_dir.glob("*.aec-prev.*"))


def test_all_or_nothing_restores_every_org_without_writing_a_payload(tmp_path, monkeypatch):
    paths = _two_orgs(tmp_path)
    before = {o: read_state(paths, o) for o in ("acme", "beta")}
    with pytest.raises(RuntimeError):
        with all_or_nothing(paths, ["acme", "beta"]):
            write_state(paths, _make_state(org_id="acme", last_applied_at="new"))
            # The disk is now full: no further payload write can succeed, the rollback included.
            monkeypatch.setattr(state_mod, "write_state", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
            raise RuntimeError("beta's stamp failed")
    assert {o: read_state(paths, o) for o in before} == before
    assert _leftovers(paths) == []


def test_all_or_nothing_keeps_changes_on_success(tmp_path):
    paths = _two_orgs(tmp_path)
    with all_or_nothing(paths, ["acme", "beta"]):
        write_state(paths, _make_state(org_id="acme", last_applied_at="new"))
    assert read_state(paths, "acme").last_applied_at == "new"
    assert _leftovers(paths) == []


def test_failed_rollback_tries_every_org_and_the_next_read_finishes_it(tmp_path, monkeypatch):
    paths = _two_orgs(tmp_path)
    before = {o: read_state(paths, o) for o in ("acme", "beta")}
    real_put_back = state_mod._put_back
    calls = []

    def first_put_back_fails(prev, live):
        calls.append(live.name)
        if len(calls) == 1:
            raise OSError("rename failed")
        real_put_back(prev, live)

    monkeypatch.setattr(state_mod, "_put_back", first_put_back_fails)
    with pytest.raises(OrgConfigError, match="could not roll back"):
        with all_or_nothing(paths, ["acme", "beta"]):
            for org in ("acme", "beta"):
                write_state(paths, _make_state(org_id=org, last_applied_at="new"))
            raise RuntimeError("publish failed")
    assert calls == ["acme.state.json", "beta.state.json"]  # kept going after acme failed
    assert read_state(paths, "beta") == before["beta"]
    # acme's snapshot stayed on disk; the next read puts it back.
    assert read_state(paths, "acme") == before["acme"]
    assert _leftovers(paths) == []


def test_snapshot_of_a_dead_process_is_rolled_back_on_read(tmp_path):
    paths = _two_orgs(tmp_path)
    before = read_state(paths, "acme")
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    live = paths.state_for("acme")
    os.link(live, live.with_name(f"{live.name}.aec-prev.{dead.pid}.0"))
    write_state(paths, _make_state(org_id="acme", last_applied_at="half-applied"))
    assert read_state(paths, "acme") == before
    assert _leftovers(paths) == []


def test_snapshot_of_a_live_process_is_left_alone(tmp_path):
    paths = _two_orgs(tmp_path)
    live = paths.state_for("acme")
    os.link(live, live.with_name(f"{live.name}.aec-prev.{os.getppid()}.0"))  # our parent: alive
    write_state(paths, _make_state(org_id="acme", last_applied_at="in-flight"))
    assert read_state(paths, "acme").last_applied_at == "in-flight"
    assert len(_leftovers(paths)) == 1


def test_nested_snapshots_recover_to_the_oldest(tmp_path):
    paths = _two_orgs(tmp_path)
    before = read_state(paths, "acme")
    outer = StateSnapshot(paths, ["acme"])
    write_state(paths, _make_state(org_id="acme", last_applied_at="promoted"))
    inner = StateSnapshot(paths, ["acme"])
    write_state(paths, _make_state(org_id="acme", last_applied_at="stamped"))
    state_mod._open_links.clear()  # simulate the process dying with both open
    assert read_state(paths, "acme") == before
    assert _leftovers(paths) == []
    outer.links = inner.links = []
