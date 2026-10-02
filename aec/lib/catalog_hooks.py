"""Hooks for items used in place in the aec repo.

In the aec repo the install target *is* the catalog (see
``scope.is_catalog_repo``), so its items are never copied, recorded in the
install manifest, or removed there. Their hooks are still wanted, and hook
wiring keeps its own per-repo state (``.aec/installed-hooks``), so it runs
against the catalog directory in place. The item's version follows the
catalog itself: a submodule bump is the upgrade, and ``refresh`` re-wires.
"""

from pathlib import Path
from typing import Optional

from .hooks.lifecycle import install_hooks_for_item, remove_hooks_for_item
from .hooks.state import STATE_DIR, load_state
from .sources import discover_available, get_source_dirs

_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def _catalog_item(repo: Path, item_type: str, name: str) -> Optional[tuple[Path, str]]:
    """Return (item dir, version) for an item in this checkout of the catalog.

    `repo` is the aec repo or a worktree of it; the item is read from `repo`,
    not from the installed checkout, so a worktree wires its own copy.
    """
    plural = _PLURAL.get(item_type)
    source_dir = get_source_dirs(repo).get(plural) if plural else None
    if not source_dir or not source_dir.exists():
        return None
    info = discover_available(source_dir, plural).get(name)
    if info is None:
        return None
    path = source_dir / info.get("path", name)
    # Directory-form rules (`my-rule/rule.md` + `hooks.json`) are discovered by
    # their content file; the item, and its hooks.json, is the directory.
    if path.is_file() and path.name == "rule.md":
        path = path.parent
    return path, info.get("version", "0.0.0")


def wire(repo: Path, item_type: str, name: str, allow_custom_check: bool = False) -> bool:
    """Wire an item's hooks from the catalog in place.

    Returns False when the item ships no hooks.json, unwiring any hooks an
    earlier version left. Raises LookupError when
    the catalog has no such item.
    """
    found = _catalog_item(repo, item_type, name)
    if found is None:
        raise LookupError(f"{item_type} not found in catalog: {name}")
    item_dir, version = found
    if not (item_dir / "hooks.json").exists():
        # A version that dropped its hooks: retract any it wired before.
        unwire(repo, item_type, name)
        return False
    return install_hooks_for_item(
        item_type=item_type,
        item_key=name,
        item_version=version,
        item_dir=item_dir,
        repo_root=repo,
        allow_custom_check=allow_custom_check,
    )


def unwire(repo: Path, item_type: str, name: str) -> bool:
    """Remove an item's hooks. Never touches the item's files."""
    return remove_hooks_for_item(item_type=item_type, item_key=name, repo_root=repo)


def refresh(repo: Path, allow_custom_check: bool = False, dry_run: bool = False) -> list[str]:
    """Re-wire every wired item whose catalog version moved.

    Items that left the catalog, or dropped their hooks.json, are unwired. Consent to custom checks given at
    install is kept. Re-wiring goes through ``install_item_hooks``, which
    renders the new hooks before retracting the old ones and restores the
    configs if any write fails, so a failed refresh leaves the previous hooks
    working; one item's failure never stops the rest. Returns one line per change
    (made, or pending when ``dry_run``).
    """
    changes: list[str] = []
    for state_file in sorted((repo / STATE_DIR).glob("*.json")):
        item_type, _, name = state_file.stem.partition(".")
        try:
            line = _refresh_one(repo, item_type, name, allow_custom_check, dry_run)
        except Exception as e:  # noqa: BLE001 — one item never blocks the rest
            line = f"{name}: not refreshed, previous hooks kept: {e}"
        if line:
            changes.append(line)
    return changes


def _refresh_one(
    repo: Path, item_type: str, name: str, allow_custom_check: bool, dry_run: bool,
) -> Optional[str]:
    """Refresh one wired item; return its change line, or None if current."""
    state = load_state(repo, item_type, name)
    found = _catalog_item(repo, item_type, name)
    if found is None:
        if not dry_run:
            unwire(repo, item_type, name)
        return f"{name}: removed from catalog, hooks unwired"
    line = name if state.item_version == found[1] else f"{name}: {state.item_version} -> {found[1]}"
    if not (found[0] / "hooks.json").exists():
        # The item dropped its hooks (with or without a version bump): retract them.
        if not dry_run:
            unwire(repo, item_type, name)
        return f"{line}: no hooks.json, hooks unwired"
    if state.item_version == found[1]:
        return None
    if not dry_run:
        wire(repo, item_type, name, allow_custom_check or state.allow_custom_check)
    return line
