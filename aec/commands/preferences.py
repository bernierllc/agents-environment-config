"""Preferences commands: aec preferences {list|set|reset}"""

try:
    import typer

    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib.console import Console
from ..lib.preferences import (
    OPTIONAL_FEATURES,
    get_preference,
    set_preference,
    reset_preference,
)

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


def set_pref(feature: str, value: str) -> None:
    """Set an optional feature on or off."""
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
