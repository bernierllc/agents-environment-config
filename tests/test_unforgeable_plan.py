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
    assert "`main` ruleset requires the context" in PLAN


def test_plan_gives_waiver_free_order_when_context_not_required():
    assert "#### Waiver-free variant when `main` does not require the context" in PLAN
    assert 'follow "Waiver-free variant when `main` does not require the context"' in PLAN
    assert "delete the legacy `main-via-staging.yml` alone" in PLAN


def test_plan_covers_canonical_on_staging_with_scripts_missing_on_main():
    assert "#### Canonical workflow already on staging, scripts missing on main" in PLAN
    assert "`main` lacks the scripts" in PLAN
    assert "the owner waives the guard check once" in PLAN


def test_canonical_no_waiver_claims_are_qualified_by_main_having_the_scripts():
    assert "need no scan waiver, provided `main` already has the guard scripts" in PLAN
    assert "needs no scan waiver, but only when\n`main` already has the scripts" in PLAN
    assert "A repo that already runs the canonical workflow starts at the promotion step and needs no waiver." not in PLAN


def test_copied_files_qualify_the_plan_path_as_an_aec_repo_path():
    root = Path(__file__).resolve().parent.parent
    for rel in ("scripts/check-forged-gate-names.py", ".github/workflows/main-via-staging.yml"):
        text = " ".join((root / rel).read_text().replace("#", " ").split())
        assert "`plans/2026-11-16-unforgeable-required-checks.md` in the aec repo" in text, rel


def test_workflow_header_says_default_branch_not_main():
    workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "main-via-staging.yml").read_text()
    assert "DEFAULT branch (main, or staging in a repo whose default is staging)" in workflow


def test_every_aec_caller_of_the_detector_names_the_integration_base():
    # Without TRUSTED_BASE_BRANCHES=staging a legitimate staging-based Review Gate run reads as forged.
    root = Path(__file__).resolve().parent.parent
    workflow = (root / ".github" / "workflows" / "main-via-staging.yml").read_text()
    invocation = next(line for line in workflow.splitlines() if "python3 scripts/check-forged-gate-names.py" in line)
    # Both integration branches: with staging as the default branch, the staging-to-main promotion's Review Gate has base main.
    assert 'TRUSTED_BASE_BRANCHES="main staging"' in invocation
    assert 'TRUSTED_BASE_BRANCHES="main staging" python3 scripts/check-forged-gate-names.py' in PLAN


def test_plan_states_interim_scope_and_s5():
    assert "into main only" in PLAN
    assert "- S5." in PLAN
