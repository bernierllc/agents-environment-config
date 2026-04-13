"""Interactive per-repo scheduling: which suites run on the daily OS job."""

from __future__ import annotations

from pathlib import Path
from typing import List

from .console import Console


def merge_discovery_into_suites(project_dir: Path, suites: dict) -> List[str]:
    """Add detected npm/pytest scripts, extended hooks, and framework defaults.

    Mutates ``suites`` in place. Does not change ``scheduled``.

    Returns:
        Names of suites newly added.
    """
    from .test_detection import (
        TEST_FRAMEWORK_HOOKS,
        detect_test_frameworks,
        scan_extended_test_commands,
        scan_test_scripts,
    )

    added: List[str] = []
    for entry in scan_test_scripts(project_dir) + scan_extended_test_commands(project_dir):
        name = entry["name"]
        if name not in suites:
            suites[name] = {"command": entry["command"], "cleanup": None}
            added.append(name)

    for fw in detect_test_frameworks(project_dir):
        key = f"fw:{fw['key']}"
        if key not in suites:
            cmd = TEST_FRAMEWORK_HOOKS[fw["key"]]["default_command"]
            suites[key] = {"command": cmd, "cleanup": None}
            added.append(key)

    return added


def move_scheduled_item(scheduled: List[str], from_1: int, to_1: int) -> bool:
    """Move one entry in the scheduled list by 1-based indices.

    Mutates ``scheduled`` in place. Indices are positions in the numbered
    **scheduled** list (not the full suites dict).

    Returns:
        True if the move was applied, False if indices were out of range.
    """
    n = len(scheduled)
    if n < 2:
        return False
    if from_1 < 1 or from_1 > n or to_1 < 1 or to_1 > n:
        return False
    i, j = from_1 - 1, to_1 - 1
    item = scheduled.pop(i)
    scheduled.insert(j, item)
    return True


def _normalize_scheduled(scheduled: List[str], suites: dict) -> List[str]:
    """Drop unknown suite keys, preserve order, de-dupe."""
    seen = set()
    out: List[str] = []
    for name in scheduled:
        if name in suites and name not in seen:
            out.append(name)
            seen.add(name)
    return out


def normalize_scheduled_for_suites(scheduled: List[str], suites: dict) -> List[str]:
    """Public alias for :func:`_normalize_scheduled` (CLI callers and detect)."""
    return _normalize_scheduled(scheduled, suites)


def _print_state(repo: Path, scheduled: List[str], suites: dict) -> None:
    Console.subheader(f"Scheduled suites (this repo: {repo.name})")
    if not scheduled:
        Console.info("  (none — daily job will skip this repo until you add some)")
    else:
        for i, name in enumerate(scheduled, 1):
            cmd = suites.get(name, {}).get("command", "")
            Console.print(f"  {i}) {name}: {cmd}")

    Console.print()
    Console.subheader("Defined suites in .aec.json")
    if not suites:
        Console.info("  (none)")
    else:
        for name, cfg in sorted(suites.items()):
            mark = " [scheduled]" if name in scheduled else ""
            Console.print(f"  {name}: {cfg.get('command', '')}{mark}")


def _print_help() -> None:
    Console.print()
    Console.subheader("Commands")
    Console.print("  l, list          Show scheduled + defined suites")
    Console.print("  m, merge         Merge detected commands into suites (from hooks)")
    Console.print("  r N              Remove scheduled item number N (see list above)")
    Console.print("  + NAME           Append suite NAME to the schedule (must exist)")
    Console.print("  n NAME :: CMD    Add a new suite NAME with shell command CMD, then schedule it")
    Console.print("  o A,B,C          Set schedule order to suite names (comma-separated)")
    Console.print("  mv FROM TO       Move scheduled item FROM position to TO (1-based, see list)")
    Console.print("  s, save          Write .aec.json and exit")
    Console.print("  q, quit          Exit without saving")
    Console.print("  h, help          Show this help")
    Console.print()
    Console.info(
        "Daily clock and OS registration are global: run `aec test schedule -g` "
        "from any directory."
    )
    Console.print()


