"""scripts/prune-merged-worktrees.sh must never delete ignored `.env*` data, and must fail closed.

The rule (see plans/2026-11-16-prune-env-guard-fail-open.md): a merged, clean worktree is kept if it holds ANY
untracked or ignored `.env*` path (any case, any path component, anything inside a nested repo) or ANY `.env*`
symlink. The one exemption is a regular file byte-identical to the same path in the primary checkout. Anything
the script cannot scan, parse or list also keeps the worktree, with a printed reason.

Every test runs the real script under /bin/bash against a real git repo with a stub `gh`. Each refusal branch
has its own test, and the controls at the top prove a worktree with nothing to protect is really removed (a
script that never removes anything must not pass).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prune-merged-worktrees.sh"
BRANCH = "feat/x"
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
KEEP_ENV = "holds ignored .env files"
GH_STUB = """#!/bin/bash
state=""
case "$*" in *"--state merged"*) state=merged ;; *"--state open"*) state=open ;; esac
[ -n "$state" ] && [ "$state" = "$GH_FAIL" ] && { echo "gh: injected failure" >&2; exit 1; }
[ "$state" = merged ] && printf '%s\\n' "$GH_MERGED"
[ "$state" = open ] && printf '%s\\n' "$GH_OPEN"
exit 0
"""


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


def _real(tool: str) -> str:
    found = shutil.which(tool)
    assert found
    return found


class Fixture:
    def __init__(self, root: Path, repo: Path, wt: Path, sha: str, bindir: Path) -> None:
        self.root, self.repo, self.wt, self.bindir = root, repo, wt, bindir
        self.merged = [f"{BRANCH} {sha}"]
        self.open: list[str] = []
        self.gh_fail = ""

    # --- running the script -------------------------------------------------------------------------------
    def run(self, dry: bool = True, env: dict[str, str] | None = None, timeout: int = 60) -> str:
        full = {
            **os.environ,
            "PATH": f"{self.bindir}{os.pathsep}{os.environ['PATH']}",
            "PROJECTS_ROOT": str(self.root),
            "DRY_RUN": "1" if dry else "0",
            "GH_MERGED": "\n".join(self.merged),
            "GH_OPEN": "\n".join(self.open),
            "GH_FAIL": self.gh_fail,
            **(env or {}),
        }
        proc = subprocess.run(
            ["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=full, timeout=timeout
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return proc.stdout + proc.stderr

    @staticmethod
    def line(out: str, wt: Path) -> str | None:
        return next((ln for ln in out.splitlines() if f"{wt}  (" in ln), None)

    def verdict(self, dry: bool = True, wt: Path | None = None, env: dict[str, str] | None = None) -> str:
        """The first word printed for the worktree: keep | would | removed | FAILED."""
        out = self.run(dry, env)
        line = self.line(out, wt or self.wt)
        assert line is not None, f"script printed nothing for the worktree:\n{out}"
        return line.split()[0]

    def keeps(self, reason: str = KEEP_ENV, env: dict[str, str] | None = None, real: bool = True) -> None:
        """A dry run and (by default) a real run both keep the worktree, the dry one saying why."""
        out = self.run(True, env)
        line = self.line(out, self.wt)
        assert line is not None and line.startswith("keep") and reason in line, out
        if real:
            out = self.run(False, env)
            line = self.line(out, self.wt)
            assert line is not None and line.startswith("keep"), out
            assert self.wt.exists()

    # --- setup helpers ------------------------------------------------------------------------------------
    def commit(self, *files: str, message: str = "more") -> None:
        """Commit files in the worktree and treat that commit as the merged one."""
        _git(self.wt, "add", "-f", "--", *files)
        _git(self.wt, "commit", "-q", "-m", message)
        self.merged = [f"{BRANCH} {_git(self.wt, 'rev-parse', 'HEAD')}"]

    def exclude(self, pattern: str) -> None:
        with (self.repo / ".git" / "info" / "exclude").open("a") as handle:
            handle.write(pattern + "\n")

    def nested_repo(self, rel: str, **files: str) -> Path:
        """An ignored nested git repo: git lists it as the single entry `rel/` and never enumerates its files."""
        self.exclude(rel.split("/")[0] + "/")
        nested = self.wt / rel
        nested.mkdir(parents=True)
        _git(nested, "init", "-q")
        for name, text in files.items():
            (nested / name).write_text(text)
        assert _git(self.wt, "status", "--porcelain") == ""
        return nested

    def shim(self, name: str, body: str) -> None:
        path = self.bindir / name
        path.write_text("#!/bin/bash\n" + body + "\n")
        path.chmod(0o755)

    def git_fails(self, args: str) -> None:
        """git exits 128 for any call whose arguments contain `args`; every other call is the real git."""
        self.shim(
            "git",
            f'case " $* " in *" {args} "*) echo "fatal: injected failure" >&2; exit 128 ;; esac\n'
            f'exec "{_real("git")}" "$@"',
        )


@pytest.fixture
def fx(tmp_path: Path) -> Fixture:
    base = tmp_path.resolve()  # git prints realpaths; /var is a symlink to /private/var on macOS
    root = base / "pro jects"  # a space in the root: every path below must survive being quoted
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
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    return Fixture(root, repo, wt, sha, bindir)


# --- controls: nothing to protect, so the worktree really goes ---------------------------------------------


def test_clean_worktree_is_removed_by_a_real_run(fx: Fixture) -> None:
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()
    assert _git(fx.repo, "branch", "--list", BRANCH) == ""
    assert fx.repo.exists()


def test_dry_run_only_says_would(fx: Fixture) -> None:
    assert fx.verdict() == "would"
    assert fx.wt.exists()


def test_env_byte_identical_to_the_primary_copy_is_removed(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("SAME=1\n")
    (fx.wt / ".env").write_text("SAME=1\n")
    assert fx.verdict(dry=False) == "removed"
    assert (fx.repo / ".env").read_text() == "SAME=1\n"


def test_worktree_inside_the_primary_checkout_is_removed(fx: Fixture) -> None:
    topic = fx.repo / ".worktrees" / "topic"
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/topic", str(topic))
    fx.merged.append(f"feat/topic {_git(topic, 'rev-parse', 'HEAD')}")
    assert fx.verdict(dry=False, wt=topic) == "removed"
    assert not topic.exists()
    assert fx.repo.exists()


def test_ignored_files_that_are_not_env_files_do_not_keep_the_worktree(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("not an .env file\n")
    assert fx.verdict() == "would"


def test_ignored_nested_repo_without_env_files_keeps_as_unproven_history(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", readme="nothing secret\n")
    fx.keeps("holds a nested git repo")


def test_tracked_symlink_that_is_not_named_env_is_removable(fx: Fixture) -> None:
    (fx.wt / "link").symlink_to(".env.example")
    fx.commit("link")
    assert fx.verdict() == "would"


def test_fifo_named_env_in_the_worktree_does_not_hang_or_keep(fx: Fixture) -> None:
    os.mkfifo(fx.wt / ".env")  # git never lists a FIFO, and nothing can be read from it
    assert fx.verdict() == "would"


# --- .env files that must keep the worktree ----------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 3])
def test_unique_ignored_envs_keep_the_worktree(fx: Fixture, n: int) -> None:
    for i in range(n):
        (fx.wt / f".env.unique{i}").write_text(f"SECRET={i}\n")
    fx.keeps()


def test_many_unique_envs_keep_the_worktree_whatever_the_scheduling(fx: Fixture) -> None:
    """The shipped guard ended in `grep -q .` under pipefail: its writer took SIGPIPE when grep exited on the
    first hit and the tree was deleted. ~125 KB of names fills any pipe buffer, and a slow grep makes the
    race certain."""
    for i in range(3000):
        (fx.wt / f".env.{i:05d}-{'x' * 30}").write_text("SECRET\n")
    fx.shim("grep", f'sleep 0.3\nexec "{_real("grep")}" "$@"')
    fx.keeps(real=False)


def test_primary_env_with_different_bytes_keeps(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("PRIMARY=1\n")
    (fx.wt / ".env").write_text("WORKTREE_ONLY=2\n")
    fx.keeps()
    assert (fx.wt / ".env").read_text() == "WORKTREE_ONLY=2\n"


def test_env_without_a_primary_copy_keeps(fx: Fixture) -> None:
    (fx.wt / ".env").write_text("WORKTREE_ONLY=2\n")
    fx.keeps()


def test_one_differing_env_among_identical_ones_keeps(fx: Fixture) -> None:
    for name in (".env", ".env.test"):
        (fx.repo / name).write_text("SAME=1\n")
        (fx.wt / name).write_text("SAME=1\n")
    (fx.wt / ".env.local").write_text("UNIQUE=1\n")
    fx.keeps()


def test_a_failing_cmp_keeps_even_identical_files(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("SAME=1\n")
    (fx.wt / ".env").write_text("SAME=1\n")
    fx.shim("cmp", "exit 2")
    fx.keeps()


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        (".ENV", KEEP_ENV),
        (".Env.local", KEEP_ENV),
        ("conf/.eNv", KEEP_ENV),
        (".env.d/secrets", KEEP_ENV),  # the name is on a parent directory, not on the file
        ("a/.ENV.d/b/c", KEEP_ENV),
        (".envé", KEEP_ENV),
        (".env\\local", KEEP_ENV),
        (".env\nlocal", "file name with a newline"),
    ],
    ids=["upper", "mixed", "nested", "parent-component", "deep-component", "unicode", "backslash", "newline"],
)
def test_env_names_match_in_any_case_and_any_path_component(fx: Fixture, name: str, reason: str) -> None:
    (fx.wt / name).parent.mkdir(parents=True, exist_ok=True)
    (fx.wt / name).write_text("unique\n")
    fx.keeps(reason)


def test_non_env_file_name_with_a_newline_keeps(fx: Fixture) -> None:
    fx.exclude("nl*")
    (fx.wt / "nl\nfile").write_text("unparseable name\n")
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps("file name with a newline")


def test_ignored_nested_repo_holding_an_env_file_keeps(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", **{".env": "unique\n"})
    fx.keeps()


@pytest.mark.parametrize("name", [".ENV", ".eNv.local", "sub/.Env"])
def test_ignored_nested_repo_holding_a_mixed_case_env_file_keeps(fx: Fixture, name: str) -> None:
    nested = fx.nested_repo("vendor/lib")
    (nested / name).parent.mkdir(parents=True, exist_ok=True)
    (nested / name).write_text("unique\n")
    fx.keeps()


def test_env_named_parent_of_a_nested_repo_keeps(fx: Fixture) -> None:
    nested = fx.wt / ".env.d" / "secrets"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    (nested / "credentials").write_text("unique\n")
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps()
    assert (nested / "credentials").exists()


# --- .env symlinks keep, whatever they point at ------------------------------------------------------------


def _outside(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("PRIMARY=1\n")
    (fx.wt / ".env").symlink_to(fx.repo / ".env")


def _ignored_target(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("PRECIOUS=1\n")
    (fx.wt / ".env").symlink_to("only-copy")


def _tracked_target(fx: Fixture) -> None:
    (fx.wt / ".env").symlink_to(".env.example")


def _unrelated_dir(fx: Fixture) -> None:
    unrelated = fx.wt.parent / "unrelated"
    unrelated.mkdir()
    (unrelated / "data").write_text("shared\n")
    (fx.wt / ".env").symlink_to(unrelated / "data")


def _sibling_repo(fx: Fixture) -> None:
    sibling = fx.root / "sibling"
    sibling.mkdir()
    (sibling / "data").write_text("shared\n")
    (fx.wt / ".env").symlink_to(sibling / "data")


def _dangling(fx: Fixture) -> None:
    (fx.wt / ".env").symlink_to("does-not-exist")


def _loop(fx: Fixture) -> None:
    (fx.wt / ".env").symlink_to(".env.b")
    (fx.wt / ".env.b").symlink_to(".env")


def _directory(fx: Fixture) -> None:
    (fx.wt / "data").mkdir()
    (fx.wt / "data" / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to("data")


def _worktree_root(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env").symlink_to(".")


def _chain(fx: Fixture) -> None:
    (fx.repo / ".env").write_text("PRIMARY=1\n")
    (fx.wt / ".env.hop").symlink_to(fx.repo / ".env")
    (fx.wt / ".env").symlink_to(".env.hop")


def _upper(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".ENV").symlink_to("only-copy")


def _component(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("unique\n")
    (fx.wt / ".env.d").mkdir()
    (fx.wt / ".env.d" / "link").symlink_to("../only-copy")


def _admin_dir(fx: Fixture) -> None:
    """The link points into the worktree's own git admin dir, which `git worktree remove` deletes with it."""
    admin = Path(_git(fx.wt, "rev-parse", "--git-dir"))
    (admin / "envdata").write_text("ADMIN_SECRET=1\n")
    (fx.wt / ".env").symlink_to(admin / "envdata")


