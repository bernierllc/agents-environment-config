"""Gap tests written during the mutation audit. Each docstring names the survivor mutant(s) it kills."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.test_prune_env_guard import (
    BRANCH,
    CACHEDIR_TAG,
    KEEP_ENV,
    KEEP_UNPROVEN,
    Fixture,
    _git,
    _ignored,
    _marked,
    _purged,
    _real,
    fx,  # noqa: F401
)
from tests.test_prune_round8_cases import KEEP_ADMIN, _admin_dir

KEEP_GITLINK = "holds files under an uninitialized submodule"


def _lines(out: str, wt: Path) -> list[str]:
    return [ln for ln in out.splitlines() if f"{wt}  (" in ln]


def _gitlinks(fx: Fixture, *paths: str) -> None:
    head = _git(fx.repo, "rev-parse", "HEAD")
    for p in paths:
        _git(fx.repo, "update-index", "--add", "--cacheinfo", f"160000,{head},{p}")
    _git(fx.repo, "commit", "-q", "-m", "gitlinks")
    _git(fx.wt, "merge", "-q", "--ff-only", "main")
    fx.merged = [f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}"]


def _data_in(fx: Fixture, rel: str) -> None:
    (fx.wt / rel).mkdir(parents=True, exist_ok=True)
    (fx.wt / rel / "data.db").write_text("only copy\n")
    assert _git(fx.wt, "status", "--porcelain") == ""


# --- regenerable() ---------------------------------------------------------------------------------------------
def test_unproven_file_after_a_marked_directory_still_keeps(fx: Fixture) -> None:
    """#35: the cached prefix must be a real prefix of the next path. (Adapted for round 9: `_marked` is now a cache
    marker, the one kind that proves a whole directory, so only the prefix test can keep `zz/`.)"""
    _marked(fx)
    _ignored(fx, "zz/only-copy.db")
    fx.keeps(KEEP_UNPROVEN)


def test_glob_characters_in_the_cached_prefix_are_literal(fx: Fixture) -> None:
    """#276: `a[b]/` unquoted would match `ab/`. Adapted for round 9: a venv marker proves only what its RECORD files
    list, so a wrongly matched `ab/data.db` would have kept the tree either way and the mutant lived. A cache marker
    proves the whole directory, so a wrong glob match would let `ab/data.db` go and only the literal match keeps it."""
    fx.exclude(r"a\[b\]/")
    (fx.wt / "a[b]").mkdir()
    (fx.wt / "a[b]" / "CACHEDIR.TAG").write_text(CACHEDIR_TAG)
    _ignored(fx, "ab/data.db")
    fx.keeps(KEEP_UNPROVEN)


def test_a_directory_named_like_a_node_modules_marker_proves_nothing(fx: Fixture) -> None:
    """#49: the marker must be a regular file."""
    fx.exclude("node_modules/")
    nm = fx.wt / "node_modules"
    (nm / ".package-lock.json").mkdir(parents=True)
    (nm / "pkg").mkdir()
    (nm / "pkg" / "data.db").write_text("x\n")
    fx.keeps(KEEP_UNPROVEN)


# --- gitlink_data() --------------------------------------------------------------------------------------------
def test_gitlink_path_with_a_space_is_scanned(fx: Fixture) -> None:
    """#64: IFS must be the newline only."""
    _gitlinks(fx, "my sub")
    _data_in(fx, "my sub")
    fx.keeps(KEEP_GITLINK)


def test_every_gitlink_is_scanned_not_just_the_last(fx: Fixture) -> None:
    """#78: subs must accumulate."""
    _gitlinks(fx, "a1", "b1")
    _data_in(fx, "a1")
    fx.keeps(KEEP_GITLINK)


def test_gitlink_named_star_is_not_globbed(fx: Fixture) -> None:
    """#63: `set -f` keeps `*` literal."""
    _gitlinks(fx, "*")
    _data_in(fx, "*")
    fx.keeps(KEEP_GITLINK)


# --- env / admin dir -------------------------------------------------------------------------------------------
def test_env_that_shares_a_prefix_with_the_primary_copy_keeps(fx: Fixture) -> None:
    """#33: cmp must compare the whole file."""
    (fx.repo / ".env").write_text("AAAAAAAAprimary\n")
    (fx.wt / ".env").write_text("AAAAAAAAworktree\n")
    fx.keeps(KEEP_ENV)


