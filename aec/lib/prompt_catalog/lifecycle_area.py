"""Catalogued prompts for removal/apply flows: uninstall, untrack, apply.

These are destructive-or-final confirmations rather than settings, so none of
them are org-overlay-eligible — a policy that pre-answers "yes, delete it" is
not a policy anyone wants. They are catalogued anyway so an agent can discover
them and answer deliberately with ``--answers``.

Most carry the item, repo, or project they act on, so they are dynamic
families with ``expander=None``: the concrete set depends on what the caller
is removing, which no static registry knows. The prefix is the contract; build
concrete IDs with :func:`~.install_flow_area.item_prompt_id`.
"""
from __future__ import annotations

from .spec import DynamicPromptFamily, PromptSpec

# --- Dynamic prefixes (concrete ID appends the item/repo/project name) -------

UNINSTALL_MCP_REMOVE_ENTRY_PREFIX = "uninstall.mcp.remove_entry"
UNINSTALL_MCP_PIP_UNINSTALL_PREFIX = "uninstall.mcp.pip_uninstall"
UNINSTALL_PLUGIN_REMOVE_PREFIX = "uninstall.plugin.remove"
UNINSTALL_PLUGIN_RUN_COMMAND_PREFIX = "uninstall.plugin.run_command"
UNINSTALL_SCOPE_GLOBAL_PREFIX = "uninstall.scope.global"
UNINSTALL_SCOPE_REPO_PREFIX = "uninstall.scope.repo"
UNINSTALL_MULTI_REPO_CHOICE_PREFIX = "uninstall.multi_repo.choice"
UNINSTALL_MULTI_REPO_EACH_PREFIX = "uninstall.multi_repo.each"
UNTRACK_CONFIRM_PREFIX = "untrack.confirm"

# --- Static IDs -------------------------------------------------------------

APPLY_PLUGINS_CONFIRM = "apply.plugins.confirm"
ORG_APPLY_CONFIRM = "org.apply.confirm"


SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        APPLY_PLUGINS_CONFIRM,
        command="apply",
        summary="Install the plugins an apply plan resolved to. Same decision as -y.",
        type="yes_no",
        default=False,
    ),
    PromptSpec(
        ORG_APPLY_CONFIRM,
        command="org apply",
        summary=(
            "Apply the printed org policy plan in guided mode. Managed mode "
            "never asks."
        ),
        type="yes_no",
        default=False,
    ),
)

FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        UNINSTALL_MCP_REMOVE_ENTRY_PREFIX,
        command="uninstall",
        summary="Remove an MCP server's mcpServers entry from the settings file.",
    ),
    DynamicPromptFamily(
        UNINSTALL_MCP_PIP_UNINSTALL_PREFIX,
        command="uninstall",
        summary=(
            "Also `pip uninstall` the MCP server's package. Defaults to no — the "
            "package may have been installed independently."
        ),
    ),
    DynamicPromptFamily(
        UNINSTALL_PLUGIN_REMOVE_PREFIX,
        command="uninstall",
        summary="Remove a plugin from the current scope.",
    ),
    DynamicPromptFamily(
        UNINSTALL_PLUGIN_RUN_COMMAND_PREFIX,
        command="uninstall",
        summary="Run a plugin's uninstall command(s).",
    ),
    DynamicPromptFamily(
        UNINSTALL_SCOPE_GLOBAL_PREFIX,
        command="uninstall --global",
        summary="Remove the item from the global scope.",
    ),
    DynamicPromptFamily(
        UNINSTALL_SCOPE_REPO_PREFIX,
        command="uninstall",
        summary="Remove the item from the current repo.",
    ),
    DynamicPromptFamily(
        UNINSTALL_MULTI_REPO_CHOICE_PREFIX,
        command="uninstall",
        summary=(
            "The item is installed in other repos too: 'a' all of them, 'e' decide "
            "per repo, 's' show where, 'g' only globally (default)."
        ),
        type="enum[a,e,s,g]",
    ),
    DynamicPromptFamily(
        UNINSTALL_MULTI_REPO_EACH_PREFIX,
        command="uninstall",
        summary=(
            "Uninstall from one specific repo during 'each' mode. The concrete ID "
            "appends that repo's path."
        ),
    ),
    DynamicPromptFamily(
        UNTRACK_CONFIRM_PREFIX,
        command="untrack",
        summary="Stop tracking a project. The concrete ID appends the project path.",
    ),
)
