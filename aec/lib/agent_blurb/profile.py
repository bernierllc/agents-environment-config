"""Profile model, command classification, and matrix expansion.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §7.
"""

from copy import deepcopy
from enum import Enum
from typing import Dict, Tuple

ITEM_TYPES: Tuple[str, ...] = ("agents", "skills", "rules", "packages", "plugins")

DEFAULT_PROFILE = "balanced"

PROFILES: Dict[str, Dict[str, Dict[str, str]]] = {
    "conservative": {it: {"additive": "ask"} for it in ITEM_TYPES},
    "balanced": {
        "agents":   {"additive": "ask"},
        "skills":   {"additive": "auto"},
        "rules":    {"additive": "auto"},
        "packages": {"additive": "ask"},
        "plugins":  {"additive": "ask"},
    },
    "permissive": {it: {"additive": "auto"} for it in ITEM_TYPES},
}


class CommandClass(str, Enum):
    READ_ONLY = "read_only"
    ADDITIVE = "additive"
    DESTRUCTIVE = "destructive"


READ_ONLY_COMMANDS = frozenset({
    "list", "status", "doctor", "search", "info", "outdated",
})

ADDITIVE_COMMANDS = frozenset({"install", "add"})

DESTRUCTIVE_COMMANDS = frozenset({
    "remove", "uninstall", "update", "upgrade", "reset", "init", "untrack",
})


def expand_profile(name: str) -> Dict[str, Dict[str, str]]:
    """Return a deep copy of the profile's matrix.

    Raises ValueError if name is not a known profile.
    """
    if name not in PROFILES:
        raise ValueError(f"Unknown profile: {name!r}")
    return deepcopy(PROFILES[name])


def classify_command(cmd: str) -> CommandClass:
    """Classify an AEC subcommand by its risk class.

    Unknown commands are conservatively classified as DESTRUCTIVE so future
    AEC versions that ship new commands fail closed (ask-first) until the
    blurb is refreshed.
    """
    if cmd in READ_ONLY_COMMANDS:
        return CommandClass.READ_ONLY
    if cmd in ADDITIVE_COMMANDS:
        return CommandClass.ADDITIVE
    return CommandClass.DESTRUCTIVE
