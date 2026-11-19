"""Round 10 of scripts/prune-merged-worktrees.sh: what two independent reviews of the round-9 head ef1e812 reproduced
(1 P0, 3 P1, four P2s), pinned as permanent tests.

Each test is the reviewer's repro adapted to this repo's Fixture, and each failed against ef1e812 before the fix (the
failures are recorded in plans/2026-11-16-prune-env-guard-fail-open.md, "Round 10").

Every test runs the real script under /bin/bash against a real git repo with a stub `gh`.
"""

from __future__ import annotations

import base64
import hashlib
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.test_prune_env_guard import (
    IS_ROOT,
    KEEP_UNPROVEN,
    SCRIPT,
    Fixture,
    _git,
    _ignored,
    _proven,
    _real,
    fx,  # noqa: F401  (the pytest fixture)
)
from tests.test_prune_round9_cases import (
    KEEP_HELD,
    _database,
    _line,
    _make_venv,
    _npm_tree,
    _site_packages,
    _to_the_end,
    _where,
)

KEEP_STAGED = "the index holds staged changes"


def _digest(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")


def _entry(rel: str, data: bytes) -> str:
    """A RECORD line the way pip writes it: path,sha256=<urlsafe base64, no padding>,size."""
    return f"{rel},{_digest(data)},{len(data)}"


def _venv_record(fx: Fixture, *lines: str) -> tuple[Path, Path]:
    """A real venv whose one installed package lists `lines` (plus its own RECORD, as pip does)."""
    venv = _make_venv(fx)
    dist = _site_packages(venv) / "foo-1.0.dist-info"
    dist.mkdir()
    (dist / "RECORD").write_text("".join(f"{ln}\n" for ln in ("foo-1.0.dist-info/RECORD,,", *lines)))
    return venv, dist


def _installed(site: Path, rel: str, data: bytes) -> str:
    """Write an installed file and return its genuine RECORD line."""
    target = site / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return _entry(rel, data)


# --- P0 (a): a RECORD hash and size are checked against the file on disk ------------------------------------------


def test_p0_a_record_with_a_real_hash_that_the_file_no_longer_matches_keeps_the_edited_module(fx: Fixture) -> None:
    """The reviewer's repro B: RECORD carries the real sha256 of `X=1`, the file now holds an uncommitted local fix."""
    venv, _ = _venv_record(fx, _entry("pkg/module.py", b"X=1\n"))
    module = _site_packages(venv) / "pkg/module.py"
    module.parent.mkdir()
    module.write_text("UNCOMMITTED LOCAL FIX\n")
    out = _to_the_end(fx)
    assert module.exists(), out
    line = _line(fx, out)
    assert KEEP_UNPROVEN in line and "pkg/module.py" in line, out


def test_p0_a_record_whose_size_disagrees_keeps_even_when_the_hash_matches(fx: Fixture) -> None:
    venv, _ = _venv_record(fx, f"pkg/module.py,{_digest(b'X=1\n')},999")
    module = _site_packages(venv) / "pkg/module.py"
    module.parent.mkdir()
    module.write_bytes(b"X=1\n")
    out = _to_the_end(fx)
    assert module.exists(), out
    assert KEEP_UNPROVEN in _line(fx, out) and "pkg/module.py" in _line(fx, out), out


@pytest.mark.parametrize(
    "fields",
    [",", ",4", "sha256=,4", f"{_digest(b'X=1\n')},", "md5=abc,4", f"sha512={_digest(b'X=1\n')[7:]},4"],
    ids=["no-hash-no-size", "no-hash", "empty-hash", "no-size", "other-algorithm", "sha512-label"],
)
def test_p0_a_record_entry_without_a_usable_hash_and_size_proves_nothing(fx: Fixture, fields: str) -> None:
    venv, _ = _venv_record(fx, f"pkg/module.py,{fields}")
    module = _site_packages(venv) / "pkg/module.py"
    module.parent.mkdir()
    module.write_bytes(b"X=1\n")
    out = _to_the_end(fx)
    assert module.exists(), out
    assert KEEP_UNPROVEN in _line(fx, out) and "pkg/module.py" in _line(fx, out), out


@pytest.mark.skipif(IS_ROOT, reason="root can read a mode-0 file")
def test_p0_a_listed_file_that_cannot_be_read_keeps_the_tree(fx: Fixture) -> None:
    venv, _ = _venv_record(fx)
    site = _site_packages(venv)
    _, dist = venv, site / "foo-1.0.dist-info"
    line = _installed(site, "pkg/module.py", b"X=1\n")
    (dist / "RECORD").write_text(f"foo-1.0.dist-info/RECORD,,\n{line}\n")
    (site / "pkg/module.py").chmod(0)
    out = fx.run(False)
    assert fx.wt.exists() and fx.line(out, fx.wt).startswith("keep"), out
    assert "pkg/module.py" in out, out


def test_p0_a_listed_symlink_is_not_a_file_the_package_installed(fx: Fixture) -> None:
    venv, dist = _venv_record(fx)
    site = _site_packages(venv)
    (site / "pkg").mkdir()
    (site / "pkg/target.py").write_bytes(b"X=1\n")
    (site / "pkg/link.py").symlink_to("target.py")
    (dist / "RECORD").write_text(
        "foo-1.0.dist-info/RECORD,,\n" + _entry("pkg/target.py", b"X=1\n") + "\n" + _entry("pkg/link.py", b"X=1\n") + "\n"
    )
    out = fx.run(True)
    assert KEEP_UNPROVEN in _line(fx, out) and "pkg/link.py" in _line(fx, out), out


def test_p0_a_record_whose_every_entry_matches_still_lets_the_tree_go(fx: Fixture) -> None:
    """The control: genuine hashes and sizes prove the files, so the tree is quarantined and then removed."""
    venv, dist = _venv_record(fx)
    site = _site_packages(venv)
    lines = [_installed(site, "pkg/__init__.py", b"X = 1\n"), _installed(site, "pkg/data.txt", b"a,b\n")]
    (dist / "RECORD").write_text("foo-1.0.dist-info/RECORD,,\n" + "\n".join(lines) + "\n")
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()


# --- P0 (b): npm records no per-file proof, so a node_modules tree proves nothing --------------------------------


def test_p0_b_a_database_inside_a_listed_npm_package_keeps(fx: Fixture) -> None:
    """The reviewer's repro A: `.package-lock.json` lists `pkg`, and the only copy of the data sits inside it."""
    nm = _npm_tree(fx, ["pkg"])
    _database(nm / "pkg/customers.sqlite")
    out = _to_the_end(fx)
    assert (_where(fx) or fx.wt).exists()
    tree = _where(fx)
    assert tree is not None and (tree / "node_modules/pkg/customers.sqlite").exists(), out
    assert KEEP_UNPROVEN in _line(fx, out), out


def test_p0_b_a_hand_patched_npm_dependency_keeps(fx: Fixture) -> None:
    nm = _npm_tree(fx, ["foo"])
    (nm / "foo/index.js").write_text("// my local debug edit\n")
    out = _to_the_end(fx)
    assert (nm / "foo/index.js").exists() or (_where(fx) and (_where(fx) / "node_modules/foo/index.js").exists()), out
    assert KEEP_UNPROVEN in _line(fx, out), out


def test_p0_b_an_untouched_npm_tree_is_kept_whole_because_nothing_proves_a_file_of_it(fx: Fixture) -> None:
    """The honest consequence: a lockfile lists packages, not file hashes, so npm reclaim is a no-op."""
    _npm_tree(fx, ["left-pad", "@scope/name"])
    out = fx.run(True)
    assert fx.line(out, fx.wt).startswith("keep") and KEEP_UNPROVEN in fx.line(out, fx.wt), out


# --- P0 (c): a CACHEDIR.TAG proves the tool that wrote it, not the files a person put beside its cache ------------

CACHEDIR_TAG = "Signature: 8a477f597d28d172789f06886806bc55\n# This file is a cache directory tag.\n"


def test_p0_c_a_dataset_in_a_directory_somebody_tagged_as_a_cache_keeps(fx: Fixture) -> None:
    fx.exclude("data/")
    (fx.wt / "data").mkdir()
    (fx.wt / "data/CACHEDIR.TAG").write_text(CACHEDIR_TAG)
    (fx.wt / "data/hand_labelled.csv").write_text("1,2,3\n")
    out = _to_the_end(fx)
    tree = _where(fx)
    assert tree is not None and (tree / "data/hand_labelled.csv").exists(), out
    assert KEEP_UNPROVEN in _line(fx, out), out


@pytest.mark.parametrize("tool_cache", [".pytest_cache/v/cache/nodeids", ".mypy_cache/3.12/x.json", "target/debug/x"])
def test_p0_c_a_tool_cache_with_the_standard_tag_is_kept_because_no_file_of_it_is_proven(fx: Fixture, tool_cache: str) -> None:
    top = tool_cache.split("/")[0]
    fx.exclude(f"{top}/")
    (fx.wt / top).mkdir()
    (fx.wt / top / "CACHEDIR.TAG").write_text(CACHEDIR_TAG)
    target = fx.wt / tool_cache
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n")
    out = fx.run(True)
    assert KEEP_UNPROVEN in fx.line(out, fx.wt), out


# --- P1: staged-only work hides behind a restored working copy ------------------------------------------------------


def test_p1_staged_content_with_the_working_copy_restored_to_head_keeps_the_tree(fx: Fixture) -> None:
    """The reviewer's repro: git status says `MM`, a status against a fresh index says clean."""
    (fx.wt / "tracked.txt").write_text("original\n")
    fx.commit("tracked.txt")
    (fx.wt / "tracked.txt").write_text("ONLY STAGED COPY\n")
    _git(fx.wt, "add", "tracked.txt")
    (fx.wt / "tracked.txt").write_text("original\n")
    assert _git(fx.wt, "status", "--porcelain") == "MM tracked.txt"
    fx.keeps(KEEP_STAGED)
    assert _git(fx.wt, "show", ":tracked.txt") == "ONLY STAGED COPY"


def test_p1_a_failing_index_comparison_keeps_the_tree_and_faults(fx: Fixture) -> None:
    fx.git_fails("diff-index --cached --quiet HEAD")
    out = fx.run(False, expect_fault=True)
    assert fx.wt.exists() and fx.line(out, fx.wt).startswith("keep"), out
    assert "could not compare the index" in out, out


# --- P1: the first move never asked whether a process is using the tree --------------------------------------------


def test_p1_a_process_with_its_cwd_in_a_clean_merged_worktree_keeps_it_in_place(fx: Fixture) -> None:
    """The reviewer's repro: the first, default-enabled move renamed the tree out from under a live shell."""
    sleeper = subprocess.Popen(["/bin/sleep", "30"], cwd=fx.wt)
    try:
        time.sleep(0.2)
        out = fx.run(False)
        line = fx.line(out, fx.wt)
        assert line is not None and line.startswith("keep") and KEEP_HELD in line, out
        assert fx.wt.exists() and fx.held() == [], out
        assert sleeper.poll() is None
    finally:
        sleeper.kill()
        sleeper.wait()


def test_p1_a_holder_check_that_cannot_run_keeps_the_tree_and_faults(fx: Fixture) -> None:
    fx.shim("lsof", 'echo "lsof: injected failure" >&2\nexit 3')
    out = fx.run(False, expect_fault=True)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("keep") and "could not list open files" in line, out
    assert fx.wt.exists() and fx.held() == [], out


# --- P1: a branch checked out in another worktree is not deleted ---------------------------------------------------


def _second_worktree_on_the_branch(fx: Fixture) -> Path:
    other = fx.wt.parent / "wt2"
    _git(fx.repo, "worktree", "add", "--force", "-q", str(other), "feat/x")
    (other / "UNSAVED.txt").write_text("work in progress\n")  # untracked: this one is never a candidate
    return other


def test_p1_the_branch_survives_while_another_worktree_has_it_checked_out(fx: Fixture) -> None:
    """The reviewer's repro: `update-ref -d` has no check `git branch -D` has, and left wt2 on an unborn branch."""
    other = _second_worktree_on_the_branch(fx)
    out = fx.run(False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    out, aged = fx.purge_run(fx.wt)
    assert (fx.line(out, aged) or "").startswith("removed"), out
    assert "feat/x" in _git(fx.repo, "branch", "--list", "feat/x")
    assert "checked out" in out and str(other) in out, out
    assert _git(other, "symbolic-ref", "HEAD") == "refs/heads/feat/x"
    assert _git(other, "rev-parse", "--verify", "HEAD")  # not an unborn branch
    assert (other / "UNSAVED.txt").exists()


def test_p1_the_branch_goes_once_no_worktree_has_it_checked_out(fx: Fixture) -> None:
    """The control: with nobody else on the branch, the purge still deletes it."""
    out = fx.run(False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    fx.purge_run(fx.wt)
    assert _git(fx.repo, "branch", "--list", "feat/x") == ""


def test_p1_a_worktree_list_that_fails_at_delete_time_keeps_the_branch_and_faults(fx: Fixture) -> None:
    """The second `git worktree list` (the one delete_branch makes) fails; the first (the sweep's own) is real."""
    counter = fx.bindir / "list-count"
    fx.shim(
        "git",
        'case " $* " in *" worktree list "*)\n'
        f'  n=$(cat "{counter}" 2>/dev/null || echo 0); n=$((n + 1)); echo $n >"{counter}"\n'
        '  if [ "$n" -ge 2 ]; then echo "fatal: injected failure" >&2; exit 128; fi ;;\n'
        f'esac\nexec "{_real("git")}" "$@"',
    )
    out = fx.run(False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    counter.unlink(missing_ok=True)
    # purge: list #1 is the sweep, list #2 is delete_branch's
    entry = fx.held()
    assert entry
    aged = fx.age(entry[0])
    out = fx.run(False, expect_fault=True)
    assert (fx.line(out, aged) or "").startswith("removed"), out
    assert _git(fx.repo, "branch", "--list", "feat/x") != "", out


# --- P2: path framing (newline and TAB) ---------------------------------------------------------------------------


def _worktree(fx: Fixture, rel: str, branch: str) -> Path:
    path = fx.root / rel
    _git(fx.repo, "worktree", "add", "-q", "-b", branch, str(path))
    return path


def test_p2_a_newline_in_a_worktree_path_cannot_forge_another_worktrees_branch(fx: Fixture) -> None:
    """The reviewer's repro: the path `victim<NL>branch refs/heads/feat/x` made `victim` look like feat/x's worktree."""
    victim = _worktree(fx, "victim", "bv")  # an unmerged branch, clean, at the merged commit
    forger = _worktree(fx, f"victim\nbranch refs/heads/{'feat/x'}", "nlb")
    assert forger.exists()
    out = fx.run(False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    assert fx.line(out, victim) is None, out
    assert victim.exists() and (victim / ".git").exists()


def test_p2_a_newline_path_is_handled_as_the_worktree_it_is(fx: Fixture) -> None:
    other = _worktree(fx, "a\nb", "feat/nl")
    fx.merged.append(f"feat/nl {_git(other, 'rev-parse', 'HEAD')}")
    out = fx.run(False)
    assert f"quarantined {other}" in out, out
    assert not other.exists() and len(fx.held()) == 2


@pytest.mark.parametrize("dirty", [True, False], ids=["dirty-keeps", "clean-is-quarantined"])
def test_p2_a_tab_in_a_worktree_path_is_reported_not_silently_dropped(fx: Fixture, dirty: bool) -> None:
    other = _worktree(fx, "w\ttab", "feat/tab")
    fx.merged.append(f"feat/tab {_git(other, 'rev-parse', 'HEAD')}")
    if dirty:
        (other / "scratch.txt").write_text("x\n")
    out = fx.run(False)
    expected = "keep" if dirty else "quarantined"
    assert (fx.line(out, other) or "").startswith(expected), out


# --- P2: the quarantine stamp is frozen so two runs share a directory deterministically -------------------------


def test_p2_two_quarantines_of_one_name_collide_deterministically_when_the_clock_ticks_between_runs(fx: Fixture) -> None:
    """Frozen to one instant: the second quarantine of `wt` must take the `-2` name inside the same stamp directory."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")  # inside the hold window, so the first copy stays
    fx.shim(
        "date",
        f'case "$*" in "-u +%Y-%m-%dT%H%M%SZ") echo {stamp}; exit 0 ;; esac\n'
        f'exec "{_real("date")}" "$@"',
    )
    fx.run(dry=False)
    (first,) = fx.held()
    other = fx.wt.parent / fx.wt.name  # the same directory name, a new branch
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/y", str(other))
    fx.merged.append(f"feat/y {_git(other, 'rev-parse', 'HEAD')}")
    out = fx.run(dry=False)
    assert (fx.line(out, other) or "").startswith("quarantined"), out
    assert first.parent.name == stamp
    assert sorted(p.name for p in fx.held()) == [first.name, f"{first.name}-2"]


# --- P2: a relative PROJECTS_ROOT -------------------------------------------------------------------------------


def test_p2_a_relative_projects_root_is_refused_once_at_startup(fx: Fixture) -> None:
    env = {**os.environ, "PATH": f"{fx.bindir}{os.pathsep}{os.environ['PATH']}", "PROJECTS_ROOT": "pro jects", "DRY_RUN": "0"}
    proc = subprocess.run(["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=env, cwd=fx.root.parent)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "PROJECTS_ROOT must be an absolute path" in proc.stdout, proc.stdout
    assert "keep" not in proc.stdout and fx.wt.exists()
    assert shutil.which("git") and sys.executable  # the run needed nothing else


# --- found by the round-10 mutation run: a venv's claim must stay inside that venv's own directory -------------------


@pytest.mark.parametrize(("venv", "other"), [("aaa", "bbb"), ("v*", "vx")], ids=["same-length-name", "glob-characters"])
def test_a_venv_scaffold_name_in_a_different_directory_is_not_proven_by_a_neighbouring_venv(
    fx: Fixture, venv: str, other: str
) -> None:
    """`<other>/bin/activate` is a scaffold name only inside a venv. The neighbouring proven venv `<venv>/` sorts first
    and must not vouch for it, neither by an unanchored prefix test nor by an unquoted glob in it."""
    _proven(fx, "pkg/module.py", top=venv)
    _ignored(fx, f"{other}/bin/activate", "only copy of this\n")
    fx.keeps(KEEP_UNPROVEN)
    assert (fx.wt / other / "bin" / "activate").read_text() == "only copy of this\n"
