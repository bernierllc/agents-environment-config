"""Round 9 of scripts/prune-merged-worktrees.sh: the four findings an independent review (Codex high) reproduced
against the round-8 head 5a8f894 (2 P0, 2 P1), pinned as permanent tests.

Why this file exists: rounds 1-8 wrote their tests from the author's own model of the failure, so 412 tests and 118
mutants missed all four. Round 9 starts from the REVIEWER'S repros instead: each test below is the reviewer's repro,
adapted only to this repo's Fixture, and each failed against 5a8f894 before the fix (the failure is recorded in
plans/2026-11-16-prune-env-guard-fail-open.md, "Round 9").

Every test runs the real script under /bin/bash against a real git repo with a stub `gh`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.test_prune_env_guard import (
    KEEP_UNPROVEN,
    Fixture,
    _git,
    _real,
    fx,  # noqa: F401  (the pytest fixture)
)

KEEP_HELD = "a process holds files inside it"
KEEP_DIRTY = "PR merged but worktree dirty"
KEEP_HISTORY = "a reflog holds commits no ref reaches (reflogs, ORIG_HEAD or FETCH_HEAD)"


def _to_the_end(fx: Fixture) -> str:
    """A real run, then (when the worktree was quarantined) the aged purge run. Returns the last run's output."""
    out = fx.run(False)
    held = fx.held()
    if held:
        for entry in held:
            fx.age(entry)
        out = fx.run(False)
    return out


def _line(fx: Fixture, out: str) -> str:
    """The script's line for the worktree wherever it sits: its own path, or a held entry (aged or set aside)."""
    for place in [fx.wt, *fx.held(), *(Path(str(h) + ".purge") for h in fx.held())]:
        found = fx.line(out, place)
        if found:
            return found
    return ""


def _where(fx: Fixture) -> Path | None:
    """The worktree wherever it is now (original place, held, or aged), None when it is gone."""
    if fx.wt.exists():
        return fx.wt
    held = fx.held()
    return held[0] if held else None


# --- P0-1: a marker authorizes only what the tool that wrote it can account for ---------------------------


def _database(path: Path) -> None:
    db = sqlite3.connect(path)
    db.execute("create table customers(name)")
    db.execute("insert into customers values ('only copy')")
    db.commit()
    db.close()


def _make_venv(fx: Fixture, *, pip: bool = False) -> Path:
    fx.exclude(".venv/")
    venv = fx.wt / ".venv"
    args = [sys.executable, "-m", "venv", str(venv)] if pip else [sys.executable, "-m", "venv", "--without-pip", str(venv)]
    subprocess.run(args, check=True, capture_output=True)
    return venv


def _site_packages(venv: Path) -> Path:
    (found,) = venv.glob("lib/python*/site-packages")
    return found


def test_p0_1_a_real_venv_marker_does_not_authorize_a_database_inside_it(fx: Fixture) -> None:
    venv = _make_venv(fx)
    _database(venv / "customers.sqlite")
    out = _to_the_end(fx)
    tree = _where(fx)
    assert tree is not None and (tree / ".venv/customers.sqlite").exists(), out
    line = _line(fx, out)
    assert KEEP_UNPROVEN in line and ".venv/customers.sqlite" in line, out


def test_p0_1_a_plain_venv_with_nothing_of_ours_in_it_is_still_removed(fx: Fixture) -> None:
    _make_venv(fx)
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()


@pytest.mark.parametrize(
    "rel",
    ["lib/customers.sqlite", "bin/customers.sqlite", "include/customers.sqlite", "customers.sqlite", "share/x.db"],
)
def test_p0_1_a_file_the_venv_tool_never_wrote_keeps_wherever_it_sits(fx: Fixture, rel: str) -> None:
    venv = _make_venv(fx)
    target = venv / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("only copy\n")
    out = _to_the_end(fx)
    assert target.exists(), out
    assert KEEP_UNPROVEN in (_line(fx, out)), out


def test_p0_1_an_unlisted_file_in_site_packages_keeps_but_a_listed_one_goes(fx: Fixture) -> None:
    venv = _make_venv(fx)
    site = _site_packages(venv)
    (site / "foo").mkdir()
    (site / "foo/__init__.py").write_text("X = 1\n")
    dist = site / "foo-1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text("Name: foo\n")
    (dist / "RECORD").write_text("foo/__init__.py,,\nfoo-1.0.dist-info/METADATA,,\nfoo-1.0.dist-info/RECORD,,\n")
    assert fx.verdict(dry=True) == "would"  # everything is listed: removable
    stray = site / "foo" / "customers.sqlite"
    _database(stray)
    out = _to_the_end(fx)
    assert stray.exists(), out
    assert "foo/customers.sqlite" in (_line(fx, out)), out


