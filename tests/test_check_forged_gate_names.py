"""A PR-controlled Actions job that borrows a required check's name is detected."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-forged-gate-names.py"
spec = importlib.util.spec_from_file_location("check_forged_gate_names", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "https://github.com/my-org/my-repo"
GUARD = "PRs into main must come from staging"
TRUSTED_GATE = (".github/workflows/review-gate.yml", "pull_request_target")
PROTECTED_BASE = True  # the run's PR targets an owner-trusted branch (the default branch, a listed one)
UNPROTECTED_BASE = False  # a stacked PR: base is the outer PR's contributor-controlled branch


def api_run(name, run_id=1):
    """Published through the Checks API: details_url has no /actions/."""
    return {"name": name, "details_url": f"{REPO}/runs/{run_id}", "html_url": f"{REPO}/runs/{run_id}"}


def job_run(name, run_id, job_id=9):
    """Created by an Actions job."""
    url = f"{REPO}/actions/runs/{run_id}/job/{job_id}"
    return {"name": name, "details_url": url, "html_url": url}


def lookup_table(table):
    return lambda run_id: table[run_id]


def test_api_published_guard_check_is_not_forged_known_limit():
    # Our own guard publishes through the Checks API, so an API-published run must pass. The cost: a PR
    # workflow with `checks: write` can publish the same way undetected. Only A/B (see the plan) closes it.
    assert mod.forged([api_run(GUARD)], lookup_table({})) == []


def test_disallowed_pr_supplying_a_same_name_success_job_is_detected():
    # ci.yml in the PR head: `jobs: x: name: <guard name>, run: true`.
    runs = [api_run(GUARD), job_run(GUARD, "777")]
    found = mod.forged(runs, lookup_table({"777": (".github/workflows/ci.yml", "pull_request", PROTECTED_BASE)}))
    assert [name for name, _ in found] == [GUARD]


def test_review_gate_forged_by_a_pr_head_workflow_is_detected():
    runs = [job_run("Review Gate", "888")]
    assert mod.forged(runs, lookup_table({"888": (".github/workflows/ci.yml", "pull_request", PROTECTED_BASE)}))


def test_a_pr_head_copy_of_the_trusted_workflow_file_is_still_forged():
    # Same path, wrong event: the PR cannot change the pull_request_target file, only add a pull_request trigger.
    runs = [job_run("Review Gate", "889")]
    assert mod.forged(runs, lookup_table({"889": (TRUSTED_GATE[0], "pull_request", PROTECTED_BASE)}))


def test_the_trusted_review_gate_job_is_not_forged():
    runs = [job_run("Review Gate", "890")]
    assert mod.forged(runs, lookup_table({"890": (*TRUSTED_GATE, PROTECTED_BASE)})) == []


def test_several_trusted_review_gate_runs_on_one_commit_are_not_forged():
    # Reruns and earlier events leave several legitimate Review Gate jobs on one commit (different run ids).
    runs = [job_run("Review Gate", "891"), job_run("Review Gate", "892"), job_run("Review Gate", "893")]
    table = {run_id: (*TRUSTED_GATE, PROTECTED_BASE) for run_id in ("891", "892", "893")}
    assert mod.forged(runs, lookup_table(table)) == []


def test_the_trusted_pair_on_an_unprotected_base_is_forged_in_a_stacked_pr():
    # pull_request_target runs the workflow file from the PR's base branch. A stacked child's base is the
    # outer PR's branch, which its author can rewrite, so the right (path, event) pair proves nothing.
    runs = [job_run("Review Gate", "894")]
    found = mod.forged(runs, lookup_table({"894": (*TRUSTED_GATE, UNPROTECTED_BASE)}))
    assert [name for name, _ in found] == ["Review Gate"]


def test_unprotected_names_are_ignored_and_never_looked_up():
    def boom(_):
        raise AssertionError("lookup must not run for unprotected names")

    assert mod.forged([job_run("test (macos-latest, 3.12)", "1")], boom) == []


def test_a_failed_run_lookup_fails_closed():
    def broken(_):
        raise RuntimeError("api down")

    with pytest.raises(RuntimeError):
        mod.forged([job_run(GUARD, "1")], broken)


def test_paginated_gh_output_is_parsed():
    text = json.dumps({"check_runs": [api_run("a")]}) + "\n" + json.dumps({"check_runs": [api_run("b")]})
    assert [r["name"] for r in mod._load_check_runs(text)] == ["a", "b"]


def _cli(stdin):
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
        env={**os.environ, "REPO": "my-org/my-repo"},
    )


@pytest.mark.parametrize("stdin", [
    "not json",
    "",  # empty stdin: no pipefail, or a silent `gh api`
    " \n",
    '{"check_runs": []}',  # a head always has check runs by merge time; an empty page is suspicious
    '{"total_count": 0}',  # page without check_runs
    '{"check_runs": [{}]}',  # nonempty but malformed entries must not count as an evaluated listing
    '{"check_runs": [{"name": null}]}',
    '{"check_runs": ["x"]}',
    '{"check_runs": "abc"}',
    "[]",  # JSON of the wrong shape
    "5",
])
def test_cli_fails_closed_on_empty_malformed_or_runless_input(stdin):
    proc = _cli(stdin)
    assert proc.returncode == 2
    assert "failing closed" in proc.stderr


def test_cli_passes_a_page_whose_protected_name_came_from_the_checks_api():
    # No Actions job involved, so no workflow-run lookup (no gh call) is needed.
    assert _cli(json.dumps({"check_runs": [api_run(GUARD)]})).returncode == 0


def run_json(bases):
    return json.dumps([TRUSTED_GATE[0], TRUSTED_GATE[1], bases])


def _fake_gh(monkeypatch, run_tsv="", default_branch="main\n"):
    """Stand in for `gh api`: the workflow-run listing and the repo's default branch."""

    def fake(cmd, **kwargs):
        class Done:
            stdout = run_tsv if "/actions/runs/" in cmd[2] else default_branch

        return Done()

    monkeypatch.setattr(mod.subprocess, "run", fake)


