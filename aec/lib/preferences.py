"""User preferences for optional AEC features."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import AEC_HOME, AEC_PREFERENCES

# Registry of optional features that users can enable/disable.
# Each feature has:
#   description: Human-readable name
#   prompt: Text shown when asking the user
#   default: Default value if user just presses Enter
OPTIONAL_FEATURES: Dict[str, Dict[str, Any]] = {
    "leave-it-better": {
        "description": "Leave It Better Than You Found It",
        "prompt": (
            "Enable the 'Leave It Better' rule? This instructs AI agents to\n"
            "track and fix any bugs, lint issues, or broken tests they discover\n"
            "while working. (Y/n): "
        ),
        "default": True,
    },
    "update_check": {
        "description": "Automatic Update Check",
        "prompt": (
            "Enable automatic update checks? AEC will check GitHub weekly\n"
            "for new releases and show a notification. (Y/n): "
        ),
        "default": True,
    },
    "port_registry_enabled": {
        "description": "Port Registry",
        "prompt": (
            "Enable the port registry? AEC will track port assignments across\n"
            "your projects to prevent collisions. (Y/n): "
        ),
        "default": True,
    },
    "scheduled_tests_enabled": {
        "description": "Scheduled Test Runs",
        "prompt": (
            "Enable scheduled test runs? AEC can run your test suites on a\n"
            "schedule and generate reports. (Y/n): "
        ),
        "default": False,
    },
}


def _default_preferences() -> Dict[str, Any]:
    """Return the default (empty) preferences structure."""
    return {
        "schema_version": "1.2",
        "optional_rules": {},
        "settings": {},
        "configurable_instructions": {},
    }


def load_preferences() -> Dict[str, Any]:
    """
    Load preferences from ~/.agents-environment-config/preferences.json.

    Returns the default structure if the file doesn't exist or is corrupt.
    """
    if not AEC_PREFERENCES.exists():
        return _default_preferences()

    try:
        content = AEC_PREFERENCES.read_text()
        data = json.loads(content)
        if not isinstance(data, dict):
            return _default_preferences()
        # Ensure required keys exist
        data.setdefault("schema_version", "1.0")
        data.setdefault("optional_rules", {})
        data.setdefault("settings", {})
        data.setdefault("configurable_instructions", {})
        return data
    except (json.JSONDecodeError, OSError):
        return _default_preferences()


def save_preferences(prefs: Dict[str, Any]) -> None:
    """
    Save preferences to ~/.agents-environment-config/preferences.json.

    Creates the AEC_HOME directory if it doesn't exist.
    """
    AEC_HOME.mkdir(parents=True, exist_ok=True)
    AEC_PREFERENCES.write_text(json.dumps(prefs, indent=2) + "\n")


def get_preference(key: str) -> Optional[bool]:
    """
    Get the value of an optional feature preference.

    Returns:
        True if enabled, False if disabled, None if never asked.
    """
    prefs = load_preferences()
    entry = prefs.get("optional_rules", {}).get(key)
    if entry is None:
        return None
    return entry.get("enabled")


def set_preference(key: str, enabled: bool) -> None:
    """
    Set an optional feature preference with a timestamp.

    Creates/updates the preference entry and saves to disk.
    """
    prefs = load_preferences()
    prefs["optional_rules"][key] = {
        "enabled": enabled,
        "asked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_preferences(prefs)


def get_setting(key: str) -> Optional[Any]:
    """
    Get a setting value from the settings section of preferences.

    Returns:
        The setting value, or None if not set.
    """
    prefs = load_preferences()
    return prefs.get("settings", {}).get(key)


def set_setting(key: str, value: Any) -> None:
    """
    Set a setting value in the settings section of preferences.

    The value can be any JSON-serializable type (str, bool, int, etc.).
    Creates/updates the setting and saves to disk.
    """
    prefs = load_preferences()
    prefs["settings"][key] = value
    save_preferences(prefs)


def reset_preference(key: str) -> None:
    """
    Remove a preference so the user will be re-prompted on next CLI run.
    """
    prefs = load_preferences()
    prefs.get("optional_rules", {}).pop(key, None)
    save_preferences(prefs)


def check_pending_preferences() -> None:
    """
    Check for unanswered optional features and prompt the user.

    Called as a pre-command hook in the CLI. If all features have been
    answered (enabled or disabled), this is a fast no-op (single file read).
    """
    pending = get_pending_prompts()
    if not pending:
        return

    from .console import Console

    Console.print()
    Console.subheader("Optional Features")
    Console.print("AEC has optional rules you can enable for your AI agents.\n")

    for feature in pending:
        try:
            response = input(feature["prompt"]).strip().lower()
        except EOFError:
            response = ""

        if response == "":
            enabled = feature["default"]
        elif response in ("y", "yes"):
            enabled = True
        elif response in ("n", "no"):
            enabled = False
        else:
            # Treat any unrecognized input as the default
            enabled = feature["default"]

        set_preference(feature["key"], enabled)

        if enabled:
            Console.success(f"Enabled: {feature['description']}")
        else:
            Console.info(f"Disabled: {feature['description']}")

    Console.print()


def get_instruction_config(instruction_key: str) -> Optional[Dict[str, Any]]:
    """Get the per-agent configuration for a configurable instruction.

    Returns:
        Dict of {agent_key: enabled} if configured, None if never asked.
    """
    prefs = load_preferences()
    entry = prefs.get("configurable_instructions", {}).get(instruction_key)
    if entry is None:
        return None
    return entry.get("agents")


def set_instruction_config(
    instruction_key: str, agents: Dict[str, bool]
) -> None:
    """Save per-agent configuration for a configurable instruction.

    Args:
        instruction_key: The instruction identifier.
        agents: {agent_key: enabled} mapping.
    """
    prefs = load_preferences()
    prefs["configurable_instructions"][instruction_key] = {
        "agents": agents,
        "configured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_preferences(prefs)


def is_instruction_configured(instruction_key: str) -> bool:
    """Check whether a configurable instruction has been configured."""
    prefs = load_preferences()
    return instruction_key in prefs.get("configurable_instructions", {})


def get_pending_prompts() -> List[Dict[str, Any]]:
    """
    Get optional features that haven't been asked about yet.

    Compares OPTIONAL_FEATURES registry against stored preferences.
    Returns a list of dicts with keys: key, description, prompt, default.
    """
    prefs = load_preferences()
    answered = prefs.get("optional_rules", {})

    pending = []
    for key, feature in OPTIONAL_FEATURES.items():
        if key not in answered:
            pending.append({
                "key": key,
                "description": feature["description"],
                "prompt": feature["prompt"],
                "default": feature["default"],
            })

    return pending
