"""Round 9 of scripts/prune-merged-worktrees.sh: the four findings an independent review (Codex high) reproduced
against the round-8 head 5a8f894 (2 P0, 2 P1), pinned as permanent tests.

Why this file exists: rounds 1-8 wrote their tests from the author's own model of the failure, so 412 tests and 118
mutants missed all four. Round 9 starts from the REVIEWER'S repros instead: each test below is the reviewer's repro,
adapted only to this repo's Fixture, and each failed against 5a8f894 before the fix (the failure is recorded in
plans/2026-11-16-prune-env-guard-fail-open.md, "Round 9").

Every test runs the real script under /bin/bash against a real git repo with a stub `gh`.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
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
    [
        "lib/customers.sqlite",
        "bin/customers.sqlite",
        "include/customers.sqlite",
        "customers.sqlite",
        "share/x.db",
        "share/pyvenv.cfg",  # a scaffold NAME is proven only where the tool puts it
        "sub/.gitignore",
        "lib/bin/python3",
    ],
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


def _venv_with_record(fx: Fixture, *record_lines: str) -> tuple[Path, Path]:
    venv = _make_venv(fx)
    dist = _site_packages(venv) / "foo-1.0.dist-info"
    dist.mkdir()
    (dist / "RECORD").write_text("".join(f"{ln}\n" for ln in ("foo-1.0.dist-info/RECORD,,", *record_lines)))
    return venv, dist


def test_p0_1_a_record_entry_that_climbs_out_of_the_worktree_proves_nothing_inside_it(fx: Fixture) -> None:
    """`..` past the top of the tree must not be clamped to the top: five levels up from site-packages leaves the
    worktree, and re-entering `.venv/` from there is not the venv tool's own listing of that file."""
    venv, _ = _venv_with_record(fx, "../../../../../.venv/customers.sqlite,,")
    _database(venv / "customers.sqlite")
    out = _to_the_end(fx)
    assert (venv / "customers.sqlite").exists() or _where(fx) is not None, out
    assert "customers.sqlite" in _line(fx, out) and KEEP_UNPROVEN in _line(fx, out), out


def test_p0_1_an_absolute_record_entry_is_not_a_path_under_site_packages(fx: Fixture) -> None:
    """`/foo/data.sqlite` names a file at the filesystem root; joined onto site-packages it would look like the
    venv's own `foo/data.sqlite`."""
    venv, _ = _venv_with_record(fx, "/foo/data.sqlite,,")
    stray = _site_packages(venv) / "foo" / "data.sqlite"
    stray.parent.mkdir()
    _database(stray)
    out = _to_the_end(fx)
    assert "foo/data.sqlite" in _line(fx, out) and KEEP_UNPROVEN in _line(fx, out), out


def test_p0_1_an_unreadable_record_keeps_the_tree_and_faults(fx: Fixture) -> None:
    """Not being able to read what the venv tool wrote is a failed check, not "nothing is proven"."""
    _, dist = _venv_with_record(fx)
    (dist / "RECORD").chmod(0)
    out = fx.run(False)
    assert "could not read the venv RECORD files" in out and fx.last_rc == 1, out
    assert fx.wt.exists()


def test_p0_1_a_lock_file_in_a_directory_not_called_node_modules_is_not_npms(fx: Fixture) -> None:
    fx.exclude("build/")
    build = fx.wt / "build"
    (build / "left-pad").mkdir(parents=True)
    (build / "left-pad/index.js").write_text("1\n")
    keys = {"": {"name": "app"}, "node_modules/left-pad": {"version": "1.0.0"}}
    (build / ".package-lock.json").write_text(json.dumps({"packages": keys}, indent=2))
    out = fx.run(False)
    assert fx.wt.exists() and (build / "left-pad/index.js").exists(), out
    assert fx.line(out, fx.wt).startswith("keep"), out


def test_p0_1_a_pycache_file_with_no_source_and_no_record_entry_keeps(fx: Fixture) -> None:
    venv = _make_venv(fx)
    cache = _site_packages(venv) / "__pycache__"
    cache.mkdir()
    (cache / "lonely.cpython-312.pyc").write_bytes(b"\0\0\0\0")
    out = _to_the_end(fx)
    assert "lonely.cpython-312.pyc" in _line(fx, out) and KEEP_UNPROVEN in _line(fx, out), out


