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

import json
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
KEEP_UNPROVEN = "holds ignored files that are not proven regenerable"
FAULT_LINE = "exit 1: at least one check could not complete"
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
        self.last_rc = 0
        self.last_out = ""

    # --- running the script -------------------------------------------------------------------------------
    def run(
        self,
        dry: bool = True,
        env: dict[str, str | None] | None = None,
        timeout: int = 60,
        expect_fault: bool | None = None,
    ) -> str:
        """Run the script. `expect_fault=True` asserts exit 1 AND the fault line together; `False` asserts exit 0 and
        no fault line. Left as None only the two are checked against each other, which a dropped `note_fault` passes
        (exit 0, no fault line), so every test that pins a fault passes True."""
        full: dict[str, str | None] = {
            **os.environ,
            "PATH": f"{self.bindir}{os.pathsep}{os.environ['PATH']}",
            "PROJECTS_ROOT": str(self.root),
            "DRY_RUN": "1" if dry else "0",
            "GH_MERGED": "\n".join(self.merged),
            "GH_OPEN": "\n".join(self.open),
            "GH_FAIL": self.gh_fail,
            "PRUNE_ALLOW_DELETE": "1",  # deletion is off by default (round 9); the suite exercises the deleting path
            **(env or {}),
        }
        full = {k: v for k, v in full.items() if v is not None}  # a None value unsets the variable
        proc = subprocess.run(
            ["/bin/bash", str(SCRIPT)], capture_output=True, text=True, env=full, timeout=timeout
        )
        # exit status 1 exactly when the script says a check could not complete; every policy keep exits 0
        faulted = FAULT_LINE in proc.stdout
        assert proc.returncode == (1 if faulted else 0), proc.stdout + proc.stderr
        if expect_fault is not None:
            assert (proc.returncode == 1 and faulted) == expect_fault, (
                f"expected {'a fault (exit 1 and the fault line)' if expect_fault else 'no fault (exit 0)'}, "
                f"got exit {proc.returncode}, fault line {'present' if faulted else 'absent'}:\n{proc.stdout}{proc.stderr}"
            )
        self.last_rc = proc.returncode
        self.last_out = proc.stdout + proc.stderr
        return self.last_out

    @staticmethod
    def line(out: str, wt: Path) -> str | None:
        return next((ln for ln in out.splitlines() if f"{wt}  (" in ln), None)

    # --- the quarantine hold --------------------------------------------------------------------------------
    @property
    def qbase(self) -> Path:
        return self.root / ".prune-quarantine"

    def held(self) -> list[Path]:
        return sorted(p for p in self.qbase.glob("*/*") if p.is_dir()) if self.qbase.exists() else []

    def age(self, entry: Path) -> Path:
        """Move a held worktree into a long-expired timestamp directory, the way git itself would move it."""
        old = self.qbase / "2000-01-01T000000Z"
        old.mkdir(parents=True, exist_ok=True)
        dest = old / entry.name
        _git(entry, "worktree", "move", str(entry), str(dest))
        return dest

    def purge_run(
        self, wt: Path, env: dict[str, str] | None = None, expect_fault: bool | None = None
    ) -> tuple[str, Path]:
        """Age every held worktree past the cutoff and do a real run: (its output, `wt`'s aged entry)."""
        entries = self.held()
        assert entries, self.last_out
        aged = [self.age(entry) for entry in entries]
        mine = [p for p in aged if p.name.endswith(f"--{wt.name}")]
        assert len(mine) == 1, (aged, self.last_out)
        return self.run(False, env, expect_fault=expect_fault), mine[0]

    def verdict(self, dry: bool = True, wt: Path | None = None, env: dict[str, str] | None = None) -> str:
        """The first word printed for the worktree: keep | would | quarantined | removed | FAILED.

        A real run only quarantines; `removed` is what the purge pass prints once the hold has expired, so a real
        run that quarantines is followed by the aged purge run and its verdict is returned."""
        wt = wt or self.wt
        out = self.run(dry, env)
        line = self.line(out, wt)
        assert line is not None, f"script printed nothing for the worktree:\n{out}"
        word = line.split()[0]
        if dry or word != "quarantined":
            return word
        out, aged = self.purge_run(wt, env)
        line = self.line(out, aged)
        assert line is not None, f"the purge pass printed nothing for the held worktree:\n{out}"
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
    tmp = tmp_path.resolve()  # git prints realpaths; /var is a symlink to /private/var on macOS
    root = tmp / "pro jects"  # a space in the root: every path below must survive being quoted
    base = root  # round 9: a worktree outside the root is refused, so the fixture's worktrees live under it
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

    bindir = tmp / "bin"
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


def test_an_ignored_file_that_is_not_proven_regenerable_keeps_the_worktree(fx: Fixture) -> None:
    """Round 7 (option B) reverses the round 1-6 rule that only secret NAMES keep a worktree: no name list is
    complete (x.p8, up.jks, prod.tfvars were all deleted), so anything not under a regenerable directory keeps."""
    (fx.wt / "only-copy").write_text("not an .env file\n")
    fx.keeps(KEEP_UNPROVEN)


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
    """The link points into the worktree's own git admin dir, which `git worktree remove` deletes with it. The target
    is FETCH_HEAD, a name the admin-dir allowlist accepts, so the .env rule is what keeps the tree here."""
    admin = Path(_git(fx.wt, "rev-parse", "--git-dir"))
    (admin / "FETCH_HEAD").write_text("ADMIN_SECRET=1\n")
    (fx.wt / ".env").symlink_to(admin / "FETCH_HEAD")


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
    assert (Path(_git(fx.wt, "rev-parse", "--git-dir")) / "FETCH_HEAD").read_text() == "ADMIN_SECRET=1\n"


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
    fx.shim("find", f'for a in "$@"; do [ "$a" = -iname ] && exit 1; done\nexec "{_real("find")}" "$@"')
    fx.keeps("could not scan vendor/lib/ (find exit 1)")