def test_p0_1_a_record_entry_with_dotdot_reaches_bin_and_nothing_else(fx: Fixture) -> None:
    venv = _make_venv(fx)
    site = _site_packages(venv)
    (venv / "bin/tool").write_text("#!/bin/sh\n")
    (venv / "bin/other").write_text("not listed\n")
    dist = site / "foo-1.0.dist-info"
    dist.mkdir()
    (dist / "RECORD").write_text("../../../bin/tool,,\nfoo-1.0.dist-info/RECORD,,\n")
    out = fx.run(True)
    line = _line(fx, out)
    assert KEEP_UNPROVEN in line and "bin/other" in line and "bin/tool" not in line, out


def _npm_tree(fx: Fixture, packages: list[str]) -> Path:
    fx.exclude("node_modules/")
    nm = fx.wt / "node_modules"
    nm.mkdir()
    keys = {"": {"name": "app"}, **{f"node_modules/{p}": {"version": "1.0.0"} for p in packages}}
    (nm / ".package-lock.json").write_text(json.dumps({"name": "app", "lockfileVersion": 3, "packages": keys}, indent=2))
    for p in packages:
        (nm / p).mkdir(parents=True, exist_ok=True)
        (nm / p / "index.js").write_text("module.exports = 1\n")
    return nm


def test_p0_1_an_npm_tree_goes_but_a_file_beside_its_packages_keeps(fx: Fixture) -> None:
    nm = _npm_tree(fx, ["left-pad", "@scope/name"])
    assert fx.verdict(dry=True) == "would"
    _database(nm / "customers.sqlite")
    out = _to_the_end(fx)
    assert (nm / "customers.sqlite").exists(), out
    assert "node_modules/customers.sqlite" in (_line(fx, out)), out


def test_p0_1_a_directory_npm_never_installed_keeps(fx: Fixture) -> None:
    nm = _npm_tree(fx, ["left-pad"])
    (nm / "not-a-package").mkdir()
    (nm / "not-a-package/data.json").write_text("{}\n")
    out = _to_the_end(fx)
    assert (nm / "not-a-package/data.json").exists(), out
    assert "not-a-package/data.json" in (_line(fx, out)), out


@pytest.mark.parametrize("marker", [".yarn-integrity", ".modules.yaml"])
def test_p0_1_yarn_and_pnpm_markers_prove_no_package_so_their_trees_keep(fx: Fixture, marker: str) -> None:
    fx.exclude("node_modules/")
    nm = fx.wt / "node_modules"
    (nm / "pkg").mkdir(parents=True)
    (nm / marker).write_text("{}\n")
    (nm / "pkg/index.js").write_text("1\n")
    out = _to_the_end(fx)
    assert (nm / "pkg/index.js").exists(), out
    assert KEEP_UNPROVEN in (_line(fx, out)), out


# --- P0-2: a writer that already holds the tree is not stopped by a rename ---------------------------------

WRITER = """
import os, sys, time
mode, tree, ready, signal, wrote = sys.argv[1:6]
if mode == "cwd":
    os.chdir(tree)
elif mode == "subdir":
    os.makedirs(os.path.join(tree, "sub"), exist_ok=True)
    os.chdir(os.path.join(tree, "sub"))
elif mode == "file":
    held = open(os.path.join(tree, ".env.example"), "rb")
open(ready, "w").close()
while not os.path.exists(signal):
    time.sleep(.005)
if mode != "file":
    open(".env.local" if mode == "cwd" else "../.env.local", "w").write("ONLY COPY OF CREDENTIAL\\n")
open(wrote, "w").write("writer completed")
"""


@pytest.mark.parametrize("mode", ["cwd", "subdir", "file"])
def test_p0_2_a_process_inside_the_tree_that_writes_during_the_final_window_loses_nothing(
    fx: Fixture, mode: str
) -> None:
    """The reviewer's repro: the worker holds the entry (cwd), a git shim lets it finish right before native
    `git worktree remove`. Whatever the script does, the credential the worker writes must still exist afterwards."""
    out = fx.run(False)
    (entry,) = fx.held()
    entry = fx.age(entry)
    work = fx.root.parent / "work"
    work.mkdir()
    ready, signal, wrote = work / "ready", work / "signal", work / "wrote"
    worker = subprocess.Popen([sys.executable, "-c", WRITER, mode, str(entry), str(ready), str(signal), str(wrote)])
    try:
        deadline = time.time() + 10
        while not ready.exists():
            assert time.time() < deadline and worker.poll() is None, "the worker did not start"
            time.sleep(0.005)
        fx.shim(
            "git",
            f"""
case " $* " in *" worktree remove "*)
  touch '{signal}'
  while [ ! -e '{wrote}' ]; do /bin/sleep 0.01; done
;; esac
exec '{_real("git")}' "$@"
""",
        )
        out = fx.run(False)
        signal.touch()  # when the script never reached the native remove, let the worker finish now
        worker.wait(timeout=10)
    finally:
        if worker.poll() is None:
            worker.kill()
    survivors = [p for p in (entry, Path(str(entry) + ".purge"), fx.wt) if p.exists()]
    assert survivors, f"the worktree is gone while a process held it:\n{out}"
    if mode != "file":
        credentials = [p / ".env.local" for p in survivors if (p / ".env.local").exists()]
        assert credentials, f"the credential the worker wrote was deleted with the tree:\n{out}"
    assert KEEP_HELD in out, out


