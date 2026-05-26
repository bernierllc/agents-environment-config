"""Tests for the custom-source clone subsystem (Phase 4c)."""
from __future__ import annotations

import pytest

from aec.lib.org_config.schema import CustomSource
from aec.lib.org_config.sources_sync import SyncResult, sync_source, sync_sources


def _source(sid="acme-skills"):
    return CustomSource(
        id=sid,
        url="https://example.com/acme/skills.git",
        ref="main",
        contributes=("skills",),
    )


def test_sync_success_returns_path(tmp_path):
    calls = []

    def fake_clone(url, dest, ref):
        calls.append((url, str(dest), ref))
        dest.mkdir(parents=True)

    result = sync_source(_source(), sources_dir=tmp_path, cloner=fake_clone)
    assert result.success is True
    assert result.path == tmp_path / "acme-skills"
    assert result.error is None
    assert calls == [("https://example.com/acme/skills.git", str(tmp_path / "acme-skills"), "main")]


def test_sync_failure_captured_not_raised(tmp_path):
    def boom(url, dest, ref):
        raise PermissionError("denied")

    result = sync_source(_source(), sources_dir=tmp_path, cloner=boom)
    assert result.success is False
    assert result.path is None
    assert "denied" in result.error


def test_sync_is_idempotent_when_dest_exists(tmp_path):
    dest = tmp_path / "acme-skills"
    dest.mkdir(parents=True)
    calls = []

    def fake_update(url, d, ref):
        calls.append(("update", str(d)))

    result = sync_source(_source(), sources_dir=tmp_path, cloner=fake_update)
    assert result.success is True
    assert result.path == dest
    # The cloner is still invoked (to refresh to ref); idempotency lives in cloner impl.
    assert calls == [("update", str(dest))]


def test_sync_sources_aggregates_per_source(tmp_path):
    s1 = _source("ok-src")
    s2 = _source("bad-src")
    s2 = CustomSource(id="bad-src", url=s2.url, ref=s2.ref, contributes=s2.contributes)

    def clone(url, dest, ref):
        if "bad-src" in str(dest):
            raise RuntimeError("no access")
        dest.mkdir(parents=True)

    results = sync_sources([s1, s2], sources_dir=tmp_path, cloner=clone)
    assert results["ok-src"].success is True
    assert results["bad-src"].success is False
    assert "no access" in results["bad-src"].error


def test_failed_source_ids_helper():
    from aec.lib.org_config.sources_sync import failed_source_ids

    results = {
        "a": SyncResult(source_id="a", success=True, path=None, error=None),
        "b": SyncResult(source_id="b", success=False, path=None, error="x"),
    }
    assert failed_source_ids(results) == {"b"}
