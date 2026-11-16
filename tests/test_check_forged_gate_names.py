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
    found = mod.forged(runs, lookup_table({"777": (".github/workflows/ci.yml", "pull_request")}))
    assert [name for name, _ in found] == [GUARD]


def test_review_gate_forged_by_a_pr_head_workflow_is_detected():
    runs = [job_run("Review Gate", "888")]
    assert mod.forged(runs, lookup_table({"888": (".github/workflows/ci.yml", "pull_request")}))


def test_a_pr_head_copy_of_the_trusted_workflow_file_is_still_forged():
    # Same path, wrong event: the PR cannot change the pull_request_target file, only add a pull_request trigger.
    runs = [job_run("Review Gate", "889")]
    assert mod.forged(runs, lookup_table({"889": (TRUSTED_GATE[0], "pull_request")}))


def test_the_trusted_review_gate_job_is_not_forged():
    runs = [job_run("Review Gate", "890")]
    assert mod.forged(runs, lookup_table({"890": TRUSTED_GATE})) == []


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


def test_cli_fails_closed_on_garbage_input():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True,
        env={**os.environ, "REPO": "my-org/my-repo"},
    )
    assert proc.returncode == 2


def test_workflow_run_path_with_a_ref_suffix_is_normalized(monkeypatch):
    class Done:
        stdout = ".github/workflows/review-gate.yml@refs/heads/main\tpull_request_target\n"

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Done())
    path_event = mod._gh_run_lookup("my-org/my-repo")("890")
    assert path_event == TRUSTED_GATE
    assert mod.forged([job_run("Review Gate", "890")], lambda _: path_event) == []


def test_documented_merge_time_scan_requires_pipefail():
    plan = (SCRIPT.parent.parent / "plans" / "2026-11-16-unforgeable-required-checks.md").read_text()
    assert "set -o pipefail; gh api" in plan
    assert "set -o pipefail; gh api" in SCRIPT.read_text()
