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
