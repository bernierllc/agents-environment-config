"""Guard for installing a hook-bearing skill globally.

Global installs wire no hooks (hooks are repo-scoped), so a skill that ships
hooks silently loses that functionality when installed with `--global`. This
decides whether to warn-and-proceed, refuse, or ask the user to confirm.
"""

from pathlib import Path

GUARD_OK = "ok"            # no guard needed — proceed silently
GUARD_CONFIRM = "confirm"  # interactive global install — caller must prompt
GUARD_REFUSE = "refuse"    # non-interactive, no flag → abort
GUARD_ALLOWED = "allowed"  # non-interactive with --allow-dormant-hooks → warn + proceed


def count_item_hooks(item_dir: Path) -> int:
    """Number of hooks declared in the item's hooks.json (0 if absent/bad)."""
    from .schema import HooksSchemaError, load_hooks_file

    hf_path = Path(item_dir) / "hooks.json"
    if not hf_path.exists():
        return 0
    try:
        return len(load_hooks_file(hf_path).hooks)
    except (HooksSchemaError, OSError, ValueError):
        return 0


def dormant_guard_status(*, is_global: bool, hook_count: int,
                         assume_yes: bool, allow_dormant: bool) -> str:
    """Decide the guard outcome for a (maybe-global) install. Pure."""
    if not is_global or hook_count <= 0:
        return GUARD_OK
    if assume_yes:
        return GUARD_ALLOWED if allow_dormant else GUARD_REFUSE
    return GUARD_CONFIRM
