"""scripts/prune-merged-worktrees.sh against real git repos: which worktrees go,
which stay, and when node_modules is stripped. `gh` is the only fake (third party).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prune-merged-worktrees.sh"
OLD = time.time() - 10 * 86400  # 10 days ago: past both the remove and the strip thresholds


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def age(worktree: Path) -> None:
    """Make git's view of the worktree 10 days old (what idle_hours reads)."""
    gd = Path(git(worktree, "rev-parse", "--absolute-git-dir"))
    for f in (gd / "index", gd / "HEAD", gd / "logs" / "HEAD"):
        if f.exists():
            os.utime(f, (OLD, OLD))


@pytest.fixture
def env(tmp_path: Path):
    root = tmp_path / "projects"
    remote = tmp_path / "remote.git"
    repo = root / "app"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / ".gitignore").write_text("node_modules/\n.env\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(
        '#!/bin/bash\ncase "$*" in *"--state merged"*) cat "$FAKE_GH_MERGED";; *"--state open"*) cat "$FAKE_GH_OPEN";; esac\n'
    )
    (bindir / "gh").chmod(0o755)
    merged, open_ = tmp_path / "merged.txt", tmp_path / "open.txt"
    merged.write_text("")
    open_.write_text("")
    run_env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "PROJECTS_ROOT": str(root),
        "FAKE_GH_MERGED": str(merged),
        "FAKE_GH_OPEN": str(open_),
        "LOW_DISK_GB": "0",  # never take the low-disk path (it would run cleanup and notify)
    }
    return {"repo": repo, "merged": merged, "open": open_, "env": run_env}


def add_worktree(repo: Path, name: str, *, push: bool, commit: bool = True, detach: bool = False) -> Path:
    wt = repo / ".worktrees" / name
    git(repo, "worktree", "add", "-q", *(["--detach"] if detach else ["-b", name]), str(wt), "main")
    if commit:
        (wt / f"{name}.txt").write_text(name)
        git(wt, "add", ".")
        git(wt, "commit", "-qm", name)
    if push:
        git(wt, "push", "-q", "origin", f"HEAD:refs/heads/{name}")
        git(repo, "fetch", "-q", "origin")
    (wt / "node_modules" / "pkg").mkdir(parents=True)
    (wt / "node_modules" / "pkg" / "index.js").write_text("x")
    return wt


