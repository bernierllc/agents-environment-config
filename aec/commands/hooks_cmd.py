"""`aec hooks ...` CLI sub-app.

Phase 1 ships only `validate`. Install/upgrade/remove/diff/list land in
Task 12.
"""

from pathlib import Path

import typer
from rich.console import Console

hooks_app = typer.Typer(help="Manage item hooks (Claude/Gemini/Cursor/git)")
_console = Console()


@hooks_app.command("verify")
def verify(
    repos: list[Path] = typer.Argument(
        None,
        help="Repos to check (default: every tracked repo)",
    ),
    repair: bool = typer.Option(
        False, "--repair",
        help="Re-wire drifted hooks from each item's repo-local source",
    ),
) -> None:
    """Report hooks that drifted out of agent settings files.

    State records that a hook was installed; an out-of-band edit can drop the
    entry while leaving state behind. This compares each recorded hook to the
    settings file by content fingerprint and reports MISSING drift. Exits 1 if
    drift remains, 0 if all recorded hooks are present. With --repair, re-wires
    drifted hooks (merge, never clobber) and then exits 0 if everything is OK.
    """
    from ..lib.hooks.drift import Drift, repair_repo, verify_repo
    from ..lib.tracked_repos import get_all_tracked_paths

    targets = list(repos) if repos else get_all_tracked_paths()
    if not targets:
        _console.print("[yellow]no tracked repos to check[/yellow]")
        raise typer.Exit(0)

    total_drift = 0
    for repo_root in targets:
        statuses = verify_repo(repo_root)
        if not statuses:
            continue
        drifted = [s for s in statuses if s.status is not Drift.OK]
        if drifted and repair:
            for r in repair_repo(repo_root):
                if r.repaired:
                    _console.print(
                        f"  [green]repaired[/green] {r.item_type}:{r.item_key}"
                    )
                elif r.detail and r.detail != "no drift":
                    _console.print(
                        f"  [yellow]cannot repair[/yellow] "
                        f"{r.item_type}:{r.item_key}: {r.detail}"
                    )
            statuses = verify_repo(repo_root)
            drifted = [s for s in statuses if s.status is not Drift.OK]
        if not drifted:
            _console.print(f"[green]ok[/green] {repo_root} ({len(statuses)} hooks)")
            continue
        total_drift += len(drifted)
        _console.print(f"[red]drift[/red] {repo_root}")
        for s in drifted:
            _console.print(
                f"  [red]{s.status.value}[/red] {s.item_type}:{s.item_key} "
                f"{s.hook_id} ({s.agent})"
            )

    if total_drift:
        hint = (
            "Some hooks could not be auto-repaired (see above)."
            if repair else
            "Re-run with --repair to restore them."
        )
        _console.print(f"\n[red]{total_drift} hook(s) drifted.[/red] {hint}")
        raise typer.Exit(1)


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