@pytest.mark.parametrize("name", ["MERGE_HEAD", "MERGE_MSG", "CHERRY_PICK_HEAD", "REVERT_HEAD", "config.worktree"])
def test_unlisted_admin_dir_file_keeps(fx: Fixture, name: str) -> None:
    """#145: only the listed names are what git writes for a clean worktree."""
    (_admin_dir(fx) / name).write_text(fx.merged[0].split()[1] + "\n")
    fx.keeps(KEEP_ADMIN)


# --- git-dir lookup failures must keep, not pass ---------------------------------------------------------------
@pytest.mark.parametrize("nth", [1, 2, 3])
def test_a_failing_absolute_git_dir_lookup_keeps_whichever_call_fails(fx: Fixture, nth: int) -> None:
    """#151 (1st: reflog, worktree), #150 (2nd: reflog, primary), #135 (3rd: admin dir scan)."""
    cnt = fx.bindir.parent / "cnt"
    cnt.write_text("0")
    fx.shim(
        "git",
        f'case " $* " in *" rev-parse --absolute-git-dir "*)\n'
        f'  c=$(cat "{cnt}"); c=$((c + 1)); echo $c >"{cnt}"\n'
        f'  [ "$c" -eq {nth} ] && {{ echo "fatal: injected" >&2; exit 128; }} ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out = fx.run(True, expect_fault=True)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("keep") and "could not locate" in line, out


# --- the purge pass --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("val", ["", "yes", "true", "2"])
def test_purge_pass_only_acts_on_dry_run_exactly_0(fx: Fixture, val: str) -> None:
    """#216, #217: DRY_RUN fails closed in the purge pass too."""
    out = fx.run(False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    (entry,) = fx.held()
    aged = fx.age(entry)
    out = fx.run(False, {"DRY_RUN": val})
    assert aged.exists() and "would   purge" in out, out


def test_a_file_written_just_before_the_remove_is_not_deleted(fx: Fixture) -> None:
    """#227: `git worktree remove` without --force refuses a tree that gained a file. Adapted for round 9: the late
    write lands after the rescan and the holder scan, which is the one gap left (it is what `PRUNE_ALLOW_DELETE`
    guards), so this pins what still holds there, git's own refusal of a non-ignored file; an ignored late file is the
    strict xfail in test_prune_round9_cases (p2-2)."""
    fx.shim(
        "git",
        'case " $* " in *" worktree remove "*) for a; do last="$a"; done; echo late >"$last/late.txt" ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out, aged = _purged(fx, expect_fault=True)
    aside = Path(str(aged) + ".purge")
    assert (aside / "late.txt").exists(), out
    assert "FAILED" in out, out


def test_purge_rescan_failure_keeps_moves_back_and_faults(fx: Fixture) -> None:
    """#226 (rc 2 treated as clean), #224 (fault not recorded)."""
    fx.shim(
        "git",
        'case "$*" in *".purge -c core.fsmonitor=false status"*) echo "fatal: injected" >&2; exit 128 ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out, aged = _purged(fx, expect_fault=True)
    assert aged.exists() and not Path(str(aged) + ".purge").exists(), out
    assert "moved back after the rescan" in out, out


def test_purge_rescan_failure_and_failed_move_back_faults(fx: Fixture) -> None:
    """#225: a move-back that fails must be recorded as a fault."""
    fx.shim(
        "git",
        'case "$*" in *".purge -c core.fsmonitor=false status"*) echo " M injected"; exit 0 ;; esac\n'
        'case "$*" in *worktree\\ move\\ *.purge\\ /*) echo "fatal: injected" >&2; exit 128 ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out, aged = _purged(fx, expect_fault=True)
    assert "FAILED" in out, out
    assert Path(str(aged) + ".purge").exists() and not aged.exists(), out


def test_purge_guard_failure_keeps_and_faults(fx: Fixture) -> None:
    """#215 (rc 2 treated as clean), #214 (fault not recorded)."""
    fx.shim(
        "git",
        'case "$*" in *"/2000-01-01T000000Z/"*"-c core.fsmonitor=false status"*)\n'
        '  case "$*" in *".purge -c"*) ;; *) echo "fatal: injected" >&2; exit 128 ;; esac ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out, aged = _purged(fx, expect_fault=True)
    assert aged.exists() and "removed" not in out, out


def test_purge_holder_found_and_failed_move_back_faults(fx: Fixture) -> None:
    """Fault-site audit (the holder-check branch): a holder is a policy keep (exit 0 from the check, so it records no
    fault of its own) AND the move back fails, so only the failed move can make the run exit 1; the tree stays at the
    `.purge` name."""
    # round 10: the first move scans too, so the holder appears only once the entry is at its `.purge` name
    fx.shim("lsof", 'case "$*" in *.purge*) printf "p1\\ncinjected\\n"; exit 0 ;; esac\nexit 1')
    fx.shim(
        "git",
        'case "$*" in *worktree\\ move\\ *.purge\\ /*) echo "fatal: injected" >&2; exit 128 ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out, aged = _purged(fx, expect_fault=True)
    assert "FAILED" in out and "a process holds files inside it" in out, out
    assert Path(str(aged) + ".purge").exists() and not aged.exists(), out


def test_a_garbage_cutoff_date_does_not_purge_a_fresh_entry(fx: Fixture) -> None:
    """#197: a cutoff that is not a date must disable the purge."""
    fx.shim(
        "date",
        'case "$*" in *"-v-"*|*"days ago"*) echo zzzz ;; *) exec "' + _real("date") + '" "$@" ;; esac',
    )
    out = fx.run(False, expect_fault=True)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    out = fx.run(False, expect_fault=True)
    assert fx.held() and "removed" not in out, out


def test_symlinked_root_still_purges_an_aged_entry(fx: Fixture) -> None:
    """#254: the quarantine test must compare directories, not text."""
    link = fx.wt.parent / "root-link"
    link.symlink_to(fx.root)
    env = {"PROJECTS_ROOT": str(link)}
    out, aged = _purged(fx, env)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("removed"), out


# --- quarantine pass -------------------------------------------------------------------------------------------
def test_quarantine_rescan_failure_moves_back_and_faults(fx: Fixture) -> None:
    """#207 (rc 2 treated as clean), #205 (fault not recorded)."""
    fx.shim(
        "git",
        'case "$*" in *"/.prune-quarantine/"*"-c core.fsmonitor=false status"*) echo "fatal: injected" >&2; exit 128 ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out = fx.run(False, expect_fault=True)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("keep") and "moved back after the move" in line, out
    assert fx.wt.exists() and fx.held() == [], out


def test_quarantine_dir_that_cannot_be_created_faults(fx: Fixture) -> None:
    """#199."""
    (fx.root / ".prune-quarantine").write_text("a file, not a directory\n")
    out = fx.run(False, expect_fault=True)
    assert len(_lines(out, fx.wt)) == 1 and "FAILED" in out and fx.wt.exists(), out


def test_quarantine_stamp_directory_that_cannot_be_created_faults(fx: Fixture) -> None:
    """Fault-site audit (the `mkdir -p "$dir"` branch): a stamp directory that cannot be made moves nothing and
    exits 1. The date is pinned so a plain file can sit where the directory must go."""
    fx.shim(
        "date",
        f'case "$*" in "-u +"*) echo 2030-01-01T000000Z ;; *) exec "{_real("date")}" "$@" ;; esac',
    )
    fx.qbase.mkdir()
    (fx.qbase / "2030-01-01T000000Z").write_text("a file, not a directory\n")
    out = fx.run(False, expect_fault=True)
    assert len(_lines(out, fx.wt)) == 1 and "could not create" in out and fx.wt.exists(), out


def test_failed_move_into_the_quarantine_stops_there(fx: Fixture) -> None:
    """#203: no rescan and no second line after a failed move."""
    fx.git_fails("worktree move")
    out = fx.run(False, expect_fault=True)
    assert len(_lines(out, fx.wt)) == 1 and fx.wt.exists(), out


# --- the main loop ---------------------------------------------------------------------------------------------
def test_open_pr_keep_does_not_fall_through_to_the_quarantine(fx: Fixture) -> None:
    """#259."""
    fx.open = [fx.merged[0]]
    out = fx.run(False, expect_fault=False)
    assert len(_lines(out, fx.wt)) == 1 and fx.held() == [] and fx.wt.exists(), out


def test_failed_scan_keep_does_not_fall_through_to_the_quarantine(fx: Fixture) -> None:
    """#263: the keep for a failed scan must `continue`."""
    fx.shim(
        "git",
        f'case "$*" in *"-C {fx.wt} -c core.fsmonitor=false status"*) echo "fatal: injected" >&2; exit 128 ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    out = fx.run(False, expect_fault=True)
    assert len(_lines(out, fx.wt)) == 1 and fx.held() == [] and fx.wt.exists(), out


def test_open_pr_list_awk_failure_keeps_and_faults(fx: Fixture) -> None:
    """#260 (ignored), #261 (not recorded)."""
    fx.shim("awk", 'case "$*" in *"exit !f"*) exit 2 ;; esac\nexec "' + _real("awk") + '" "$@"')
    out = fx.run(False, expect_fault=True)
    assert "could not read the open PR list" in out and fx.held() == [] and fx.wt.exists(), out


@pytest.mark.parametrize("state", ["merged", "open"])
def test_gh_failure_is_a_recorded_fault(fx: Fixture, state: str) -> None:
    """#245 (merged), #247 (open): the skip must exit 1."""
    fx.gh_fail = state
    out = fx.run(False, expect_fault=True)
    assert "injected failure" in out, out  # #22: the gh error text is shown
    assert fx.wt.exists() and fx.line(out, fx.wt) is None, out


def test_rev_parse_git_dir_failure_is_a_recorded_fault(fx: Fixture) -> None:
    """#235."""
    fx.git_fails("rev-parse --git-dir")
    out = fx.run(False, expect_fault=True)
    assert "skip" in out, out


def test_worktree_list_failure_is_a_recorded_fault(fx: Fixture) -> None:
    """#237."""
    fx.git_fails("worktree list --porcelain")
    out = fx.run(False, expect_fault=True)
    assert "could not list worktrees" in out, out


def test_gh_merged_failure_with_a_held_entry_prints_nothing_about_it(fx: Fixture) -> None:
    """#246: after a failed merged list the repo is skipped, not walked with an empty list."""
    out = fx.run(False, expect_fault=False)
    assert fx.held()
    fx.gh_fail = "merged"
    out = fx.run(False, expect_fault=True)
    assert "no longer in the merged PR list" not in out, out


# --- environment -----------------------------------------------------------------------------------------------
def test_empty_projects_root_falls_back_to_home_projects(fx: Fixture) -> None:
    """#3: PROJECTS_ROOT set but empty must not make ROOT empty (a scan of /)."""
    home = fx.wt.parent / "home"
    home.mkdir()
    (home / "projects").symlink_to(fx.root)
    out = fx.run(True, {"PROJECTS_ROOT": "", "HOME": str(home)})
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("would"), out


def test_the_run_leaves_no_temp_files(fx: Fixture) -> None:
    """#16: the EXIT trap removes the fault file."""
    tmp = fx.wt.parent / "private-tmp"
    tmp.mkdir()
    # macOS mktemp ignores TMPDIR when given no template, so route it through the shim
    fx.shim("mktemp", f'exec "{_real("mktemp")}" "{tmp}/tmp.XXXXXX"')
    fx.run(True)
    assert list(tmp.iterdir()) == []


# --- policy keeps must exit 0 ----------------------------------------------------------------------------------
def test_policy_keeps_exit_zero(fx: Fixture) -> None:
    """#83 (gitlink policy keep), #181 (reflog policy keep): a policy keep is not a fault."""
    _gitlinks(fx, "sub")
    _data_in(fx, "sub")
    fx.run(True, expect_fault=False)


def test_reflog_orphan_keep_exits_zero(fx: Fixture) -> None:
    """#181."""
    _git(fx.wt, "commit", "-q", "--allow-empty", "-m", "lost")
    _git(fx.wt, "reset", "-q", "--hard", "HEAD~1")
    out = fx.run(True, expect_fault=False)
    assert "reflog holds commits no ref reaches" in out, out


def test_dangling_symlink_reflog_keeps_and_faults(fx: Fixture) -> None:
    """#156: an unreadable (dangling) reflog is not 'no reflog'."""
    log = _admin_dir(fx) / "logs" / "HEAD"
    log.unlink()
    log.symlink_to("/nonexistent-reflog")
    out = fx.run(True, expect_fault=True)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("keep"), out


def test_no_reflogs_at_all_means_removable(fx: Fixture) -> None:
    """#162: nothing in any log, nothing to lose."""
    (_admin_dir(fx) / "logs" / "HEAD").unlink()
    (_admin_dir(fx) / "ORIG_HEAD").unlink()  # it names a commit too, so ids would not be empty
    (fx.repo / ".git" / "logs" / "refs" / "heads" / "feat" / "x").unlink()
    out = fx.run(True)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("would"), out
