"""Discovery command -- scan for local items similar to AEC catalog."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.aec_json import load_aec_json
from ..lib.config import AEC_HOME
from ..lib.scope import resolve_scope, Scope, ScopeError
from ..lib.sources import discover_available, get_source_dirs

# Foundation libraries (built in separate branches, imported as if available)
from ..lib.similarity import MatchResult, scan, scan_local_items
from ..lib.catalog_hashes import load_catalog_hashes, regenerate_if_missing
from ..lib.dismissals import (
    save_dismissal,
    is_dismissed,
    clear_dismissals,
    prune_stale,
)
from ..lib.backup import backup_item, ensure_backup_gitignore
ITEM_TYPES = ("agents", "skills", "rules")

CONTRIBUTING_URLS = {
    "agents": "https://github.com/bernierllc/agency-agents/blob/main/CONTRIBUTING.md",
    "skills": "https://github.com/bernierllc/claude-skills/blob/main/CONTRIBUTING.md",
    "rules": "https://github.com/bernierllc/agents-environment-config/blob/main/CONTRIBUTING.md",
}


def _prompt_depth() -> int:
    """Prompt user for scan depth. Returns 1, 2, or 3."""
    Console.newline()
    Console.print("How deep should we scan?")
    Console.print("  1) Quick  -- Name matching only (fast, could be false match)")
    Console.print("  2) Normal -- Name match + content hash comparison (shows identical vs modified)")
    Console.print("  3) Deep   -- Full content similarity scan, finds renamed/similar files (<1 min for ~500 items)")
    Console.print("Choose [2]: ", end="")
    try:
        raw = input().strip()
    except EOFError:
        raw = ""
    if raw == "":
        return 2
    if raw in ("1", "2", "3"):
        return int(raw)
    Console.error(f"Invalid depth: {raw}. Must be 1, 2, or 3.")
    raise SystemExit(1)


def _format_match(index: int, result: MatchResult) -> str:
    """Format a single match result for display."""
    name = result.local_name
    match_type = result.match_type

    if match_type == "exact":
        icon = Console._colorize(Console.GREEN, "✓ Exact match")
    elif match_type == "modified":
        icon = Console._colorize(Console.YELLOW, "⚠ Modified (hash differs from AEC)")
    elif match_type == "renamed":
        icon = Console._colorize(Console.YELLOW, f"⚠ Renamed (identical to {result.catalog_item})")
    elif match_type == "similar":
        pct = int((result.similarity or 0) * 100)
        icon = Console._colorize(Console.YELLOW, f"⚠ Similar ({pct}%) to {result.catalog_item}")
    else:
        icon = Console.dim("? Unknown match type")

    return f"  {index}) {name:<40} {icon}"


def _prompt_action_menu() -> int:
    """Prompt user for how to handle discovered items. Returns 1-4."""
    Console.newline()
    Console.print("How would you like to handle these?")
    Console.print("  1) Install exact matches, then ask me about the rest")
    Console.print("  2) Review one by one")
    Console.print("  3) Replace all with AEC-managed versions (will ask about backups)")
    Console.print("  4) Skip -- don't install any")
    Console.print("Choose [1]: ", end="")
    try:
        raw = input().strip()
    except EOFError:
        raw = ""
    if raw == "":
        return 1
    if raw in ("1", "2", "3", "4"):
        return int(raw)
    Console.warning(f"Invalid choice: {raw}. Defaulting to skip.")
    return 4


def _prompt_backup() -> bool:
    """Prompt user for backup before replacing. Returns True for yes."""
    Console.print("  Back up original before replacing? [Y/n]: ", end="")
    try:
        raw = input().strip().lower()
    except EOFError:
        raw = ""
    return raw != "n"


def _prompt_review_item(result: MatchResult) -> str:
    """Prompt user about a single item. Returns 'install', 'skip'."""
    Console.print(f"  Replace with AEC version? [y/N]: ", end="")
    try:
        raw = input().strip().lower()
    except EOFError:
        raw = ""
    if raw == "y":
        return "install"
    return "skip"


def _install_item(result: MatchResult, scope: Scope, do_backup: bool) -> None:
    """Install a single matched item via the existing install path."""
    from ..commands.install_cmd import run_install

    item_type_singular = {
        "agents": "agent",
        "skills": "skill",
        "rules": "rule",
    }
    singular = item_type_singular.get(result.item_type, result.item_type)

    if do_backup:
        backup_item(Path(result.local_path), scope.repo_path)
        ensure_backup_gitignore(scope.repo_path)

    run_install(
        item_type=singular,
        name=result.catalog_item,
        global_flag=scope.is_global,
        yes=True,
    )


def _run_scan(
    scope: Scope,
    depth: int,
    rediscover: bool = False,
    catalog: dict = None,
    catalog_hashes: dict = None,
) -> list:
    """Run the scan logic without UI. Reusable by setup integration.

    Args:
        scope: Resolved scope (local or global).
        depth: Scan depth (1=Quick, 2=Normal, 3=Deep).
        rediscover: If True, clear dismissals before scanning.
        catalog: Dict of item_type -> {name -> item_info}.
        catalog_hashes: Loaded catalog hashes dict.

    Returns:
        List of MatchResult objects.
    """
    if catalog is None:
        catalog = {}
    if catalog_hashes is None:
        catalog_hashes = {}

    # Build installed manifest from .aec.json for scan_local_items
    aec_json = load_aec_json(scope.repo_path) if scope.repo_path else None
    installed_manifest = (aec_json or {}).get("installed", {})

    all_results = []

    scope_dirs = {
        "agents": scope.agents_dir,
        "skills": scope.skills_dir,
        "rules": scope.rules_dir,
    }

    for item_type in ITEM_TYPES:
        if rediscover:
            clear_dismissals(item_type, scope)

        # Find untracked local items
        installed = installed_manifest.get(item_type, {})
        local_items = scan_local_items(scope_dirs[item_type], item_type, installed)
        if not local_items:
            continue

        # Filter out dismissed items
        if not rediscover:
            local_items = [
                item for item in local_items
                if not is_dismissed(item_type, scope, item["name"])
            ]

        if not local_items:
            continue

        type_catalog = catalog.get(item_type, {})
        type_hashes = catalog_hashes.get(item_type, {})

        results = scan(
            local_items=local_items,
            catalog=type_catalog,
            catalog_hashes=type_hashes,
            depth=depth,
        )

        for r in results:
            r.item_type = item_type

        all_results.extend(results)

        # Prune stale dismissals
        prune_stale(item_type, scope, type_catalog)

    return all_results


def _present_results(
    results: list,
    scope: Scope,
    yes: bool = False,
    dry_run: bool = False,
) -> None:
    """Present scan results and handle interactive UI flow.

    Args:
        results: List of MatchResult objects from _run_scan.
        scope: Resolved scope.
        yes: If True, install exact matches and skip the rest.
        dry_run: If True, only display results without writing.
    """
    if not results:
        Console.info("No similar items found.")
        return

    Console.newline()
    Console.print(f"Found {Console.bold(str(len(results)))} items similar to AEC tracked items:")

    # Group by type and display
    index = 1
    for item_type in ITEM_TYPES:
        type_results = [r for r in results if r.item_type == item_type]
        if not type_results:
            continue
        Console.newline()
        Console.print(f"  {item_type.upper()}")
        for result in type_results:
            Console.print(_format_match(index, result))
            index += 1

    Console.newline()

    if dry_run:
        Console.info("Dry run -- no changes made.")
        return

    if yes:
        # Auto mode: install exact matches, skip everything else
        dismissed_count = 0
        dismissed_types = set()
        for result in results:
            if result.match_type == "exact":
                do_backup = True  # conservative default in --yes mode
                _install_item(result, scope, do_backup)
            else:
                save_dismissal(result.item_type, scope, result.local_name, _build_dismissal_record(result))
                dismissed_count += 1
                dismissed_types.add(result.item_type)

        if dismissed_count > 0:
            _show_contribution_message(dismissed_count, dismissed_types)
        return

    # Interactive menu
    action = _prompt_action_menu()

    if action == 4:
        # Skip all -- dismiss everything
        dismissed_types = set()
        for result in results:
            save_dismissal(result.item_type, scope, result.local_name, _build_dismissal_record(result))
            dismissed_types.add(result.item_type)
        _show_contribution_message(len(results), dismissed_types)
        return

    if action == 3:
        # Replace all with AEC versions
        do_backup = _prompt_backup()
        for result in results:
            _install_item(result, scope, do_backup)
        return

    if action == 1:
        # Install exact matches, then review the rest
        exact = [r for r in results if r.match_type == "exact"]
        remaining = [r for r in results if r.match_type != "exact"]

        if exact:
            do_backup = _prompt_backup()
            for result in exact:
                _install_item(result, scope, do_backup)

        if remaining:
            Console.newline()
            Console.print("Remaining items:")
            dismissed_count = 0
            dismissed_types = set()
            for result in remaining:
                Console.newline()
                Console.print(f"  {result.local_name} -- {result.match_type}")
                choice = _prompt_review_item(result)
                if choice == "install":
                    do_backup = _prompt_backup()
                    _install_item(result, scope, do_backup)
                else:
                    save_dismissal(result.item_type, scope, result.local_name, _build_dismissal_record(result))
                    Console.success("Skipped (won't ask again)")
                    dismissed_count += 1
                    dismissed_types.add(result.item_type)

            if dismissed_count > 0:
                _show_contribution_message(dismissed_count, dismissed_types)
        return

    if action == 2:
        # Review one by one
        dismissed_count = 0
        dismissed_types = set()
        for result in results:
            Console.newline()
            Console.print(f"  {result.local_name} -- {result.match_type}")
            if result.catalog_item:
                Console.print(f"    Matched to: {result.catalog_item}")
            choice = _prompt_review_item(result)
            if choice == "install":
                do_backup = _prompt_backup()
                _install_item(result, scope, do_backup)
            else:
                save_dismissal(result.item_type, scope, result.local_name, _build_dismissal_record(result))
                Console.success("Skipped (won't ask again)")
                dismissed_count += 1
                dismissed_types.add(result.item_type)

        if dismissed_count > 0:
            _show_contribution_message(dismissed_count, dismissed_types)
        return


def _build_dismissal_record(result: MatchResult) -> dict:
    """Build a dismissal record dict from a MatchResult."""
    record = {
        "dismissedAt": datetime.now(timezone.utc).isoformat(),
        "matchedCatalogItem": result.catalog_item,
        "matchedCatalogVersion": result.catalog_version,
        "matchedCatalogHash": result.catalog_hash,
        "localHash": result.local_hash,
        "matchType": result.match_type,
        "scanDepth": result.scan_depth,
    }
    if result.match_type == "similar":
        record["similarity"] = result.similarity
    return record


def _show_contribution_message(count: int, item_types: set) -> None:
    """Show contribution encouragement message once after all items processed."""
    Console.newline()
    Console.print(
        f"You skipped {count} item{'s' if count != 1 else ''}. "
        "If any would be useful to others, consider contributing:"
    )
    for item_type in sorted(item_types):
        url = CONTRIBUTING_URLS.get(item_type)
        if url:
            Console.print(f"  {url}")


def run_discover(
    global_flag: bool = False,
    rediscover: bool = False,
    depth: Optional[int] = None,
    yes: bool = False,
    dry_run: bool = False,
) -> None:
    """Run the catalog discovery command.

    Scans for local items similar to AEC catalog entries.

    Args:
        global_flag: If True, scan global scope (~/.claude/).
        rediscover: If True, re-surface previously dismissed items.
        depth: Scan depth (1=Quick, 2=Normal, 3=Deep). Prompts if None.
        yes: If True, install exact matches and skip non-exact.
        dry_run: If True, show results without writing.
    """
    Console.header("Catalog Discovery")

    # Validate scope
    if not global_flag:
        # Check .aec.json exists for local repos
        aec_json = load_aec_json(Path.cwd())
        if aec_json is None:
            Console.error(
                "This repo is not tracked by AEC. "
                "Run `aec setup <path>` first."
            )
            raise SystemExit(1)

    try:
        scope = resolve_scope(global_flag)
    except ScopeError as exc:
        Console.error(str(exc))
        raise SystemExit(1)

    # Load catalog
    source_dirs = get_source_dirs()
    if not source_dirs:
        Console.error("Could not find AEC source repository.")
        raise SystemExit(1)

    catalog = {}
    for item_type, source_dir in source_dirs.items():
        catalog[item_type] = discover_available(source_dir, item_type)

    # Load catalog hashes
    catalog_path = AEC_HOME / "catalog-hashes.json"
    catalog_hashes = load_catalog_hashes(catalog_path)
    if not catalog_hashes:
        catalog_hashes = regenerate_if_missing(catalog_path, source_dirs)
        if not catalog_hashes:
            Console.warning("Running name-only scan -- hash comparison unavailable.")
            if depth is None or depth > 1:
                depth = 1

    # Determine depth
    if depth is not None:
        if depth not in (1, 2, 3):
            Console.error(f"Invalid depth: {depth}. Must be 1, 2, or 3.")
            raise SystemExit(1)
    else:
        depth = _prompt_depth()

    Console.print("Scanning... ", end="")
    results = _run_scan(scope, depth, rediscover, catalog, catalog_hashes)
    Console.print("done.")

    _present_results(results, scope, yes=yes, dry_run=dry_run)
