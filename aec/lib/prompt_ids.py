"""Stable prompt-ID constants for org-config overlay pre-answering.

Phase 1 of the org-config overlay introduces a single seam (`prompt()` in
`aec.lib.prompts`) that all install/setup/preferences prompts call through.
Each prompt site has a stable, dotted-path identifier defined here. The
overlay applier (later phase) looks up the ID in the loaded org overlay; if
present, the user is not prompted and the pre-answered value flows through
the same validator path the interactive answer would.

Source of truth: docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md (§2.1).

Do not introduce new prompt IDs here without simultaneously adding them to
`PROMPTS_ALLOW_LIST` in `aec.lib.org_config.allow_lists` and to the
addendum.
"""
from __future__ import annotations


# --- Static prompt IDs (one per install/setup callsite) ---------------------

# Flow control (install.py)
INSTALL_BATCH_PROJECT_SETUP_START = "install.batch_project_setup.start"
INSTALL_BATCH_PROJECT_SETUP_SCAN_MODE = "install.batch_project_setup.scan_mode"

# Settings (install.py — mirror of install.preferences as prompt answers)
INSTALL_SETTINGS_PROJECTS_DIR = "install.settings.projects_dir"
INSTALL_SETTINGS_PLANS_DIR = "install.settings.plans_dir"
INSTALL_SETTINGS_PLANS_DIR_CUSTOM = "install.settings.plans_dir.custom"
INSTALL_SETTINGS_PLANS_GITIGNORED = "install.settings.plans_gitignored"
INSTALL_SETTINGS_PLANS_COMPLETION = "install.settings.plans_completion"

# Quality infrastructure (install.py)
INSTALL_QUALITY_REPORT_VIEWER = "install.quality.report_viewer"
INSTALL_QUALITY_REPORT_RETENTION_MODE = "install.quality.report_retention_mode"
INSTALL_QUALITY_REPORT_RETENTION_DAYS = "install.quality.report_retention_days"

# Setup (setup.py)
SETUP_TRACK_CURRENT_REPO = "setup.track_current_repo"


# --- Dynamic prompt-ID prefixes ---------------------------------------------
#
# Some prompt sites are emitted in loops where the concrete ID depends on a
# runtime value (e.g. the OPTIONAL_FEATURES key, the configurable-instructions
# key + agent key). For these we expose a prefix and a builder so callsites
# stay consistent with the allow-list.

INSTALL_CONFIGURABLE_INSTRUCTIONS_PREFIX = "install.configurable_instructions"
PREFS_OPTIONAL_RULES_PREFIX = "prefs.optional_rules"


def configurable_instruction_prompt_id(instruction_key: str, agent_key: str) -> str:
    """Build the dynamic prompt ID for the per-agent configurable-instruction
    prompt at install.py:341.

    Shape: ``install.configurable_instructions.<key>.<agent_key>``.
    """
    return f"{INSTALL_CONFIGURABLE_INSTRUCTIONS_PREFIX}.{instruction_key}.{agent_key}"


def optional_rule_prompt_id(feature_key: str) -> str:
    """Build the dynamic prompt ID for an OPTIONAL_FEATURES prompt
    (preferences.py:186 loop).

    Shape: ``prefs.optional_rules.<feature_key>``.
    """
    return f"{PREFS_OPTIONAL_RULES_PREFIX}.{feature_key}"


# Tuple of all static IDs — handy for parity tests with the allow-list.
ALL_STATIC_PROMPT_IDS: tuple[str, ...] = (
    INSTALL_BATCH_PROJECT_SETUP_START,
    INSTALL_BATCH_PROJECT_SETUP_SCAN_MODE,
    INSTALL_SETTINGS_PROJECTS_DIR,
    INSTALL_SETTINGS_PLANS_DIR,
    INSTALL_SETTINGS_PLANS_DIR_CUSTOM,
    INSTALL_SETTINGS_PLANS_GITIGNORED,
    INSTALL_SETTINGS_PLANS_COMPLETION,
    INSTALL_QUALITY_REPORT_VIEWER,
    INSTALL_QUALITY_REPORT_RETENTION_MODE,
    INSTALL_QUALITY_REPORT_RETENTION_DAYS,
    SETUP_TRACK_CURRENT_REPO,
)

# Prefixes for dynamic prompt families.
DYNAMIC_PROMPT_ID_PREFIXES: tuple[str, ...] = (
    INSTALL_CONFIGURABLE_INSTRUCTIONS_PREFIX,
    PREFS_OPTIONAL_RULES_PREFIX,
)
