# aec/commands/deprecation.py
"""Deprecation shims for old AEC commands."""

import sys


def deprecation_warning(old_cmd: str, new_cmd: str) -> None:
    """Print a deprecation warning to stderr."""
    print(
        f"Warning: `{old_cmd}` is deprecated and will be removed in the next major version.\n"
        f"Use `{new_cmd}` instead.\n",
        file=sys.stderr,
    )
