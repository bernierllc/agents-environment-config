# aec/commands/config_cmd.py
"""aec config — manage preferences (replaces aec preferences)."""

from .preferences import list_preferences, set_pref, reset_pref


def run_config_list() -> None:
    list_preferences()


def run_config_set(key: str, value: str) -> None:
    set_pref(key, value)


def run_config_reset(key: str) -> None:
    reset_pref(key)
