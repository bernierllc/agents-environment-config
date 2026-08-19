"""Catalogued prompts for ``aec install`` and ``aec setup``.

One module per command area so parallel work on different areas never edits
the same file. ``__init__`` aggregates them.
"""
from __future__ import annotations

from ..prompt_ids import (
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
)
from .spec import DynamicPromptFamily, PromptSpec


# Note on menu-style prompts: several install prompts present a numbered menu,
# so the accepted answer is the menu number ("1"/"2"), not the semantic value.
# ``choices`` records what the callsite actually accepts.

SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        INSTALL_BATCH_PROJECT_SETUP_START,
        command="install",
        summary="Set up tracked project directories now?",
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        INSTALL_BATCH_PROJECT_SETUP_SCAN_MODE,
        command="install",
        summary="Scan only git repositories (1) or all directories (2).",
        type="enum",
        default="1",
        choices=("1", "2"),
    ),
    PromptSpec(
        INSTALL_SETTINGS_PROJECTS_DIR,
        command="install",
        summary="Root directory holding your projects.",
        type="path",
        default=None,  # runtime-derived from get_projects_dir()
    ),
    PromptSpec(
        INSTALL_SETTINGS_PLANS_DIR,
        command="install",
        summary="Plans directory: 1=.plans, 2=plans, 3=custom, or type a name.",
        type="enum",
        default="1",
    ),
    PromptSpec(
        INSTALL_SETTINGS_PLANS_DIR_CUSTOM,
        command="install",
        summary="Custom plans directory name (asked only when 3 is chosen).",
        type="bare-dirname",
        default=".plans",
    ),
    PromptSpec(
        INSTALL_SETTINGS_PLANS_GITIGNORED,
        command="install",
        summary="Track the plans directory in git? (no = gitignored)",
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        INSTALL_SETTINGS_PLANS_COMPLETION,
        command="install",
        summary="On plan completion: 1=archive, 2=delete.",
        type="enum",
        default="1",
        choices=("1", "2"),
    ),
    PromptSpec(
        INSTALL_QUALITY_REPORT_VIEWER,
        command="install",
        summary="Which detected report viewer to use (menu index; last entry is None).",
        type="enum",
        default="1",
    ),
    PromptSpec(
        INSTALL_QUALITY_REPORT_RETENTION_MODE,
        command="install",
        summary="Report retention: 1=auto-prune, 2=manual.",
        type="enum",
        default="1",
        choices=("1", "2"),
    ),
    PromptSpec(
        INSTALL_QUALITY_REPORT_RETENTION_DAYS,
        command="install",
        summary="Days to keep test reports before pruning.",
        type="int[1..3650]",
        default=30,
    ),
    PromptSpec(
        SETUP_TRACK_CURRENT_REPO,
        command="setup",
        summary="Track the current repository with AEC?",
        type="yes_no",
        default=True,
    ),
)


def _expand_configurable_instructions(family) -> list:
    from ..configurable_instructions import CONFIGURABLE_INSTRUCTIONS, get_all_agent_keys
    from ..prompt_ids import configurable_instruction_prompt_id

    out = []
    for key, meta in CONFIGURABLE_INSTRUCTIONS.items():
        for agent_key in get_all_agent_keys():
            out.append(
                PromptSpec(
                    configurable_instruction_prompt_id(key, agent_key),
                    command=family.command,
                    summary=f"{meta.get('description', key)} — for {agent_key}",
                    type="yes_no",
                    default=bool(meta.get("default", False)),
                )
            )
    return out


def _expand_optional_rules(family) -> list:
    from ..preferences import OPTIONAL_FEATURES
    from ..prompt_ids import optional_rule_prompt_id

    return [
        PromptSpec(
            optional_rule_prompt_id(key),
            command=family.command,
            summary=str(meta.get("prompt", key)).strip(),
            type="yes_no",
            default=bool(meta.get("default", False)),
        )
        for key, meta in OPTIONAL_FEATURES.items()
    ]


FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        INSTALL_CONFIGURABLE_INSTRUCTIONS_PREFIX,
        command="install",
        summary="Per-agent configurable-instruction toggles.",
        expander=_expand_configurable_instructions,
    ),
    DynamicPromptFamily(
        PREFS_OPTIONAL_RULES_PREFIX,
        command="install",
        summary="Optional rule/feature opt-ins.",
        expander=_expand_optional_rules,
    ),
)
