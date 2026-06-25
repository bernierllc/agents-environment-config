"""Preferences commands: aec preferences {list|set|reset}"""

try:
    import typer

    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib.console import Console
from ..lib import preferences as lib_preferences
from ..lib.preferences import (
    OPTIONAL_FEATURES,
    get_preference,
    set_preference,
    reset_preference,
)

# String-valued settings (stored under preferences "settings", not the boolean
# optional_rules). Maps key -> allowed values.
STRING_SETTINGS = {"plugins.execution": {"default", "instructions-only"}}

if HAS_TYPER:
    app = typer.Typer(help="Manage optional feature preferences")
else:
    app = None


def list_preferences() -> None:
    """List all optional features and their current settings."""
    Console.header("Optional Feature Preferences")

    for key, feature in OPTIONAL_FEATURES.items():
        value = get_preference(key)
        if value is True:
            status = Console._colorize(Console.GREEN, "\u2713 enabled")
        elif value is False:
            status = Console._colorize(Console.RED, "\u2717 disabled")
        else:
            status = Console._colorize(Console.YELLOW, "\u2014 not set (will prompt on next run)")

        Console.print(f"  {key:<25} {status}")
        Console.print(f"  {Console.dim(feature['description'])}")
        Console.print()

    for key in STRING_SETTINGS:
        value = lib_preferences.get_setting(key) or "default"
        Console.print(f"  {key:<25} {Console._colorize(Console.GREEN, value)}")
        Console.print()


def set_pref(feature: str, value: str) -> None:
    """Set an optional feature on or off."""
    if feature in STRING_SETTINGS:
        allowed = STRING_SETTINGS[feature]
        value = value.strip().lower()
        if value not in allowed:
            Console.error(f"Invalid value: {value}.")
            Console.print(f"Allowed values: {', '.join(sorted(allowed))}")
            raise SystemExit(1)
        lib_preferences.set_setting(feature, value)
        Console.success(f"Set: {feature} = {value}")
        return

    if feature not in OPTIONAL_FEATURES:
        Console.error(f"Unknown feature: {feature}")
        Console.print(f"Available features: {', '.join(OPTIONAL_FEATURES.keys())}")
        raise SystemExit(1)

    if value.lower() in ("on", "true", "yes", "1"):
        set_preference(feature, True)
        Console.success(f"Enabled: {feature}")
    elif value.lower() in ("off", "false", "no", "0"):
        set_preference(feature, False)
        Console.success(f"Disabled: {feature}")
    else:
        Console.error(f"Invalid value: {value}. Use 'on' or 'off'.")
        raise SystemExit(1)


def reset_pref(feature: str) -> None:
    """Reset a preference so the user will be re-prompted."""
    if feature in STRING_SETTINGS:
        # ponytail: lib has no settings-delete; set back to "default" (the
        # unset sentinel). Add lib_preferences.clear_setting() if a real
        # "remove the key" distinction is ever needed.
        lib_preferences.set_setting(feature, "default")
        Console.success(f"Reset: {feature} = default")
        return

    reset_preference(feature)
    Console.success(f"Reset: {feature} (will prompt on next CLI run)")


# Typer command decorators
if HAS_TYPER:

    @app.command("list")
    def list_cmd():
        """List all optional features and their current settings."""
        list_preferences()

    @app.command("set")
    def set_cmd(
        feature: str = typer.Argument(..., help="Feature name (e.g., leave-it-better)"),
        value: str = typer.Argument(..., help="'on' or 'off'"),
    ):
        """Enable or disable an optional feature."""
        set_pref(feature, value)

    @app.command("reset")
    def reset_cmd(
        feature: str = typer.Argument(..., help="Feature name to reset"),
    ):
        """Reset a preference (will re-prompt on next CLI run)."""
        reset_pref(feature)