def test_failing_head_does_not_change_the_nested_repo_verdict(fx: Fixture) -> None:
    fx.nested_repo("vendor/lib", **{".env": "unique\n"})
    fx.shim("head", "exit 1")
    fx.keeps()


def test_scan_killed_mid_way_keeps(fx: Fixture) -> None:
    # the first `rm` is the scan's own, inside its command substitution; killing its parent kills the whole scan
    # with status 137. Later calls (the exit trap's) are the real rm, or the script itself would be killed.
    marker = fx.bindir / "rm.killed"
    fx.shim("rm", f'[ -e "{marker}" ] && exec "{_real("rm")}" "$@"\ntouch "{marker}"\nkill -9 $PPID')
    fx.keeps("scan failed, exit 137", real=False)
    assert fx.last_rc == 1


def _first_mktemp_is_real(fx: Fixture, then: str) -> None:
    """The script's own bookkeeping file is the first mktemp; the scan's list files come after it."""
    marker = fx.bindir / "mktemp.used"
    fx.shim("mktemp", f'[ -e "{marker}" ] || {{ touch "{marker}"; exec "{_real("mktemp")}" "$@"; }}\n{then}')


def test_mktemp_failure_keeps(fx: Fixture) -> None:
    _first_mktemp_is_real(fx, "exit 1")
    fx.keeps("could not create a temp file", real=False)
    assert fx.last_rc == 1


def test_mktemp_failing_at_start_stops_the_run_nonzero(fx: Fixture) -> None:
    fx.shim("mktemp", "exit 1")
    proc = subprocess.run(
        ["/bin/bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{fx.bindir}{os.pathsep}{os.environ['PATH']}", "PROJECTS_ROOT": str(fx.root)},
    )
    assert proc.returncode == 1 and "could not create a temp file" in proc.stdout, proc.stdout + proc.stderr
    assert fx.wt.exists() and not fx.held()


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
    _first_mktemp_is_real(fx, f'echo "{target}"')
    (fx.wt / ".env").write_text("unique\n")  # would be removed if the unwritable list were taken as empty
    fx.keeps("could not scan the git dir", real=False)  # the first scan to write into the list stops the run
    assert fx.last_rc == 1


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
    fx.keeps("PR merged but worktree dirty")  # round 9: status runs on a throwaway index, so the flag hides nothing
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


def _discovery_fails(fx: Fixture, args: str, mode: str) -> None:
    """`silent`: git prints nothing and fails. `prints-then-dies`: the real git prints its valid answer, then exits
    137, so no later check (`$gd = .git`, the worktree count) can supply the keep: only the exit-status test can."""
    if mode == "silent":
        fx.git_fails(args)
    else:
        fx.shim("git", f'case " $* " in *" {args} "*) "{_real("git")}" "$@"; exit 137 ;; esac\nexec "{_real("git")}" "$@"')


@pytest.mark.parametrize("mode", ["silent", "prints-then-dies"])
def test_failing_worktree_discovery_skips_the_repo_with_a_reason(fx: Fixture, mode: str) -> None:
    _discovery_fails(fx, "rev-parse --git-dir", mode)
    out = fx.run(dry=False)
    assert f"skip {fx.repo}: git rev-parse failed" in out
    assert fx.last_rc == 1 and FAULT_LINE in out  # a skipped repo is a fault, not a clean run
    assert fx.line(out, fx.wt) is None and fx.held() == [] and fx.wt.exists()


@pytest.mark.parametrize("mode", ["silent", "prints-then-dies"])
def test_failing_worktree_list_skips_the_repo_with_a_reason(fx: Fixture, mode: str) -> None:
    _discovery_fails(fx, "worktree list --porcelain", mode)
    out = fx.run(dry=False)
    assert f"skip {fx.repo}: could not list worktrees" in out
    assert fx.last_rc == 1 and FAULT_LINE in out
    assert fx.line(out, fx.wt) is None and fx.held() == [] and fx.wt.exists()


def test_a_locked_worktree_is_kept_by_policy(fx: Fixture) -> None:
    """Round 7 let git's own refusal stop a locked worktree; round 8 keeps it before touching it (`locked` is not a
    file git creates for a clean worktree), so the run exits 0 and nothing is moved."""
    _git(fx.repo, "worktree", "lock", str(fx.wt))
    fx.keeps("its git directory holds locked")
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_a_refused_quarantine_move_is_reported_and_keeps_everything(fx: Fixture) -> None:
    fx.git_fails("worktree move")
    out = fx.run(dry=False)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("FAILED") and "could not move" in line, out
    assert fx.last_rc == 1 and fx.wt.exists() and not fx.held()
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_a_refused_purge_removal_is_reported_and_keeps_the_branch(fx: Fixture) -> None:
    out = fx.run(dry=False)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    fx.git_fails("worktree remove")
    out, aged = fx.purge_run(fx.wt)
    aside = Path(f"{aged}.purge")
    line = fx.line(out, aside)
    assert line is not None and line.startswith("FAILED"), out
    assert fx.last_rc == 1 and aside.exists()
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


