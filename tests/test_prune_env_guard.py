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
        _git(self.wt, "add", "-f", *files)
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


def test_ignored_nested_repo_without_env_files_is_removable(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", readme="nothing secret\n")
    assert fx.verdict() == "would"


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


def test_worktree_with_an_initialized_submodule_is_left_to_gits_own_refusal(fx: Fixture) -> None:
    """The scan does not look inside submodules; `git worktree remove` refuses them, which is all that
    protects an ignored .env inside one. This pins that refusal."""
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
    _git(fx.wt, *allow, "submodule", "update", "--init", "-q")
    (fx.wt / "sub" / ".env").write_text("SUBSECRET=1\n")
    fx.merged = [f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}"]
    assert fx.verdict(dry=False) == "FAILED"
    assert (fx.wt / "sub" / ".env").read_text() == "SUBSECRET=1\n"


def test_script_parses_under_the_system_bash() -> None:
    subprocess.run(["/bin/bash", "-n", str(SCRIPT)], check=True)