LINKS: dict[str, Callable[[Fixture], None]] = {
    "outside-target": _outside,
    "ignored-target": _ignored_target,
    "tracked-target": _tracked_target,
    "unrelated-dir": _unrelated_dir,
    "sibling-repo": _sibling_repo,
    "dangling": _dangling,
    "loop": _loop,
    "directory": _directory,
    "worktree-root": _worktree_root,
    "chain": _chain,
    "upper-case-name": _upper,
    "env-named-parent": _component,
    "admin-dir": _admin_dir,
}


@pytest.mark.parametrize("make", LINKS.values(), ids=LINKS.keys())
def test_env_symlink_keeps_the_worktree_whatever_it_points_at(fx: Fixture, make: Callable[[Fixture], None]) -> None:
    make(fx)
    fx.keeps()


def test_admin_dir_symlink_target_survives_a_real_run(fx: Fixture) -> None:
    _admin_dir(fx)
    fx.keeps()
    assert (Path(_git(fx.wt, "rev-parse", "--git-dir")) / "envdata").read_text() == "ADMIN_SECRET=1\n"


def test_ignored_symlink_target_survives_a_real_run(fx: Fixture) -> None:
    _ignored_target(fx)
    fx.keeps()
    assert (fx.wt / "only-copy").read_text() == "PRECIOUS=1\n"


@pytest.mark.parametrize("name", [".env", ".ENV", "conf/.env.d/link"])
def test_tracked_env_symlink_keeps(fx: Fixture, name: str) -> None:
    (fx.wt / name).parent.mkdir(parents=True, exist_ok=True)
    (fx.wt / name).symlink_to("/etc/hosts")
    fx.commit(name)
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps("holds an .env symlink")


# --- the primary copy has to be a plain file in a plain directory ------------------------------------------


def test_primary_env_that_is_a_symlink_to_an_identical_file_keeps(fx: Fixture) -> None:
    external = fx.wt.parent / "external.env"
    external.write_text("SAME=1\n")
    (fx.repo / ".env").symlink_to(external)
    (fx.wt / ".env").write_text("SAME=1\n")
    fx.keeps()


def test_primary_env_that_is_a_symlink_into_the_worktree_keeps(fx: Fixture) -> None:
    # cmp would compare the worktree file with itself and call it identical
    (fx.wt / ".env").write_text("unique\n")
    (fx.repo / ".env").symlink_to(fx.wt / ".env")
    fx.keeps()


def test_primary_env_that_is_a_fifo_keeps_without_hanging(fx: Fixture) -> None:
    os.mkfifo(fx.repo / ".env")  # cmp would block forever opening it
    (fx.wt / ".env").write_text("SAME=1\n")
    assert fx.verdict(env=None) == "keep"


