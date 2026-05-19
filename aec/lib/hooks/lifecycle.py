"""High-level lifecycle helpers for hook install/remove.

Thin wrappers over `installer.install_item_hooks` / `remove_item_hooks` that
give command code a single best-effort entry point: no-op when there's
nothing to do, raise on real failures.
"""

from pathlib import Path
from typing import Sequence


def install_hooks_for_item(
    *,
    item_type: str,
    item_key: str,
    item_version: str,
    item_dir: Path,
    repo_root: Path,
    agents: Sequence[str] = ("claude", "gemini", "cursor", "git"),
    allow_custom_check: bool = False,
) -> bool:
    """Install hooks declared by an item if it ships a hooks.json.

    Returns True if hooks.json was present and processed, False if the item
    has no hooks.json (nothing to do).
    """
    if not (item_dir / "hooks.json").exists():
        return False
    from .installer import install_item_hooks

    install_item_hooks(
        item_type=item_type,
        item_key=item_key,
        item_version=item_version,
        item_dir=item_dir,
        repo_root=repo_root,
        agents=list(agents),
        allow_custom_check=allow_custom_check,
    )
    return True


def remove_hooks_for_item(
    *, item_type: str, item_key: str, repo_root: Path,
) -> bool:
    """Remove hooks recorded in state for an item.

    Returns True if state existed (and was removed), False if there was no
    state to act on. Driven entirely from the recorded state file so it works
    even when the source item directory has already been deleted.
    """
    from .state import _state_path, load_state, remove_state

    sp = _state_path(repo_root, item_type=item_type, item_key=item_key)
    if not sp.exists():
        return False
    state = load_state(repo_root, item_type=item_type, item_key=item_key)
    if not state.hooks_installed:
        remove_state(repo_root, item_type=item_type, item_key=item_key)
        return True
    from .installer import remove_item_hooks

    remove_item_hooks(item_type=item_type, item_key=item_key, repo_root=repo_root)
    return True