def test_p0_2_lsof_failing_keeps_the_tree_and_faults(fx: Fixture) -> None:
    fx.run(False)
    for entry in fx.held():
        fx.age(entry)
    fx.shim("lsof", 'echo "lsof: injected failure" >&2; exit 1')
    out = fx.run(False)
    assert "could not list open files" in out and fx.last_rc == 1, out
    assert any(p.exists() for p in fx.qbase.glob("2000-01-01/*")), out


def test_p0_2_lsof_missing_keeps_the_tree_and_faults(fx: Fixture) -> None:
    fx.run(False)
    for entry in fx.held():
        fx.age(entry)
    fx.shim("lsof", "exit 127")
    out = fx.run(False)
    assert "could not list open files" in out and fx.last_rc == 1, out
    assert any(p.exists() for p in fx.qbase.glob("2000-01-01/*")), out


def test_p0_2_a_tree_nothing_holds_is_still_removed(fx: Fixture) -> None:
    assert fx.verdict(dry=False) == "removed"


# --- P1-3: FETCH_HEAD can be the only reference to fetched history ----------------------------------------


def test_p1_3_commits_only_fetch_head_names_are_not_deleted_with_the_worktree(fx: Fixture) -> None:
    source = fx.root.parent / "source"
    source.mkdir()
    _git(source, "init", "-q", "-b", "main")
    (source / "unique.txt").write_text("ONLY COPY OF WORK\n")
    _git(source, "add", ".")
    _git(source, "commit", "-qm", "unique work")
    unique = _git(source, "rev-parse", "HEAD")
    _git(fx.wt, "fetch", "-q", str(source), "main")
    _git(source, "update-ref", "-d", "refs/heads/main")
    _git(source, "reflog", "expire", "--expire=now", "--all")
    _git(source, "gc", "-q", "--prune=now")
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    assert unique in (gd / "FETCH_HEAD").read_text()
    assert _git(fx.repo, "for-each-ref", "--contains", unique) == ""

    out = _to_the_end(fx)

    # the worktree is kept, so its FETCH_HEAD (the only name for the commit; gc ignores it) is still there
    assert _where(fx) is not None and unique in (gd / "FETCH_HEAD").read_text(), f"the fetched commit was lost:\n{out}"
    assert KEEP_HISTORY in (_line(fx, out)), out


def test_p1_3_fetch_head_naming_only_protected_history_does_not_keep(fx: Fixture) -> None:
    _git(fx.wt, "fetch", "-q", str(fx.repo), "main")
    assert "FETCH_HEAD" in "".join(p.name for p in Path(_git(fx.wt, "rev-parse", "--absolute-git-dir")).iterdir())
    assert fx.verdict(dry=False) == "removed"


# --- P1-4: a stat cache is not evidence about content -----------------------------------------------------


def test_p1_4_a_same_size_edit_with_the_mtime_restored_is_still_found(fx: Fixture) -> None:
    _git(fx.repo, "config", "core.trustctime", "false")
    _git(fx.repo, "config", "core.checkStat", "minimal")
    p = fx.wt / ".env.example"
    os.utime(p, (946684800, 946684800))
    _git(fx.wt, "update-index", "--refresh")
    p.write_text("SECRET!=1\n")  # same length as the tracked "EXAMPLE=1\n"
    os.utime(p, (946684800, 946684800))
    assert _git(fx.wt, "status", "--porcelain") == "", "precondition: git's own status is fooled"
    out = _to_the_end(fx)
    assert fx.wt.exists() and p.read_text() == "SECRET!=1\n", out
    assert KEEP_DIRTY in (_line(fx, out)), out


def test_p1_4_a_clean_worktree_with_the_cache_settings_is_still_removed(fx: Fixture) -> None:
    _git(fx.repo, "config", "core.trustctime", "false")
    _git(fx.repo, "config", "core.checkStat", "minimal")
    assert fx.verdict(dry=False) == "removed"
