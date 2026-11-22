"""Merge-with-main promote slice provenance, on real git graphs served by a local bare remote.

check-slice-provenance.sh only decides whether a slice's parents may feed the trusted replay (plan
2026-11-21-mvs-trusted-slice-replay, step 3). check-main-source.sh still rejects every slice: no replay, no pass.
The network boundary is the git remote; it is a real bare repository here, so nothing is stubbed.
"""
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
        """The guard's checkout: main at the event commit, shallow like actions/checkout."""
        dest = self.author.parent / f"guard{self.n}"
        self.n += 1
        self.git(None, "clone", "-q", "--no-local", f"--depth={depth}", "--branch", "main",
                 f"file://{self.origin}", str(dest))
        return dest

    def run(self, script, head, base, ref=SLICE, cwd=None, head_repo="my-org/my-repo"):
        e = {**self.env, "HEAD_SHA": head, "BASE_SHA": base, "HEAD_REF": ref,
             "HEAD_REPO": head_repo, "REPO": "my-org/my-repo"}
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


def test_a_slice_that_satisfies_provenance_is_still_rejected_by_the_guard(g):
    # Program-cop constraint for R1: provenance may only add rejections. No slice passes until the
    # trusted replay (R2) and its hosted evidence (R3) land.
    head = slice_of(g, g.s1, g.m1)
    code, out = g.run(GUARD, head, g.m1)
    assert code == 1, out
    assert "slice provenance holds" in out and "rejected" in out


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
    assert not marker.exists()
    assert g.git(clone, "rev-parse", "HEAD") == before
    assert g.git(clone, "status", "--porcelain") == ""


def test_the_guard_without_provenance_inputs_still_rejects_a_slice(g):
    # Today's workflow passes no HEAD_SHA/BASE_SHA; the slice branch must fail closed, never skip.
    e = {k: v for k, v in g.env.items() if k not in ("HEAD_SHA", "BASE_SHA")}
    e.update(HEAD_REF=SLICE, HEAD_REPO="my-org/my-repo", REPO="my-org/my-repo")
    p = subprocess.run(["bash", str(GUARD)], cwd=g.guard_clone(), env=e, capture_output=True, text=True)
    assert p.returncode == 1 and "HEAD_SHA is required" in p.stderr
