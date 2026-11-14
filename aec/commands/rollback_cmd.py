"""aec rollback: list, inspect and undo changes AEC recorded as changesets.

Undoing a change records the undo as a new changeset linked to the original,
so rolling back a rollback redoes the change.
"""

from __future__ import annotations

import sys
from typing import Optional

from ..lib import changesets
from ..lib.console import Console
from ..lib.prompt_catalog.maintenance_area import ROLLBACK_APPLY_CONFIRM, ROLLBACK_OVERWRITE_EDITS
from ..lib.prompts import prompt


def _status(cs: changesets.Changeset) -> str:
    if cs.reversed_by:
        return f"rolled back by {cs.reversed_by}"
    if cs.reverses:
        return f"undoes {cs.reverses}"
    return ""


def _date(cs: changesets.Changeset) -> str:
    return cs.created_at[:16].replace("T", " ")


def run_rollback_list() -> int:
    items = changesets.list_changesets()
    if not items:
        Console.info(f"No recorded changes in {changesets.rollbacks_dir()}")
        return 0
    for i, cs in enumerate(items, 1):
        status = _status(cs)
        Console.print(
            f"  {i:>3}. {cs.id}  {_date(cs)}  {cs.short}"
            + (f"  {Console.dim('(' + status + ')')}" if status else "")
        )
    return 0


def _load(cs_id: str) -> Optional[changesets.Changeset]:
    try:
        return changesets.load(cs_id)
    except changesets.ChangesetNotFound:
        Console.error(f"No recorded change {cs_id}. See {Console.cmd('aec rollback list')}.")
        return None


def _print_detail(cs: changesets.Changeset) -> None:
    Console.header(cs.short)
    Console.print(f"  id:      {cs.id}")
    Console.print(f"  date:    {_date(cs)} UTC")
    Console.print(f"  kind:    {cs.kind}")
    if _status(cs):
        Console.print(f"  status:  {_status(cs)}")
    Console.print()
    for line in cs.long.splitlines():
        Console.print(f"  {line}")
    Console.print()
    edited = {fc.path for fc in changesets.conflicts(cs)}
    Console.print("  Rolling back would:")
    for fc in cs.files:
        verb = "delete " if fc.before is None else ("recreate" if fc.after is None else "restore")
        note = "  (edited since; would overwrite)" if fc.path in edited else ""
        Console.print(f"    {verb:<8} {fc.path}{note}")


def run_rollback_show(cs_id: str) -> int:
    cs = _load(cs_id)
    if cs is None:
        return 2
    _print_detail(cs)
    return 0


def run_rollback_apply(cs_id: str, force: bool = False, yes: bool = False) -> int:
    cs = _load(cs_id)
    if cs is None:
        return 2
    if cs.reversed_by:
        Console.error(
            f"{cs.id} was already rolled back by {cs.reversed_by}. "
            f"To redo it, roll that one back: {Console.cmd('aec rollback apply ' + cs.reversed_by)}"
        )
        return 1
    _print_detail(cs)
    Console.print()

    edited = changesets.conflicts(cs)
    if edited and not force:
        Console.warning("These files changed after AEC recorded this change:")
        for fc in edited:
            Console.print(changesets.diff_text(cs, fc) or f"    {fc.path} (deleted since)")
        answer = prompt(
            ROLLBACK_OVERWRITE_EDITS,
            "  Overwrite those edits? Rolling back this rollback brings them back. [y/N]: ",
            type="yes_no",
            default=False,
            sensitive=True,
        )
        if answer.strip().lower() != "y":
            Console.skip("Nothing changed")
            return 1
    elif not yes:
        answer = prompt(ROLLBACK_APPLY_CONFIRM, "  Roll back this change? [y/N]: ", type="yes_no", default=False)
        if answer.strip().lower() != "y":
            Console.skip("Nothing changed")
            return 0

    new = changesets.revert(cs.id, force=True)  # conflicts were confirmed above
    Console.success(f"Rolled back {cs.id}; recorded as {new.id}")
    Console.info(f"Redo: {Console.cmd('aec rollback apply ' + new.id)}")
    return 0


def run_rollback(cs_id: Optional[str] = None) -> int:
    """`aec rollback` with no subcommand: list, then let a person browse."""
    if cs_id:
        return run_rollback_show(cs_id)
    code = run_rollback_list()
    items = changesets.list_changesets()
    if not items or not sys.stdin.isatty():
        if items:
            Console.print()
            Console.info(f"Details: {Console.cmd('aec rollback show <id>')}  Undo: {Console.cmd('aec rollback apply <id>')}")
        return code
    while True:
        try:
            raw = input("\n  Number to view (Enter to quit): ").strip()
        except EOFError:
            return 0
        if not raw:
            return 0
        if not raw.isdigit() or not 1 <= int(raw) <= len(items):
            Console.warning(f"Enter 1-{len(items)}")
            continue
        cs = items[int(raw) - 1]
        if cs.reversed_by:
            _print_detail(cs)
        else:
            run_rollback_apply(cs.id)
        items = changesets.list_changesets()
        run_rollback_list()