@pytest.mark.parametrize("target", ["elsewhere", "worktree"])
def test_primary_copy_behind_a_symlinked_parent_directory_keeps(fx: Fixture, target: str) -> None:
    store = fx.wt.parent / "elsewhere" if target == "elsewhere" else fx.wt / "store"
    store.mkdir(exist_ok=True)
    (store / ".env").write_text("SAME=1\n")
    (fx.repo / "conf").symlink_to(store, target_is_directory=True)
    (fx.wt / "conf").mkdir(exist_ok=True)
    (fx.wt / "conf" / ".env").write_text("SAME=1\n")
    fx.keeps()


# --- anything that cannot be scanned keeps the worktree, with a printed reason ------------------------------


def test_git_ls_files_index_failure_keeps(fx: Fixture) -> None:
    fx.git_fails("ls-files -z -s -v")
    fx.keeps("could not read the index")


def test_git_ls_files_untracked_failure_keeps(fx: Fixture) -> None:
    fx.git_fails("ls-files -z -o")
    fx.keeps("could not list ignored files")


@pytest.mark.skipif(IS_ROOT, reason="root ignores directory permissions")
def test_unreadable_ignored_directory_keeps(fx: Fixture) -> None:
    # git warns "could not open directory" and still exits 0; the .env inside is invisible to it
    vault = fx.wt / "only-copy"
    vault.mkdir()
    (vault / ".env").write_text("unique\n")
    vault.chmod(0)
    try:
        fx.keeps("could not list ignored files")
    finally:
        vault.chmod(0o755)


def test_git_status_failure_keeps(fx: Fixture) -> None:
    fx.git_fails("status --porcelain -uall")
    fx.keeps("could not read git status")


def test_git_rev_parse_head_failure_keeps(fx: Fixture) -> None:
    fx.git_fails("rev-parse HEAD")
    fx.keeps("HEAD is not the merged commit")