def test_worktree_with_an_initialized_submodule_is_kept_by_policy(fx: Fixture) -> None:
    """Round 7 left an initialized submodule to git's refusal to remove it (a FAILED line, exit 1). Round 8 keeps
    it before touching it: its git dir holds modules/<name>, which git does not create for a clean worktree."""
    _with_submodule(fx)
    (fx.wt / "sub" / ".env").write_text("SUBSECRET=1\n")
    fx.keeps("its git directory holds modules/")
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
    """`read -d ''` without -r treats `\\<NUL>` as an escaped delimiter and fuses two records (bash 3.2 and 5).
    Round 7: the fused record `dist/-adocs.txt` sits under dist/, so a swallowed `docs.txt` would be removed."""
    _marked(fx)
    fx.exclude("docs.txt")
    (fx.wt / "tree" / "-a\\").write_text("x\n")  # sorts directly before docs.txt
    (fx.wt / "docs.txt").write_text("unique\n")
    fx.keeps(KEEP_UNPROVEN)


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
    fx.keeps("PR merged but worktree dirty")  # round 9: the throwaway index reads content, flags hide nothing


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
    fx.keeps("PR merged but worktree dirty")  # round 9: the throwaway index reads content, flags hide nothing
    assert (fx.wt / "a.conf").read_text() == "LOCAL_SECRET=9\n"


@pytest.mark.parametrize("flags", [["--assume-unchanged"], ["--skip-worktree"], ["--skip-worktree", "--assume-unchanged"]])
def test_an_index_flag_alone_still_keeps_with_its_own_reason(fx: Fixture, flags: list[str]) -> None:
    """The flag arm of the admin scan outlived round 9's content-level status check: a flagged file with no edit is
    clean to every status, and the flag is still the sign that somebody hid something from git."""
    (fx.wt / "a.conf").write_text("TEMPLATE=1\n")
    fx.commit("a.conf")
    for flag in flags:
        _git(fx.wt, "update-index", flag, "a.conf")
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps("assume-unchanged or skip-worktree")


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
    line = fx.line(out, fx.wt)  # control: the sweep really ran and acted on the worktree
    assert line is not None and line.startswith("quarantined"), out


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
    # BSD mktemp ignores $TMPDIR when called without a template, so a TMPDIR scratch dir would watch nothing on macOS:
    # a shim puts every temp file the script makes in the scratch dir, whatever the platform
    made = fx.bindir / "mktemp.calls"
    fx.shim("mktemp", f'echo x >>"{made}"; exec "{_real("mktemp")}" "{scratch}/tmp.XXXXXX"')
    if verdict_run == "dry":
        assert fx.verdict() == "would"
    else:  # control: the scan, the rescan and the purge scan all ran and the tree really went
        assert fx.verdict(dry=False) == "removed"
        assert not fx.wt.exists()
    assert len(made.read_text().split()) >= 2  # the shim was used: the script's own file and at least one scan list
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


def _marked(fx: Fixture, top: str = "tree") -> None:
    """An ignored cache directory (CACHEDIR.TAG, standard signature): the one marker whose spec makes the WHOLE directory
    regenerable, so a file of any name under it is proven and only the rule under test can keep it. A venv or npm
    marker proves only what its tool recorded (round 9), so it cannot play this part."""
    fx.exclude(f"{top}/")
    (fx.wt / top).mkdir(parents=True, exist_ok=True)
    (fx.wt / top / "CACHEDIR.TAG").write_text(CACHEDIR_TAG)


