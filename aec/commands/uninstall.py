"""aec uninstall <type> <name> -- remove a skill, rule, or agent."""

import shutil
from pathlib import Path

from ..lib.console import Console
from ..lib.installed_store import remove_item_install
from ..lib.manifest_v2 import load_manifest, save_manifest, remove_install
from ..lib.scope import resolve_scope, ScopeError

VALID_TYPES = ("skill", "rule", "agent")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def _manifest_path() -> Path:
    """Return manifest path dynamically so monkeypatch can redirect Path.home()."""
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_uninstall(
    item_type: str,
    name: str,
    global_flag: bool = False,
    yes: bool = False,
) -> None:
    """Remove an installed skill, rule, or agent."""
    if item_type not in VALID_TYPES:
        Console.error(
            f"Unknown type: {item_type}. Must be one of: {', '.join(VALID_TYPES)}"
        )
        raise SystemExit(1)

    plural = TYPE_TO_PLURAL[item_type]

    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    target_dir = getattr(scope, f"{plural}_dir")
    item_path = target_dir / name

    if not item_path.exists():
        Console.warning(f"{item_type.title()} not found: {name}")
        return

    if not yes:
        scope_label = "global" if scope.is_global else str(scope.repo_path)
        try:
            resp = input(f"  Remove {name} from {scope_label}? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    if item_path.is_dir():
        shutil.rmtree(item_path)
    else:
        item_path.unlink()

    mp = _manifest_path()
    manifest = load_manifest(mp)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())
    remove_install(manifest, scope_key, plural, name)
    save_manifest(manifest, mp)

    # Dual-write to per-type installed file (best-effort during transition)
    remove_item_install(item_type, name)

    Console.success(f"Uninstalled {name}")
