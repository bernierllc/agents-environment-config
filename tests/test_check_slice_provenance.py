"""Merge-with-main promote slice provenance, on real git graphs served by a local bare remote.

check-slice-provenance.sh only decides whether a slice's parents may feed the trusted replay (plan
2026-11-21-mvs-trusted-slice-replay, step 3): provenance alone is never a pass. The network boundary is the git
remote; it is a real bare repository here. The one guard test that gets past the replay reads main's rules from a
stub `gh`, the GitHub API boundary.
"""
import hashlib
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = ROOT / "scripts" / "check-slice-provenance.sh"
GUARD = ROOT / "scripts" / "check-main-source.sh"
SLICE = "promote/2026-11-21-1"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@pytest.fixture
def env(tmp_path):
    return {
        **os.environ,
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }


class Graph:
    """main: m0-m1; staging (first parent): m0-s1-s2, where s2 merges side commit f1; plus an unrelated root u."""

    def __init__(self, tmp_path, env):
        self.env, self.n = env, 0
        self.origin, self.author = tmp_path / "origin.git", tmp_path / "author"
        self.git(None, "init", "-q", "--bare", str(self.origin))
        self.git(self.origin, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.git(None, "init", "-q", str(self.author))
        self.git(self.author, "remote", "add", "origin", str(self.origin))
        self.m0 = self.commit()
        self.m1 = self.commit(self.m0)
        self.s1 = self.commit(self.m0)
        self.f1 = self.commit(self.s1)
        self.s2 = self.commit(self.s1, self.f1)
        self.u = self.commit()
        self.push(self.m1, "main")
        self.push(self.s2, "staging")

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, *parents, tree=EMPTY_TREE):
        self.n += 1
        args = [x for p in parents for x in ("-p", p)]
        return self.git(self.author, "commit-tree", tree, *args, "-m", f"c{self.n}")

    def push(self, sha, branch):
        self.git(self.author, "push", "-q", "-f", "origin", f"{sha}:refs/heads/{branch}")

    def guard_clone(self, depth=1):
        """The guard's checkout: main at the event commit, shallow like actions/checkout (depth=None: full)."""
        dest = self.author.parent / f"guard{self.n}"
        self.n += 1
        self.git(None, "clone", "-q", "--no-local", *([f"--depth={depth}"] if depth else []), "--branch", "main",
                 f"file://{self.origin}", str(dest))
        return dest

    def run(self, script, head, base, ref=SLICE, cwd=None, head_repo="my-org/my-repo", **extra_env):
        # The remote comes from the runner (GITHUB_SERVER_URL/GITHUB_REPOSITORY), never from the checkout.
        e = {**self.env, "HEAD_SHA": head, "BASE_SHA": base, "HEAD_REF": ref,
             "HEAD_REPO": head_repo, "REPO": "my-org/my-repo",
             "GITHUB_SERVER_URL": f"file://{self.origin.parent}", "GITHUB_REPOSITORY": self.origin.name,
             **extra_env}
        p = subprocess.run(["bash", str(script)], cwd=cwd or self.guard_clone(), env=e,
                           capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr


@pytest.fixture
def g(tmp_path, env):
    return Graph(tmp_path, env)


def slice_of(g, *parents, **kw):
    head = g.commit(*parents, **kw)
    g.push(head, SLICE)
    return head


def test_a_valid_slice_satisfies_provenance_even_from_a_shallow_checkout(g):
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 0, out
    assert f"staging={g.s2}" in out and f"base={g.m1}" in out


def test_provenance_and_replay_alone_do_not_admit_a_slice_without_mains_up_to_date_rule(g, tmp_path):
    # The plain merge of these empty trees is the empty tree, so the replay holds; main's rules without the strict
    # up-to-date policy still reject it (test_replay_promote_slice.py covers admission).
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text("#!/bin/sh\n"
                               'case "$*" in *rules/branches/main*) echo \'[[{"type":"required_status_checks",'
                               '"parameters":{"strict_required_status_checks_policy":false}}]]\' ;; *) exit 98 ;; esac\n')
    (bindir / "gh").chmod(0o755)
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(GUARD, head, g.m1, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
    assert code == 1, out
    assert "slice replay holds" in out and "does not require branches to be up to date" in out, out


@pytest.mark.parametrize("head_repo", ["someone/my-repo", "my-org/other-repo", ""],
                         ids=["fork", "other-repo", "deleted-fork"])
def test_a_slice_from_outside_this_repo_fails_closed_before_provenance(g, head_repo):
    head = slice_of(g, g.s1, g.m1)  # a slice that would satisfy provenance
    code, out = g.run(GUARD, head, g.m1, head_repo=head_repo)
    assert code == 1, out
    assert "slice provenance" not in out and "promote slice" not in out
    assert ("not a fork" in out) if head_repo else ("HEAD_REPO is required" in out)


@pytest.mark.parametrize("extra", [1, 2], ids=["octopus", "four-parents"])
def test_more_than_two_parents_fails_closed(g, extra):
    head = slice_of(g, g.s1, g.m1, *[g.commit(g.m0) for _ in range(extra)])
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "exactly two parents" in out, out


def test_a_plain_commit_is_not_a_slice(g):
    head = slice_of(g, g.s1)
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "exactly two parents (has 1)" in out, out


def test_a_first_parent_off_stagings_first_parent_history_fails_closed(g):
    head = slice_of(g, g.f1, g.m1)  # f1 is reachable from staging only through a merge's second parent
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "not on staging's first-parent history" in out, out


def test_an_unrelated_second_parent_fails_closed(g):
    head = slice_of(g, g.s1, g.u)
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "is not the event base" in out, out


def test_an_older_main_second_parent_is_stale_and_fails_closed(g):
    head = slice_of(g, g.s1, g.m0)
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "stale, rebuild the slice" in out, out


def test_a_commit_appended_after_the_merge_fails_closed(g):
    head = slice_of(g, g.commit(g.s1, g.m1))
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "appended after the merge" in out, out


def test_a_head_ref_moved_after_the_event_fails_closed(g):
    head = slice_of(g, g.s1, g.m1)
    g.push(g.commit(g.s1, g.m1), SLICE)  # a new push after the event; the event's SHA is no longer the tip
    code, out = g.run(PROVENANCE, head, g.m1)
    assert code == 1 and "moved after the event" in out, out


def test_a_rerun_of_the_same_event_keeps_its_base_sha_after_main_moves(g):
    head = slice_of(g, g.s1, g.m1)
    first = g.run(PROVENANCE, head, g.m1)
    g.push(g.commit(g.m1), "main")  # main advances; the event's base.sha does not
    second = g.run(PROVENANCE, head, g.m1)
    assert first[0] == second[0] == 0, (first, second)
    assert f"base={g.m1}" in first[1] and f"base={g.m1}" in second[1]


def test_a_base_sha_the_remote_does_not_have_fails_closed(g):
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(PROVENANCE, head, "0" * 40)
    assert code == 1 and "fetch of the event objects" in out, out


@pytest.mark.parametrize("bad", ["", "HEAD", "deadbeef", "refs/heads/main"])
def test_a_non_sha_input_fails_closed(g, bad):
    head = slice_of(g, g.s1, g.m1)
    assert g.run(PROVENANCE, head, bad)[0] == 1
    assert g.run(PROVENANCE, bad, g.m1)[0] == 1


def test_head_content_is_never_checked_out_or_run(g, tmp_path):
    marker = tmp_path / "pwned"
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=g.author, env=g.env, check=True,
                          input=f"#!/bin/bash\ntouch {marker}\n", capture_output=True, text=True).stdout.strip()
    scripts = subprocess.run(["git", "mktree"], cwd=g.author, env=g.env, check=True, capture_output=True, text=True,
                             input=f"100755 blob {blob}\tcheck-slice-provenance.sh\n").stdout.strip()
    tree = subprocess.run(["git", "mktree"], cwd=g.author, env=g.env, check=True, capture_output=True, text=True,
                          input=f"040000 tree {scripts}\tscripts\n").stdout.strip()
    head = slice_of(g, g.s1, g.m1, tree=tree)
    clone = g.guard_clone()
    before = g.git(clone, "rev-parse", "HEAD")
    code, out = g.run(GUARD, head, g.m1, cwd=clone)
    assert code == 1, out
    assert "slice provenance holds" in out and "is not the replayed merge" in out, out  # examined, not an early error
    assert not marker.exists()
    assert g.git(clone, "rev-parse", "HEAD") == before
    assert g.git(clone, "status", "--porcelain") == ""
    # the walk ran in a scratch repo: the head's objects never entered the checkout, and the checkout stays shallow
    assert subprocess.run(["git", "cat-file", "-e", f"{head}^{{commit}}"], cwd=clone, env=g.env).returncode != 0
    assert g.git(clone, "rev-parse", "--is-shallow-repository") == "true"


def test_the_guard_without_provenance_inputs_still_rejects_a_slice(g):
    # A workflow copy that passes no HEAD_SHA/BASE_SHA must fail closed on the slice branch, never skip.
    e = {k: v for k, v in g.env.items() if k not in ("HEAD_SHA", "BASE_SHA")}
    e.update(HEAD_REF=SLICE, HEAD_REPO="my-org/my-repo", REPO="my-org/my-repo")
    p = subprocess.run(["bash", str(GUARD)], cwd=g.guard_clone(), env=e, capture_output=True, text=True)
    assert p.returncode == 1 and "HEAD_SHA is required" in p.stderr


def _rewritten_clone(g, how):
    """A guard checkout whose local history claims f1 is staging's first parent (s2 really is s1 + f1)."""
    clone = g.guard_clone()
    g.git(clone, "fetch", "-q", "origin", "staging")
    if how == "replace":
        g.git(clone, "replace", "--graft", g.s2, g.f1, g.s1)
    else:
        Path(g.git(clone, "rev-parse", "--absolute-git-dir"), "info", "grafts").write_text(f"{g.s2} {g.f1} {g.s1}\n")
    return clone


@pytest.mark.parametrize("how", ["replace", "grafts"])
def test_a_locally_rewritten_staging_graph_cannot_fake_provenance(g, how):
    head = slice_of(g, g.f1, g.m1)  # f1 is only staging's second parent
    code, out = g.run(PROVENANCE, head, g.m1, cwd=_rewritten_clone(g, how))
    assert code == 1, out


def _swap_parents_in_commit_graph(graph_file, oid):
    """Swap oid's two parents in a v1 SHA-1 commit-graph file and re-sign it; the commit objects stay untouched."""
    data = bytearray(graph_file.read_bytes())
    chunks = {bytes(data[8 + 12 * i:12 + 12 * i]): int.from_bytes(data[12 + 12 * i:20 + 12 * i], "big")
              for i in range(data[6])}
    n = int.from_bytes(data[chunks[b"OIDF"] + 255 * 4:chunks[b"OIDF"] + 256 * 4], "big")
    oids = [bytes(data[chunks[b"OIDL"] + 20 * i:chunks[b"OIDL"] + 20 * (i + 1)]).hex() for i in range(n)]
    at = chunks[b"CDAT"] + 36 * oids.index(oid) + 20
    data[at:at + 8] = data[at + 4:at + 8] + data[at:at + 4]
    data[-20:] = hashlib.sha1(data[:-20]).digest()
    graph_file.chmod(0o644)  # git writes the file read-only
    graph_file.write_bytes(bytes(data))


def test_a_tampered_commit_graph_cannot_fake_provenance(g):
    clone = g.guard_clone(depth=None)
    g.git(clone, "fetch", "-q", "origin", "staging")
    g.git(clone, "commit-graph", "write", "--reachable")
    graph = Path(g.git(clone, "rev-parse", "--absolute-git-dir"), "objects", "info", "commit-graph")
    _swap_parents_in_commit_graph(graph, g.s2)  # the cache now claims f1 is staging's first parent
    assert g.git(clone, "rev-list", "--first-parent", g.s2).split()[1] == g.f1  # the tamper is live
    head = slice_of(g, g.f1, g.m1)
    code, out = g.run(PROVENANCE, head, g.m1, cwd=clone)
    assert code == 1 and "not on staging's first-parent history" in out, out


@pytest.mark.parametrize("where", ["checkout", "parameters", "env-pairs", "global", "system"])
def test_a_config_redirect_to_a_forged_remote_cannot_fake_provenance(g, tmp_path, where):
    head = slice_of(g, g.f1, g.m1)  # f1 is only staging's second parent
    forged = tmp_path / "forged.git"
    g.git(None, "clone", "-q", "--mirror", str(g.origin), str(forged))
    g.git(forged, "config", "uploadpack.allowAnySHA1InWant", "true")
    g.git(forged, "update-ref", "refs/heads/staging", g.f1)  # the forged staging makes f1 a first parent
    real, fake = f"file://{g.origin}", f"file://{forged}"
    clone, extra = g.guard_clone(), {}
    if where == "checkout":
        g.git(clone, "config", f"url.{fake}.insteadOf", real)
    elif where == "parameters":
        extra = {"GIT_CONFIG_PARAMETERS": f"'url.{fake}.insteadof'='{real}'"}
    elif where == "env-pairs":  # inherited GIT_CONFIG_COUNT/KEY_n/VALUE_n reach every git call, git init included
        extra = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{fake}.insteadOf", "GIT_CONFIG_VALUE_0": real}
    else:
        cfg = tmp_path / f"{where}.gitconfig"
        cfg.write_text(f'[url "{fake}"]\n\tinsteadOf = {real}\n')
        extra = {"GIT_CONFIG_GLOBAL": str(cfg)} if where == "global" else {"GIT_CONFIG_SYSTEM": str(cfg)}
        if where == "system":
            extra["GIT_CONFIG_NOSYSTEM"] = ""
    live = subprocess.run(["git", "ls-remote", real, "refs/heads/staging"], cwd=clone, env={**g.env, **extra},
                          check=True, capture_output=True, text=True).stdout.split()[0]
    assert live == g.f1  # the redirect is live for an unsanitized git
    code, out = g.run(PROVENANCE, head, g.m1, cwd=clone, **extra)
    assert code == 1 and "not on staging's first-parent history" in out, out


def test_no_remote_input_fails_closed(g):
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(PROVENANCE, head, g.m1, GITHUB_SERVER_URL="", GITHUB_REPOSITORY="")
    assert code == 1 and "GIT_REMOTE or GITHUB_SERVER_URL" in out, out


def test_an_explicit_git_remote_is_used_literally(g):
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(PROVENANCE, head, g.m1, GITHUB_SERVER_URL="", GITHUB_REPOSITORY="",
                      GIT_REMOTE=f"file://{g.origin}")
    assert code == 0, out


def test_inherited_git_exec_and_transport_env_never_reaches_git(g, tmp_path):
    # GIT_EXEC_PATH would swap git's helpers (upload-pack runs from it on a local fetch); GIT_SSH_COMMAND and
    # GIT_PROXY_COMMAND would run code on a transport. Every GIT_* variable but GIT_REMOTE is dropped first.
    marker = tmp_path / "ran"
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(PROVENANCE, head, g.m1, GIT_EXEC_PATH=str(tmp_path / "nowhere"),
                      GIT_SSH_COMMAND=f"touch {marker}", GIT_PROXY_COMMAND=f"touch {marker}")
    assert code == 0, out
    assert not marker.exists()


def test_a_fetch_token_is_never_sent_to_a_non_https_remote_or_printed(g):
    head = slice_of(g, g.s1, g.m1)
    token = "ghs_" + "x" * 36
    code, out = g.run(PROVENANCE, head, g.m1, SLICE_FETCH_TOKEN=token)
    assert code == 1 and "only sent to an https remote" in out, out
    assert token not in out


def test_a_kept_scratch_repo_must_be_new(g, tmp_path):
    head = slice_of(g, g.s1, g.m1)
    existing = tmp_path / "scratch"
    existing.mkdir()
    code, out = g.run(PROVENANCE, head, g.m1, SLICE_SCRATCH=str(existing))
    assert code == 1 and "must be a new directory" in out, out
    fresh = tmp_path / "fresh"
    code, out = g.run(PROVENANCE, head, g.m1, SLICE_SCRATCH=str(fresh))
    assert code == 0, out
    assert (fresh / "walk.git").is_dir()  # kept for the replay; the caller removes it
