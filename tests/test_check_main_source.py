"""The promotion guard: only a same-repo `staging` branch may open a PR into main."""
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-main-source.sh"


def _run(head_ref, head_repo="my-org/my-repo", repo="my-org/my-repo"):
    env = {**os.environ, "HEAD_REF": head_ref, "HEAD_REPO": head_repo, "REPO": repo}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True).returncode


def test_staging_may_promote_to_main():
    assert _run("staging") == 0


@pytest.mark.parametrize("ref", ["feat/x", "hotfix/y", "revert-1", "main", "staging-2"])
def test_every_other_branch_is_refused(ref):
    assert _run(ref) == 1


def test_a_fork_named_staging_is_refused():
    assert _run("staging", head_repo="someone/my-repo") == 1


def test_a_deleted_fork_is_refused_not_skipped():
    assert _run("staging", head_repo="") != 0


WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "main-via-staging.yml"
WORKFLOW = WORKFLOW_PATH.read_text()
DOC = yaml.safe_load(WORKFLOW)
CHECK_NAME = "PRs into main must come from staging"


def _job():
    (job,) = DOC["jobs"].values()
    return job


def test_the_job_itself_is_the_required_check():
    # Mirrors review-gate.yml's `Review Gate`: a pull_request_target job's check run lands on the PR head.
    assert _job()["name"] == CHECK_NAME


def test_no_concurrency_group_so_a_cancelled_run_cannot_strand_the_required_check():
    assert "concurrency" not in DOC
    assert "concurrency" not in _job()


def test_trigger_is_pull_request_target_on_main_only():
    on = DOC[True]  # PyYAML reads the bare key `on` as boolean True
    assert set(on) == {"pull_request_target"}
    assert on["pull_request_target"]["branches"] == ["main"]
    assert on["pull_request_target"]["types"] == ["opened", "edited", "synchronize", "reopened"]


def test_checkout_is_v7_on_the_base_sha_without_unsafe_pr_checkout():
    (checkout,) = [s for s in _job()["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
    assert checkout["uses"] == "actions/checkout@v7"
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert "allow-unsafe-pr-checkout" not in checkout["with"]
    assert "Never add allow-unsafe-pr-checkout" in WORKFLOW


def test_no_step_publishes_a_hand_made_check_run():
    assert "/check-runs\"" not in WORKFLOW and "check-runs/" not in WORKFLOW
    assert "-X POST" not in WORKFLOW and "-X PATCH" not in WORKFLOW
    assert "publish-guard-result" not in WORKFLOW


def test_permissions_are_minimal():
    # Setting `permissions:` zeroes every omitted scope; GET /actions/runs/{id} needs actions: read in private repos.
    assert DOC["permissions"] == {"contents": "read", "actions": "read"}


def test_missing_guard_script_on_base_fails_with_a_clear_message_before_running_them():
    # Bootstrap artifact: workflow on the base branch before its scripts (was a silent exit 127).
    missing = WORKFLOW.index("guard script missing on base")
    assert missing < WORKFLOW.index("scripts/check-forged-gate-names.py 2>&1")
    assert "scripts/check-forged-gate-names.py scripts/check-main-source.sh; do" in WORKFLOW


def test_check_run_listing_uses_filter_all_so_an_earlier_same_name_run_is_not_hidden():
    assert "check-runs?per_page=100&filter=all" in WORKFLOW


# What the real listing holds at that point: the guard's own in-progress job check run.
OWN_JOB_ONLY = json.dumps({"total_count": 1, "check_runs": [{
    "name": CHECK_NAME,
    "details_url": "https://github.com/my-org/my-repo/actions/runs/42/job/7",
}]})


def _run_workflow_step(tmp_path, head_ref, list_fails=False, list_json=OWN_JOB_ONLY,
                       run_path_event=".github/workflows/main-via-staging.yml\tpull_request_target",
                       head_repo="my-org/my-repo", drop_script=None):
    """Run the guard step's shell body with a fake `gh`; return (exit code, combined output)."""
    (step,) = [s for s in _job()["steps"] if "run" in s]
    root = Path(__file__).resolve().parent.parent
    work = tmp_path / "repo"
    (work / "scripts").mkdir(parents=True)
    for name in ("check-forged-gate-names.py", "check-main-source.sh"):
        if name != drop_script:
            (work / "scripts" / name).write_bytes((root / "scripts" / name).read_bytes())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  *"-X "*) echo "unexpected write: $*" >&2; exit 99 ;;\n'
        '  *actions/runs/*) printf "%s\\n" "$RUN_PATH_EVENT" ;;\n'
        '  *) [ -n "$LIST_FAILS" ] && exit 7; echo "$LIST_JSON" ;;\n'
        "esac\n"
    )
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "LIST_FAILS": "1" if list_fails else "",
        "LIST_JSON": list_json,
        "RUN_PATH_EVENT": run_path_event,
        **{k: v for k, v in step["env"].items() if not v.startswith("${{")},
        "HEAD_REF": head_ref,
        "HEAD_REPO": head_repo,
        "REPO": "my-org/my-repo",
        "SHA": "deadbeef",
        "GH_TOKEN": "unused",
    }
    proc = subprocess.run(["bash", "-c", step["run"]], cwd=work, env=env, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def test_staging_with_only_the_guards_own_job_passes(tmp_path):
    code, out = _run_workflow_step(tmp_path, "staging")
    assert code == 0, out
    assert "unexpected write" not in out


def test_a_disallowed_branch_fails_the_job_naming_the_head(tmp_path):
    code, out = _run_workflow_step(tmp_path, "feat/x")
    assert code == 1
    assert "feat/x" in out and "staging" in out


def test_a_fork_fails_the_job_naming_the_head_repo(tmp_path):
    code, out = _run_workflow_step(tmp_path, "staging", head_repo="someone/my-repo")
    assert code == 1
    assert "someone/my-repo" in out


def test_a_failed_check_run_listing_fails_the_job_closed(tmp_path):
    code, out = _run_workflow_step(tmp_path, "staging", list_fails=True)
    assert code == 1
    assert "failing closed" in out


def test_an_empty_listing_fails_the_job_closed(tmp_path):
    # The guard's own job is always in the listing, so an empty one means the listing is wrong.
    code, out = _run_workflow_step(tmp_path, "staging", list_json='{"check_runs":[]}')
    assert code == 1


def test_a_forged_same_name_job_fails_the_job_even_from_staging(tmp_path):
    code, out = _run_workflow_step(tmp_path, "staging", run_path_event=".github/workflows/ci.yml\tpull_request")
    assert code == 1
    assert "forged check" in out


def test_a_missing_guard_script_fails_the_job_with_a_message_not_127(tmp_path):
    code, out = _run_workflow_step(tmp_path, "staging", drop_script="check-main-source.sh")
    assert code == 1
    assert "guard script missing on base: scripts/check-main-source.sh" in out