def _purged(
    fx: Fixture, env: dict[str, str] | None = None, expect_fault: bool | None = None
) -> tuple[str, Path]:
    """A real run that quarantines the worktree, then the aged purge run: (the purge run's output, the aged entry).
    `expect_fault` applies to the purge run."""
    out = fx.run(False, env)
    assert (fx.line(out, fx.wt) or "").startswith("quarantined"), out
    return fx.purge_run(fx.wt, env, expect_fault)


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
    link = fx.root.parent / "root-link"
    link.symlink_to(fx.root)
    fx.merged.append(f"main {_git(fx.repo, 'rev-parse', 'HEAD')}")
    out = fx.run(dry=False, env={"PROJECTS_ROOT": str(link)})
    assert fx.line(out, fx.repo) is None, out
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("quarantined"), out
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
    _marked(fx)  # a proven-regenerable directory, so only the nested-repo rule can keep this
    (fx.wt / "tree" / "lib" / ".git").mkdir(parents=True)
    (fx.wt / "tree" / "lib" / "a").write_text("x\n")
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
    """A lookalike path next to an (uninitialized) gitlink directory is still a nested repo."""
    _with_submodule(fx, init=False)
    fx.nested_repo("sub-extra/lib", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_nested_repo_whose_path_is_a_prefix_of_a_submodule_path_keeps(fx: Fixture) -> None:
    """`su` is a substring of the gitlink path `sub`, but it is a different directory and a nested repo."""
    _with_submodule(fx, init=False)
    fx.nested_repo("su", readme="x\n")
    fx.keeps(KEEP_GIT)


def test_names_that_only_look_like_a_git_directory_do_not_keep(fx: Fixture) -> None:
    _marked(fx)
    for rel in ("tree/.github/ci.yml", "tree/pkg.git", "tree/.gitkeep", "tree/not.git/x"):
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
    """Under a marked tree (regenerable) so only the secret-NAME rule could keep these: it must not match a lookalike."""
    _marked(fx)
    _ignored(fx, f"tree/{rel}")
    assert fx.verdict() == "would"


# --- secret names apply everywhere, package trees included (round 7 deletes the round 5 exemption) -----------

IN_PACKAGE_TREE = [
    "node_modules/pkg/test/server.pem",
    "node_modules/pkg/prod.key",  # reproduced in review: removed on 3b3b76f
    "secrets/venv/prod.pem",  # reproduced in review: a directory named venv anywhere exempted the whole path
    "node_modules/.bin/.npmrc",
    "node_modules/x/id_ed25519",
    "node_modules/x/sample.env",
    "a/node_modules/b/cert.pfx",
    ".venv/lib/certs/ca.key",
    "venv/lib/id_rsa",
    "lib/python3.12/site-packages/certifi/cacert.pem",
]


@pytest.mark.parametrize("rel", IN_PACKAGE_TREE)
def test_secret_named_file_inside_a_package_tree_keeps(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel)
    fx.keeps(KEEP_SECRET)


# every one of these was deleted from a clean merged worktree on 3b3b76f
UNLISTED_NAMES = ["x.p8", "up.jks", "prod.keystore", "prod.tfvars", "app.env.local", ".git-credentials", "credentials.json"]


@pytest.mark.parametrize("rel", UNLISTED_NAMES)
def test_secret_files_the_name_list_did_not_know_keep(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel, "not a real secret\n")
    fx.keeps(KEEP_SECRET)


@pytest.mark.parametrize("rel", ["notes/todo.md", "data.sqlite", "scratch.py", "Makefile.local", "keys/dev"])
def test_any_other_ignored_file_outside_a_regenerable_directory_keeps(fx: Fixture, rel: str) -> None:
    """No name list is complete; whatever is not proven regenerable is unproven data."""
    _ignored(fx, rel)
    fx.keeps(KEEP_UNPROVEN)


def _npm_lock(*keys: str) -> str:
    """node_modules/.package-lock.json as npm writes it: one pretty-printed key per installed package."""
    return json.dumps({"lockfileVersion": 3, "packages": {k: {"version": "1.0.0"} for k in keys}}, indent=2) + "\n"


CACHEDIR_TAG = "Signature: 8a477f597d28d172789f06886806bc55\n# This file is a cache directory tag.\n"


@pytest.mark.parametrize(
    ("marker", "rel"),
    [
        ("node_modules/.package-lock.json", "node_modules/pkg/index.js"),
        ("a/node_modules/.package-lock.json", "a/node_modules/pkg/index.js"),
        (".venv/pyvenv.cfg", ".venv/bin/activate"),  # the scaffold files a venv creates; its other files need a RECORD
        ("a/venv/pyvenv.cfg", "a/venv/bin/activate"),
        ("myenv/pyvenv.cfg", "myenv/bin/activate"),  # a venv is a venv whatever it is called
        (".pytest_cache/CACHEDIR.TAG", ".pytest_cache/v/cache/nodeids"),
        (".mypy_cache/CACHEDIR.TAG", ".mypy_cache/3.12/x.json"),
        ("target/CACHEDIR.TAG", "target/debug/x"),
    ],
)
def test_each_marker_proven_directory_alone_does_not_keep(fx: Fixture, marker: str, rel: str) -> None:
    """The control for the marker rule: each documented marker really proves a tree removable (and not just never reached)."""
    if marker.endswith("CACHEDIR.TAG"):
        text = CACHEDIR_TAG
    elif marker.endswith(".package-lock.json"):
        text = _npm_lock("node_modules/pkg")  # npm's own record, keyed relative to the project that owns node_modules
    else:
        text = "home = /usr/bin\n"
    _ignored(fx, marker, text)
    _ignored(fx, rel)
    assert fx.verdict() == "would"
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()


def test_a_pycache_file_beside_its_tracked_source_does_not_keep(fx: Fixture) -> None:
    (fx.wt / "src").mkdir()
    (fx.wt / "src" / "m.py").write_text("x = 1\n")
    fx.commit("src/m.py")
    _ignored(fx, "src/__pycache__/m.cpython-312.pyc")
    assert fx.verdict(dry=False) == "removed"


@pytest.mark.parametrize(
    "rel",
    [
        "dist/out.js",  # reversed in round 8: a directory NAME proves nothing
        "build/out.js",
        "web/.next/cache/x",
        ".turbo/log",
        "coverage/lcov.info",
        ".pytest_cache/v/cache/nodeids",  # no CACHEDIR.TAG written
        ".ruff_cache/0.1/x",
        ".venv/lib/x.py",  # no pyvenv.cfg
        "lib/site-packages/pkg/mod.py",
        "node_modules/pkg/index.js",  # no npm/yarn/pnpm marker
        "src/__pycache__/m.cpython-312.pyc",  # no source beside it
    ],
)
def test_a_directory_name_alone_never_proves_a_tree_regenerable(fx: Fixture, rel: str) -> None:
    _ignored(fx, rel)
    fx.keeps(KEEP_UNPROVEN)


def test_a_cachedir_tag_with_the_wrong_signature_proves_nothing(fx: Fixture) -> None:
    _ignored(fx, "cache/CACHEDIR.TAG", "Signature: not-the-standard-one\n")
    _ignored(fx, "cache/x")
    fx.keeps(KEEP_UNPROVEN)


@pytest.mark.parametrize("marker", ["pyvenv.cfg", "CACHEDIR.TAG", "node_modules/.package-lock.json"])
def test_a_symlinked_marker_proves_nothing(fx: Fixture, marker: str) -> None:
    fx.exclude("tree/")
    tree = fx.wt / "tree"
    (tree / "node_modules").mkdir(parents=True)
    real = fx.wt.parent / "real-marker"
    real.write_text(CACHEDIR_TAG)
    (tree / marker).symlink_to(real)
    (tree / "node_modules" / "pkg.js").write_text("x\n")
    fx.keeps(KEEP_UNPROVEN)


def test_worktree_with_only_marked_package_trees_is_still_removed(fx: Fixture) -> None:
    for marker, text, rel in (
        ("node_modules/.package-lock.json", _npm_lock("node_modules/pkg"), "node_modules/pkg/index.js"),
        (".venv/pyvenv.cfg", "home = /usr/bin\n", ".venv/bin/activate"),
    ):
        _ignored(fx, marker, text)
        _ignored(fx, rel)
    assert fx.verdict(dry=False) == "removed"
    assert not fx.wt.exists()


def test_an_allowlisted_name_that_is_a_symlink_is_not_allowlisted(fx: Fixture) -> None:
    """`tree` -> a marked directory holding unique data. git lists a link as one entry (no directory part) and
    never enumerates the target, so reaching the symlink predicate needs a listing through the link: a stale one."""
    fx.exclude("tree")
    (fx.wt.parent / "elsewhere").mkdir()
    (fx.wt.parent / "elsewhere" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (fx.wt.parent / "elsewhere" / "data").write_text("unique\n")
    (fx.wt / "tree").symlink_to(fx.wt.parent / "elsewhere")
    fx.shim("git", 'case " $* " in *" ls-files -z -o "*) printf \'%s\\0\' "tree/data"; exit 0 ;; esac\nexec "' + _real("git") + '" "$@"')
    fx.keeps(KEEP_UNPROVEN)
    assert (fx.wt.parent / "elsewhere" / "data").read_text() == "unique\n"


def test_an_allowlisted_directory_below_a_symlinked_one_is_not_allowlisted(fx: Fixture) -> None:
    """`link/node_modules` where `link` is a symlink to a directory that holds a real, marked node_modules."""
    fx.exclude("link")
    other = fx.wt.parent / "elsewhere"
    (other / "node_modules").mkdir(parents=True)
    (other / "node_modules" / ".package-lock.json").write_text("{}\n")
    (other / "node_modules" / "x.js").write_text("unique\n")
    (fx.wt / "link").symlink_to(other)
    fx.shim("git", 'case " $* " in *" ls-files -z -o "*) printf \'%s\\0\' "link/node_modules/x.js"; exit 0 ;; esac\nexec "' + _real("git") + '" "$@"')
    fx.keeps(KEEP_UNPROVEN)
    assert (other / "node_modules" / "x.js").read_text() == "unique\n"


@pytest.mark.parametrize("name", ["Node_Modules", "NODE_MODULES", "Dist", "BUILD", "Venv"])
def test_an_allowlisted_name_in_another_case_is_not_allowlisted(fx: Fixture, name: str) -> None:
    _ignored(fx, f"{name}/x.js")
    fx.keeps(KEEP_UNPROVEN)


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
        "my_node_modules/x.js",
        "node_modules.bak/x.js",
        "venv2/x.js",
        "not.venv/x.js",
        "site-packages-old/x.js",
        "distribution/x.js",
    ],
)
def test_lookalike_of_a_regenerable_directory_is_not_allowlisted(fx: Fixture, rel: str) -> None:
    """Whole path components only: a directory that merely contains or starts with an allowed name is not one."""
    _ignored(fx, rel)
    fx.keeps(KEEP_UNPROVEN)