TRUSTED = {"main", "staging"}


def test_workflow_run_path_with_a_ref_suffix_is_normalized(monkeypatch):
    _fake_gh(monkeypatch, '[".github/workflows/review-gate.yml@refs/heads/main", "pull_request_target", ["staging"]]')
    looked_up = mod._gh_run_lookup("my-org/my-repo", lambda: TRUSTED)("890")
    assert looked_up == (*TRUSTED_GATE, True)
    assert mod.forged([job_run("Review Gate", "890")], lambda _: looked_up) == []


def test_a_stacked_run_whose_base_is_a_contributor_branch_is_untrusted(monkeypatch):
    _fake_gh(monkeypatch, run_json(["feat/outer"]))
    assert mod._gh_run_lookup("my-org/my-repo", lambda: TRUSTED)("894") == (*TRUSTED_GATE, False)


def test_a_branch_is_trusted_only_when_listed_not_because_it_is_protected(monkeypatch):
    # No branch-protection lookup exists: a wildcard-protected contributor branch is still untrusted.
    _fake_gh(monkeypatch, run_json(["staging"]))
    assert mod._gh_run_lookup("my-org/my-repo", lambda: {"main"})("896")[2] is False


def test_a_comma_in_a_branch_name_cannot_pose_as_two_trusted_branches(monkeypatch):
    # git allows commas in branch names: one contributor branch `main,staging` must not match `main` + `staging`.
    _fake_gh(monkeypatch, run_json(["main,staging"]))
    assert mod._gh_run_lookup("my-org/my-repo", lambda: TRUSTED)("897")[2] is False


def test_a_run_without_a_pull_request_has_no_trusted_base(monkeypatch):
    _fake_gh(monkeypatch, run_json([]))
    assert mod._gh_run_lookup("my-org/my-repo", lambda: TRUSTED)("895") == (*TRUSTED_GATE, False)


def test_trusted_bases_are_the_default_branch_plus_the_env_list(monkeypatch):
    _fake_gh(monkeypatch, default_branch="main\n")
    monkeypatch.setenv("TRUSTED_BASE_BRANCHES", " staging  release/1\n")
    assert mod.trusted_base_branches("my-org/my-repo") == {"main", "staging", "release/1"}
    # A comma is part of a git branch name, never a separator: `release,1` is one branch, not `release` and `1`.
    monkeypatch.setenv("TRUSTED_BASE_BRANCHES", "release,1")
    assert mod.trusted_base_branches("my-org/my-repo") == {"main", "release,1"}
    monkeypatch.delenv("TRUSTED_BASE_BRANCHES")
    assert mod.trusted_base_branches("my-org/my-repo") == {"main"}


def test_an_unreadable_default_branch_fails_closed(monkeypatch):
    _fake_gh(monkeypatch, default_branch="\n")
    with pytest.raises(ValueError):
        mod.trusted_base_branches("my-org/my-repo")


# This file is copied byte-identically into downstream repos: it may read only
# the copied script. Assertions about aec's own plan live in test_unforgeable_plan.py.
def test_documented_merge_time_scan_requires_pipefail():
    assert "set -o pipefail; gh api" in SCRIPT.read_text()


def test_interim_scope_is_stated_in_the_script():
    assert "plan step S5" in SCRIPT.read_text()
