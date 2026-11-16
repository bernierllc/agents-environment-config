"""aec-only: the unforgeable-required-checks plan states the interim's scope and merge-time command.

Not part of the downstream copy set (it reads aec's own plan); the copied
tests/test_check_forged_gate_names.py must not depend on this file or the plan.
"""
from pathlib import Path

PLAN = (Path(__file__).resolve().parent.parent / "plans" / "2026-11-16-unforgeable-required-checks.md").read_text()


def test_plan_documents_merge_time_scan_with_pipefail():
    assert "set -o pipefail; gh api" in PLAN


def test_plan_states_interim_scope_and_s5():
    assert "into main only" in PLAN
    assert "- S5." in PLAN