def test_one_unproven_file_keeps_even_with_regenerable_ones_beside_it(fx: Fixture) -> None:
    _ignored(fx, "node_modules/pkg/ok.js")
    _ignored(fx, "real.txt")
    fx.keeps(KEEP_UNPROVEN)


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
    fx.keeps(KEEP_SUB)  # and the script still keeps it: the blind spot is covered, not just real


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


def test_an_initialized_submodule_with_an_ignored_file_keeps(fx: Fixture) -> None:
    _with_submodule(fx, init=True)
    fx.keeps("its git directory holds modules/")  # even a clean initialized submodule: nothing is lost by keeping it


def test_a_dangling_git_symlink_does_not_make_a_gitlink_directory_look_initialized(fx: Fixture) -> None:
    """git sees nothing wrong (status clean, `worktree remove` succeeds), so only the scan protects the file."""
    _with_submodule(fx, init=False)
    (fx.wt / "sub" / ".git").symlink_to("/nonexistent-gitdir-for-test")
    (fx.wt / "sub" / "data.txt").write_text("only copy\n")
    assert _git(fx.wt, "status", "--porcelain", "-uall") == ""
    fx.keeps(KEEP_SUB)
    assert (fx.wt / "sub" / "data.txt").read_text() == "only copy\n"


def test_a_git_symlink_to_a_real_directory_that_is_not_a_repo_is_left_to_gits_refusal(fx: Fixture) -> None:
    """Control: `-e` is true, so the loop skips it; git itself fails the status and the tree is kept."""
    _with_submodule(fx, init=False)
    target = fx.wt.parent / "not-a-repo"
    target.mkdir()
    (fx.wt / "sub" / ".git").symlink_to(target)
    (fx.wt / "sub" / "data.txt").write_text("only copy\n")
    fx.keeps("could not read git status")


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
    _marked(fx)  # regenerable: only the nested-repo rule can keep it
    _git(fx.wt / "tree", "init", "-q", "--bare", "lib.git")
    assert not (fx.wt / "tree" / "lib.git" / ".git").exists()
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps(KEEP_GIT)


