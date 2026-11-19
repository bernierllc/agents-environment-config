"""Round 8 of scripts/prune-merged-worktrees.sh: the six data-loss cases a review of round 7 reproduced, pinned one
test each (the `test_case<N>_` tests), and the quarantine that now sits between "found" and "deleted".

Every test runs the real script under /bin/bash against a real git repo with a stub `gh`, through the Fixture of
tests/test_prune_env_guard.py. Each `test_case<N>_` test failed against the round-7 head (c5d4663) and passes now.
No test depends on a platform tool beyond git, bash and coreutils (case 6 used macOS `lsof` in the review's repro;
here the readback failure is injected through a private TMPDIR instead).
"""

from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

import pytest

from tests.test_prune_env_guard import (
    BRANCH,
    FAULT_LINE,
    KEEP_ENV,
    KEEP_UNPROVEN,
    SCRIPT,
    Fixture,
    _git,
    _first_mktemp_is_real,
    _ignored,
    _marked,
    _purged,
    _real,
    _with_submodule,
    fx,  # noqa: F401  (the pytest fixture)
)

KEEP_REFLOG = "a reflog holds commits no ref reaches"
KEEP_ADMIN = "its git directory holds"


def _git_in(repo: Path, *args: str, text: str) -> str:
    """git with stdin, for plumbing (hash-object, mktree, commit-tree)."""
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    import os

    return subprocess.run(
        ["git", "-C", str(repo), *args], input=text, check=True, capture_output=True, text=True, env={**os.environ, **env}
    ).stdout.strip()


def _admin_dir(fx: Fixture) -> Path:
    return Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))


def _entry_on(fx: Fixture, entry: Path, day: str) -> Path:
    """Move a quarantined worktree into the dated directory `day`, the way git would."""
    parent = fx.qbase / day
    parent.mkdir(parents=True, exist_ok=True)
    dest = parent / entry.name
    _git(entry, "worktree", "move", str(entry), str(dest))
    return dest


