"""The ignored-.env guard in scripts/prune-merged-worktrees.sh must fail closed.

Two shipped defects (see plans/2026-11-16-prune-env-guard-fail-open.md):

A. Fail-open. The guard was `ls-files | grep | while ... echo | grep -q .` under `pipefail`: `grep -q`
   exits on the first hit, the loop takes SIGPIPE on its next echo, the pipeline reports failure and the
   `if` read "no unique .env", so a worktree with two or more unique ignored .env files was removed.
   A failing `git ls-files` also read as "nothing to keep".
B. Symlink exemption. Every `.env*` symlink was exempt without looking at its target, so
   `.env -> only-copy` (an ignored file that exists only in the worktree) was deleted with the worktree.

These tests run the real script against a real git repo with a stub `gh`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prune-merged-worktrees.sh"
BRANCH = "feat/x"


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


class Fixture:
    def __init__(self, root: Path, repo: Path, wt: Path, sha: str, bindir: Path) -> None:
        self.root, self.repo, self.wt, self.sha, self.bindir = root, repo, wt, sha, bindir

    def run(self, dry: bool = True) -> str:
        env = {
            **os.environ,
            "PATH": f"{self.bindir}{os.pathsep}{os.environ['PATH']}",
            "PROJECTS_ROOT": str(self.root),
            "DRY_RUN": "1" if dry else "0",
            "GH_MERGED": f"{BRANCH} {self.sha}",
        }
        proc = subprocess.run(
            ["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=120
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return proc.stdout

    def verdict(self, dry: bool = True) -> str:
        """The first word printed for the worktree: keep | would | removed."""
        for line in self.run(dry).splitlines():
            if str(self.wt) in line:
                return line.split()[0]
        raise AssertionError("script printed nothing for the worktree")


@pytest.fixture
def fx(tmp_path: Path) -> Fixture:
    base = tmp_path.resolve()  # git prints realpaths; /var is a symlink to /private/var on macOS
    root = base / "projects"
    repo = root / "proj"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".env*\nonly-copy\n")
    (repo / ".env.example").write_text("EXAMPLE=1\n")
    # .env.example is tracked despite the ignore pattern
    _git(repo, "add", "-f", ".gitignore", ".env.example")
    _git(repo, "commit", "-q", "-m", "init")
    wt = base / "wt"
    _git(repo, "worktree", "add", "-q", "-b", BRANCH, str(wt))
    sha = _git(wt, "rev-parse", "HEAD")

    bindir = base / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text('#!/bin/bash\ncase "$*" in *"--state merged"*) echo "$GH_MERGED";; esac\nexit 0\n')
    gh.chmod(0o755)
    return Fixture(root, repo, wt, sha, bindir)


def _unique_envs(wt: Path, n: int) -> None:
    for i in range(n):
        (wt / f".env.unique{i}").write_text(f"SECRET={i}\n")


@pytest.mark.parametrize("n", [1, 2, 50])
def test_unique_ignored_envs_keep_the_worktree(fx: Fixture, n: int) -> None:
    # n >= 2 hit the SIGPIPE race: grep -q closed the pipe early and the guard read "nothing unique"
    _unique_envs(fx.wt, n)
    assert fx.verdict() == "keep"
    assert "holds ignored .env files" in fx.run()


def test_env_identical_to_primary_copy_is_removable(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("SAME=1\n")
    (fx.wt / ".env").write_text("SAME=1\n")
    assert fx.verdict() == "would"


def test_one_differing_env_among_identical_ones_keeps(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("SAME=1\n")
    (fx.wt / ".env").write_text("SAME=1\n")
    _unique_envs(fx.wt, 3)
    assert fx.verdict() == "keep"


def test_symlink_to_ignored_file_in_worktree_keeps_and_survives_a_real_run(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("PRECIOUS=1\n")
    (fx.wt / ".env").symlink_to("only-copy")
    assert fx.verdict() == "keep"
    assert fx.verdict(dry=False) == "keep"
    assert (fx.wt / "only-copy").read_text() == "PRECIOUS=1\n"


def test_symlink_to_tracked_file_in_worktree_is_removable(fx: Fixture) -> None:
    (fx.wt / ".env").symlink_to(".env.example")
    assert fx.verdict() == "would"


def test_symlink_to_target_outside_worktree_is_removable(fx: Fixture) -> None:
    outside = fx.repo / ".env"
    outside.write_text("PRIMARY=1\n")
    (fx.wt / ".env").symlink_to(outside)
    assert fx.verdict() == "would"


def test_dangling_symlink_is_removable(fx: Fixture) -> None:
    (fx.wt / ".env").symlink_to("does-not-exist")
    assert fx.verdict() == "would"


def test_git_ls_files_failure_keeps_the_worktree(fx: Fixture) -> None:
    real_git = shutil.which("git")
    assert real_git
    shim = fx.bindir / "git"
    shim.write_text(
        "#!/bin/bash\n"
        'for a in "$@"; do [ "$a" = ls-files ] && { echo "fatal: injected ls-files failure" >&2; exit 128; }; done\n'
        f'exec "{real_git}" "$@"\n'
    )
    shim.chmod(0o755)
    out = fx.run()
    line = next(ln for ln in out.splitlines() if str(fx.wt) in ln)
    assert line.startswith("keep"), out
    assert "ls-files" in line, line
