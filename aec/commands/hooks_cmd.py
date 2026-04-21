"""`aec hooks ...` CLI sub-app.

Phase 1 ships only `validate`. Install/upgrade/remove/diff/list land in
Task 12.
"""

from pathlib import Path

import typer
from rich.console import Console

hooks_app = typer.Typer(help="Manage item hooks (Claude/Gemini/Cursor/git)")
_console = Console()


@hooks_app.command("validate")
def validate(
    path: Path = typer.Argument(..., help="Path to hooks.json"),
    item_version: str = typer.Option(
        ..., "--item-version",
        help="Expected item frontmatter version (matched against hooks.json `version`)",
    ),
) -> None:
    """Validate a hooks.json file against the schema and spec §1.6 rules."""
    from ..lib.hooks.schema import HooksSchemaError, load_hooks_file
    from ..lib.hooks.validator import validate_hooks_file

    try:
        hf = load_hooks_file(path)
    except FileNotFoundError as e:
        _console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2)
    except HooksSchemaError as e:
        _console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2)

    errors, warnings = validate_hooks_file(hf, expected_version=item_version)

    for w in warnings:
        where = f" [{w.hook_id}]" if w.hook_id else ""
        _console.print(f"[yellow]warning[/yellow]{where}: {w.message}")

    for err in errors:
        where = f" [{err.hook_id}]" if err.hook_id else ""
        _console.print(f"[red]error[/red]{where}: {err.message}")

    if errors:
        raise typer.Exit(1)

    _console.print(f"[green]ok[/green] {path} is valid")
