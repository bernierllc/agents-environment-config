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
}


def _default_preferences() -> Dict[str, Any]:
    """Return the default (empty) preferences structure."""
    return {"schema_version": "1.0", "optional_rules": {}}


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


def reset_preference(key: str) -> None:
    """
    Remove a preference so the user will be re-prompted on next CLI run.
    """
    prefs = load_preferences()
    prefs.get("optional_rules", {}).pop(key, None)
    save_preferences(prefs)


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
