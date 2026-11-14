"""Tests for aec.lib.changesets (real files, only rollbacks_dir is redirected)."""

import hashlib
import logging

import pytest

from aec.lib import changesets as c


@pytest.fixture(autouse=True)
def rb(tmp_path, monkeypatch):
    root = tmp_path / "rb"
    monkeypatch.setattr(c, "rollbacks_dir", lambda: root)
    return root


def sha(b):
    return hashlib.sha256(b).hexdigest()


def change(paths, fn, short="s", kind="test"):
    p = c.begin(paths, short, "long text", kind)
    fn()
    return p.commit()


def test_commit_records_hashes_and_blobs(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"old")
    cs = change([f], lambda: f.write_bytes(b"new"))
    fc = cs.files[0]
    assert (fc.before, fc.after) == (sha(b"old"), sha(b"new"))
    assert (cs.dir / "blobs" / sha(b"old")).read_bytes() == b"old"
    assert (cs.dir / "blobs" / sha(b"new")).read_bytes() == b"new"
    assert c.load(cs.id).files == cs.files


def test_unchanged_dropped_and_none_when_all_unchanged(tmp_path, rb):
    f, g = tmp_path / "f", tmp_path / "g"
    f.write_bytes(b"x")
    g.write_bytes(b"y")
    cs = change([f, g], lambda: g.write_bytes(b"z"))
    assert [x.path for x in cs.files] == [g]
    assert change([f], lambda: None) is None
    assert len([d for d in rb.iterdir() if d.is_dir()]) == 1


def test_no_change_leaves_rollbacks_dir_empty(tmp_path, rb):
    f = tmp_path / "f"
    f.write_bytes(b"x")
    assert change([f], lambda: None) is None
    assert not rb.exists() or not [d for d in rb.iterdir() if d.is_dir()]


def test_created_and_deleted(tmp_path):
    new, old = tmp_path / "new", tmp_path / "old"
    old.write_bytes(b"o")

    def go():
        new.write_bytes(b"n")
        old.unlink()

    cs = change([new, old], go)
    by = {fc.path: fc for fc in cs.files}
    assert by[new].before is None and by[new].after == sha(b"n")
    assert by[old].after is None and by[old].before == sha(b"o")


def test_revert_byte_exact_binary_and_crlf(tmp_path):
    f, g = tmp_path / "bin", tmp_path / "crlf.md"
    f.write_bytes(b"\x00\xff\r\n")
    g.write_bytes(b"a\r\nb\r\n")

    def go():
        f.write_bytes(b"changed")
        g.write_bytes(b"a\nb\n")

    cs = change([f, g], go)
    c.revert(cs.id)
    assert f.read_bytes() == b"\x00\xff\r\n"
    assert g.read_bytes() == b"a\r\nb\r\n"


def test_revert_created_deletes_and_deleted_recreates(tmp_path):
    new, old = tmp_path / "sub" / "new", tmp_path / "old"
    old.write_bytes(b"o")

    def go():
        new.parent.mkdir()
        new.write_bytes(b"n")
        old.unlink()

    cs = change([new, old], go)
    c.revert(cs.id)
    assert not new.exists()
    assert old.read_bytes() == b"o"


def test_inverse_linking_and_redo(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"1")
    cs = change([f], lambda: f.write_bytes(b"2"))
    inv = c.revert(cs.id)
    assert inv.reverses == cs.id and inv.kind == "revert"
    assert c.load(cs.id).reversed_by == inv.id
    assert f.read_bytes() == b"1"
    c.revert(inv.id)
    assert f.read_bytes() == b"2"


def test_already_reverted(tmp_path):
    f = tmp_path / "f"
    cs = change([f], lambda: f.write_bytes(b"1"))
    c.revert(cs.id)
    with pytest.raises(c.AlreadyReverted):
        c.revert(cs.id)


def test_conflict_and_force_keeps_edit_recoverable(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"1")
    cs = change([f], lambda: f.write_bytes(b"2"))
    f.write_bytes(b"edited")
    assert [x.path for x in c.conflicts(cs)] == [f]
    assert "edited" in c.diff_text(cs, cs.files[0])
    with pytest.raises(c.ConflictError) as e:
        c.revert(cs.id)
    assert e.value.conflicts[0].path == f
    assert f.read_bytes() == b"edited"
    inv = c.revert(cs.id, force=True)
    assert f.read_bytes() == b"1"
    assert inv.files[0].before == sha(b"edited")
    c.revert(inv.id)
    assert f.read_bytes() == b"edited"