def test_p0_1_a_pycache_file_with_its_source_listed_in_the_record_goes(fx: Fixture) -> None:
    venv, _ = _venv_with_record(fx, "foo/__init__.py,,")
    site = _site_packages(venv)
    (site / "foo/__pycache__").mkdir(parents=True)
    (site / "foo/__init__.py").write_text("X = 1\n")
    (site / "foo/__pycache__/__init__.cpython-312.pyc").write_bytes(b"\0\0\0\0")
    assert fx.verdict(dry=True) == "would"


def test_p0_1_a_venv_marker_that_is_a_symlink_is_no_marker(fx: Fixture) -> None:
    fx.exclude(".venv/")
    target = fx.root.parent / "elsewhere.cfg"
    target.write_text("home = /usr/bin\n")
    (fx.wt / ".venv").mkdir()
    (fx.wt / ".venv/pyvenv.cfg").symlink_to(target)
    out = fx.run(False)
    assert fx.wt.exists() and fx.line(out, fx.wt).startswith("keep"), out


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
    assert any(p.exists() for p in fx.qbase.glob("2000-01-01T000000Z/*")), out


def test_p0_2_lsof_missing_keeps_the_tree_and_faults(fx: Fixture) -> None:
    fx.run(False)
    for entry in fx.held():
        fx.age(entry)
    safe = fx.root.parent / "no-lsof-bin"
    safe.mkdir()
    for d in ("/usr/bin", "/bin"):
        for tool in Path(d).iterdir():
            if tool.name != "lsof" and not (safe / tool.name).exists():
                (safe / tool.name).symlink_to(tool)
    out = fx.run(False, {"PATH": f"{fx.bindir}{os.pathsep}{safe}"})
    assert "could not list open files (lsof not found)" in out and fx.last_rc == 1, out
    assert any(p.exists() for p in fx.qbase.glob("2000-01-01T000000Z/*")), out


def test_p0_2_a_tree_nothing_holds_is_still_removed(fx: Fixture) -> None:
    assert fx.verdict(dry=False) == "removed"


def test_p0_2_a_write_between_the_first_guard_and_the_rename_is_caught_by_the_rescan(fx: Fixture) -> None:
    """The rescan of the renamed tree exists for writes that land after the first guard: a git shim writes a
    credential into the tree the moment the rename starts."""
    fx.run(False)
    (entry,) = fx.held()
    entry = fx.age(entry)
    fx.shim(
        "git",
        f"""
args=("$@"); n=${{#args[@]}}
case "${{args[$((n-1))]}}" in *.purge) case " $* " in *" worktree move "*)
  printf 'ONLY COPY OF CREDENTIAL\\n' > "${{args[$((n-2))]}}/.env.local" ;; esac ;; esac
exec '{_real("git")}' "$@"
""",
    )
    out = fx.run(False)
    survivors = [p for p in (entry, Path(str(entry) + ".purge")) if (p / ".env.local").exists()]
    assert survivors, f"the credential written during the rename was deleted with the tree:\n{out}"
    assert "moved back after the rescan" in out, out


@pytest.mark.parametrize("value", [None, "", "0", "yes", "true", "2"])
def test_p0_2_deletion_is_off_unless_the_operator_sets_exactly_1(fx: Fixture, value: str | None) -> None:
    """No lsof check can see another user's process or the milliseconds before the remove, so the unattended purge
    stops at the quarantine until PRUNE_ALLOW_DELETE=1 (the suite's Fixture.run sets it for every other test)."""
    fx.run(False)
    (entry,) = fx.held()
    entry = fx.age(entry)
    out = fx.run(False, {"PRUNE_ALLOW_DELETE": value})
    assert entry.exists(), out
    assert "unattended deletion is off" in _line(fx, out), out


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


def test_p1_4_a_failing_read_tree_keeps_the_tree_and_faults(fx: Fixture) -> None:
    fx.git_fails("read-tree HEAD")
    out = fx.run(False)
    assert "could not read git status" in out and fx.last_rc == 1, out
    assert fx.wt.exists()


def test_p1_3_a_dangling_fetch_head_symlink_keeps_the_tree_and_faults(fx: Fixture) -> None:
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    (gd / "FETCH_HEAD").symlink_to(fx.root.parent / "nowhere")
    out = fx.run(False)
    assert fx.wt.exists() and fx.last_rc == 1 and "could not read the reflogs" in out, out