def test_a_minimal_bare_layout_keeps(fx: Fixture) -> None:
    _marked(fx)  # regenerable: only the nested-repo rule can keep it
    bare = fx.wt / "tree" / "lib"
    (bare / "objects").mkdir(parents=True)
    (bare / "refs").mkdir()
    (bare / "HEAD").write_text("ref: refs/heads/main\n")
    fx.keeps(KEEP_GIT)


@pytest.mark.parametrize("spelling", ["OBJECTS", "Objects"])
def test_a_bare_layout_with_objects_spelled_in_another_case_keeps(fx: Fixture, spelling: str) -> None:
    """APFS is case-insensitive: git opens `OBJECTS` as `objects`, so the name match must not be exact."""
    _marked(fx)  # regenerable: only the nested-repo rule can keep it
    bare = fx.wt / "tree" / "lib"
    (bare / spelling).mkdir(parents=True)
    (bare / "refs").mkdir()
    (bare / "HEAD").write_text("ref: refs/heads/main\n")
    fx.keeps(KEEP_GIT)


@pytest.mark.parametrize(
    "missing",
    ["HEAD", "refs", "objects-as-file"],
    ids=["no-HEAD", "no-refs", "objects-is-a-file"],
)
def test_a_directory_that_only_partly_looks_like_a_bare_repo_does_not_keep(fx: Fixture, missing: str) -> None:
    _marked(fx)  # regenerable: only the nested-repo rule can keep it
    bare = fx.wt / "tree" / "lib"
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
def test_dry_run_unset_or_exactly_zero_acts_for_real(fx: Fixture, value: str | None) -> None:
    out = _run_with_dry_run(fx, value)
    line = fx.line(out, fx.wt)
    assert line is not None and line.startswith("quarantined"), out
    assert not fx.wt.exists() and len(fx.held()) == 1


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


def test_a_primary_marked_bare_prints_a_bare_line_that_is_accepted(fx: Fixture) -> None:
    _git(fx.repo, "config", "core.bare", "true")
    assert "\nbare\n" in _git(fx.repo, "worktree", "list", "--porcelain")
    assert fx.verdict(dry=False) == "removed"


def test_awk_failing_in_the_worktree_list_check_skips_the_repo(fx: Fixture) -> None:
    fx.shim("awk", 'case "$*" in *prunable*) exit 2 ;; esac\nexec "' + _real("awk") + '" "$@"')
    out = fx.run(dry=False)
    assert fx.wt.exists(), out
    assert f"keep    {fx.repo}  (" in out and "could not check the worktree list" in out, out


# =============================================================================================================
# Round 7 (option B): keep unless PROVEN regenerable, secret names everywhere, branch deleted by compare-and-
# delete, a HEAD reflog that no ref reaches, and a bare repo whose objects/ is a symlink.
# Each rule has a test that fails on 3b3b76f (see plans/2026-11-16-prune-env-guard-fail-open.md, round 7).
# =============================================================================================================

KEEP_REFLOG = "a reflog holds commits no ref reaches"


@pytest.mark.parametrize("rel", UNLISTED_NAMES)
def test_new_secret_names_keep_even_inside_a_regenerable_directory(fx: Fixture, rel: str) -> None:
    _marked(fx)
    _ignored(fx, f"tree/{rel}", "not a real secret\n")
    fx.keeps(KEEP_SECRET)


def test_a_tracked_env_symlink_to_an_ignored_file_keeps_and_the_file_survives(fx: Fixture) -> None:
    (fx.wt / "only-copy").write_text("PRECIOUS=1\n")
    (fx.wt / ".env").symlink_to("only-copy")
    fx.commit(".env")  # the link is tracked; its target is ignored and exists nowhere else
    assert _git(fx.wt, "status", "--porcelain") == ""
    fx.keeps("holds an .env symlink")
    assert (fx.wt / "only-copy").read_text() == "PRECIOUS=1\n"


@pytest.mark.parametrize("name", [".env", "notes.txt"])
def test_an_uninitialized_submodule_directory_holding_a_unique_file_keeps_and_the_file_survives(
    fx: Fixture, name: str
) -> None:
    _with_submodule(fx, init=False)
    (fx.wt / "sub" / name).write_text("UNIQUE=1\n")
    fx.keeps(KEEP_SUB)
    assert (fx.wt / "sub" / name).read_text() == "UNIQUE=1\n"


# --- the bare-repo layout with a symlinked objects/ ------------------------------------------------------------


def test_a_bare_layout_whose_objects_is_a_symlink_to_a_shared_store_keeps(fx: Fixture) -> None:
    """`git clone --shared`-style repos and linked object stores make objects/ a symlink; `-type d` missed it."""
    _marked(fx)
    store = fx.wt.parent / "shared-objects"
    store.mkdir()
    bare = fx.wt / "tree" / "lib"
    (bare / "refs").mkdir(parents=True)
    (bare / "objects").symlink_to(store)
    (bare / "HEAD").write_text("ref: refs/heads/main\n")
    fx.keeps(KEEP_GIT)


