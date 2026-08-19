"""Catalogued prompts for ``aec skills {install|uninstall|update|sync}``.

None of these are org-overlay-eligible: they are per-invocation confirmations
and selections over whatever skills happen to be present, not settings an
administrator can decide once. They are catalogued so an agent can enumerate
them and answer with ``--answers``.

The confirmations that name a specific skill are dynamic families with
``expander=None`` — the concrete set depends on the installed/available skills
at run time. Build concrete IDs with
:func:`~.install_flow_area.item_prompt_id`.
"""
from __future__ import annotations

from .spec import DynamicPromptFamily, PromptSpec

# --- Dynamic prefixes (concrete ID appends the skill name) ------------------

SKILLS_INSTALL_OVERWRITE_PREFIX = "skills.install.overwrite"
SKILLS_UNINSTALL_CONFIRM_PREFIX = "skills.uninstall.confirm"
SKILLS_UPDATE_OVERWRITE_LOCAL_PREFIX = "skills.update.overwrite_local"

# --- Static IDs -------------------------------------------------------------

SKILLS_UPDATE_APPLY = "skills.update.apply"
SKILLS_INSTALL_SELECTION = "skills.install.selection"
SKILLS_SYNC_CHOICE = "skills.sync.choice"
SKILLS_SYNC_SELECTION = "skills.sync.selection"


SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        SKILLS_UPDATE_APPLY,
        command="skills update",
        summary="Apply the listed skill updates. Same decision as -y.",
        type="yes_no",
        default=True,
    ),
    PromptSpec(
        SKILLS_INSTALL_SELECTION,
        command="skills install",
        summary=(
            "Which of the listed skills to install: 'a' for all, 'n' for none, "
            "or a 1-based number selection like '1,3,5-8'."
        ),
        default="n",
    ),
    PromptSpec(
        SKILLS_SYNC_CHOICE,
        command="skills sync",
        summary=(
            "What to do with pending updates and new skills: 'a' all, 's' pick "
            "from a numbered list, anything else skips. The answer is lowercased, "
            "so the displayed 'S' for skip is not distinguishable from 's'."
        ),
        default="s",
    ),
    PromptSpec(
        SKILLS_SYNC_SELECTION,
        command="skills sync",
        summary=(
            "1-based number selection like '1,3,5-8' over the numbered list of "
            "updates and new skills. Only asked after choosing 's'."
        ),
        default="",
    ),
)

FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        SKILLS_INSTALL_OVERWRITE_PREFIX,
        command="skills install",
        summary="A skill of that name is already installed — overwrite it?",
    ),
    DynamicPromptFamily(
        SKILLS_UNINSTALL_CONFIRM_PREFIX,
        command="skills uninstall",
        summary="Remove one skill directory from the installed skills dir.",
    ),
    DynamicPromptFamily(
        SKILLS_UPDATE_OVERWRITE_LOCAL_PREFIX,
        command="skills update",
        summary=(
            "The installed skill differs from both its install baseline and the "
            "source — overwrite and lose the local edits?"
        ),
    ),
)
