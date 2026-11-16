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


def test_check_run_listing_uses_filter_all_so_an_earlier_same_name_run_is_not_hidden():
    assert "check-runs?per_page=100&filter=all" in WORKFLOW


def _run_workflow_step(tmp_path, head_ref, list_fails):
    """Run the publish step's shell body with a fake `gh` and return the PATCH conclusions/titles it sent."""
    body = WORKFLOW.split("run: |\n", 1)[1]
    script = "\n".join(line[10:] for line in body.splitlines())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "patch.log"
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        '  *"-X POST"*) echo 42 ;;\n'
        '  *"-X PATCH"*) echo "$*" >> "$PATCH_LOG" ;;\n'
        '  *) [ -n "$LIST_FAILS" ] && exit 7; echo \'{"check_runs":[]}\' ;;\n'
        "esac\n"
    )
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "PATCH_LOG": str(log),
        "LIST_FAILS": "1" if list_fails else "",
        "HEAD_REF": head_ref,
        "HEAD_REPO": "my-org/my-repo",
        "REPO": "my-org/my-repo",
        "SHA": "deadbeef",
        "CHECK_NAME": "PRs into main must come from staging",
        "GH_TOKEN": "unused",
    }
    proc = subprocess.run(
        ["bash", "-c", script], cwd=Path(__file__).resolve().parent.parent,
        env=env, capture_output=True, text=True,
    )
    return proc.returncode, log.read_text() if log.exists() else ""


def test_a_failed_check_run_listing_fails_the_check_closed(tmp_path):
    code, patches = _run_workflow_step(tmp_path, "staging", list_fails=True)
    assert code == 1
    assert "conclusion=failure" in patches and "forged check name" in patches
    assert "conclusion=success" not in patches


def test_an_empty_listing_from_staging_passes(tmp_path):
    code, patches = _run_workflow_step(tmp_path, "staging", list_fails=False)
    assert code == 0
    assert "conclusion=success" in patches