def test_find_killed_in_a_nested_repo_scan_keeps(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", **{".env": "unique\n"})
    fx.shim("find", f'for a in "$@"; do [ "$a" = -iname ] && kill -9 $$; done\nexec "{_real("find")}" "$@"')
    fx.keeps("could not scan vendor/lib/ (find exit 137)")


def test_find_failing_quietly_in_a_nested_repo_scan_keeps(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", readme="nothing\n")
    fx.shim("find", "exit 1")
    fx.keeps("could not scan vendor/lib/ (find exit 1)")


def test_failing_head_does_not_change_the_nested_repo_verdict(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", **{".env": "unique\n"})
    fx.shim("head", "exit 1")
    fx.keeps()


def test_scan_killed_mid_way_keeps(fx: Fixture) -> None:
    # `rm` runs directly inside the scan's subshell; killing its parent kills the whole scan with status 137
    fx.shim("rm", 'kill -9 $PPID')
    fx.keeps("scan failed, exit 137")


def test_mktemp_failure_keeps(fx: Fixture) -> None:
    fx.shim("mktemp", "exit 1")
    fx.keeps("could not create a temp file")


@pytest.mark.parametrize("kind", ["directory", "read-only-file"])
def test_unwritable_temp_file_keeps(fx: Fixture, tmp_path: Path, kind: str) -> None:
    """A temp file that cannot be written must not read as "nothing to protect"."""
    if kind == "read-only-file" and IS_ROOT:
        pytest.skip("root ignores file permissions")
    target = tmp_path / "scratch"
    if kind == "directory":
        target.mkdir()
    else:
        target.write_text("")
        target.chmod(0o444)
    fx.shim("mktemp", f'echo "{target}"')
    (fx.wt / ".env").write_text("unique\n")  # would be removed if the unwritable list were taken as empty
    fx.keeps("could not read the index")


def test_du_runs_before_the_scan_so_a_file_created_meanwhile_is_seen(fx: Fixture) -> None:
    # du is slow on a big worktree; an .env created while it runs must not escape the scan that follows it
    fx.shim("du", f'"{_real("du")}" "$@"\necho "RACE_SECRET=1" > "{fx.wt}/.env.local"')
    fx.keeps()
    assert (fx.wt / ".env.local").read_text() == "RACE_SECRET=1\n"


# --- index flags hide local edits from `git status` --------------------------------------------------------


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
@pytest.mark.parametrize("name", [".envrc", "README"])
def test_hidden_local_edit_of_a_tracked_file_keeps(fx: Fixture, flag: str, name: str) -> None:
    (fx.wt / name).write_text("TEMPLATE=1\n")
    fx.commit(name)
    _git(fx.wt, "update-index", flag, name)
    (fx.wt / name).write_text("LOCAL_SECRET=9\n")
    assert _git(fx.wt, "status", "--porcelain") == ""  # git itself calls this worktree clean
    fx.keeps("assume-unchanged or skip-worktree")
    assert (fx.wt / name).read_text() == "LOCAL_SECRET=9\n"


@pytest.mark.parametrize("name", ["notes.txt", ".env"])
def test_untracked_file_is_seen_even_when_status_hides_untracked_files(fx: Fixture, tmp_path: Path, name: str) -> None:
    (fx.wt / ".gitignore").write_text("")  # an untracked, not ignored file
    fx.commit(".gitignore")
    config = tmp_path / "gitconfig"
    config.write_text("[status]\n\tshowUntrackedFiles = no\n")
    (fx.wt / name).write_text("UNIQUE=1\n")
    env = {"GIT_CONFIG_GLOBAL": str(config)}
    fx.keeps("PR merged but worktree dirty", env=env)
    assert (fx.wt / name).read_text() == "UNIQUE=1\n"


# --- the refusals that predate the .env guard --------------------------------------------------------------


def test_worktree_with_an_untracked_file_is_kept(fx: Fixture) -> None:
    (fx.wt / "notes.txt").write_text("not ignored, not committed\n")
    fx.keeps("PR merged but worktree dirty")


def test_worktree_with_a_modified_tracked_file_is_kept(fx: Fixture) -> None:
    (fx.wt / ".env.example").write_text("EDITED=1\n")
    fx.keeps("PR merged but worktree dirty")


def test_worktree_whose_head_is_past_the_merged_commit_is_kept(fx: Fixture) -> None:
    (fx.wt / "later.txt").write_text("unpushed\n")
    _git(fx.wt, "add", "later.txt")
    _git(fx.wt, "commit", "-q", "-m", "unpushed work")  # fx.merged still names the earlier commit
    fx.keeps("HEAD is not the merged commit")
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_branch_name_reused_by_an_open_pr_is_kept(fx: Fixture) -> None:
    fx.open = [f"{BRANCH} 0123456789abcdef0123456789abcdef01234567"]
    fx.keeps("name reused by an open PR")


def test_primary_checkout_is_never_a_candidate_even_if_its_branch_has_a_merged_pr(fx: Fixture) -> None:
    fx.merged.append(f"main {_git(fx.repo, 'rev-parse', 'HEAD')}")
    out = fx.run(dry=False)
    assert fx.line(out, fx.repo) is None, out
    assert fx.repo.exists()


def test_branch_without_a_merged_pr_is_left_alone(fx: Fixture) -> None:
    fx.merged = []
    assert fx.line(fx.run(dry=False), fx.wt) is None
    assert fx.wt.exists()


@pytest.mark.parametrize("state", ["merged", "open"])
def test_gh_failure_skips_the_repo_and_removes_nothing(fx: Fixture, state: str) -> None:
    fx.gh_fail = state
    out = fx.run(dry=False)
    assert f"skip {fx.repo}: gh pr list --state {state} failed" in out
    assert fx.line(out, fx.wt) is None
    assert fx.wt.exists()


def test_failing_worktree_discovery_skips_the_repo_with_a_reason(fx: Fixture) -> None:
    fx.git_fails("rev-parse --git-dir")
    out = fx.run(dry=False)
    assert f"skip {fx.repo}: git rev-parse failed" in out
    assert fx.wt.exists()


def test_failing_worktree_list_skips_the_repo_with_a_reason(fx: Fixture) -> None:
    fx.git_fails("worktree list --porcelain")
    out = fx.run(dry=False)
    assert f"skip {fx.repo}: could not list worktrees" in out
    assert fx.wt.exists()


def test_a_refused_removal_is_reported_and_keeps_the_branch(fx: Fixture) -> None:
    _git(fx.repo, "worktree", "lock", str(fx.wt))  # git refuses to remove a locked worktree
    assert fx.verdict(dry=False) == "FAILED"
    assert fx.wt.exists()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def _with_submodule(fx: Fixture, init: bool = True) -> None:
    """The worktree gets a tracked submodule at `sub` (initialized unless `init` is false: then `sub/` is an
    empty directory, as after a plain checkout), and its HEAD becomes the merged commit."""
    sub = fx.wt.parent / "subsrc"
    sub.mkdir()
    _git(sub, "init", "-q", "-b", "main")
    (sub / "f").write_text("x\n")
    (sub / ".gitignore").write_text(".env\n")
    _git(sub, "add", "-A")
    _git(sub, "commit", "-q", "-m", "init")
    allow = ("-c", "protocol.file.allow=always")
    _git(fx.repo, *allow, "submodule", "add", "-q", str(sub), "sub")
    _git(fx.repo, "commit", "-q", "-m", "add submodule")
    _git(fx.wt, "merge", "-q", "--ff-only", "main")
    if init:
        _git(fx.wt, *allow, "submodule", "update", "--init", "-q")
    fx.merged = [f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}"]


def test_worktree_with_an_initialized_submodule_is_left_to_gits_own_refusal(fx: Fixture) -> None:
    """The scan does not look inside submodules; `git worktree remove` refuses them, which is all that
    protects an ignored .env inside one. This pins that refusal, and that a tracked submodule's own `.git`
    is not mistaken for a nested repo."""
    _with_submodule(fx)
    (fx.wt / "sub" / ".env").write_text("SUBSECRET=1\n")
    assert fx.verdict(dry=False) == "FAILED"
    assert (fx.wt / "sub" / ".env").read_text() == "SUBSECRET=1\n"


def test_script_parses_under_the_system_bash() -> None:
    subprocess.run(["/bin/bash", "-n", str(SCRIPT)], check=True)


# =============================================================================================================
# Audit additions: each test below kills a mutant of the script that the suite above let survive.
# =============================================================================================================

LOGGING_GH_STUB = GH_STUB.replace(
    '[ -n "$state" ] && [ "$state" = "$GH_FAIL" ]',
    'echo "$PWD" >>"$GH_LOG"; printf \'%s\\0\' "$PWD" "$@" >"$GH_LOG.$state"\n'
    '[ -n "$state" ] && [ "$state" = "$GH_FAIL" ]',
    1,
)


def _second_repo(fx: Fixture, rel: str, branch: str, wt_name: str) -> tuple[Path, Path]:
    """A second repo at PROJECTS_ROOT/<rel> with one linked worktree outside it, its branch marked merged."""
    repo = fx.root / rel
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".env*\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "init")
    wt = fx.wt.parent / wt_name
    _git(repo, "worktree", "add", "-q", "-b", branch, str(wt))
    fx.merged.append(f"{branch} {_git(wt, 'rev-parse', 'HEAD')}")
    return repo, wt


def _silent_git_failure(fx: Fixture, args: str, code: int = 1) -> None:
    """git dies with no output at all (an OOM kill, a full disk) for any call whose arguments contain `args`."""
    fx.shim("git", f'case " $* " in *" {args} "*) exit {code} ;; esac\nexec "{_real("git")}" "$@"')


# --- records and names: the NUL-separated reads must not merge, trim or reinterpret names ---------------------


def test_untracked_name_ending_in_a_backslash_cannot_swallow_the_next_env_file(fx: Fixture) -> None:
    """`read -d ''` without -r treats `\\<NUL>` as an escaped delimiter and fuses two records (bash 3.2 and 5)."""
    fx.exclude("-*")
    (fx.wt / "-a\\").write_text("x\n")  # sorts directly before .env
    (fx.wt / ".env").write_text("unique\n")
    fx.keeps()


def test_tracked_name_ending_in_a_backslash_cannot_swallow_an_env_symlink(fx: Fixture) -> None:
    (fx.wt / "-a\\").write_text("x\n")
    (fx.wt / "only-copy").write_text("PRECIOUS=1\n")
    (fx.wt / ".env").symlink_to("only-copy")
    fx.commit("-a\\", ".env")
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps("holds an .env symlink")
    assert (fx.wt / "only-copy").read_text() == "PRECIOUS=1\n"


def test_tracked_name_ending_in_a_backslash_cannot_swallow_a_hidden_edit(fx: Fixture) -> None:
    (fx.wt / "-a\\").write_text("x\n")
    (fx.wt / "a.conf").write_text("TEMPLATE=1\n")
    fx.commit("-a\\", "a.conf")
    _git(fx.wt, "update-index", "--assume-unchanged", "a.conf")
    (fx.wt / "a.conf").write_text("LOCAL_SECRET=9\n")
    fx.keeps("assume-unchanged or skip-worktree")


def test_env_file_with_a_trailing_space_is_not_mistaken_for_its_identical_trimmed_name(fx: Fixture) -> None:
    """`read` without IFS= trims the space: `.env ` would be looked up as `.env`, which matches the primary copy."""
    (fx.repo / ".env").write_text("SAME=1\n")
    (fx.wt / ".env").write_text("SAME=1\n")
    (fx.wt / ".env ").write_text("UNIQUE=1\n")
    fx.keeps()
    assert (fx.wt / ".env ").read_text() == "UNIQUE=1\n"


def test_tracked_env_symlink_whose_name_contains_a_tab_keeps(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("PRECIOUS=1\n")
    (fx.wt / ".env\tfoo").symlink_to("only-copy")
    fx.commit(".env\tfoo")
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps("holds an .env symlink")


def test_both_index_flags_on_one_file_keep(fx: Fixture) -> None:
    """assume-unchanged and skip-worktree both set make `ls-files -v` print the lowercase tag `s`, not `h` or `S`."""
    (fx.wt / "a.conf").write_text("TEMPLATE=1\n")
    fx.commit("a.conf")
    # two calls: a single `--assume-unchanged --skip-worktree` call records only assume-unchanged (tag `h`)
    _git(fx.wt, "update-index", "--skip-worktree", "a.conf")
    _git(fx.wt, "update-index", "--assume-unchanged", "a.conf")
    (fx.wt / "a.conf").write_text("LOCAL_SECRET=9\n")
    assert _git(fx.wt, "status", "--porcelain") == ""
    assert _git(fx.wt, "ls-files", "-v", "a.conf").startswith("s ")
    fx.keeps("assume-unchanged or skip-worktree")
    assert (fx.wt / "a.conf").read_text() == "LOCAL_SECRET=9\n"


# --- the byte comparison -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("primary", "worktree"),
    [
        ("AAME=1\n", "BAME=1\n"),  # same length, first byte differs
        ("SAME=1\n", "SAME=2\n"),  # same length, last byte differs
        ("SAME=1\n", "SAME=1\nEXTRA=2\n"),  # the primary copy is a prefix
        ("SAME=1\nEXTRA=2\n", "SAME=1\n"),  # the worktree copy is a prefix
    ],
    ids=["first-byte", "last-byte", "primary-is-prefix", "worktree-is-prefix"],
)
def test_env_that_differs_in_one_place_from_the_primary_copy_keeps(fx: Fixture, primary: str, worktree: str) -> None:
    (fx.repo / ".env").write_text(primary)
    (fx.wt / ".env").write_text(worktree)
    fx.keeps()


def test_symlinked_grandparent_of_the_primary_copy_keeps(fx: Fixture) -> None:
    store = fx.wt.parent / "elsewhere"
    (store / "b").mkdir(parents=True)
    (store / "b" / ".env").write_text("SAME=1\n")
    (fx.repo / "a").symlink_to(store, target_is_directory=True)  # a -> store, a/b is a plain dir inside it
    (fx.wt / "a" / "b").mkdir(parents=True)
    (fx.wt / "a" / "b" / ".env").write_text("SAME=1\n")
    fx.keeps()


# --- failures that print nothing -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "reason"),
    [
        ("ls-files -z -s -v", "could not read the index"),
        ("ls-files -z -o", "could not list ignored files"),
        ("status --porcelain -uall", "could not read git status"),
    ],
    ids=["index", "untracked", "status"],
)
def test_a_git_failure_with_no_output_keeps(fx: Fixture, args: str, reason: str) -> None:
    """The stderr check alone cannot see a killed git; the exit status has to be tested too."""
    _silent_git_failure(fx, args)
    fx.keeps(reason)


# --- discovery, quoting and the third-party contract --------------------------------------------------------


def test_clean_sweep_prints_no_skip_lines(fx: Fixture) -> None:
    """A glob that matches nothing (here the two-level one) must not be treated as a repo."""
    out = fx.run(dry=False)
    assert not [ln for ln in out.splitlines() if ln.startswith("skip")], out


def test_repo_two_levels_below_the_root_is_swept(fx: Fixture) -> None:
    _repo2, wt2 = _second_repo(fx, "group/proj2", "feat/y", "wt2")
    assert fx.verdict(dry=False, wt=wt2) == "removed"
    assert not wt2.exists()


def test_linked_worktree_under_the_root_is_not_treated_as_a_repo(fx: Fixture) -> None:
    linked = fx.root / "linked"  # PROJECTS_ROOT/linked/.git is a file: a linked worktree, not a main checkout
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/linked", str(linked))
    fx.merged.append(f"main {_git(fx.repo, 'rev-parse', 'HEAD')}")
    out = fx.run(dry=True)
    assert fx.line(out, fx.repo) is None, out
    assert "FAILED" not in out, out


def test_repo_without_linked_worktrees_costs_no_gh_calls(fx: Fixture, tmp_path: Path) -> None:
    (fx.bindir / "gh").write_text(LOGGING_GH_STUB)
    solo = fx.root / "solo"
    solo.mkdir()
    _git(solo, "init", "-q", "-b", "main")
    (solo / "f").write_text("x\n")
    _git(solo, "add", "f")
    _git(solo, "commit", "-q", "-m", "init")
    log = tmp_path / "gh.log"
    fx.run(dry=True, env={"GH_LOG": str(log)})
    calls = log.read_text().splitlines()
    assert calls and set(calls) == {str(fx.repo)}, calls


def test_gh_is_called_with_arguments_real_gh_accepts(fx: Fixture, tmp_path: Path) -> None:
    """The stub ignores its arguments, so this pins what the script really sends: subcommand, state, limit, json
    fields, and a -q expression that turns real `gh pr list --json` output into `branch sha` lines."""
    (fx.bindir / "gh").write_text(LOGGING_GH_STUB)
    log = tmp_path / "gh.log"
    fx.run(dry=True, env={"GH_LOG": str(log)})
    for state in ("merged", "open"):
        args = Path(f"{log}.{state}").read_text().split("\0")[1:-1]
        assert args[:2] == ["pr", "list"], args
        assert args[args.index("--state") + 1] == state
        assert int(args[args.index("--limit") + 1]) >= 1000  # gh's default of 30 would silently truncate
        assert args[args.index("--json") + 1].split(",") == ["headRefName", "headRefOid"]
        expr = args[args.index("-q") + 1]
        if shutil.which("jq"):
            sample = '[{"headRefName":"feat/x","headRefOid":"abc123","number":1},{"headRefName":"b","headRefOid":"def"}]'
            got = subprocess.run(["jq", "-r", expr], input=sample, capture_output=True, text=True, check=True)
            assert got.stdout.splitlines() == ["feat/x abc123", "b def"], got.stdout


def test_missing_gh_stops_the_script_with_a_message() -> None:
    bare = "/usr/bin:/bin"
    if shutil.which("gh", path=bare):
        pytest.skip("gh lives in a system directory here")
    proc = subprocess.run(
        ["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env={"PATH": bare, "HOME": "/nonexistent"}
    )
    assert proc.returncode == 1 and "gh not found" in proc.stdout, proc.stdout + proc.stderr


def test_dry_run_is_off_by_default(fx: Fixture) -> None:
    env = {k: v for k, v in os.environ.items() if k != "DRY_RUN"}
    env.update(PATH=f"{fx.bindir}{os.pathsep}{os.environ['PATH']}", PROJECTS_ROOT=str(fx.root))
    env.update(GH_MERGED="\n".join(fx.merged), GH_OPEN="", GH_FAIL="")
    proc = subprocess.run(["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not fx.wt.exists(), proc.stdout


def test_squash_merged_branch_with_its_own_commits_is_deleted(fx: Fixture) -> None:
    """After a squash merge the branch is not an ancestor of main, so `branch -d` would refuse and leak it."""
    (fx.wt / "feature.txt").write_text("work\n")
    fx.commit("feature.txt")
    assert fx.verdict(dry=False) == "removed"
    assert _git(fx.repo, "branch", "--list", BRANCH) == ""


def test_stale_worktree_entry_is_left_for_gits_own_gc(fx: Fixture) -> None:
    """Round 6 (P1-1): the script no longer runs `git worktree prune`. A missing directory is also what a moved
    folder or an unmounted volume looks like, and pruning it dangles that worktree's unpushed commits."""
    shutil.rmtree(fx.wt)  # a worktree directory someone deleted by hand
    out = fx.run(dry=False)
    assert str(fx.wt) in _git(fx.repo, "worktree", "list", "--porcelain"), out


def test_open_pr_on_a_longer_branch_name_does_not_keep_this_one(fx: Fixture) -> None:
    fx.open = [f"{BRANCH}-followup 0123456789abcdef0123456789abcdef01234567"]
    assert fx.verdict() == "would"


@pytest.fixture
def spaced(fx: Fixture) -> Path:
    """A second worktree whose own path contains a space (the repo path already does)."""
    wt = fx.wt.parent / "my wt"
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/sp", str(wt))
    fx.merged.append(f"feat/sp {_git(wt, 'rev-parse', 'HEAD')}")
    return wt


def test_worktree_path_with_a_space_is_removed(fx: Fixture, spaced: Path) -> None:
    assert fx.verdict(dry=False, wt=spaced) == "removed"
    assert not spaced.exists()


def test_worktree_path_with_a_space_still_matches_an_identical_primary_copy(fx: Fixture, spaced: Path) -> None:
    (fx.repo / ".env").write_text("SAME=1\n")
    (spaced / ".env").write_text("SAME=1\n")
    assert fx.verdict(dry=False, wt=spaced) == "removed"


def test_worktree_path_with_a_space_keeps_a_unique_env(fx: Fixture, spaced: Path) -> None:
    (spaced / ".env").write_text("UNIQUE=1\n")
    assert fx.verdict(dry=False, wt=spaced) == "keep"
    assert spaced.exists()


def test_worktree_path_with_a_space_keeps_an_env_in_a_nested_repo(fx: Fixture, spaced: Path) -> None:
    fx.exclude("vendor/")
    nested = spaced / "vendor" / "lib"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    (nested / ".env").write_text("UNIQUE=1\n")
    assert fx.verdict(dry=False, wt=spaced) == "keep"
    assert (nested / ".env").exists()


def test_worktree_path_with_a_space_keeps_a_nested_repo_without_env(fx: Fixture, spaced: Path) -> None:
    """The nested-.git scan must run on a spaced path and name the nested repo, not fail on the quoting."""
    fx.exclude("vendor/")
    nested = spaced / "vendor" / "lib"
    nested.mkdir(parents=True)
    _git(nested, "init", "-q")
    (nested / "readme").write_text("nothing secret\n")
    out = fx.run(dry=False)
    line = fx.line(out, spaced)
    assert line is not None and line.startswith("keep") and "holds a nested git repo" in line, out
    assert nested.exists()


@pytest.mark.parametrize("verdict_run", ["dry", "real"])
def test_scan_leaves_no_temp_file_behind(fx: Fixture, tmp_path: Path, verdict_run: str) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    fx.run(dry=verdict_run == "dry", env={"TMPDIR": str(scratch)})
    assert list(scratch.iterdir()) == []


def test_merged_pr_on_a_longer_branch_name_does_not_make_this_branch_removable(fx: Fixture) -> None:
    """Merged lookup must match the whole branch name: `feat/x-2` merged says nothing about `feat/x`."""
    sha = fx.merged[0].split()[1]
    fx.merged = [f"{BRANCH}-2 {sha}"]
    out = fx.run(dry=True)
    assert fx.line(out, fx.wt) is None, out


def test_reported_size_is_right_for_a_path_with_a_space(fx: Fixture, spaced: Path) -> None:
    (spaced / "blob.bin").write_bytes(b"\0" * 3 * 1024 * 1024)
    _git(spaced, "add", "-f", "blob.bin")
    _git(spaced, "commit", "-q", "-m", "blob")
    fx.merged = [f"feat/sp {_git(spaced, 'rev-parse', 'HEAD')}"]
    line = fx.line(fx.run(dry=True), spaced)
    assert line is not None and line.startswith("would") and ", 3M)" in line, line


# =============================================================================================================
# Round 5: a symlinked root, nested .git, secret-named files, and the package-tree exemption.
# =============================================================================================================

KEEP_GIT = "holds a nested git repo"
KEEP_SECRET = "holds secret-named files"


def _ignored(fx: Fixture, rel: str, text: str = "x\n") -> None:
    """An ignored (not untracked) file at `rel` in the worktree, parents created."""
    fx.exclude(rel)
    path = fx.wt / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    assert _git(fx.wt, "status", "--porcelain") == ""


# --- a symlinked PROJECTS_ROOT -------------------------------------------------------------------------------


def test_symlinked_projects_root_still_skips_the_primary_and_removes_the_worktree(fx: Fixture) -> None:
    """`git worktree list` prints realpaths while the sweep reaches the primary through the link; comparing the
    two as text would treat the primary as a linked worktree and try to remove it."""
    link = fx.wt.parent / "root-link"
    link.symlink_to(fx.root)
    fx.merged.append(f"main {_git(fx.repo, 'rev-parse', 'HEAD')}")
    out = fx.run(dry=False, env={"PROJECTS_ROOT": str(link)})
    assert fx.line(out, fx.repo) is None, out
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("removed"), out
    assert fx.repo.exists() and (fx.repo / ".git").exists()
    assert "FAILED" not in out and "skip" not in out, out


# --- nested .git: unproven pushed history ------------------------------------------------------------------


def test_nested_repo_under_node_modules_keeps(fx: Fixture) -> None:
    """The package-tree exemption covers the secret NAME rule only, never a nested repo."""
    fx.nested_repo("node_modules/pkg", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_nested_repo_under_a_path_with_spaces_keeps(fx: Fixture) -> None:
    fx.nested_repo("my vendor/lib dir", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_nested_repo_with_an_empty_git_directory_keeps(fx: Fixture) -> None:
    """git skips a broken nested repo silently, so only a scan for the name `.git` sees it."""
    fx.exclude("vendor/")
    (fx.wt / "vendor" / "lib" / ".git").mkdir(parents=True)
    (fx.wt / "vendor" / "lib" / "a").write_text("x\n")
    fx.keeps(KEEP_GIT)


def test_nested_repo_with_a_dangling_gitfile_keeps(fx: Fixture) -> None:
    fx.exclude("vendor/")
    (fx.wt / "vendor" / "lib").mkdir(parents=True)
    (fx.wt / "vendor" / "lib" / ".git").write_text("gitdir: /nonexistent/place\n")
    fx.keeps(KEEP_GIT)


def test_nested_linked_worktree_with_a_gitfile_keeps(fx: Fixture) -> None:
    fx.exclude("inner/")
    # --no-checkout: the checkout would carry the tracked .env.example, which the .env* scan reports first
    _git(fx.repo, "worktree", "add", "-q", "--no-checkout", "-b", "feat/inner", str(fx.wt / "inner"))
    fx.keeps(KEEP_GIT)


def test_nested_repo_under_site_packages_keeps(fx: Fixture) -> None:
    fx.nested_repo("lib/python3/site-packages/pkg", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_nested_repo_next_to_a_tracked_submodule_still_keeps(fx: Fixture) -> None:
    """Only the exact submodule path is left to git's refusal; a lookalike path is a nested repo."""
    _with_submodule(fx)
    fx.nested_repo("sub-extra/lib", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_nested_repo_whose_path_is_a_prefix_of_a_submodule_path_keeps(fx: Fixture) -> None:
    """`su` is a substring of the submodule path `sub`, but only the exact path is git's to refuse."""
    _with_submodule(fx)
    fx.nested_repo("su", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_names_that_only_look_like_a_git_directory_do_not_keep(fx: Fixture) -> None:
    for rel in ("dist/.github/ci.yml", "dist/pkg.git", "dist/.gitkeep", "dist/not.git/x"):
        _ignored(fx, rel)
    assert fx.verdict() == "would"


def test_find_failing_in_the_nested_git_scan_keeps(fx: Fixture) -> None:
    fx.shim("find", 'for a in "$@"; do [ "$a" = .git ] && exit 1; done\nexec "' + _real("find") + '" "$@"')
    fx.keeps("could not scan for nested git repos (find exit 1)")


def test_find_killed_in_the_nested_git_scan_keeps(fx: Fixture) -> None:
    fx.shim("find", 'for a in "$@"; do [ "$a" = .git ] && kill -9 $$; done\nexec "' + _real("find") + '" "$@"')
    fx.keeps("could not scan for nested git repos (find exit 137)")


def test_find_warning_in_the_nested_git_scan_keeps_even_with_exit_zero(fx: Fixture) -> None:
    fx.shim(
        "find",
        'for a in "$@"; do [ "$a" = .git ] && echo "find: warning" >&2; done\nexec "' + _real("find") + '" "$@"',
    )
    fx.keeps("could not scan for nested git repos (find exit 0)")


# --- secret-named files --------------------------------------------------------------------------------------

SECRET_NAMES = [
    "prod.env", "PROD.ENV", "conf/Stage.eNv",
    ".dev.vars", ".dev.vars.production", ".DEV.VARS", "apps/web/.Dev.Vars",
    ".npmrc", ".NPMRC", "pkg/.npmrc",
    ".netrc", ".NetRC",
    ".pypirc", ".PyPiRC",
    "server.pem", "SERVER.PEM", "certs/ca.Pem",
    "tls.key", "TLS.KEY",
    "cert.p12", "CERT.P12",
    "cert.pfx", "CERT.PFX",
    "id_rsa", "id_rsa.pub", "ID_RSA", ".ssh/id_rsa",
    "id_ed25519", "id_ed25519.pub", "ID_ED25519", ".ssh/ID_Ed25519",
]  # fmt: skip


@pytest.mark.parametrize("rel", SECRET_NAMES)
def test_ignored_secret_named_file_keeps_the_worktree(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel, "not a real secret\n")
    fx.keeps(KEEP_SECRET)


@pytest.mark.parametrize("rel", ["notes.txt", "monkey", "keyboard.js", "valid_rsa", "npmrc", "dev.vars", "pem", "src/key"])
def test_names_that_only_resemble_a_secret_name_do_not_keep(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel)
    assert fx.verdict() == "would"


# --- the package-tree exemption: NAME rule only ---------------------------------------------------------------

EXEMPT = [
    "node_modules/pkg/test/server.pem",
    "node_modules/.bin/.npmrc",
    "node_modules/x/id_ed25519",
    "node_modules/x/sample.env",
    "a/node_modules/b/cert.pfx",
    ".venv/lib/certs/ca.key",
    "venv/lib/id_rsa",
    "lib/python3.12/site-packages/certifi/cacert.pem",
]


@pytest.mark.parametrize("rel", EXEMPT)
def test_secret_named_file_inside_a_package_tree_does_not_keep(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel)
    assert fx.verdict() == "would"
    assert fx.verdict(dry=False) == "removed"


def test_worktree_with_only_package_trees_and_build_output_is_still_removed(fx: Fixture) -> None:
    for rel in ("node_modules/pkg/index.js", ".venv/lib/x.pem", "build/out.js"):
        _ignored(fx, rel)
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()


@pytest.mark.parametrize("name", [".env", ".env.local", "sub/.ENV"])
def test_env_file_inside_node_modules_still_keeps(fx: Fixture, name: str) -> None:
    _ignored(fx, f"node_modules/pkg/{name}", "unique\n")
    fx.keeps()


def test_env_file_inside_a_nested_repo_under_node_modules_is_reported_as_env(fx: Fixture) -> None:
    """The exemption must not skip the `.env*` scan of a nested repo (git lists it as one `dir/` entry)."""
    fx.nested_repo("node_modules/pkg", **{".env": "unique\n"})
    fx.keeps("holds ignored .env files")


@pytest.mark.parametrize(
    "rel",
    [
        "my_node_modules/x.pem",
        "node_modules.bak/x.pem",
        "Node_Modules/x.pem",  # the component test is case-sensitive: a path it cannot classify is kept
        "venv2/x.pem",
        "not.venv/x.pem",
        "site-packages-old/x.pem",
    ],
)
def test_lookalike_of_a_package_tree_is_not_exempt(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel)
    fx.keeps(KEEP_SECRET)


def test_one_secret_outside_a_package_tree_keeps_even_with_exempt_ones_beside_it(fx: Fixture) -> None:
    _ignored(fx, "node_modules/pkg/ok.pem")
    _ignored(fx, "real.pem")
    fx.keeps(KEEP_SECRET)


# =============================================================================================================
# Round 6: git worktree prune, uninitialized submodules, bare/.Git nested repos, per-worktree refs, a stale
# fsmonitor, a fail-closed DRY_RUN, and a worktree list that cannot be parsed. Each test fails on 3d0d7d7.
# =============================================================================================================

KEEP_SUB = "holds files under an uninitialized submodule"
KEEP_REFS = "holds per-worktree refs"
KEEP_DIRTY = "PR merged but worktree dirty"


# --- P1-1: no `git worktree prune` ---------------------------------------------------------------------------


@pytest.mark.parametrize("dry", [True, False], ids=["dry-run", "live"])
def test_a_moved_detached_worktree_keeps_its_admin_dir_and_unpushed_commit(fx: Fixture, dry: bool) -> None:
    """A folder moved aside (or on an unmounted volume) looks exactly like a deleted worktree to git. Pruning it
    deletes its admin dir, and the detached HEAD's unpushed commit then dangles. Even a dry run must not."""
    det = fx.wt.parent / "det"
    _git(fx.repo, "worktree", "add", "-q", "--detach", str(det))
    (det / "work.txt").write_text("unpushed\n")
    _git(det, "add", "work.txt")
    _git(det, "commit", "-q", "-m", "unpushed")
    sha = _git(det, "rev-parse", "HEAD")
    moved = det.with_name("det-moved")
    det.rename(moved)
    out = fx.run(dry=dry)
    admin = fx.repo / ".git" / "worktrees" / "det"
    assert admin.is_dir(), out
    assert (admin / "HEAD").read_text().strip() == sha
    assert _git(moved, "rev-parse", "HEAD") == sha  # still reachable through the moved folder's gitfile
    assert fx.line(out, fx.wt) is not None and (dry or not fx.wt.exists()), out  # the merged one still goes


# --- P1-2: files under a gitlink path that is not initialized here -------------------------------------------


def test_the_blind_spot_is_real_git_status_cannot_see_files_under_an_uninitialized_submodule(fx: Fixture) -> None:
    _with_submodule(fx, init=False)
    (fx.wt / "sub" / ".env").write_text("API_KEY=abc\n")
    assert _git(fx.wt, "status", "--porcelain", "-uall") == ""
    assert _git(fx.wt, "ls-files", "-o") == ""


@pytest.mark.parametrize("name", [".env", "notes.txt", "dir/deep.txt"])
def test_a_file_under_an_uninitialized_submodule_keeps(fx: Fixture, name: str) -> None:
    _with_submodule(fx, init=False)
    target = fx.wt / "sub" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("API_KEY=abc\n")
    fx.keeps(KEEP_SUB)
    assert target.read_text() == "API_KEY=abc\n"


def test_an_empty_uninitialized_submodule_directory_is_removable(fx: Fixture) -> None:
    _with_submodule(fx, init=False)
    assert (fx.wt / "sub").is_dir() and not any((fx.wt / "sub").iterdir())
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()


def test_an_initialized_submodule_is_still_left_to_gits_own_refusal(fx: Fixture) -> None:
    _with_submodule(fx, init=True)
    (fx.wt / "sub" / ".env").write_text("SUBSECRET=1\n")
    assert fx.verdict(dry=False) == "FAILED"
    assert (fx.wt / "sub" / ".env").read_text() == "SUBSECRET=1\n"


def test_find_failing_in_the_submodule_directory_scan_keeps(fx: Fixture) -> None:
    _with_submodule(fx, init=False)
    fx.shim("find", 'for a in "$@"; do [ "$a" = -mindepth ] && exit 1; done\nexec "' + _real("find") + '" "$@"')
    fx.keeps("could not scan the submodule directory sub (find exit 1)")


def test_find_warning_in_the_submodule_directory_scan_keeps_even_with_exit_zero(fx: Fixture) -> None:
    _with_submodule(fx, init=False)
    fx.shim(
        "find",
        'for a in "$@"; do [ "$a" = -mindepth ] && echo "find: warning" >&2; done\nexec "' + _real("find") + '" "$@"',
    )
    fx.keeps("could not scan the submodule directory sub (find exit 0)")


def test_a_tracked_submodule_path_with_a_newline_keeps(fx: Fixture) -> None:
    """The submodule list is newline-joined elsewhere, so a name with a newline cannot be trusted to split."""
    # `git submodule add` refuses such a path, but a gitlink index entry can still carry it
    head = _git(fx.repo, "rev-parse", "HEAD")
    _git(fx.repo, "update-index", "--add", "--cacheinfo", f"160000,{head},a\nb")
    _git(fx.repo, "commit", "-q", "-m", "add gitlink")
    _git(fx.wt, "merge", "-q", "--ff-only", "main")
    fx.merged = [f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}"]
    fx.keeps("has a file name with a newline")


# --- P2-a: bare repos and `.Git` spellings --------------------------------------------------------------------


def test_a_bare_repo_inside_an_ignored_directory_keeps(fx: Fixture) -> None:
    """A bare repo has no `.git` entry at all, so only its layout (HEAD, objects/, refs/) gives it away."""
    fx.exclude("vendor/")
    (fx.wt / "vendor").mkdir()
    _git(fx.wt / "vendor", "init", "-q", "--bare", "lib.git")
    assert not (fx.wt / "vendor" / "lib.git" / ".git").exists()
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps(KEEP_GIT)


def test_a_minimal_bare_layout_keeps(fx: Fixture) -> None:
    fx.exclude("vendor/")
    bare = fx.wt / "vendor" / "lib"
    (bare / "objects").mkdir(parents=True)
    (bare / "refs").mkdir()
    (bare / "HEAD").write_text("ref: refs/heads/main\n")
    fx.keeps(KEEP_GIT)


@pytest.mark.parametrize(
    "missing",
    ["HEAD", "refs", "objects-as-file"],
    ids=["no-HEAD", "no-refs", "objects-is-a-file"],
)
def test_a_directory_that_only_partly_looks_like_a_bare_repo_does_not_keep(fx: Fixture, missing: str) -> None:
    fx.exclude("vendor/")
    bare = fx.wt / "vendor" / "lib"
    bare.mkdir(parents=True)
    if missing == "objects-as-file":
        (bare / "objects").write_text("not a directory\n")
    else:
        (bare / "objects").mkdir()
    if missing != "refs":
        (bare / "refs").mkdir()
    if missing != "HEAD":
        (bare / "HEAD").write_text("ref: refs/heads/main\n")
    assert fx.verdict() == "would"


@pytest.mark.parametrize("spelling", [".Git", ".GIT", ".gIt"])
@pytest.mark.parametrize("kind", ["dir", "gitfile"])
def test_a_nested_repo_whose_git_entry_is_spelled_in_another_case_keeps(
    fx: Fixture, spelling: str, kind: str
) -> None:
    """APFS is case-insensitive: git opens `.Git` as `.git`, so a name match on the exact spelling misses it."""
    fx.exclude("vendor/")
    entry = fx.wt / "vendor" / "lib" / spelling
    entry.parent.mkdir(parents=True)
    if kind == "dir":
        entry.mkdir()
    else:
        entry.write_text("gitdir: /nonexistent/place\n")
    fx.keeps(KEEP_GIT)


# --- P2-b: per-worktree refs ---------------------------------------------------------------------------------


@pytest.mark.parametrize("ref", ["refs/worktree/save", "refs/bisect/bad", "refs/rewritten/x"])
def test_a_per_worktree_ref_to_an_unmerged_commit_keeps(fx: Fixture, ref: str) -> None:
    """`git worktree remove` deletes the worktree's private refs, which can be the only pointer to a commit."""
    merged = fx.merged[0].split()[1]
    (fx.wt / "work.txt").write_text("unpushed\n")
    _git(fx.wt, "add", "work.txt")
    _git(fx.wt, "commit", "-q", "-m", "unpushed")
    _git(fx.wt, "update-ref", ref, "HEAD")
    _git(fx.wt, "reset", "-q", "--hard", merged)
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps(KEEP_REFS)
    assert _git(fx.wt, "rev-parse", ref)


def test_a_per_worktree_ref_of_another_worktree_does_not_keep_this_one(fx: Fixture) -> None:
    _git(fx.repo, "update-ref", "refs/worktree/primary-only", "HEAD")
    assert _git(fx.wt, "for-each-ref", "refs/worktree") == ""
    assert fx.verdict() == "would"


def test_a_shared_branch_ref_does_not_keep(fx: Fixture) -> None:
    _git(fx.wt, "branch", "other")
    assert fx.verdict() == "would"


def test_a_git_failure_reading_per_worktree_refs_keeps(fx: Fixture) -> None:
    _silent_git_failure(fx, "for-each-ref refs/worktree refs/bisect refs/rewritten")
    fx.keeps("could not read per-worktree refs")


# --- P2-c: a stale core.fsmonitor ----------------------------------------------------------------------------


def test_a_stale_fsmonitor_cannot_hide_a_tracked_edit(fx: Fixture, tmp_path: Path) -> None:
    """A hook that answers "nothing changed" makes plain `git status` call an edited tracked file clean."""
    (fx.wt / "notes.txt").write_text("v1\n")
    fx.commit("notes.txt")
    hook = tmp_path / "fsmonitor-hook.sh"
    hook.write_text("#!/bin/bash\nprintf 'tok\\0'\n")
    hook.chmod(0o755)
    _git(fx.repo, "config", "core.fsmonitor", str(hook))
    _git(fx.wt, "status", "--porcelain")  # records the token and marks every file as unchanged
    (fx.wt / "notes.txt").write_text("v2 unsaved edit\n")
    assert _git(fx.wt, "status", "--porcelain") == "", "precondition: the stale hook hides the edit"
    fx.keeps(KEEP_DIRTY)
    assert (fx.wt / "notes.txt").read_text() == "v2 unsaved edit\n"


# --- P2-d: DRY_RUN fails closed ------------------------------------------------------------------------------


def _run_with_dry_run(fx: Fixture, value: str | None) -> str:
    """The real script with DRY_RUN set to `value` exactly (None: not set at all)."""
    env = {k: v for k, v in os.environ.items() if k != "DRY_RUN"}
    env.update(PATH=f"{fx.bindir}{os.pathsep}{os.environ['PATH']}", PROJECTS_ROOT=str(fx.root))
    env.update(GH_MERGED="\n".join(fx.merged), GH_OPEN="", GH_FAIL="")
    if value is not None:
        env["DRY_RUN"] = value
    proc = subprocess.run(["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout + proc.stderr


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "dry", "", " 0", "00", "false", "no"])
def test_any_dry_run_value_other_than_exactly_zero_only_prints(fx: Fixture, value: str) -> None:
    out = _run_with_dry_run(fx, value)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("would"), out
    assert fx.wt.exists()


@pytest.mark.parametrize("value", [None, "0"], ids=["unset", "zero"])
def test_dry_run_unset_or_exactly_zero_removes_for_real(fx: Fixture, value: str | None) -> None:
    out = _run_with_dry_run(fx, value)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("removed"), out
    assert not fx.wt.exists()


def test_dry_run_is_documented_as_fail_closed_in_the_header() -> None:
    header = "\n".join(SCRIPT.read_text().splitlines()[:10])
    assert "DRY_RUN=0" in header and "unset" in header, header


# --- P2-e: a worktree list that cannot be parsed -------------------------------------------------------------


def _worktree_with_newline_in_its_path(fx: Fixture) -> Path:
    """A real worktree whose directory name is `<fx.wt name>\\nx`: porcelain prints that path across two lines,
    so a line-based parser reads the first line as the path of `fx.wt` itself."""
    odd = fx.wt.parent / (fx.wt.name + "\nx")
    _git(fx.repo, "worktree", "add", "-q", "-b", "feat/nl", str(odd))
    fx.merged = [f"feat/nl {_git(odd, 'rev-parse', 'HEAD')}"]  # only the odd one is merged; fx.wt is on feat/x
    return odd


def test_a_newline_in_a_worktree_path_cannot_make_another_worktree_go_under_the_wrong_label(fx: Fixture) -> None:
    _worktree_with_newline_in_its_path(fx)
    out = fx.run(dry=False)
    assert fx.wt.exists(), out  # feat/x was never merged: nothing may remove it, whatever label is printed
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""
    assert "removed" not in out, out
    assert f"keep    {fx.repo}  (" in out and "unrecognised line" in out, out


def test_an_unparseable_worktree_list_skips_the_whole_repo_not_just_the_odd_worktree(fx: Fixture) -> None:
    _worktree_with_newline_in_its_path(fx)
    fx.merged.append(f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}")  # now a clean, merged, removable fx.wt too
    out = fx.run(dry=False)
    assert fx.wt.exists(), out


def test_every_known_porcelain_key_is_accepted(fx: Fixture) -> None:
    """A locked worktree prints `locked`, a bare repo `bare`, a detached one `detached`: none is junk."""
    det = fx.wt.parent / "det"
    _git(fx.repo, "worktree", "add", "-q", "--detach", str(det))
    _git(fx.repo, "worktree", "lock", "--reason", "on a usb stick", str(det))
    porcelain = _git(fx.repo, "worktree", "list", "--porcelain")
    assert "detached" in porcelain and "locked on a usb stick" in porcelain
    assert fx.verdict(dry=False) == "removed"


def test_awk_failing_in_the_worktree_list_check_skips_the_repo(fx: Fixture) -> None:
    fx.shim("awk", 'case "$*" in *prunable*) exit 2 ;; esac\nexec "' + _real("awk") + '" "$@"')
    out = fx.run(dry=False)
    assert fx.wt.exists(), out
    assert f"keep    {fx.repo}  (" in out and "could not check the worktree list" in out, out
