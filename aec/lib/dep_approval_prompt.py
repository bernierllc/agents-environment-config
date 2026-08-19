"""Dependency approval prompt for skill installs.

Handles the [y/n/each] prompt shown when a skill has dependencies that need
to be installed alongside it.
"""

from typing import List

from . import Console
from .prompt_catalog.install_flow_area import (
    INSTALL_DEPS_APPROVE_EACH_PREFIX,
    INSTALL_DEPS_APPROVE_PREFIX,
    INSTALL_DEPS_UPGRADE_PREFIX,
    item_prompt_id,
)
from .prompts import prompt


def prompt_dep_install(
    target: str,
    target_version: str,
    deps_to_install: List[dict],
    assume_yes: bool = False,
) -> bool:
    """Show dependency approval prompt and return True if all approved, False to abort.

    Format::

        Installing playwright-test-generator@3.5.0 will also install:

          verification-writer@3.3.0
            Reason: Reads verification page docs...

        Approve all? [y/n/each]:

    ``each`` enters per-skill approval — y/n for each dep individually.
    If any dep is rejected with ``each``, the entire install is aborted.

    ``n`` / cancel returns False (caller aborts, no partial state).

    Args:
        target: Name of the skill being installed.
        target_version: Version of the skill being installed.
        deps_to_install: List of dicts with keys ``name``, ``version``, ``reason``.
        assume_yes: When True, skip the prompt and return True (the ``-y`` flag).

    Returns:
        True if the install should proceed, False to abort.
    """
    if assume_yes or not deps_to_install:
        return True

    Console.print(f"\nInstalling {target}@{target_version} will also install:\n")
    for dep in deps_to_install:
        Console.print(f"  {dep['name']}@{dep['version']}")
        Console.print(f"    Reason: {dep['reason']}")

    Console.print()

    resp = prompt(
        item_prompt_id(INSTALL_DEPS_APPROVE_PREFIX, target),
        "Approve all? [y/n/each]: ",
        default="n",
        choices=["y", "n", "each"],
    ).strip().lower()

    if resp == "y":
        return True

    if resp == "each":
        for dep in deps_to_install:
            each_resp = prompt(
                item_prompt_id(INSTALL_DEPS_APPROVE_EACH_PREFIX, dep["name"]),
                f"  Install {dep['name']}@{dep['version']}? [y/N]: ",
                type="yes_no",
                default=False,
            ).strip().lower()
            if each_resp != "y":
                Console.info(f"Rejected {dep['name']}. Aborting full install.")
                return False
        return True

    # "n" or anything else → abort
    return False


def prompt_dep_upgrade_conflict(
    target: str,
    target_new_version: str,
    dep_name: str,
    required_min: str,
    installed_ver: str,
    assume_yes: bool = False,
) -> bool:
    """Prompt to upgrade a dep whose installed version no longer satisfies the updated target's constraint.

    Returns True if the dep should be upgraded (proceed with target upgrade),
    False to abort the target upgrade entirely.
    """
    if assume_yes:
        return True

    resp = prompt(
        item_prompt_id(INSTALL_DEPS_UPGRADE_PREFIX, dep_name),
        f"Updating {target} to {target_new_version} requires {dep_name} "
        f">={required_min} (currently {installed_ver}). "
        f"Update {dep_name} too? [y/n/cancel]: ",
        default="n",
        choices=["y", "n", "cancel"],
    ).strip().lower()

    return resp == "y"
