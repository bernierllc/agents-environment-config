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

    def run(self, dry: bool = True, path: str | None = None) -> str:
        env = {
            **os.environ,
            "PATH": path or f"{self.bindir}{os.pathsep}{os.environ['PATH']}",
            "PROJECTS_ROOT": str(self.root),
            "DRY_RUN": "1" if dry else "0",
            "GH_MERGED": f"{BRANCH} {self.sha}",
        }
        proc = subprocess.run(
            ["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=120
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return proc.stdout

    def verdict(self, dry: bool = True, path: str | None = None, wt: Path | None = None) -> str:
        """The first word printed for the worktree: keep | would | removed."""
        for line in self.run(dry, path).splitlines():
            if f"{wt or self.wt}  (" in line:
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


@pytest.mark.parametrize("n", [1, 2])
def test_unique_ignored_envs_keep_the_worktree(fx: Fixture, n: int) -> None:
    _unique_envs(fx.wt, n)
    assert fx.verdict() == "keep"
    assert "holds ignored .env files" in fx.run()


def test_many_unique_envs_keep_the_worktree_whatever_the_scheduling(fx: Fixture) -> None:
    """Defect A, deterministically. The old guard ended in `grep -q .` under pipefail. Its writer only takes
    SIGPIPE if it is still writing when grep exits, which a fast grep makes a matter of luck. Here the writer
    emits ~125 KB (more than any pipe buffer), so it must block on a full pipe and is guaranteed to be writing
    when `grep -q` exits on the first line; a grep that sleeps first (below) removes the race entirely."""
    for i in range(3000):
        (fx.wt / f".env.{i:05d}-{'x' * 30}").write_text("SECRET\n")
    real_grep = shutil.which("grep")
    assert real_grep
    slow = fx.bindir / "grep"
    slow.write_text(f'#!/bin/bash\nsleep 0.3\nexec "{real_grep}" "$@"\n')
    slow.chmod(0o755)
    assert fx.verdict() == "keep"


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


def test_dangling_symlink_is_kept(fx: Fixture) -> None:
    # a dangling link holds no data, but the guard keeps anything it cannot positively resolve
    (fx.wt / ".env").symlink_to("does-not-exist")
    assert fx.verdict() == "keep"


@pytest.mark.parametrize("name", [".envé", ".env\\local", ".env\nlocal"], ids=["unicode", "backslash", "newline"])
def test_odd_env_file_names_keep(fx: Fixture, name: str) -> None:
    # without -z git quotes these names, the quoted form no longer matches .env and the tree was deleted
    (fx.wt / name).write_text("unique\n")
    assert fx.verdict() == "keep"


def test_symlink_to_a_directory_keeps(fx: Fixture) -> None:
    (fx.wt / "data").mkdir()
    (fx.wt / "data" / "tracked").write_text("tracked\n")
    _git(fx.wt, "add", "data/tracked")
    _git(fx.wt, "commit", "-q", "-m", "tracked data")
    fx.sha = _git(fx.wt, "rev-parse", "HEAD")
    (fx.wt / "data" / "only-copy").write_text("unique\n")  # ignored, so status stays clean
    (fx.wt / ".env").symlink_to("data")
    assert fx.verdict() == "keep"


def test_symlink_to_the_worktree_root_keeps(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to(".")
    assert fx.verdict() == "keep"


def test_primary_copy_that_is_a_symlink_into_the_worktree_keeps(fx: Fixture) -> None:
    # cmp would compare the worktree file with itself and call it identical
    (fx.wt / ".env").write_text("unique\n")
    (fx.repo / ".env").symlink_to(fx.wt / ".env")
    assert fx.verdict() == "keep"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_symlink_whose_target_cannot_be_read_keeps(fx: Fixture) -> None:
    ignore = fx.root.parent / "ignore"
    ignore.write_text("vault/\n")
    _git(fx.repo, "config", "core.excludesFile", str(ignore))
    vault = fx.wt / "vault"
    vault.mkdir()
    (vault / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to("vault/only-copy")
    vault.chmod(0)
    try:
        assert fx.verdict() == "keep"
    finally:
        vault.chmod(0o755)


def test_failing_resolver_output_is_not_taken_as_an_external_target(fx: Fixture) -> None:
    # the old guard ran realpath || readlink -f and took whatever they printed, even with a failing status
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to("only-copy")
    for tool in ("realpath", "readlink"):
        stub = fx.bindir / tool
        stub.write_text('#!/bin/bash\nprintf "unresolved\\n"\nexit 1\n')
        stub.chmod(0o755)
    assert fx.verdict() == "keep"


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_symlink_to_tracked_file_with_hidden_local_edits_keeps(fx: Fixture, flag: str) -> None:
    # these index flags make `git status` and `git diff` report a modified tracked file as clean
    (fx.wt / ".env").symlink_to(".env.example")
    (fx.wt / ".env.example").write_text("LOCAL_ONLY_EDIT=1\n")
    _git(fx.wt, "update-index", flag, ".env.example")
    assert _git(fx.wt, "status", "--porcelain") == ""
    assert fx.verdict() == "keep"


def test_symlink_chain_to_an_external_target_is_removable(fx: Fixture) -> None:
    outside = fx.repo / ".env"
    outside.write_text("PRIMARY=1\n")
    (fx.wt / ".env.hop").symlink_to(outside)
    (fx.wt / ".env").symlink_to(".env.hop")
    assert fx.verdict() == "would"


def test_symlink_loop_keeps(fx: Fixture) -> None:
    (fx.wt / ".env").symlink_to(".env.b")
    (fx.wt / ".env.b").symlink_to(".env")
    assert fx.verdict() == "keep"


def _bare_path(fx: Fixture) -> str:
    """A PATH holding only the tools the script needs, with no realpath and a readlink that rejects -f
    (as on older macOS); every other call passes through to the real readlink."""
    bare = fx.bindir.parent / "bare"
    bare.mkdir()
    for tool in ("git", "awk", "wc", "du", "cut", "df", "tail", "date", "mktemp", "rm", "cmp", "cat", "sed", "dirname", "basename"):
        found = shutil.which(tool)
        if found:
            (bare / tool).symlink_to(found)
    (bare / "gh").symlink_to(fx.bindir / "gh")
    real_readlink = shutil.which("readlink")
    assert real_readlink
    stub = bare / "readlink"
    stub.write_text(
        '#!/bin/bash\nfor a in "$@"; do [ "$a" = -f ] && { echo "readlink: illegal option -- f" >&2; exit 1; }; done\n'
        f'exec "{real_readlink}" "$@"\n'
    )
    stub.chmod(0o755)
    assert shutil.which("realpath", path=str(bare)) is None
    return str(bare)


def test_symlinks_resolve_without_realpath_or_readlink_f(fx: Fixture) -> None:
    path = _bare_path(fx)
    outside = fx.repo / ".env"
    outside.write_text("PRIMARY=1\n")
    (fx.wt / ".env").symlink_to(outside)
    assert fx.verdict(path=path) == "would"  # an external target is still exempt
    (fx.wt / ".env").unlink()
    (fx.wt / ".env").symlink_to(".env.example")
    assert fx.verdict(path=path) == "would"  # a clean tracked target in the worktree too
    (fx.wt / ".env").unlink()
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to("only-copy")
    assert fx.verdict(path=path) == "keep"  # an ignored target in the worktree still keeps


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


# Round 2: "outside this worktree" and "a copy exists" must be proven by filesystem identity and by the data
# surviving the whole sweep, never by comparing path text or looking at one inode.


def _second_worktree(fx: Fixture, at: Path) -> Path:
    """A second merged linked worktree of the same repo, so the sweep may remove both."""
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/y", str(at))
    gh = fx.bindir / "gh"
    gh.write_text(
        '#!/bin/bash\ncase "$*" in *"--state merged"*) echo "$GH_MERGED"; '
        f'echo "feat/y {fx.sha}";; esac\nexit 0\n'
    )
    return at


def test_symlink_target_through_a_case_alias_of_the_worktree_keeps(fx: Fixture) -> None:
    alias = fx.wt.parent / "WT"
    if not alias.exists():
        pytest.skip("case-sensitive filesystem: /WT does not alias /wt")
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to(alias / "only-copy")
    assert fx.verdict() == "keep"


def test_symlink_target_through_a_firmlink_alias_of_the_worktree_keeps(fx: Fixture) -> None:
    # /System/Volumes/Data/<path> and <path> are one directory with two spellings, on any macOS volume layout
    alias = Path("/System/Volumes/Data") / str(fx.wt).lstrip("/")
    if not alias.exists():
        pytest.skip("no firmlink alias on this platform")
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to(alias / "only-copy")
    assert fx.verdict() == "keep"


def test_symlink_into_another_removable_worktree_keeps_both(fx: Fixture) -> None:
    other = _second_worktree(fx, fx.wt.parent / "other")
    (fx.wt / "only-copy").write_text("one\n")
    (other / "only-copy").write_text("two\n")
    (fx.wt / ".env").symlink_to(other / "only-copy")
    (other / ".env").symlink_to(fx.wt / "only-copy")
    assert fx.verdict() == "keep"
    assert fx.verdict(wt=other) == "keep"


def test_other_worktree_registered_through_a_symlinked_path_still_keeps(fx: Fixture) -> None:
    # git records the worktree under the spelling it was given; the target resolves to a different spelling
    real = fx.wt.parent / "real"
    real.mkdir()
    (fx.wt.parent / "link").symlink_to(real, target_is_directory=True)
    other = _second_worktree(fx, fx.wt.parent / "link" / "other")
    (other / "only-copy").write_text("two\n")
    (fx.wt / ".env").symlink_to(other / "only-copy")
    assert fx.verdict() == "keep"


@pytest.mark.parametrize("name", [".ENV", ".Env.local", "conf/.eNv"], ids=["upper", "mixed", "nested"])
def test_env_names_match_in_any_case(fx: Fixture, name: str) -> None:
    (fx.wt / name).parent.mkdir(exist_ok=True)
    (fx.wt / name).write_text("unique\n")
    assert fx.verdict() == "keep"


def test_primary_copies_reached_through_parent_symlinks_keep(fx: Fixture) -> None:
    # primary a -> wt/b and b -> wt/a: each "primary copy" resolves back into the worktree being removed
    for d in ("a", "b"):
        (fx.wt / d).mkdir()
        (fx.wt / d / ".env").write_text("unique\n")  # equal bytes, so only the resolved location can tell
    (fx.repo / "a").symlink_to(fx.wt / "b", target_is_directory=True)
    (fx.repo / "b").symlink_to(fx.wt / "a", target_is_directory=True)
    assert fx.verdict() == "keep"


def test_primary_copy_reached_through_a_parent_symlink_to_a_safe_place_is_removable(fx: Fixture) -> None:
    safe = fx.wt.parent / "elsewhere"
    safe.mkdir()
    (safe / ".env").write_text("SAME=1\n")
    (fx.repo / "conf").symlink_to(safe, target_is_directory=True)
    (fx.wt / "conf").mkdir()
    (fx.wt / "conf" / ".env").write_text("SAME=1\n")
    assert fx.verdict() == "would"


def test_symlink_target_in_an_unrelated_directory_outside_the_projects_root_is_removable(fx: Fixture) -> None:
    unrelated = fx.wt.parent / "unrelated"
    unrelated.mkdir()
    (unrelated / "data").write_text("shared\n")
    (fx.wt / ".env").symlink_to(unrelated / "data")
    assert fx.verdict() == "would"


def test_symlink_target_in_the_primary_checkout_outside_every_worktree_is_removable(fx: Fixture) -> None:
    (fx.repo / "conf").mkdir()
    (fx.repo / "conf" / "shared").write_text("shared\n")
    (fx.wt / ".env").symlink_to(fx.repo / "conf" / "shared")
    assert fx.verdict() == "would"


def test_symlink_target_in_another_repo_under_the_projects_root_keeps(fx: Fixture) -> None:
    # the sweep walks the whole projects root and may remove that repo's worktrees too
    sibling = fx.root / "sibling"
    sibling.mkdir()
    (sibling / "data").write_text("shared\n")
    (fx.wt / ".env").symlink_to(sibling / "data")
    assert fx.verdict() == "keep"


def test_ignored_nested_repo_holding_an_env_file_keeps(fx: Fixture) -> None:
    # git lists an ignored nested repo as one `vendor/lib/` entry and never enumerates its files
    (fx.repo / ".git" / "info" / "exclude").write_text("vendor/\n")
    nested = fx.wt / "vendor" / "lib"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    (nested / ".env").write_text("unique\n")
    assert _git(fx.wt, "status", "--porcelain") == ""
    assert fx.verdict() == "keep"


def test_ignored_nested_repo_without_env_files_is_removable(fx: Fixture) -> None:
    (fx.repo / ".git" / "info" / "exclude").write_text("vendor/\n")
    nested = fx.wt / "vendor" / "lib"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    (nested / "readme").write_text("nothing secret\n")
    assert fx.verdict() == "would"
