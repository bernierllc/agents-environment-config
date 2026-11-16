"""Disk-reclaim helpers in scripts/cleanup-hung-processes.sh: stale updater
staging and old Playwright browser revisions, on real directories."""

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


def test_playwright_keeps_newest_revision_per_browser(tmp_path):
    pw = tmp_path / "ms-playwright"
    old_chromium = _mkdir(pw / "chromium-1217", old=True)
    new_chromium = _mkdir(pw / "chromium-1223", old=True)
    old_shell = _mkdir(pw / "chromium_headless_shell-999", old=True)  # numeric, not lexical, order
    new_shell = _mkdir(pw / "chromium_headless_shell-1223", old=True)
    only_ffmpeg = _mkdir(pw / "ffmpeg-1011", old=True)
    recent_old_rev = _mkdir(pw / "webkit-2000", old=False)
    _mkdir(pw / "webkit-2287", old=False)
    profile = _mkdir(pw / "mcp-chrome-1a2b3c", old=True)  # MCP profile: handled elsewhere
    _call(f'prune_playwright_browsers "{pw}"')
    assert not old_chromium.exists() and not old_shell.exists()
    assert new_chromium.exists() and new_shell.exists() and only_ffmpeg.exists()
    assert recent_old_rev.exists()  # used within 14 days
    assert profile.exists()


def test_playwright_missing_dir_is_a_noop(tmp_path):
    _call(f'prune_playwright_browsers "{tmp_path / "nope"}"')