def _days_ago(n: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


# =============================================================================================================
# Case 1: a directory NAME (dist, build, ...) authorised deleting any ignored file beneath it
# =============================================================================================================


@pytest.mark.parametrize("top", ["dist", "build", "coverage", ".next", ".turbo", "out", "node_modules"])
def test_case1_a_directory_name_does_not_authorise_deleting_what_is_inside(fx: Fixture, top: str) -> None:
    _ignored(fx, f"{top}/customer-database.sqlite", "ONLY COPY OF CUSTOMER DATA\n")
    fx.keeps(KEEP_UNPROVEN)
    assert (fx.wt / top / "customer-database.sqlite").read_text() == "ONLY COPY OF CUSTOMER DATA\n"


def test_case1_a_marked_tree_does_not_vouch_for_its_unmarked_neighbour(fx: Fixture) -> None:
    _ignored(fx, "node_modules/.package-lock.json", "{}\n")
    _ignored(fx, "node_modules/pkg/index.js")
    _ignored(fx, "dist/customer-database.sqlite", "ONLY COPY\n")
    fx.keeps(KEEP_UNPROVEN)


def test_case1_a_file_inside_a_marked_tree_is_regenerable_but_a_secret_name_still_keeps(fx: Fixture) -> None:
    _marked(fx)
    _ignored(fx, "tree/lib/x.py")
    assert fx.verdict() == "would"
    _ignored(fx, "tree/lib/server.pem")
    fx.keeps("holds secret-named files")


# =============================================================================================================
# Case 2: update-ref -d deletes the BRANCH reflog; only the worktree's HEAD reflog was checked
# =============================================================================================================


def _commit_only_the_branch_reflog_remembers(fx: Fixture) -> str:
    """A commit (with a unique blob) that the branch pointed at, then moved off: no ref reaches it, the worktree's
    HEAD reflog never saw it, and the branch reflog is the only place that names it."""
    base = _git(fx.repo, "rev-parse", "HEAD")
    blob = _git_in(fx.repo, "hash-object", "-w", "--stdin", text="ONLY COPY OF UNPUSHED FILE\n")
    tree = _git_in(fx.repo, "mktree", text=f"100644 blob {blob}\tunique.txt\n")
    unique = _git_in(fx.repo, "commit-tree", tree, "-p", base, text="unpushed work\n")
    _git(fx.repo, "update-ref", f"refs/heads/{BRANCH}", unique, base)
    _git(fx.repo, "update-ref", f"refs/heads/{BRANCH}", base, unique)
    assert unique in _git(fx.repo, "reflog", "show", "--format=%H", BRANCH)
    assert unique not in _git(fx.wt, "reflog", "show", "--format=%H", "HEAD"), "the case needs the branch log alone"
    assert _git(fx.wt, "status", "--porcelain") == ""
    return unique


def test_case2_a_commit_only_the_branch_reflog_names_keeps_the_worktree(fx: Fixture) -> None:
    unique = _commit_only_the_branch_reflog_remembers(fx)
    fx.keeps(KEEP_REFLOG)
    assert unique in _git(fx.repo, "reflog", "show", "--format=%H", BRANCH)
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_case2_controls_the_same_worktree_goes_once_a_ref_reaches_the_commit_or_the_log_is_gone(fx: Fixture) -> None:
    unique = _commit_only_the_branch_reflog_remembers(fx)
    _git(fx.repo, "tag", "rescued", unique)
    assert fx.verdict() == "would"
    _git(fx.repo, "tag", "-d", "rescued")
    fx.keeps(KEEP_REFLOG, real=False)
    _git(fx.repo, "reflog", "expire", "--expire=now", f"refs/heads/{BRANCH}")
    assert fx.verdict() == "would"


def test_case2_a_branch_reflog_that_cannot_be_read_keeps_and_faults(fx: Fixture) -> None:
    _commit_only_the_branch_reflog_remembers(fx)
    log = fx.repo / ".git" / "logs" / "refs" / "heads" / "feat" / "x"
    log.chmod(0)
    try:
        if log.read_text:  # root can read a mode-0 file; the injected failure only exists for other users
            import os

            if hasattr(os, "geteuid") and os.geteuid() == 0:
                pytest.skip("root reads a mode 0 file")
        out = fx.run(True)
        line = fx.line(out, fx.wt)
        assert line is not None and line.startswith("keep"), out
        assert fx.last_rc == 1 and FAULT_LINE in out
    finally:
        log.chmod(0o644)


# =============================================================================================================
# Case 3: MERGE_AUTOSTASH (and every other pseudoref or per-worktree file git does not create for a clean worktree)
# =============================================================================================================


def test_case3_a_real_merge_autostash_keeps_the_worktree(fx: Fixture) -> None:
    base = _git(fx.repo, "rev-parse", "HEAD")
    tree = _git(fx.repo, "rev-parse", "HEAD^{tree}")
    other = _git_in(fx.repo, "commit-tree", tree, "-p", base, text="empty integration commit\n")
    _git(fx.repo, "branch", "integration-tip", other)
    (fx.wt / ".env.example").write_text("ONLY COPY OF UNCOMMITTED WORK\n")
    _git(fx.wt, "merge", "--autostash", "--no-commit", "--no-ff", "integration-tip")
    gd = _admin_dir(fx)
    assert (gd / "MERGE_AUTOSTASH").exists()
    assert _git(fx.wt, "status", "--porcelain") == "", "the case needs a clean-looking worktree"
    fx.keeps(KEEP_ADMIN)
    assert (gd / "MERGE_AUTOSTASH").exists()


def test_case3_a_merge_autostash_pseudoref_alone_keeps_and_is_named(fx: Fixture) -> None:
    gd = _admin_dir(fx)
    (fx.wt / ".env.example").write_text("ONLY COPY OF UNCOMMITTED WORK\n")
    stash = _git(fx.wt, "stash", "create")
    assert stash
    _git(fx.wt, "checkout", "--", ".env.example")
    (gd / "MERGE_AUTOSTASH").write_text(stash + "\n")
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps(f"{KEEP_ADMIN} MERGE_AUTOSTASH")


@pytest.mark.parametrize(
    "rel",
    [
        "MERGE_MSG",
        "SQUASH_MSG",
        "BISECT_LOG",
        "modules/sub/HEAD",
        "rebase-merge/head-name",
        "info/exclude",
        "refs/x",
        "logs/refs/worktree/x",  # only logs/HEAD is allowed, not the rest of logs/
    ],
)
def test_case3_any_file_git_does_not_create_for_a_clean_worktree_keeps(fx: Fixture, rel: str) -> None:
    gd = _admin_dir(fx)
    (gd / rel).parent.mkdir(parents=True, exist_ok=True)
    (gd / rel).write_text("only copy\n")
    fx.keeps(f"{KEEP_ADMIN} {rel}")
    assert (gd / rel).read_text() == "only copy\n"


def test_case3_what_git_writes_for_a_clean_worktree_does_not_keep(fx: Fixture) -> None:
    """COMMIT_EDITMSG, FETCH_HEAD, index and logs/HEAD are the control: they alone never keep a worktree."""
    _git(fx.wt, "commit", "-q", "--allow-empty", "-m", "more")
    fx.merged = [f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}"]
    _git(fx.wt, "fetch", "-q", str(fx.repo), "main")
    gd = _admin_dir(fx)
    assert (gd / "COMMIT_EDITMSG").exists() and (gd / "FETCH_HEAD").exists()
    assert fx.verdict() == "would"


# =============================================================================================================
# Case 4: per-worktree config.worktree may hold the only copy of a credential
# =============================================================================================================


def test_case4_a_per_worktree_config_keeps_the_worktree(fx: Fixture) -> None:
    _git(fx.repo, "config", "extensions.worktreeConfig", "true")
    _git(fx.wt, "config", "--worktree", "http.https://example.invalid/.extraHeader", "Authorization: Bearer SYNTHETIC")
    gd = _admin_dir(fx)
    assert (gd / "config.worktree").exists()
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps(f"{KEEP_ADMIN} config.worktree")
    assert (gd / "config.worktree").exists()


# =============================================================================================================
# Case 5: a file written between the scan and the deletion (TOCTOU)
# =============================================================================================================

RACE_SHIM = """case " $* " in *" worktree move "*|*" worktree remove "*) ;; *) exec "{real}" "$@" ;; esac
[ -e "{mark}" ] && exec "{real}" "$@"
: >"{mark}"
after=0; src=""
for a in "$@"; do
  if [ "$after" = 1 ]; then case "$a" in -*) ;; *) src="$a"; break ;; esac
  else case "$a" in move|remove) after=1 ;; esac; fi
done
printf 'ONLY_COPY=synthetic\\n' >"$src/.env.local"
exec "{real}" "$@\""""


def _race_on_the_first_move_or_remove(fx: Fixture) -> Path:
    """The first `git worktree move|remove` of the run first writes an ignored .env.local into its source path."""
    mark = fx.root.parent / "race-mark"
    fx.shim("git", RACE_SHIM.format(real=_real("git"), mark=mark).replace('"$@\\""', '"$@"'))
    return mark


def test_case5_a_secret_written_before_the_quarantine_move_is_found_by_the_rescan_and_moved_back(fx: Fixture) -> None:
    _race_on_the_first_move_or_remove(fx)
    out = fx.run(dry=False)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("keep") and "moved back after the move" in line, out
    assert (fx.wt / ".env.local").read_text() == "ONLY_COPY=synthetic\n"
    assert fx.last_rc == 0 and not fx.held()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_case5_a_secret_written_before_the_purge_move_is_found_by_the_rescan_and_moved_back(fx: Fixture) -> None:
    out = fx.run(dry=False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    _race_on_the_first_move_or_remove(fx)
    out, aged = fx.purge_run(fx.wt)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("keep") and "moved back after the rescan" in line, out
    assert (aged / ".env.local").read_text() == "ONLY_COPY=synthetic\n"
    assert fx.last_rc == 0 and not Path(f"{aged}.purge").exists()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


# =============================================================================================================
# Case 6: a scan list that cannot be read back must not read as "nothing found"
# =============================================================================================================


def _list_files_vanish_after(fx: Fixture, tool: str, needle: str) -> dict[str, str]:
    """The scan's list files are made in a private directory; `tool` runs for real and, when its arguments contain
    `needle`, every list file is then deleted, the way a full disk, a cleaner or a race would. Portable: it uses only
    mktemp with a template, never lsof or a platform's TMPDIR rules."""
    scratch = fx.root.parent / "scratch-tmp"
    scratch.mkdir(exist_ok=True)
    _first_mktemp_is_real(fx, f'exec "{_real("mktemp")}" "{scratch}/list.XXXXXX"')
    fx.shim(
        tool,
        f'"{_real(tool)}" "$@"; rc=$?\ncase " $* " in *" {needle} "*) rm -f "{scratch}"/list.* ;; esac\nexit $rc',
    )
    return {}


@pytest.mark.parametrize(
    ("tool", "needle", "why"),
    [
        ("git", "ls-files -z -s -v", "could not read back the index list"),
        ("git", "ls-files -z -o", "could not read back the list of ignored files"),
        ("find", "! -type d", "could not read back the git dir scan"),
        ("find", "-iname objects", "could not read back the nested repo scan"),
    ],
    ids=["index", "ignored", "admin-dir", "nested-repo"],
)
def test_case6_a_scan_list_that_cannot_be_read_back_keeps_and_faults(fx: Fixture, tool: str, needle: str, why: str) -> None:
    env = _list_files_vanish_after(fx, tool, needle)
    fx.keeps(why, env=env)
    assert fx.last_rc == 1 and FAULT_LINE in fx.last_out
    assert fx.wt.exists()


def test_case6_control_the_same_shim_that_never_fires_does_not_keep(fx: Fixture) -> None:
    env = _list_files_vanish_after(fx, "git", "a-needle-no-call-contains")
    assert fx.verdict(env=env) == "would"


# =============================================================================================================
# Quarantine and purge
# =============================================================================================================


def test_a_real_run_moves_the_worktree_aside_and_keeps_it_a_working_worktree(fx: Fixture) -> None:
    out = fx.run(dry=False)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("quarantined"), out
    (entry,) = fx.held()
    assert entry.parent.name == datetime.date.today().isoformat() and entry.name == f"{fx.repo.name}--{fx.wt.name}"
    assert not fx.wt.exists()
    assert f"restore: git -C {fx.repo} worktree move {entry} {fx.wt}" in line
    assert str(entry) in _git(fx.repo, "worktree", "list", "--porcelain")
    assert _git(entry, "rev-parse", "--abbrev-ref", "HEAD") == BRANCH and _git(entry, "status", "--porcelain") == ""
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""  # the branch is deleted only by the purge
    # the printed restore command works
    _git(fx.repo, "worktree", "move", str(entry), str(fx.wt))
    assert _git(fx.wt, "status", "--porcelain") == "" and not fx.held()


def test_dry_run_reports_would_quarantine_and_would_purge_and_changes_nothing(fx: Fixture) -> None:
    out = fx.run(dry=True)
    assert "would   quarantine" in out and fx.wt.exists() and not fx.held()
    out = fx.run(dry=False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined")
    (entry,) = fx.held()
    aged = _entry_on(fx, entry, "2000-01-01")
    out = fx.run(dry=True)
    assert f"would   purge {aged}" in out and aged.exists()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_a_young_entry_is_kept_until_the_cutoff(fx: Fixture) -> None:
    fx.run(dry=False)
    out = fx.run(dry=False)
    (entry,) = fx.held()
    line = fx.line(out, entry)
    assert line is not None and line.startswith("keep") and "purge after" in line, out
    assert fx.last_rc == 0


@pytest.mark.parametrize(
    ("days_env", "age_days", "purged"),
    [
        (None, 7, True),  # exactly at the cutoff: purged
        (None, 6, False),
        ("30", 10, False),
        ("30", 30, True),
        ("1", 1, True),
        ("1", 0, False),
    ],
    ids=["default-at-7", "default-at-6", "30-at-10", "30-at-30", "1-at-1", "1-at-0"],
)
def test_the_cutoff_is_prune_quarantine_days(fx: Fixture, days_env: str | None, age_days: int, purged: bool) -> None:
    env = {"PRUNE_QUARANTINE_DAYS": days_env} if days_env else {}
    fx.run(dry=False, env=env)
    (entry,) = fx.held()
    aged = _entry_on(fx, entry, _days_ago(age_days)) if age_days else entry
    out = fx.run(dry=False, env=env)
    line = fx.line(out, aged)
    assert line is not None, out
    assert line.startswith("removed" if purged else "keep"), out
    assert aged.exists() is not purged


@pytest.mark.parametrize("value", ["0", "-1", "abc", "", "1.5", "07", " 3"])
def test_an_invalid_quarantine_days_value_refuses_to_run(fx: Fixture, value: str) -> None:
    proc = subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env={
            "PATH": f"{fx.bindir}:/usr/bin:/bin",
            "HOME": str(fx.root),
            "PROJECTS_ROOT": str(fx.root),
            "DRY_RUN": "0",
            "PRUNE_QUARANTINE_DAYS": value,
        },
    )
    assert proc.returncode == 1 and "PRUNE_QUARANTINE_DAYS must be a whole number of days" in proc.stdout
    assert fx.wt.exists() and not fx.held()


def test_an_expired_entry_is_purged_and_only_then_is_the_branch_deleted(fx: Fixture) -> None:
    out = fx.run(dry=False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""
    out, aged = fx.purge_run(fx.wt)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("removed"), out
    assert not aged.exists() and not Path(f"{aged}.purge").exists() and not fx.held()
    assert _git(fx.repo, "branch", "--list", BRANCH) == ""
    assert fx.last_rc == 0 and fx.repo.exists()


def test_the_purge_runs_the_full_guard_again_on_the_held_tree(fx: Fixture) -> None:
    fx.run(dry=False)
    (entry,) = fx.held()
    (entry / ".env.local").write_text("WRITTEN_DURING_THE_HOLD=1\n")
    out, aged = fx.purge_run(fx.wt)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("keep") and KEEP_ENV in line, out
    assert (aged / ".env.local").read_text() == "WRITTEN_DURING_THE_HOLD=1\n"
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_a_tracked_edit_made_during_the_hold_keeps_the_entry(fx: Fixture) -> None:
    fx.run(dry=False)
    (entry,) = fx.held()
    (entry / ".env.example").write_text("EDITED\n")
    out, aged = fx.purge_run(fx.wt)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("keep") and "worktree dirty" in line, out


def test_an_entry_whose_pr_left_the_merged_list_is_kept_and_reported(fx: Fixture) -> None:
    fx.run(dry=False)
    fx.merged = []
    (entry,) = fx.held()
    aged = _entry_on(fx, entry, "2000-01-01")
    out = fx.run(dry=False)
    line = fx.line(out, aged)
    assert line is not None and "no longer in the merged PR list" in line, out
    assert aged.exists() and fx.last_rc == 0


def test_an_entry_under_a_directory_that_is_not_a_date_is_kept_and_faults(fx: Fixture) -> None:
    fx.run(dry=False)
    (entry,) = fx.held()
    odd = _entry_on(fx, entry, "not-a-date")
    out = fx.run(dry=False)
    line = fx.line(out, odd)
    assert line is not None and "is not a date" in line, out
    assert odd.exists() and fx.last_rc == 1


def test_an_aside_name_that_is_already_taken_fails_the_purge_and_keeps_the_entry(fx: Fixture) -> None:
    fx.run(dry=False)
    (entry,) = fx.held()
    aged = _entry_on(fx, entry, "2000-01-01")
    Path(f"{aged}.purge").mkdir()
    out = fx.run(dry=False)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("FAILED") and "already exists" in line, out
    assert fx.last_rc == 1 and aged.exists()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_two_quarantines_of_the_same_name_on_one_day_do_not_collide(fx: Fixture) -> None:
    fx.run(dry=False)
    (first,) = fx.held()
    other = fx.wt.parent / fx.wt.name  # the same directory name, a new branch
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/y", str(other))
    fx.merged.append(f"feat/y {_git(other, 'rev-parse', 'HEAD')}")
    out = fx.run(dry=False)
    assert (fx.line(out, other) or "").startswith("quarantined"), out
    assert sorted(p.name for p in fx.held()) == [first.name, f"{first.name}-2"]


def test_a_quarantined_entry_is_not_mistaken_for_a_repository(fx: Fixture) -> None:
    fx.run(dry=False)
    out = fx.run(dry=True)
    assert "skip" not in out and fx.last_rc == 0


# =============================================================================================================
# Mutation-run survivors, each pinned by one test: the marker rules, the reflog sources, the quarantine edges
# =============================================================================================================

SIG = "Signature: 8a477f597d28d172789f06886806bc55"


def test_a_cachedir_tag_whose_first_line_continues_after_the_signature_still_proves_the_directory(fx: Fixture) -> None:
    _ignored(fx, "cache/CACHEDIR.TAG", f"{SIG} (written by a tool that appends text)\n")
    _ignored(fx, "cache/x.bin")
    assert fx.verdict() == "would"


def test_a_package_lock_marker_proves_only_node_modules_not_any_directory(fx: Fixture) -> None:
    _ignored(fx, "vendor/.package-lock.json", "{}\n")
    _ignored(fx, "vendor/x.js")
    fx.keeps(KEEP_UNPROVEN)


def test_a_pnpm_marker_that_is_a_symlink_proves_nothing(fx: Fixture) -> None:
    store = fx.root.parent / "pnpm-store"
    store.mkdir()
    fx.exclude("node_modules/")
    (fx.wt / "node_modules").mkdir()
    (fx.wt / "node_modules" / ".pnpm").symlink_to(store)
    _ignored(fx, "node_modules/pkg/index.js")
    fx.keeps(KEEP_UNPROVEN)


def _commit_py(fx: Fixture, name: str) -> None:
    (fx.wt / name).write_text("x = 1\n")
    fx.commit(name)


@pytest.mark.parametrize("ext", ["pyc", "pyo"])
def test_a_compiled_file_in_pycache_with_its_source_beside_it_is_regenerable(fx: Fixture, ext: str) -> None:
    _commit_py(fx, "mod.py")
    _ignored(fx, f"__pycache__/mod.cpython-312.{ext}")
    assert fx.verdict() == "would"


def test_only_compiled_extensions_in_pycache_are_regenerable(fx: Fixture) -> None:
    _commit_py(fx, "mod.py")
    _ignored(fx, "__pycache__/mod.txt")
    fx.keeps(KEEP_UNPROVEN)


def test_a_compiled_file_outside_a_pycache_directory_is_not_regenerable(fx: Fixture) -> None:
    _commit_py(fx, "libmod.py")  # what a sloppy "<dir minus __pycache__>/<module>.py" would find for lib/mod.pyc
    _ignored(fx, "lib/mod.pyc")
    fx.keeps(KEEP_UNPROVEN)


def test_a_dangling_source_symlink_does_not_vouch_for_the_compiled_file(fx: Fixture) -> None:
    (fx.wt / "mod.py").symlink_to("missing-target.py")
    fx.commit("mod.py")
    _ignored(fx, "__pycache__/mod.cpython-312.pyc")
    fx.keeps(KEEP_UNPROVEN)


def test_case6_a_submodule_directory_scan_that_cannot_be_read_back_keeps_and_faults(fx: Fixture) -> None:
    _with_submodule(fx, init=False)
    env = _list_files_vanish_after(fx, "find", "-mindepth 1 -maxdepth 1")
    fx.keeps("could not read back the scan of the submodule directory", env=env)
    assert fx.last_rc == 1 and FAULT_LINE in fx.last_out and fx.wt.exists()


def _orphan_commit(fx: Fixture) -> str:
    """A commit no ref reaches and no log has seen yet."""
    base = _git(fx.repo, "rev-parse", "HEAD")
    blob = _git_in(fx.repo, "hash-object", "-w", "--stdin", text="ONLY COPY OF UNPUSHED FILE\n")
    tree = _git_in(fx.repo, "mktree", text=f"100644 blob {blob}\tunique.txt\n")
    return _git_in(fx.repo, "commit-tree", tree, "-p", base, text="unpushed work\n")


def test_case2_a_commit_only_orig_head_names_keeps_the_worktree(fx: Fixture) -> None:
    orphan = _orphan_commit(fx)
    _git(fx.wt, "update-ref", "ORIG_HEAD", orphan)
    assert (_admin_dir(fx) / "ORIG_HEAD").read_text().strip() == orphan
    fx.keeps(KEEP_REFLOG)


@pytest.mark.parametrize("position", ["old", "new"])
def test_case2_a_commit_named_in_either_column_of_a_reflog_line_keeps_the_worktree(fx: Fixture, position: str) -> None:
    orphan = _orphan_commit(fx)
    head = _git(fx.wt, "rev-parse", "HEAD")
    old, new = (orphan, head) if position == "old" else (head, orphan)
    with (_admin_dir(fx) / "logs" / "HEAD").open("a") as log:
        log.write(f"{old} {new} t <t@example.com> 1700000000 +0000\treset: moving\n")
    fx.keeps(KEEP_REFLOG)


def test_case2_a_reftable_repository_keeps_because_its_reflogs_cannot_be_read(fx: Fixture) -> None:
    (fx.repo / ".git" / "reftable").mkdir()
    fx.keeps("a reftable repository")


def test_case3_control_a_leftover_auto_merge_pseudoref_does_not_keep(fx: Fixture) -> None:
    """git 2.56 removes AUTO_MERGE when a merge ends, but a git that leaves it behind holds only a tree id of the
    merge it tried: nothing a user wrote. It is on the allowlist, so it alone must not keep a clean worktree."""
    (_admin_dir(fx) / "AUTO_MERGE").write_text(_git(fx.wt, "rev-parse", "HEAD^{tree}") + "\n")
    assert _git(fx.wt, "status", "--porcelain") == ""
    assert fx.verdict() == "would"


def test_a_failed_move_back_after_a_rescan_hit_says_where_the_tree_stays_and_faults(fx: Fixture) -> None:
    mark = fx.root.parent / "move-mark"
    fx.shim(
        "git",
        'case "$*" in *"worktree move"*) ;; *) exec "' + _real("git") + '" "$@" ;; esac\n'
        'if [ ! -e "' + str(mark) + '" ]; then\n'
        '  : >"' + str(mark) + '"; "' + _real("git") + '" "$@" || exit $?\n'
        '  for a in "$@"; do last="$a"; done\n'
        '  printf "ONLY_COPY=1\\n" >"$last/.env.local"; exit 0\n'
        "fi\n"
        'echo "fatal: injected failure" >&2; exit 128',
    )
    out = fx.run(dry=False)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("FAILED") and "it stays at" in line, out
    assert fx.last_rc == 1 and FAULT_LINE in out
    (entry,) = fx.held()
    assert (entry / ".env.local").read_text() == "ONLY_COPY=1\n"
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_a_dangling_symlink_at_the_quarantine_name_is_not_overwritten_and_the_name_gets_a_suffix(fx: Fixture) -> None:
    day = fx.qbase / datetime.date.today().isoformat()
    day.mkdir(parents=True)
    taken = day / f"{fx.repo.name}--{fx.wt.name}"
    taken.symlink_to(fx.root.parent / "nowhere")
    out = fx.run(dry=False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    assert taken.is_symlink() and (day / f"{taken.name}-2").is_dir()


def test_a_dry_run_purge_runs_the_whole_guard_before_it_says_would_purge(fx: Fixture) -> None:
    fx.run(dry=False)
    (entry,) = fx.held()
    aged = _entry_on(fx, entry, "2000-01-01")
    (aged / ".env.example").write_text("EDITED\n")
    out = fx.run(dry=True)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("keep") and "worktree dirty" in line, out
    assert "would   purge" not in out


def test_a_refused_rename_aside_at_the_purge_fails_keeps_the_entry_and_faults(fx: Fixture) -> None:
    fx.run(dry=False)
    fx.shim(
        "git",
        'case "$*" in *"worktree move"*.purge) echo "fatal: injected failure" >&2; exit 128 ;; esac\n'
        'exec "' + _real("git") + '" "$@"',
    )
    out, aged = fx.purge_run(fx.wt)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("FAILED") and "could not move" in line, out
    assert fx.last_rc == 1 and FAULT_LINE in out and aged.exists()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_an_uncomputable_cutoff_date_purges_nothing_and_faults(fx: Fixture) -> None:
    fx.shim(
        "date",
        'case "$*" in *-v-*|*"days ago"*) exit 1 ;; esac\nexec "' + _real("date") + '" "$@"',
    )
    out = fx.run(dry=False)
    assert "cannot compute the quarantine cutoff date" in out and fx.last_rc == 1
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    (entry,) = fx.held()
    aged = _entry_on(fx, entry, "2000-01-01")
    out = fx.run(dry=False)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("keep") and "no cutoff date" in line, out
    assert aged.exists() and fx.last_rc == 1
