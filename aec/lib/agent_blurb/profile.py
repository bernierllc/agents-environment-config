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


# Routine upkeep of already-installed items. Whether an agent may run these
# unprompted depends on the profile (see MAINTENANCE_STANCE); a custom
# profile always asks.
MAINTENANCE_STANCE: Dict[str, str] = {
    "conservative": "ask",
    "balanced": "auto",
    "permissive": "auto",
}


class CommandClass(str, Enum):
    READ_ONLY = "read_only"
    ADDITIVE = "additive"
    MAINTENANCE = "maintenance"
    DESTRUCTIVE = "destructive"


READ_ONLY_COMMANDS = frozenset({
    "list", "doctor", "search", "info", "outdated",
    "discover", "discover-repos", "validate", "version",
})

ADDITIVE_COMMANDS = frozenset({"install"})

MAINTENANCE_COMMANDS = frozenset({"update", "upgrade"})

DESTRUCTIVE_COMMANDS = frozenset({
    "uninstall", "untrack", "setup", "prune", "configure-agent",
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
    if cmd in MAINTENANCE_COMMANDS:
        return CommandClass.MAINTENANCE
    return CommandClass.DESTRUCTIVE
