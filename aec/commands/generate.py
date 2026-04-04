# aec/commands/generate.py
"""aec generate rules|files, aec validate, aec prune — thin wrappers."""

from ..lib import Console


def run_generate_rules() -> None:
    from .rules import generate
    generate()


def run_generate_files() -> None:
    from .files import generate
    generate()


def run_validate() -> None:
    from .rules import validate
    validate()


def run_prune(yes: bool = False, dry_run: bool = False) -> None:
    from ..lib.tracking import prune_stale
    pruned = prune_stale(dry_run=dry_run)
    if not pruned:
        Console.success("No stale entries found.")
        return
    for entry in pruned:
        label = "Would prune" if dry_run else "Pruned"
        Console.print(f"  {label}: {entry.path}")
    if not dry_run:
        Console.success(f"Pruned {len(pruned)} stale entries.")
