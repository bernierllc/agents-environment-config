"""Test detection for ``aec test detect`` (uses same merge as ``aec test schedule``)."""

from __future__ import annotations

from typing import List

from ..lib.aec_json import create_skeleton, load_aec_json, save_aec_json, update_test_section
from ..lib.console import Console
from ..lib.test_detection import detect_test_frameworks
from ..lib.test_schedule_repo import merge_discovery_into_suites, normalize_scheduled_for_suites


def run_test_detect() -> None:
    """Re-run test framework detection for the current project."""
    from ..lib.scope import find_tracked_repo

    repo = find_tracked_repo()
    if repo is None:
        Console.error("Not inside a tracked project.")
        return

    Console.info(f"Detecting test frameworks in {repo.name}...")

    data = load_aec_json(repo)
    if data is None:
        data = create_skeleton(repo.name)

    test = data.setdefault("test", {"suites": {}, "prerequisites": [], "scheduled": []})
    suites = dict(test.get("suites") or {})
    frameworks = detect_test_frameworks(repo)
    added = merge_discovery_into_suites(repo, suites)

    if not frameworks and not suites:
        Console.info("No test frameworks or scripts detected.")
        return

    if frameworks:
        Console.subheader("Detected frameworks")
        for fw in frameworks:
            Console.success(f"{fw['display_name']} ({fw['detected_by']})")

    if added:
        Console.subheader("Merged into test.suites (same hooks as `aec test schedule` merge)")
        for name in added:
            Console.print(f"  {name}: {suites[name]['command']}")

    Console.subheader("Test commands available for scheduling")
    for name, cfg in sorted(suites.items()):
        Console.print(f"  {name}: {cfg['command']}")

    suite_names = sorted(suites.keys())
    prev_scheduled = test.get("scheduled") or []
    if isinstance(prev_scheduled, str):
        prev_scheduled = [prev_scheduled] if prev_scheduled else []
    prev_scheduled = [n for n in prev_scheduled if n in suites]

    scheduled: List[str] = []
    if suite_names:
        Console.print()
        for i, name in enumerate(suite_names, 1):
            Console.print(f"  {i}) {name}: {suites[name]['command']}")
        Console.print("  Type 'all', 'none', comma-separated numbers, or Enter to keep current")
        Console.print()

        try:
            choice = input(
                f"Selection [Enter=keep {prev_scheduled!r}]: "
            ).strip().lower()
        except EOFError:
            choice = ""

        if choice == "":
            scheduled = list(prev_scheduled)
        elif choice == "all":
            scheduled = list(suite_names)
        elif choice != "none":
            for part in choice.split(","):
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(suite_names):
                        scheduled.append(suite_names[idx])
                except ValueError:
                    pass
            # de-dupe preserving order
            seen = set()
            scheduled = [x for x in scheduled if not (x in seen or seen.add(x))]

    scheduled = normalize_scheduled_for_suites(scheduled, suites)

    update_test_section(data, suites=suites, scheduled=scheduled)
    save_aec_json(repo, data)

    Console.success("Updated test configuration")
    if scheduled:
        Console.info(f"Scheduled suites: {', '.join(scheduled)}")
