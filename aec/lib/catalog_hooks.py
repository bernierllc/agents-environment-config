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


def _catalog_item(item_type: str, name: str) -> Optional[tuple[Path, str]]:
    """Return (item dir, version) for a catalog item, or None if absent."""
    plural = _PLURAL.get(item_type)
    source_dir = get_source_dirs().get(plural) if plural else None
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

    Returns False when the item ships no hooks.json. Raises LookupError when
    the catalog has no such item.
    """
    found = _catalog_item(item_type, name)
    if found is None:
        raise LookupError(f"{item_type} not found in catalog: {name}")
    item_dir, version = found
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

    Items that left the catalog are unwired. Consent to custom checks given at
    install is kept. Re-wiring goes through ``install_item_hooks``, which
    validates the new hooks.json before retracting the old hooks, so a failed
    refresh leaves the previous hooks working. Returns one line per change
    (made, or pending when ``dry_run``).
    """
    changes: list[str] = []
    for state_file in sorted((repo / STATE_DIR).glob("*.json")):
        item_type, _, name = state_file.stem.partition(".")
        state = load_state(repo, item_type, name)
        found = _catalog_item(item_type, name)
        if found is None:
            if not dry_run:
                unwire(repo, item_type, name)
            changes.append(f"{name}: removed from catalog, hooks unwired")
            continue
        if state.item_version == found[1]:
            continue
        line = f"{name}: {state.item_version} -> {found[1]}"
        if not dry_run:
            try:
                wire(repo, item_type, name, allow_custom_check or state.allow_custom_check)
            except Exception as e:  # noqa: BLE001 — one item never blocks the rest
                line += f" not refreshed, previous hooks kept: {e}"
        changes.append(line)
    return changes
