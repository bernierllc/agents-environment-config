"""Detect many per-repo copies of the same item and offer a global install."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .console import Console
from .installed_store import record_item_install
from .manifest_v2 import get_installed, record_install, remove_install, save_manifest
from .preferences import load_preferences, save_preferences
from .scope import Scope
from .skills_manifest import hash_skill_directory

# Preferences keys (under settings/)
THRESHOLD_KEY = "global_install_multi_repo_threshold"
DISMISS_MAP_KEY = "skip_global_install_prompt_for"

# Default: prompt when a local install would be the 4th distinct repo (3 already have it).
DEFAULT_THRESHOLD = 3


def english_ordinal(n: int) -> str:
    """Return ``1st``, ``2nd``, ``3rd``, ``4th``, etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _item_label(item_type: str) -> str:
    """Singular label for prompts (skill, rule, agent)."""
    return item_type


def get_multi_repo_global_threshold() -> int:
    """Minimum number of *other* repos that must already record this item.

    When that count is reached, installing into a *new* repo triggers the
    global-install offer. Default ``3`` means the 4th distinct repo prompts.
    """
    prefs = load_preferences()
    raw = prefs.get("settings", {}).get(THRESHOLD_KEY, DEFAULT_THRESHOLD)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD
    return max(2, min(n, 50))


def is_global_install_prompt_dismissed(item_type: str, name: str) -> bool:
    """True if the user asked never to offer again for this item."""
    prefs = load_preferences()
    m = prefs.get("settings", {}).get(DISMISS_MAP_KEY) or {}
    return m.get(f"{item_type}:{name}") is True


def dismiss_global_install_prompt(item_type: str, name: str) -> None:
    """Remember not to offer the global migration prompt for this item."""
    prefs = load_preferences()
    prefs.setdefault("settings", {})
    prefs["settings"].setdefault(DISMISS_MAP_KEY, {})
    prefs["settings"][DISMISS_MAP_KEY][f"{item_type}:{name}"] = True
    save_preferences(prefs)


def repo_keys_with_item(manifest: dict, plural: str, name: str) -> List[str]:
    """Repo scope keys (absolute paths) that already record ``name``."""
    out: List[str] = []
    for repo_key, scope_data in manifest.get("repos", {}).items():
        if name in scope_data.get(plural, {}):
            out.append(repo_key)
    return out


def should_offer_global_multi_repo(
    manifest: dict,
    plural: str,
    name: str,
    current_repo: Path,
    item_type: str,
    *,
    assume_yes: bool,
) -> bool:
    """Return True if we should prompt before a new per-repo install."""
    if assume_yes:
        return False
    if is_global_install_prompt_dismissed(item_type, name):
        return False
    if name in get_installed(manifest, "global", plural):
        return False
    cur = str(current_repo.resolve())
    existing = repo_keys_with_item(manifest, plural, name)
    if cur in existing:
        return False
    return len(existing) >= get_multi_repo_global_threshold()


def _delete_item_at_scope(
    plural: str,
    name: str,
    scope: Scope,
) -> None:
    """Remove files for ``name`` under ``scope`` (skill dir, agent dir, or rule file)."""
    target = getattr(scope, f"{plural}_dir") / name
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def migrate_item_to_global(
    *,
    item_type: str,
    plural: str,
    name: str,
    item_info: Dict[str, Any],
    src: Path,
    manifest: dict,
    manifest_path: Path,
) -> None:
    """Remove per-repo installs and install ``name`` to global scope from ``src``."""
    repo_keys = repo_keys_with_item(manifest, plural, name)
    for rk in repo_keys:
        repo_path = Path(rk)
        scope_l = Scope(is_global=False, repo_path=repo_path)
        _delete_item_at_scope(plural, name, scope_l)
        remove_install(manifest, rk, plural, name)

    scope_g = Scope(is_global=True, repo_path=None)
    gdir = getattr(scope_g, f"{plural}_dir")
    gdst = gdir / name
    if gdst.exists():
        if gdst.is_dir():
            shutil.rmtree(gdst)
        else:
            gdst.unlink()
    gdir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, gdst, ignore=shutil.ignore_patterns(".*"))
    else:
        shutil.copy2(src, gdst)

    content_hash = hash_skill_directory(gdst) if gdst.is_dir() else ""
    record_install(
        manifest,
        "global",
        plural,
        name,
        item_info.get("version", "0.0.0"),
        content_hash,
    )
    save_manifest(manifest, manifest_path)
    record_item_install(
        item_type,
        name,
        item_info.get("version", "0.0.0"),
        content_hash,
    )


def prompt_multi_repo_global_or_proceed(
    *,
    item_type: str,
    plural: str,
    name: str,
    manifest: dict,
    current_repo: Path,
    item_info: Dict[str, Any],
    src: Path,
    manifest_path: Path,
    assume_yes: bool,
) -> str:
    """Handle multi-repo global offer. Returns ``global``, ``local``, or ``abort``."""
    if not should_offer_global_multi_repo(
        manifest, plural, name, current_repo, item_type, assume_yes=assume_yes
    ):
        return "local"

    existing = repo_keys_with_item(manifest, plural, name)
    upcoming = len(existing) + 1
    label = _item_label(item_type)
    ord_ = english_ordinal(upcoming)
    try:
        ans = input(
            f"You are about to install this {label} in your {ord_} tracked repo "
            f"({len(existing)} repo(s) already have it). "
            f"Would you like aec to convert this to a global install instead? [y/N]: "
        ).strip().lower()
    except EOFError:
        ans = "n"

    if ans == "y":
        migrate_item_to_global(
            item_type=item_type,
            plural=plural,
            name=name,
            item_info=item_info,
            src=src,
            manifest=manifest,
            manifest_path=manifest_path,
        )
        Console.success(f"Installed {name} globally (removed per-repo copies).")
        try:
            from .discovery_hooks import quick_scan_notification

            quick_scan_notification(Scope(is_global=True, repo_path=None))
        except ImportError:
            pass
        return "global"

    try:
        remember = input(
            "Stop offering to make this a global install for this item? [y/N]: "
        ).strip().lower()
    except EOFError:
        remember = "n"
    if remember == "y":
        dismiss_global_install_prompt(item_type, name)
        Console.info("Saved preference: will not ask again for this item.")
    return "local"
