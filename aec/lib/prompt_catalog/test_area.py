"""Catalogued prompts for ``aec test`` (schedule + detect).

These are not org-overlay-eligible: an administrator does not pick a machine's
daily test hour. They live in the catalog so an agent can still discover and
answer them via ``--answers``.
"""
from __future__ import annotations

from .spec import PromptSpec


TEST_SCHEDULE_ENABLE = "test.schedule.enable"
TEST_SCHEDULE_TIME = "test.schedule.time"
TEST_SCHEDULE_RETENTION_DAYS = "test.schedule.retention_days"
TEST_SCHEDULE_PROFILE_RETENTION_DAYS = "test.schedule.profile_retention_days"
TEST_DETECT_SCHEDULED_SUITES = "test.detect.scheduled_suites"


SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        TEST_SCHEDULE_ENABLE,
        command="test schedule --global",
        summary=(
            "Enable scheduled tests when the preference is off. Answering 'y' "
            "registers a daily OS job (launchd/cron)."
        ),
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        TEST_SCHEDULE_TIME,
        command="test schedule --global",
        summary="Time of day the daily job runs, 24h 'HH:MM'.",
        type="time-hh-mm",
        default="02:00",
    ),
    PromptSpec(
        TEST_SCHEDULE_RETENTION_DAYS,
        command="test schedule --global",
        summary="How many days of test reports to keep.",
        type="int[1..3650]",
        default=30,
    ),
    PromptSpec(
        TEST_SCHEDULE_PROFILE_RETENTION_DAYS,
        command="test schedule --global",
        summary="How many days of timing profiles to keep.",
        type="int[1..3650]",
        default=90,
    ),
    PromptSpec(
        TEST_DETECT_SCHEDULED_SUITES,
        command="test detect",
        summary=(
            "Which detected suites to schedule: 'all', 'none', comma-separated "
            "menu numbers, or empty to keep the current selection."
        ),
        type="string",
        default="",
    ),
)

FAMILIES: tuple = ()