def test_a_dangling_objects_symlink_without_a_bare_layout_does_not_keep(fx: Fixture) -> None:
    _marked(fx)
    (fx.wt / "tree" / "lib").mkdir(parents=True)
    (fx.wt / "tree" / "lib" / "objects").symlink_to("nowhere")
    assert fx.verdict() == "would"


# --- the branch is deleted by compare-and-delete -----------------------------------------------------------------


def _move_the_branch_after_the_worktree_is_removed(fx: Fixture) -> str:
    """A git shim that moves the branch to another commit as soon as `worktree remove` has finished: the
    window between the scan and the branch deletion, in which somebody commits to or resets the branch."""
    other = _git(fx.repo, "commit-tree", "HEAD^{tree}", "-m", "somebody else's commit")
    fx.shim(
        "git",
        f'case " $* " in *" worktree remove "*)\n'
        f'  "{_real("git")}" "$@"; rc=$?\n'
        f'  "{_real("git")}" -C "{fx.repo}" update-ref refs/heads/{BRANCH} {other}; exit $rc ;;\n'
        f'esac\nexec "{_real("git")}" "$@"',
    )
    return other


def test_a_branch_moved_after_the_scan_is_kept_and_reported(fx: Fixture) -> None:
    other = _move_the_branch_after_the_worktree_is_removed(fx)
    out, aged = _purged(fx)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("removed"), out
    assert f"kept    branch {BRANCH} of {fx.repo}" in out and f"it is now {other}" in out, out
    assert _git(fx.repo, "rev-parse", f"refs/heads/{BRANCH}") == other


def test_a_failing_branch_deletion_is_reported_not_swallowed(fx: Fixture) -> None:
    fx.git_fails("update-ref -d")
    out, aged = _purged(fx)
    line = fx.line(out, aged)
    assert line is not None and line.startswith("removed"), out
    assert fx.last_rc == 1
    assert f"kept    branch {BRANCH} of {fx.repo}  (git update-ref -d failed)" in out, out
    assert _git(fx.repo, "branch", "--list", BRANCH) != ""


def test_the_branch_config_section_goes_with_the_branch(fx: Fixture) -> None:
    """`branch -D` removed branch.<name>.*; update-ref -d does not, so the script must."""
    _git(fx.repo, "config", f"branch.{BRANCH}.remote", "origin")
    _git(fx.repo, "config", f"branch.{BRANCH}.merge", f"refs/heads/{BRANCH}")
    out, _aged = _purged(fx)
    assert "note" not in out and "kept    branch" not in out, out
    assert _git(fx.repo, "branch", "--list", BRANCH) == ""
    assert subprocess.run(
        ["git", "-C", str(fx.repo), "config", "--get-regexp", f"^branch\\.{BRANCH}\\."], capture_output=True
    ).returncode == 1


def test_a_branch_without_a_config_section_is_deleted_without_a_note(fx: Fixture) -> None:
    out, _aged = _purged(fx)
    assert "note" not in out and "kept    branch" not in out, out
    assert _git(fx.repo, "branch", "--list", BRANCH) == ""


def test_a_failing_config_cleanup_is_reported(fx: Fixture) -> None:
    _git(fx.repo, "config", f"branch.{BRANCH}.remote", "origin")
    fx.git_fails("config --remove-section")
    out, _aged = _purged(fx)
    assert f"note    {fx.repo}: could not remove the branch.{BRANCH} config section" in out, out
    assert _git(fx.repo, "branch", "--list", BRANCH) == ""


# --- the HEAD reflog ---------------------------------------------------------------------------------------------


def _orphan_commit_in_the_reflog(fx: Fixture) -> str:
    """Commit in the worktree, then reset the branch back: the commit stays in the worktree's HEAD reflog only."""
    keep = _git(fx.wt, "rev-parse", "HEAD")
    _git(fx.wt, "commit", "-q", "--allow-empty", "-m", "work nobody pushed")
    orphan = _git(fx.wt, "rev-parse", "HEAD")
    _git(fx.wt, "reset", "-q", "--hard", keep)
    assert _git(fx.wt, "status", "--porcelain") == "" and _git(fx.wt, "rev-parse", "HEAD") == keep
    return orphan


def test_a_commit_only_the_head_reflog_remembers_keeps_and_survives(fx: Fixture) -> None:
    orphan = _orphan_commit_in_the_reflog(fx)
    fx.keeps(KEEP_REFLOG)
    _git(fx.repo, "cat-file", "-e", orphan)  # exits non-zero if the commit is gone


def test_an_amended_commit_keeps_the_worktree(fx: Fixture) -> None:
    """The pre-amend commit is no ref's ancestor any more; it lives in the reflog and nowhere else."""
    _git(fx.wt, "commit", "-q", "--allow-empty", "-m", "first try")
    _git(fx.wt, "commit", "-q", "--amend", "--allow-empty", "-m", "second try")
    fx.merged = [f"{BRANCH} {_git(fx.wt, 'rev-parse', 'HEAD')}"]
    fx.keeps(KEEP_REFLOG)


def test_reflog_commits_that_a_branch_reaches_do_not_keep(fx: Fixture) -> None:
    (fx.wt / "a.txt").write_text("a\n")
    fx.commit("a.txt")
    (fx.wt / "b.txt").write_text("b\n")
    fx.commit("b.txt")
    assert fx.verdict(dry=False) == "removed"