def test_p1_4_a_clean_worktree_with_the_cache_settings_is_still_removed(fx: Fixture) -> None:
    _git(fx.repo, "config", "core.trustctime", "false")
    _git(fx.repo, "config", "core.checkStat", "minimal")
    assert fx.verdict(dry=False) == "removed"


# --- Addendum 1: Review B (Sonnet high, on 5a8f894), independent of Review A -----------------------------------
# P2-1 and P2-2 are the same two defects Review A found (P0-1 and P0-2); Review B's own repros are kept as tests.
# P2-3, P3-1, P3-2 and P3-3 are new. Each test below failed against 5a8f894.


@pytest.mark.parametrize("lock", ["", "{}\n", '{"name": "app", "lockfileVersion": 3, "packages": {"": {"name": "app"}}}\n'])
def test_p2_1_an_npm_marker_that_lists_no_package_authorizes_nothing_beneath_it(fx: Fixture, lock: str) -> None:
    """Review B's repro: ignore node_modules/, add node_modules/.package-lock.json, put node_modules/pkg/my.sqlite and
    node_modules/notes.txt under it: both were quarantined and later purged."""
    fx.exclude("node_modules/")
    nm = fx.wt / "node_modules"
    (nm / "pkg").mkdir(parents=True)
    (nm / ".package-lock.json").write_text(lock)
    _database(nm / "pkg" / "my.sqlite")
    (nm / "notes.txt").write_text("only copy\n")
    out = _to_the_end(fx)
    place = _where(fx)
    assert place is not None, f"the worktree is gone:\n{out}"
    assert (place / "node_modules/pkg/my.sqlite").exists() and (place / "node_modules/notes.txt").exists(), out
    assert _line(fx, out).startswith("keep"), out


LATE_WRITER = """
args=("$@"); n=${{#args[@]}}
case " $* " in *" worktree remove "*) printf 'ONLY COPY\\n' > "${{args[$((n-1))]}}/.env.late" ;; esac
exec '{real}' "$@"
"""


def test_p2_2_a_file_written_just_before_the_native_remove_is_not_deleted_by_default(fx: Fixture) -> None:
    """Review B's repro: a git wrapper writes .env.late into the .purge tree right before `git worktree remove`.
    Unattended deletion is off by default, so the remove is never reached and the entry stays held."""
    fx.run(False)
    (entry,) = fx.held()
    entry = fx.age(entry)
    fx.shim("git", LATE_WRITER.format(real=_real("git")))
    out = fx.run(False, {"PRUNE_ALLOW_DELETE": None})
    assert entry.exists() and not (entry / ".env.late").exists(), out
    assert "unattended deletion is off" in _line(fx, out), out


@pytest.mark.xfail(
    strict=True,
    reason="documented residual (plan, Residual limits): once PRUNE_ALLOW_DELETE=1 is set, a writer that acts between "
    "the holder scan and `git worktree remove` still loses its file; no check can close that gap, which is why "
    "deletion is off by default. If this ever XPASSes the residual was closed: delete the xfail and the plan entry.",
)
def test_p2_2_residual_with_deletion_enabled_a_writer_in_the_last_gap_still_loses_its_file(fx: Fixture) -> None:
    fx.run(False)
    (entry,) = fx.held()
    entry = fx.age(entry)
    fx.shim("git", LATE_WRITER.format(real=_real("git")))
    out = fx.run(False)
    survivors = [p for p in (entry, Path(str(entry) + ".purge")) if (p / ".env.late").exists()]
    assert survivors, out


def _outside_worktree(fx: Fixture, where: Path, branch: str = "feat/out") -> Path:
    where.parent.mkdir(parents=True, exist_ok=True)
    _git(fx.repo, "worktree", "add", "-q", "-b", branch, str(where))
    fx.merged.append(f"{branch} {_git(where, 'rev-parse', 'HEAD')}")
    return where


