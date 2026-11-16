"""The promotion guard: only a same-repo `staging` branch may open a PR into main."""
import os
import subprocess
from pathlib import Path

import pytest

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


WORKFLOW = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "main-via-staging.yml").read_text()


def test_guard_fails_closed_named_check_exists_before_validation_and_fails_on_reject():
    # in_progress is created before either validator runs; both rejections complete it `failure`.
    created = WORKFLOW.index('status="in_progress"')
    assert created < WORKFLOW.index("scripts/check-forged-gate-names.py 2>&1")
    assert created < WORKFLOW.index("scripts/check-main-source.sh")
    assert 'complete_check failure "source branch rejected"' in WORKFLOW
    assert 'complete_check failure "forged check name"' in WORKFLOW
    assert WORKFLOW.count('complete_check success') == 1


def test_missing_guard_script_on_base_fails_with_a_clear_message_before_running_them():
    # Bootstrap artifact: workflow on the base branch before its scripts (was a silent exit 127).
    missing = WORKFLOW.index("guard script missing on base")
    assert WORKFLOW.index('status="in_progress"') < missing
    assert missing < WORKFLOW.index("scripts/check-forged-gate-names.py 2>&1")
    assert "scripts/check-forged-gate-names.py scripts/check-main-source.sh; do" in WORKFLOW