def run_repo_schedule_interactive(repo: Path) -> None:
    """Edit ``test.scheduled`` / ``test.suites`` for the current tracked repo."""
    from .aec_json import load_aec_json, save_aec_json, create_skeleton, update_test_section

    data = load_aec_json(repo)
    if data is None:
        data = create_skeleton(repo.name)

    test = data.setdefault("test", {"suites": {}, "prerequisites": [], "scheduled": []})
    suites = dict(test.get("suites") or {})
    scheduled = list(test.get("scheduled") or [])
    if isinstance(scheduled, str):  # tolerate bad type
        scheduled = [scheduled] if scheduled else []
    scheduled = _normalize_scheduled(scheduled, suites)

    Console.header("AEC — schedule tests for this repository")
    Console.print(
        "This edits which suites run when the **global** daily job fires "
        "(same as `aec test run -g`)."
    )
    _print_help()
    _print_state(repo, scheduled, suites)

    dirty = False

    while True:
        try:
            line = input("\nschedule> ").strip()
        except EOFError:
            Console.print()
            if dirty:
                Console.warning("EOF — exiting without save.")
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if verb in ("h", "help", "?"):
            _print_help()
        elif verb in ("l", "list"):
            _print_state(repo, scheduled, suites)
        elif verb in ("m", "merge"):
            new_keys = merge_discovery_into_suites(repo, suites)
            if new_keys:
                Console.success(f"Merged {len(new_keys)} suite(s): {', '.join(new_keys)}")
                dirty = True
            else:
                Console.info("Nothing new to merge (already present or not detected).")
            _print_state(repo, scheduled, suites)
        elif verb == "r" and arg.isdigit():
            idx = int(arg)
            if 1 <= idx <= len(scheduled):
                removed = scheduled.pop(idx - 1)
                Console.success(f"Removed '{removed}' from schedule.")
                dirty = True
            else:
                Console.error(f"No scheduled item #{idx}.")
            _print_state(repo, scheduled, suites)
        elif verb == "+" and arg:
            name = arg.strip()
            if name not in suites:
                Console.error(f"Unknown suite '{name}'. Use `merge` or `n NAME :: CMD` first.")
            elif name in scheduled:
                Console.info(f"'{name}' is already scheduled.")
            else:
                scheduled.append(name)
                Console.success(f"Scheduled '{name}'.")
                dirty = True
            _print_state(repo, scheduled, suites)
        elif verb == "n" and " :: " in arg:
            left, cmd = arg.split(" :: ", 1)
            name = left.strip()
            cmd = cmd.strip()
            if not name or not cmd:
                Console.error("Usage: n NAME :: COMMAND")
            else:
                suites[name] = {"command": cmd, "cleanup": None}
                if name not in scheduled:
                    scheduled.append(name)
                Console.success(f"Added suite '{name}' and scheduled it.")
                dirty = True
            _print_state(repo, scheduled, suites)
        elif verb == "o" and arg:
            names = [x.strip() for x in arg.split(",") if x.strip()]
            missing = [n for n in names if n not in suites]
            if missing:
                Console.error(f"Unknown suite(s): {', '.join(missing)}")
            else:
                scheduled = names
                Console.success("Schedule order updated.")
                dirty = True
            _print_state(repo, scheduled, suites)
        elif verb == "mv" and arg:
            bits = arg.split()
            if len(bits) == 2 and bits[0].isdigit() and bits[1].isdigit():
                f_, t_ = int(bits[0]), int(bits[1])
                if move_scheduled_item(scheduled, f_, t_):
                    Console.success(f"Moved scheduled item {f_} to position {t_}.")
                    dirty = True
                else:
                    Console.error("mv: use two positions 1–N from the scheduled list (need ≥2 items).")
            else:
                Console.error("Usage: mv FROM TO   (e.g. mv 1 3)")
            _print_state(repo, scheduled, suites)
        elif verb in ("s", "save"):
            scheduled = _normalize_scheduled(scheduled, suites)
            update_test_section(data, suites=suites, scheduled=scheduled)
            save_aec_json(repo, data)
            Console.success(f"Saved {repo / '.aec.json'}")
            break
        elif verb in ("q", "quit", "exit"):
            if dirty:
                Console.warning("Discarding unsaved changes.")
            break
        else:
            Console.error("Unknown command — type `help`.")