@pytest.mark.parametrize("name", ["elsewhere", "pro jects2/wt2"])
def test_p2_3_a_worktree_outside_the_projects_root_is_refused_not_quarantined(fx: Fixture, name: str) -> None:
    """Review B's repro (`$S/elsewhere`), and a sibling whose name merely starts with the root's: a text prefix test
    would let `pro jects2` through."""
    out_wt = _outside_worktree(fx, fx.root.parent / name)
    for dry in (True, False):
        out = fx.run(dry)
        line = fx.line(out, out_wt)
        assert line is not None and line.startswith("keep") and "outside" in line, out
        assert out_wt.exists() and not any(out_wt.name in p.name for p in fx.held()), out
    assert fx.last_rc == 0, "a policy refusal is a keep, not a fault"


def test_p2_3_a_worktree_directory_that_is_really_a_symlink_to_outside_the_root_is_refused(fx: Fixture) -> None:
    inside = fx.root / "w4"
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/w4", str(inside))
    fx.merged.append(f"feat/w4 {_git(inside, 'rev-parse', 'HEAD')}")
    away = fx.root.parent / "away"
    away.mkdir()
    shutil.move(str(inside), str(away / "w4"))
    inside.symlink_to(away / "w4")
    out = fx.run(False)
    line = fx.line(out, inside)
    assert line is not None and line.startswith("keep") and "outside" in line, out
    assert (away / "w4").is_dir() and not any("w4" in p.name for p in fx.held()), out


def test_p2_3_a_quarantine_directory_that_is_a_symlink_out_of_the_root_moves_nothing_and_faults(fx: Fixture) -> None:
    """The quarantine lives under the root only by name: a `.prune-quarantine` symlink would carry the worktree out."""
    away = fx.root.parent / "away-q"
    away.mkdir()
    (fx.root / ".prune-quarantine").symlink_to(away)
    out = fx.run(False)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("FAILED") and "resolves outside" in line, out
    assert fx.wt.is_dir() and not any(away.iterdir()) and fx.last_rc == 1, out


def test_p2_3_a_stamp_directory_that_is_a_symlink_out_of_the_root_moves_nothing_and_faults(fx: Fixture) -> None:
    """The quarantine base is fine but the directory named for this run is a planted link: the move would leave the root."""
    pinned = "2030-01-01T000000Z"
    fx.shim("date", f'[ "$*" = "-u +%Y-%m-%dT%H%M%SZ" ] && {{ echo {pinned}; exit 0; }}\nexec /bin/date "$@"')
    away = fx.root.parent / "away-s"
    away.mkdir()
    fx.qbase.mkdir(parents=True)
    (fx.qbase / pinned).symlink_to(away)
    out = fx.run(False)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("FAILED") and "resolves outside" in line, out
    assert fx.wt.is_dir() and not any(away.iterdir()) and fx.last_rc == 1, out


@pytest.mark.parametrize("form", ["symlink", "dotdot"])
def test_p2_3_a_root_given_as_a_symlink_or_with_dotdot_still_accepts_its_own_worktrees_and_refuses_others(
    fx: Fixture, form: str
) -> None:
    if form == "symlink":
        link = fx.root.parent / "root-link"
        link.symlink_to(fx.root)
        given = str(link)
    else:
        given = f"{fx.root}/proj/../../{fx.root.name}"
    out_wt = _outside_worktree(fx, fx.root.parent / "elsewhere")
    out = fx.run(False, {"PROJECTS_ROOT": given})
    inside = fx.line(out, fx.wt)
    assert inside is not None and inside.startswith("quarantined"), out
    outside = fx.line(out, out_wt)
    assert outside is not None and outside.startswith("keep") and "outside" in outside, out
    assert out_wt.exists()


def _stamped(fx: Fixture, entry: Path, ago: datetime.timedelta) -> Path:
    """Move a held worktree into a directory named for the UTC instant `ago` before now, the way git itself would."""
    stamp = (datetime.datetime.now(datetime.timezone.utc) - ago).strftime("%Y-%m-%dT%H%M%SZ")
    parent = fx.qbase / stamp
    parent.mkdir(parents=True)
    dest = parent / entry.name
    _git(entry, "worktree", "move", str(entry), str(dest))
    return dest


