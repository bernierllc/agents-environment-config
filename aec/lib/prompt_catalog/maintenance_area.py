"""Catalogued prompts for ``aec upgrade`` and ``aec agent-tools``.

All of these are per-invocation confirmations over local state, so none are
org-overlay-eligible. The rollback confirmation in particular is destructive:
it is catalogued so an agent can *see* it, not so a policy can pre-answer it.

The per-item overwrite confirmation is a dynamic family with ``expander=None``
— the concrete set depends on which installed items drifted. Build concrete
IDs with :func:`~.install_flow_area.item_prompt_id`.
"""
from __future__ import annotations

from .spec import DynamicPromptFamily, PromptSpec

# --- Dynamic prefixes (concrete ID appends the item name) -------------------

UPGRADE_OVERWRITE_LOCAL_PREFIX = "upgrade.overwrite_local"

# --- Static IDs -------------------------------------------------------------

UPGRADE_RUN_UPDATE_FIRST = "upgrade.run_update_first"
UPGRADE_OTHER_REPOS = "upgrade.other_repos"
UPGRADE_PLUGINS_CONFIRM = "upgrade.plugins.confirm"
AGENT_TOOLS_MIGRATE_RERUN = "agent_tools.migrate.rerun"
AGENT_TOOLS_ROLLBACK_CONFIRM = "agent_tools.rollback.confirm"
MIGRATE_AGENTS_MD_CONFIRM = "migrate.agents_md.confirm"
MIGRATE_AGENTS_MD_TIDY_CONFIRM = "migrate.agents_md.tidy_confirm"
ROLLBACK_APPLY_CONFIRM = "rollback.apply.confirm"
ROLLBACK_OVERWRITE_EDITS = "rollback.apply.overwrite_edits"


SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        UPGRADE_PLUGINS_CONFIRM,
        command="upgrade",
        summary="Run the plugin install/update commands for outdated plugins. Same decision as -y.",
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        UPGRADE_RUN_UPDATE_FIRST,
        command="upgrade",
        summary=(
            "Sources look stale — run `aec update` before upgrading. Anything "
            "other than no runs the update."
        ),
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        UPGRADE_OTHER_REPOS,
        command="upgrade",
        summary=(
            "Other tracked repos have outdated items too (they are listed above "
            "the prompt): 'y' upgrades them all."
        ),
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        AGENT_TOOLS_MIGRATE_RERUN,
        command="agent-tools migrate",
        summary=(
            "The migration marker already exists — re-run the migration to "
            "refresh the symlinks."
        ),
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        AGENT_TOOLS_ROLLBACK_CONFIRM,
        command="agent-tools rollback",
        summary=(
            "Destructive: removes ~/.agent-tools/ and the current agent symlinks, "
            "then restores the ones in the backup."
        ),
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        MIGRATE_AGENTS_MD_CONFIRM,
        command="migrate agents-md",
        summary=(
            "Move AGENTINFO.md into AGENTS.md and turn CLAUDE.md, GEMINI.md and "
            "QWEN.md into @AGENTS.md imports in the listed repos. Recorded; "
            "`aec rollback` undoes it."
        ),
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        MIGRATE_AGENTS_MD_TIDY_CONFIRM,
        command="migrate agents-md",
        summary=(
            "Run the chosen agent headless with the prompt shown, to remove "
            "duplication from the instruction files. Recorded; `aec rollback` undoes it."
        ),
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        ROLLBACK_APPLY_CONFIRM,
        command="rollback",
        summary="Restore the files listed to their state before the chosen change. Recorded as a new change.",
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        ROLLBACK_OVERWRITE_EDITS,
        command="rollback",
        summary=(
            "Destructive: some files were edited after the change (diff shown). "
            "Overwrite those edits? They stay recoverable by rolling back the rollback."
        ),
        type="yes_no",
        default=False,
        sensitive=True,
    ),
)

FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        UPGRADE_OVERWRITE_LOCAL_PREFIX,
        command="upgrade",
        summary=(
            "The installed item differs from both its install baseline and the "
            "source — overwrite and lose the local edits?"
        ),
    ),
)
