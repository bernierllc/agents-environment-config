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
AGENT_TOOLS_MIGRATE_RERUN = "agent_tools.migrate.rerun"
AGENT_TOOLS_ROLLBACK_CONFIRM = "agent_tools.rollback.confirm"


SPECS: tuple[PromptSpec, ...] = (
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
            "Other tracked repos have outdated items too: 'y' upgrades them all, "
            "'list' just lists them, anything else skips."
        ),
        default="n",
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
