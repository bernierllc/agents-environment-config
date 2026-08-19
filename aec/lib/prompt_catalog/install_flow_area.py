"""Catalogued prompts for the ``aec install`` execution flow.

Separate from ``install_area`` on purpose: those are the org-overlay-eligible
setup/settings prompts, these are the per-run confirmations an install asks as
it works (overwrite, reinstall, run this command, approve these deps). They are
not overlay-eligible — an org policy does not pre-approve "overwrite the copy
already on this machine" — but an agent still needs to discover and answer
them, so they live in the catalog.

Most are per-item, so their concrete IDs carry the item name and they are
declared as dynamic families. The expander is ``None``: the concrete set
depends on what the caller happens to be installing, which no static registry
knows. The prefix is the contract.
"""
from __future__ import annotations

from .spec import DynamicPromptFamily, PromptSpec

# --- Dynamic prefixes (concrete ID appends the item/dep name) ---------------

INSTALL_OVERWRITE_PREFIX = "install.overwrite"
INSTALL_REINSTALL_PREFIX = "install.reinstall"
INSTALL_HOOKS_DORMANT_PREFIX = "install.hooks.dormant"
INSTALL_MCP_PIP_PREFIX = "install.mcp.pip_install"
INSTALL_PLUGIN_RUN_PREFIX = "install.plugin.run_command"
INSTALL_PIPELINE_COPY_PREFIX = "install.verification_pipeline.copy_scripts"
INSTALL_GLOBAL_OFFER_CHOICE_PREFIX = "install.global_offer.choice"
INSTALL_GLOBAL_OFFER_DISMISS_PREFIX = "install.global_offer.dismiss"
INSTALL_DEPS_APPROVE_PREFIX = "install.dependencies.approve"
INSTALL_DEPS_APPROVE_EACH_PREFIX = "install.dependencies.approve_each"
INSTALL_DEPS_UPGRADE_PREFIX = "install.dependencies.upgrade"


def item_prompt_id(prefix: str, name: str) -> str:
    """Concrete ID for a per-item prompt: ``<prefix>.<name>``."""
    return f"{prefix}.{name}"


# --- Static IDs -------------------------------------------------------------
#
# Both are deliberately absent from PROMPTS_ALLOW_LIST (they are in
# PROMPTS_EXCLUDED_IDS): one depends on the local project list, the other is a
# free-form shell command. Excluded from the org overlay, still catalogued —
# an agent answering for the user with --answers is not an org policy.

INSTALL_BATCH_PROJECT_SETUP_PER_PROJECT = "install.batch_project_setup.per_project"
INSTALL_QUALITY_REPORT_VIEWER_COMMAND = "install.quality.report_viewer.command"

SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        INSTALL_BATCH_PROJECT_SETUP_PER_PROJECT,
        command="install",
        summary=(
            "Set up one discovered project during batch setup: y/Y to set up, "
            "n to skip, q to stop the batch. The concrete answer applies to "
            "every project in turn."
        ),
        type="enum[y,n,q]",
        default="y",
        choices=("y", "n", "q", ""),
    ),
    PromptSpec(
        INSTALL_QUALITY_REPORT_VIEWER_COMMAND,
        command="install",
        summary=(
            "Free-form command used to open test reports, with {file} as the "
            "placeholder. 'none' skips report viewing."
        ),
        type="string",
        default="none",
    ),
)

FAMILIES: tuple[DynamicPromptFamily, ...] = (
    DynamicPromptFamily(
        INSTALL_OVERWRITE_PREFIX,
        command="install",
        summary="Overwrite an item that already exists at the destination.",
    ),
    DynamicPromptFamily(
        INSTALL_REINSTALL_PREFIX,
        command="install",
        summary="Reinstall an MCP server or plugin already in the manifest.",
    ),
    DynamicPromptFamily(
        INSTALL_HOOKS_DORMANT_PREFIX,
        command="install --global",
        summary=(
            "Install a hook-bearing item globally anyway, leaving its hooks "
            "dormant. Same decision as --allow-dormant-hooks."
        ),
    ),
    DynamicPromptFamily(
        INSTALL_MCP_PIP_PREFIX,
        command="install",
        summary="Run `pip install` for an MCP server's Python package.",
    ),
    DynamicPromptFamily(
        INSTALL_PLUGIN_RUN_PREFIX,
        command="install",
        summary="Run a plugin's install command(s). Same decision as -y.",
    ),
    DynamicPromptFamily(
        INSTALL_PIPELINE_COPY_PREFIX,
        command="install",
        summary="Copy verification-pipeline scripts into scripts/verification-playwright/.",
    ),
    DynamicPromptFamily(
        INSTALL_GLOBAL_OFFER_CHOICE_PREFIX,
        command="install",
        summary=(
            "Convert a per-repo install to a global one after the item shows up "
            "in several tracked repos. 'y' migrates and removes per-repo copies."
        ),
    ),
    DynamicPromptFamily(
        INSTALL_GLOBAL_OFFER_DISMISS_PREFIX,
        command="install",
        summary="Stop offering the global-install conversion for this item.",
    ),
    DynamicPromptFamily(
        INSTALL_DEPS_APPROVE_PREFIX,
        command="install",
        summary=(
            "Approve installing a skill's dependencies: 'y' all, 'n' abort, "
            "'each' to decide per dependency."
        ),
        type="enum[y,n,each]",
    ),
    DynamicPromptFamily(
        INSTALL_DEPS_APPROVE_EACH_PREFIX,
        command="install",
        summary="Approve one dependency during 'each' mode. Any 'n' aborts the install.",
    ),
    DynamicPromptFamily(
        INSTALL_DEPS_UPGRADE_PREFIX,
        command="install",
        summary=(
            "Upgrade a dependency whose installed version no longer satisfies "
            "the updated target's constraint. 'n' aborts the target upgrade."
        ),
    ),
)
