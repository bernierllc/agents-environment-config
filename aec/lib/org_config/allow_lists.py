"""Allow-lists for the org-config overlay's ``install.preferences`` and
``install.prompts`` blocks.

These constants are the runtime materialization of the resolved addendum at
``docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md``. The
validator (Task 3) embeds them as a closed schema; any key not present must
be rejected with a clear error.

Two intentional design choices:

  1. **Closed schema.** ``PREFERENCES_ALLOW_LIST`` and ``PROMPTS_ALLOW_LIST``
     enumerate every key an org overlay may set. The two ``DYNAMIC_*``
     entries describe the families that are dynamic by construction
     (``configurable_instructions.<key>.<agent>`` and
     ``prefs.optional_rules.<feature_key>``); the validator expands them at
     load time using the same registries the interactive prompts use.

  2. **Type tags only.** Each value here is a short tag (``"bool"``,
     ``"int[1..3650]"``, etc.) describing the contract; full validation
     logic lives in the validator (Task 3). Keeping the tags string-based
     means tests that diff this module against the addendum stay readable.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# install.preferences
# ---------------------------------------------------------------------------
#
# Sourced from §1.2 of the addendum. Order matches that section.

PREFERENCES_ALLOW_LIST: dict[str, str] = {
    # optional_rules.* (all booleans)
    "leave-it-better": "bool",
    "update_check": "bool",
    "port_registry_enabled": "bool",
    "scheduled_tests_enabled": "bool",
    "discovery_recompare": "bool",
    # settings.*
    "projects_dir": "path-under-home",
    "plans_dir": "bare-dirname",
    "plans_gitignored": "bool",
    "plans_completion": "enum[archive,delete]",
    "hook_mode": "enum[auto,per-repo,never]",
    "aec_json_gitignored": "bool",
    "report_viewer": "enum-from-detect-viewers",
    "report_retention_mode": "enum[auto,manual]",
    "report_retention_days": "int[1..3650]",
    "global_install_multi_repo_threshold": "int[2..50]",
}

# configurable_instructions.* is a dynamic namespace — keys come from the
# CONFIGURABLE_INSTRUCTIONS registry, agent keys from get_all_agent_keys().
# The validator expands this dynamically; we record it here so callers know
# the namespace is part of the closed allow-list.
PREFERENCES_DYNAMIC_NAMESPACES: tuple[str, ...] = (
    "configurable_instructions",
)

# Explicitly excluded keys (kept here so a future contributor can see the
# decision instead of rediscovering it). Validator must reject these.
PREFERENCES_EXCLUDED_KEYS: frozenset[str] = frozenset({
    "skip_global_install_prompt_for",
})


# ---------------------------------------------------------------------------
# install.prompts
# ---------------------------------------------------------------------------
#
# Sourced from §2.2 of the addendum. Each entry is the stable prompt ID a
# callsite emits, mapped to the type tag describing its accepted shape.

PROMPTS_ALLOW_LIST: dict[str, str] = {
    # Flow control
    "install.batch_project_setup.start": "yes_no",
    "install.batch_project_setup.scan_mode": "enum[git_only,all]",
    # Settings (mirror of install.preferences but expressed as prompt answers)
    "install.settings.projects_dir": "path-under-home",
    "install.settings.plans_dir": "enum[dotplans,plans,custom]_or_bare_dirname",
    "install.settings.plans_dir.custom": "bare-dirname",
    "install.settings.plans_gitignored": "yes_no",
    "install.settings.plans_completion": "enum[archive,delete]",
    # Quality infrastructure
    "install.quality.report_viewer": "enum-from-detect-viewers",
    "install.quality.report_retention_mode": "enum[auto,manual]",
    "install.quality.report_retention_days": "int[1..3650]",
    # Setup
    "setup.track_current_repo": "yes_no",
}

# Dynamic prompt-ID prefixes. Matches DYNAMIC_PROMPT_ID_PREFIXES in
# aec.lib.prompt_ids; the validator expands these with the relevant runtime
# registries (CONFIGURABLE_INSTRUCTIONS, get_all_agent_keys, OPTIONAL_FEATURES).
PROMPTS_DYNAMIC_PREFIXES: dict[str, str] = {
    "install.configurable_instructions": "yes_no",  # .<key>.<agent_key>
    "prefs.optional_rules": "yes_no",               # .<feature_key>
}

# Prompt sites that are intentionally excluded — see §2.2 of the addendum.
PROMPTS_EXCLUDED_IDS: frozenset[str] = frozenset({
    "install.batch_project_setup.per_project",      # depends on local project list
    "install.quality.report_viewer.command",        # free-form shell command
    "install.global_offer.dismiss",                 # user-only dismissal state
    "install.global_offer.choice",                  # deferred to later phase
})
