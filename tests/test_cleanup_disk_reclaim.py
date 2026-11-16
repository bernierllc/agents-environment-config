"""Updater-staging pruning in scripts/cleanup-hung-processes.sh, on real directories."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from tests.test_cleanup_hung_processes_script import _helper_prelude

OLD = time.time() - 30 * 86400


def _call(fn_call: str) -> str:
    r = subprocess.run(["bash", "-c", _helper_prelude() + "\n" + fn_call], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _mkdir(p: Path, old: bool) -> Path:
    p.mkdir(parents=True)
    (p / "f").write_text("x")
    if old:
        os.utime(p, (OLD, OLD))
    return p


def test_updater_staging_removes_old_entries_and_keeps_newest(tmp_path):
    staging = tmp_path / "com.example.app.ShipIt"
    older = _mkdir(staging / "update.AAA", old=True)
    newest_but_old = _mkdir(staging / "update.BBB", old=True)
    os.utime(newest_but_old, (OLD + 3600, OLD + 3600))
    (staging / "ShipItState.plist").write_text("state")  # touched now, as on every check
    _call(f'prune_updater_staging "{staging}"')
    assert not older.exists()
    assert newest_but_old.exists()  # may be waiting to install on quit
    assert (staging / "ShipItState.plist").exists()


def test_updater_staging_keeps_recent_entries(tmp_path):
    staging = tmp_path / "Installation"
    a = _mkdir(staging / "a", old=False)
    b = _mkdir(staging / "b", old=False)
    _call(f'prune_updater_staging "{staging}"')
    assert a.exists() and b.exists()


def test_updater_staging_keeps_an_old_entry_a_process_has_open(tmp_path):
    staging = tmp_path / "Installation"
    held = _mkdir(staging / "a", old=True)
    os.utime(held, (OLD, OLD))
    newest = _mkdir(staging / "b", old=False)
    proc = subprocess.Popen(["tail", "-f", str(held / "f")])
    try:
        time.sleep(0.5)
        os.utime(held, (OLD, OLD))
        out = _call(f'prune_updater_staging "{staging}"')
    finally:
        proc.kill()
    assert held.exists() and newest.exists(), out
