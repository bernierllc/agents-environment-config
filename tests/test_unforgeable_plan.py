"""aec-only: the unforgeable-required-checks plan states the interim's scope and merge-time command.

Not part of the downstream copy set (it reads aec's own plan); the copied
tests/test_check_forged_gate_names.py must not depend on this file or the plan.
"""
from pathlib import Path

PLAN = (Path(__file__).resolve().parent.parent / "plans" / "2026-11-16-unforgeable-required-checks.md").read_text()


def test_plan_documents_merge_time_scan_with_pipefail():
    assert "set -o pipefail; gh api" in PLAN


def test_plan_covers_staging_default_order_and_one_waiver_per_legacy_repo():
    assert "### Rollout order when the default branch is staging" in PLAN
    assert "needs exactly one owner waiver" in PLAN
    assert "Never combine them." in PLAN


def test_workflow_header_says_default_branch_not_main():
    workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "main-via-staging.yml").read_text()
    assert "DEFAULT branch (main, or staging in a repo whose default is staging)" in workflow


def test_plan_states_interim_scope_and_s5():
    assert "into main only" in PLAN
    assert "- S5." in PLAN