def test_list_newest_first(tmp_path):
    f = tmp_path / "f"
    a = change([f], lambda: f.write_bytes(b"1"))
    b = change([f], lambda: f.write_bytes(b"2"))
    assert [x.id for x in c.list_changesets()] == [b.id, a.id]


def test_corrupt_skipped_with_warning(tmp_path, rb, caplog):
    f = tmp_path / "f"
    cs = change([f], lambda: f.write_bytes(b"1"))
    bad = rb / "20000101T000000Z-dead"
    bad.mkdir()
    (bad / "rollback.json").write_text("{not json")
    with caplog.at_level(logging.WARNING):
        got = c.list_changesets()
    assert [x.id for x in got] == [cs.id]
    assert "20000101T000000Z-dead" in caplog.text


def test_load_missing():
    with pytest.raises(c.ChangesetNotFound):
        c.load("nope")


def test_store_failure_happens_before_any_change(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setattr(c, "rollbacks_dir", lambda: blocker / "rollbacks")
    f = tmp_path / "f"
    f.write_bytes(b"keep")
    with pytest.raises(OSError):
        c.begin([f], "s", "l", "test")
    assert f.read_bytes() == b"keep"


def test_interrupted_change_is_listed_and_revertible(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"old")
    c.begin([f], "s", "l", "test")  # process dies before commit
    f.write_bytes(b"new")
    (cs,) = c.list_changesets()
    assert cs.short.endswith("(interrupted)")
    c.revert(cs.id)
    assert f.read_bytes() == b"old"


def test_listing_never_finalizes_a_running_change(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"old")
    pending = c.begin([f], "s", "l", "test")
    assert c.list_changesets() == []  # nothing changed yet; must not delete the snapshot
    f.write_bytes(b"new")
    cs = pending.commit()
    c.revert(cs.id)
    assert f.read_bytes() == b"old"


def test_symlinks_are_refused(tmp_path):
    target = tmp_path / "AGENTS.md"
    target.write_text("x")
    link = tmp_path / "CLAUDE.md"
    link.symlink_to(target)
    with pytest.raises(c.ChangesetError, match="symlink"):
        c.begin([link], "s", "l", "test")
    assert c.list_changesets() == []


def test_partial_revert_is_recorded(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"a0")
    b.write_bytes(b"b0")
    cs = change([a, b], lambda: (a.write_bytes(b"A"), b.write_bytes(b"B")))
    a.write_bytes(b"edited")
    real = c._write_bytes_atomic

    def flaky(path, data):
        if path == b:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(c, "_write_bytes_atomic", flaky)
    with pytest.raises(OSError):
        c.revert(cs.id, force=True)
    monkeypatch.setattr(c, "_write_bytes_atomic", real)
    partial = c.list_changesets()[0]
    assert partial.reverses == cs.id
    c.revert(partial.id)
    assert a.read_bytes() == b"edited"  # the overwritten edit is recoverable


def test_late_commit_after_rollback_keeps_history(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"old")
    pending = c.begin([f], "s", "l", "test")
    f.write_bytes(b"new")
    (cs,) = c.list_changesets()
    undo = c.revert(cs.id)
    with pytest.raises(c.ChangesetError, match="rolled back while running"):
        pending.commit()
    assert c.load(cs.id).reversed_by == undo.id
    assert f.read_bytes() == b"old"


def test_rollback_waits_for_a_commit_in_progress(tmp_path, monkeypatch):
    """Codex round 4 race: a revert that lands mid-commit must not erase history."""
    import threading

    f = tmp_path / "f"
    f.write_bytes(b"old")
    pending = c.begin([f], "s", "l", "test")
    f.write_bytes(b"new")
    (cs,) = c.list_changesets()  # still interrupted: no manifest yet

    in_commit, release = threading.Event(), threading.Event()
    real_read = c._read

    def paused_read(path):
        if threading.current_thread().name == "committer" and not in_commit.is_set():
            in_commit.set()
            assert release.wait(5)
        return real_read(path)

    monkeypatch.setattr(c, "_read", paused_read)
    results = {}
    committer = threading.Thread(target=lambda: results.update(commit=pending.commit()), name="committer")
    committer.start()
    assert in_commit.wait(5)
    reverter = threading.Thread(target=lambda: results.update(undo=c.revert(cs.id)))
    reverter.start()
    reverter.join(0.3)
    assert reverter.is_alive()  # blocked on the store lock while the commit runs
    release.set()
    committer.join(5)
    reverter.join(5)

    assert results["commit"].id == cs.id
    assert c.load(cs.id).reversed_by == results["undo"].id
    assert c.load(results["undo"].id).reverses == cs.id
    assert f.read_bytes() == b"old"
