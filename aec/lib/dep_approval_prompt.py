"""Dependency approval prompt for skill installs.

Handles the [y/n/each] prompt shown when a skill has dependencies that need
to be installed alongside it.
"""

from typing import List

from . import Console


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

    try:
        resp = input("Approve all? [y/n/each]: ").strip().lower()
    except EOFError:
        resp = "n"

    if resp == "y":
        return True

    if resp == "each":
        for dep in deps_to_install:
            try:
                each_resp = input(f"  Install {dep['name']}@{dep['version']}? [y/N]: ").strip().lower()
            except EOFError:
                each_resp = "n"
            if each_resp != "y":
                Console.info(f"Rejected {dep['name']}. Aborting full install.")
                return False
        return True

    # "n" or anything else → abort
    return False
