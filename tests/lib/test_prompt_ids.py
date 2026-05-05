"""Tests for the stable prompt-ID constants and the prompt() helper.

These tests defend two contracts:

  1. Every constant in ``aec.lib.prompt_ids`` is a non-empty string and
     matches the addendum's resolved IDs.
  2. The ``prompt()`` helper in ``aec.lib.prompts`` falls through to
     ``input()`` in Phase 1 (overlay applier arrives later).
"""
from __future__ import annotations

import builtins

import pytest

from aec.lib import prompt_ids
from aec.lib.prompt_ids import (
    ALL_STATIC_PROMPT_IDS,
    DYNAMIC_PROMPT_ID_PREFIXES,
    INSTALL_BATCH_PROJECT_SETUP_SCAN_MODE,
    INSTALL_BATCH_PROJECT_SETUP_START,
    INSTALL_CONFIGURABLE_INSTRUCTIONS_PREFIX,
    INSTALL_QUALITY_REPORT_RETENTION_DAYS,
    INSTALL_QUALITY_REPORT_RETENTION_MODE,
    INSTALL_QUALITY_REPORT_VIEWER,
    INSTALL_SETTINGS_PLANS_COMPLETION,
    INSTALL_SETTINGS_PLANS_DIR,
    INSTALL_SETTINGS_PLANS_DIR_CUSTOM,
    INSTALL_SETTINGS_PLANS_GITIGNORED,
    INSTALL_SETTINGS_PROJECTS_DIR,
    PREFS_OPTIONAL_RULES_PREFIX,
    SETUP_TRACK_CURRENT_REPO,
    configurable_instruction_prompt_id,
    optional_rule_prompt_id,
)
from aec.lib.prompts import prompt


# --- Static IDs match the addendum -----------------------------------------


def test_static_prompt_ids_have_addendum_values():
    expected = {
        "install.batch_project_setup.start": INSTALL_BATCH_PROJECT_SETUP_START,
        "install.batch_project_setup.scan_mode": INSTALL_BATCH_PROJECT_SETUP_SCAN_MODE,
        "install.settings.projects_dir": INSTALL_SETTINGS_PROJECTS_DIR,
        "install.settings.plans_dir": INSTALL_SETTINGS_PLANS_DIR,
        "install.settings.plans_dir.custom": INSTALL_SETTINGS_PLANS_DIR_CUSTOM,
        "install.settings.plans_gitignored": INSTALL_SETTINGS_PLANS_GITIGNORED,
        "install.settings.plans_completion": INSTALL_SETTINGS_PLANS_COMPLETION,
        "install.quality.report_viewer": INSTALL_QUALITY_REPORT_VIEWER,
        "install.quality.report_retention_mode": INSTALL_QUALITY_REPORT_RETENTION_MODE,
        "install.quality.report_retention_days": INSTALL_QUALITY_REPORT_RETENTION_DAYS,
        "setup.track_current_repo": SETUP_TRACK_CURRENT_REPO,
    }
    for value, constant in expected.items():
        assert constant == value


def test_all_static_prompt_ids_tuple_is_complete():
    assert len(ALL_STATIC_PROMPT_IDS) == 11
    assert len(set(ALL_STATIC_PROMPT_IDS)) == 11  # no duplicates


def test_dynamic_prefixes_are_declared():
    assert INSTALL_CONFIGURABLE_INSTRUCTIONS_PREFIX in DYNAMIC_PROMPT_ID_PREFIXES
    assert PREFS_OPTIONAL_RULES_PREFIX in DYNAMIC_PROMPT_ID_PREFIXES


def test_configurable_instruction_prompt_id_builder():
    pid = configurable_instruction_prompt_id("session-separation", "claude")
    assert pid == "install.configurable_instructions.session-separation.claude"


def test_optional_rule_prompt_id_builder():
    pid = optional_rule_prompt_id("leave-it-better")
    assert pid == "prefs.optional_rules.leave-it-better"


def test_no_static_id_collides_with_dynamic_prefix():
    """A static ID must not start with a dynamic prefix — otherwise overlay
    lookups become ambiguous."""
    for pid in ALL_STATIC_PROMPT_IDS:
        for prefix in DYNAMIC_PROMPT_ID_PREFIXES:
            assert not pid.startswith(prefix + "."), (
                f"Static ID {pid!r} collides with dynamic prefix {prefix!r}"
            )


# --- prompt() helper -------------------------------------------------------


def test_prompt_falls_through_to_input(monkeypatch):
    """Phase 1: prompt() must always delegate to input()."""
    captured: dict[str, str] = {}

    def fake_input(text: str = "") -> str:
        captured["text"] = text
        return "user-typed-value"

    monkeypatch.setattr(builtins, "input", fake_input)

    result = prompt(
        INSTALL_BATCH_PROJECT_SETUP_START,
        "Continue? ",
        type="yes_no",
        default=True,
    )
    assert result == "user-typed-value"
    assert captured["text"] == "Continue? "


def test_prompt_returns_empty_string_on_eof(monkeypatch):
    """Matches pre-refactor try/except EOFError behaviour: callers default."""

    def fake_input(text: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(builtins, "input", fake_input)

    result = prompt(
        INSTALL_SETTINGS_PROJECTS_DIR,
        "Where? ",
        type="path",
        default="/tmp",
    )
    assert result == ""


def test_prompt_accepts_validator_argument_without_calling_it(monkeypatch):
    """Validator parameter is part of the Phase 1 surface but not yet wired."""
    monkeypatch.setattr(builtins, "input", lambda _t="": "raw")

    calls: list[str] = []

    def fake_validator(value: str):
        calls.append(value)
        return value

    result = prompt(
        SETUP_TRACK_CURRENT_REPO,
        "[Y/n]: ",
        type="yes_no",
        default=True,
        validator=fake_validator,
    )
    assert result == "raw"
    assert calls == []  # Phase 1 does not yet invoke the validator