def test_an_orphan_that_a_tag_reaches_does_not_keep(fx: Fixture) -> None:
    orphan = _orphan_commit_in_the_reflog(fx)
    _git(fx.repo, "tag", "saved", orphan)
    assert fx.verdict() == "would"


def test_an_orphan_that_another_branch_reaches_does_not_keep(fx: Fixture) -> None:
    orphan = _orphan_commit_in_the_reflog(fx)
    _git(fx.repo, "branch", "rescued", orphan)
    assert fx.verdict() == "would"


def test_a_reflog_entry_for_an_object_that_is_gone_does_not_keep(fx: Fixture) -> None:
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    with (gd / "logs" / "HEAD").open("a") as log:
        log.write(f"{'0' * 40} {'ab' * 20} t <t@t> 1700000000 +0000\treset: moving to a pruned commit\n")
    assert fx.verdict() == "would"


def test_a_worktree_without_a_head_reflog_does_not_keep(fx: Fixture) -> None:
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    (gd / "logs" / "HEAD").unlink()
    assert fx.verdict() == "would"


@pytest.mark.parametrize(
    ("args", "why"),
    [
        ("rev-parse --absolute-git-dir", "could not locate the git dir (git rev-parse exit 128)"),
        ("cat-file", "could not read the reflogs (exit 128)"),
        ("rev-list --stdin", "could not check the reflogs against the refs (git rev-list exit 128)"),
    ],
)
def test_a_git_failure_while_checking_the_reflog_keeps(fx: Fixture, args: str, why: str) -> None:
    fx.git_fails(args)
    fx.keeps(why)


def test_rev_list_killed_while_checking_the_reflog_keeps(fx: Fixture) -> None:
    fx.shim("git", f'case " $* " in *" rev-list --stdin "*) kill -9 $$ ;; esac\nexec "{_real("git")}" "$@"')
    fx.keeps("could not check the reflogs against the refs (git rev-list exit 137)")


@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
def test_an_unreadable_head_reflog_keeps(fx: Fixture) -> None:
    log = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir")) / "logs" / "HEAD"
    log.chmod(0)
    try:
        fx.keeps("could not read the reflogs")
    finally:
        log.chmod(0o644)


# --- a failed write of the scan's own files ----------------------------------------------------------------------


@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
@pytest.mark.parametrize(
    ("after", "why"),
    [
        ("ls-files -z -s -v", "could not list ignored files"),
        ("ls-files -z -o", "could not scan for nested git repos"),
    ],
    ids=["second-use", "third-use"],
)
def test_a_scan_file_that_becomes_unwritable_midway_keeps(fx: Fixture, tmp_path: Path, after: str, why: str) -> None:
    """The one temp file is reused by every scan step. Each later step's write failing must read as unknown, not
    as an empty list: the worktree has nothing else to protect, so only the failed write could save it."""
    target = tmp_path / "scratch"
    fx.shim("mktemp", f'chmod 644 "{target}" 2>/dev/null; : >"{target}"; echo "{target}"')
    fx.shim(
        "git",
        f'case " $* " in *" {after} "*) "{_real("git")}" "$@"; rc=$?; chmod 444 "{target}"; exit $rc ;; esac\n'
        f'exec "{_real("git")}" "$@"',
    )
    fx.keeps(why)


# --- found by the round-7 mutation run: each of these survived until the test below existed ------------------


@pytest.mark.parametrize("rel", ["credentials", "CREDENTIALS", "terraform.tfstate", "prod.TFSTATE"])
def test_credentials_and_tfstate_names_keep_even_inside_a_regenerable_directory(fx: Fixture, rel: str) -> None:
    _marked(fx)
    _ignored(fx, f"tree/{rel}", "not a real secret\n")
    fx.keeps(KEEP_SECRET)


@pytest.mark.parametrize("rel", [".cache/x.txt", ".cache/pip/http/ab/cd", ".gradle/caches/x.bin", "target/debug/x"])
def test_cache_style_directories_are_not_on_the_allowlist(fx: Fixture, rel: str) -> None:
    """`.cache` and friends can hold user data (tool state, sqlite files), so they are not proven regenerable."""
    _ignored(fx, rel, "may be the only copy\n")
    fx.keeps(KEEP_UNPROVEN)


def _forge_reflog_line(fx: Fixture, old: str, new: str) -> None:
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    with (gd / "logs" / "HEAD").open("a") as log:
        log.write(f"{old} {new} t <t@t> 1700000000 +0000\tforged\n")


def test_an_orphan_named_only_as_the_new_sha_of_a_reflog_line_keeps(fx: Fixture) -> None:
    """Each field is read on its own: a log whose chain is broken still names the orphan once."""
    orphan = _orphan_commit_in_the_reflog(fx)
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    (gd / "logs" / "HEAD").write_text("")  # drop the real chain, leave only the forged line
    _forge_reflog_line(fx, "0" * 40, orphan)
    fx.keeps(KEEP_REFLOG)


def test_an_orphan_named_only_as_the_old_sha_of_a_reflog_line_keeps(fx: Fixture) -> None:
    orphan = _orphan_commit_in_the_reflog(fx)
    gd = Path(_git(fx.wt, "rev-parse", "--absolute-git-dir"))
    (gd / "logs" / "HEAD").write_text("")
    _forge_reflog_line(fx, orphan, "0" * 40)
    fx.keeps(KEEP_REFLOG)