def run(env: dict, **extra: str) -> str:
    r = subprocess.run(["bash", str(SCRIPT)], env={**env["env"], **extra}, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_pushed_idle_clean_worktree_is_removed_with_its_branch(env):
    wt = add_worktree(env["repo"], "review-x", push=True)
    age(wt)
    out = run(env)
    assert not wt.exists(), out
    assert "review-x" not in git(env["repo"], "branch", "--list", "review-x")


def test_pushed_detached_worktree_is_removed(env):
    wt = add_worktree(env["repo"], "det", push=True, detach=True)
    age(wt)
    run(env)
    assert not wt.exists()


def test_recently_touched_pushed_worktree_is_kept(env):
    wt = add_worktree(env["repo"], "fresh", push=True)
    out = run(env)
    assert wt.exists() and (wt / "node_modules").exists(), out


def test_unpushed_commits_keep_the_worktree_but_strip_node_modules(env):
    wt = add_worktree(env["repo"], "local", push=False)
    age(wt)
    out = run(env)
    assert wt.exists(), out
    assert not (wt / "node_modules").exists()
    assert "stripped" in out


def test_open_pr_branch_is_kept_and_stripped(env):
    wt = add_worktree(env["repo"], "feat-open", push=True)
    env["open"].write_text(f"feat-open {git(wt, 'rev-parse', 'HEAD')}\n")
    age(wt)
    run(env)
    assert wt.exists() and not (wt / "node_modules").exists()


def test_dirty_worktree_is_kept(env):
    wt = add_worktree(env["repo"], "dirty", push=True)
    (wt / "dirty.txt").write_text("edited")
    age(wt)
    run(env)
    assert (wt / "dirty.txt").read_text() == "edited"


def test_own_env_file_keeps_the_worktree(env):
    wt = add_worktree(env["repo"], "envy", push=True)
    (wt / ".env").write_text("SECRET=1\n")
    age(wt)
    out = run(env)
    assert wt.exists() and "holds ignored .env" in out


def test_merged_exact_head_is_removed_even_when_recent(env):
    wt = add_worktree(env["repo"], "done", push=True)
    env["merged"].write_text(f"done {git(wt, 'rev-parse', 'HEAD')}\n")
    run(env)
    assert not wt.exists()


def test_worktree_with_a_process_inside_is_left_alone(env):
    wt = add_worktree(env["repo"], "busy", push=True)
    age(wt)
    proc = subprocess.Popen(["sleep", "30"], cwd=wt)
    try:
        out = run(env)
    finally:
        proc.kill()
    assert wt.exists() and (wt / "node_modules").exists(), out
    assert "a process is running inside it" in out


def test_dry_run_changes_nothing(env):
    wt = add_worktree(env["repo"], "dry", push=True)
    age(wt)
    out = run(env, DRY_RUN="1")
    assert wt.exists() and (wt / "node_modules").exists()
    assert "would" in out


def test_status_check_does_not_reset_idleness(env):
    """git status would rewrite the index and make every worktree look fresh."""
    wt = add_worktree(env["repo"], "stale", push=False)
    age(wt)
    gd = Path(git(wt, "rev-parse", "--absolute-git-dir"))
    run(env, STRIP_IDLE_DAYS="99")
    assert (gd / "index").stat().st_mtime == pytest.approx(OLD, abs=2)


# Tools the script needs; a PATH holding only these simulates a machine without gh, lsof or osascript.
BASE_TOOLS = (
    "bash git awk sed sort df date stat du cut find rm wc id grep cmp dirname readlink tail cat ls"
).split()


def minimal_path(tmp: Path, *extra: str) -> str:
    import shutil

    d = tmp / "minbin"
    d.mkdir(exist_ok=True)
    for tool in (*BASE_TOOLS, *extra):
        src = shutil.which(tool)
        if src and not (d / tool).exists():
            (d / tool).symlink_to(src)
    return str(d)


def test_without_gh_nothing_is_removed_but_idle_node_modules_are_stripped(env, tmp_path):
    wt = add_worktree(env["repo"], "nogh", push=True)
    age(wt)
    out = run(env, PATH=minimal_path(tmp_path, "lsof"))
    assert wt.exists() and not (wt / "node_modules").exists(), out
    assert "gh not found" in out


@pytest.mark.skipif(Path("/proc/self").exists(), reason="/proc is the fallback when lsof is missing")
def test_without_lsof_or_proc_nothing_is_touched(env, tmp_path):
    wt = add_worktree(env["repo"], "blind", push=True)
    age(wt)
    out = run(env, PATH=f"{env['env']['PATH'].split(':')[0]}:{minimal_path(tmp_path)}")
    assert wt.exists() and (wt / "node_modules").exists(), out
    assert "cannot tell which worktrees are in use" in out


def test_low_disk_runs_cleanup_only_when_opted_in(env, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "prune-merged-worktrees.sh").write_text(SCRIPT.read_text())
    marker = tmp_path / "cleanup-ran"
    (scripts / "cleanup-hung-processes.sh").write_text(f"#!/bin/bash\n: > {marker}\n")
    (scripts / "cleanup-hung-processes.sh").chmod(0o755)
    path = f"{env['env']['PATH'].split(':')[0]}:{minimal_path(tmp_path, 'lsof')}"  # fake gh, no osascript
    for opt_in, expect in (("0", False), ("1", True)):
        r = subprocess.run(
            ["bash", str(scripts / "prune-merged-worktrees.sh")],
            env={**env["env"], "PATH": path, "LOW_DISK_GB": "999999999", "LOW_DISK_CLEANUP": opt_in},
            capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, r.stderr
        assert marker.exists() is expect, r.stdout