def test_p3_1_the_hold_is_a_true_minimum_of_the_configured_days(fx: Fixture) -> None:
    """With PRUNE_QUARANTINE_DAYS=1 an entry quarantined 23h59m ago stays, one quarantined 24h01m ago goes, however
    the clock sits against midnight. A calendar-day directory purged the first one about a minute after midnight."""
    env = {"PRUNE_QUARANTINE_DAYS": "1"}
    fx.run(False, env)
    (entry,) = fx.held()
    young = _stamped(fx, entry, datetime.timedelta(hours=23, minutes=59))
    out = fx.run(False, env)
    assert young.exists() and "purge after" in _line(fx, out), out
    old = _stamped(fx, young, datetime.timedelta(hours=24, minutes=1))
    # _stamped moved it out of the first stamped directory
    out = fx.run(False, env)
    assert not old.exists() and not Path(str(old) + ".purge").exists(), out
    assert "removed" in out, out


def test_p3_1_a_quarantine_directory_that_is_not_a_timestamp_is_kept_and_faults(fx: Fixture) -> None:
    fx.run(False)
    (entry,) = fx.held()
    legacy = fx.qbase / "2000-01-01"  # the pre-round-9 calendar-day name
    legacy.mkdir()
    dest = legacy / entry.name
    _git(entry, "worktree", "move", str(entry), str(dest))
    out = fx.run(False)
    assert dest.exists() and "not a UTC timestamp" in out and fx.last_rc == 1, out


@pytest.mark.parametrize("name", ["staging", "develop", "master", "trunk"])
def test_p3_2_a_long_lived_branch_is_never_deleted_when_its_worktree_goes(fx: Fixture, name: str) -> None:
    """A linked worktree on staging whose HEAD equals a merged promotion PR head: the worktree may go, the branch
    (staging, develop, master, main or the remote HEAD branch) stays."""
    if name == "trunk":
        _git(fx.repo, "update-ref", "refs/remotes/origin/trunk", _git(fx.repo, "rev-parse", "HEAD"))
        _git(fx.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    stg = fx.root / "stg"
    _git(fx.repo, "worktree", "add", "-q", "-b", name, str(stg))
    fx.merged.append(f"{name} {_git(stg, 'rev-parse', 'HEAD')}")
    out = _to_the_end(fx)
    assert not any(stg.name in p.name for p in [stg, *fx.held()] if p.exists()), f"worktree should be gone:\n{out}"
    assert _git(fx.repo, "branch", "--list", name) != "", out
    assert f"kept    branch {name}" in out and "long-lived" in out, out
    assert _git(fx.repo, "branch", "--list", BRANCH_X) == "", "an ordinary merged branch is still deleted"


def test_p3_2_when_the_remote_head_branches_cannot_be_listed_the_branch_is_kept(fx: Fixture) -> None:
    """Fail closed: an unreadable `for-each-ref` for the remote HEADs means the branch might be the default branch."""
    fx.shim("git", f'case "$*" in *for-each-ref*symref*) exit 1 ;; esac\nexec \'{_real("git")}\' "$@"')
    out = _to_the_end(fx)
    assert not fx.wt.exists() and _git(fx.repo, "branch", "--list", "feat/x") != "", out
    assert "kept    branch feat/x" in out, out


BRANCH_X = "feat/x"


def _lines(prefix: str, n: int) -> list[str]:
    return [f"{prefix}-{i} {'0' * 40}" for i in range(n)]


def test_p3_3_an_open_pr_list_that_reached_the_limit_skips_the_repo_and_faults(fx: Fixture) -> None:
    """`gh pr list --limit 1000` truncates silently; a list of exactly 1000 might be missing the PR that reuses the
    branch name, so the repo is unverifiable."""
    fx.open = _lines("other", 1000)
    out = fx.run(False)
    assert "open PR list reached the limit" in out and fx.last_rc == 1, out
    assert fx.wt.exists() and not fx.held(), out


def test_p3_3_an_open_pr_list_below_the_limit_is_trusted(fx: Fixture) -> None:
    fx.open = _lines("other", 999)
    out = fx.run(False)
    assert "reached the limit" not in out and fx.last_rc == 0, out
    assert fx.held() and not fx.wt.exists(), out


def test_p3_3_a_merged_list_at_the_limit_only_misses_candidates_so_it_is_not_a_skip(fx: Fixture) -> None:
    fx.merged = [*_lines("old", 999), *fx.merged]
    out = fx.run(False)
    assert "reached the limit" not in out and fx.last_rc == 0, out
    assert fx.held(), out
