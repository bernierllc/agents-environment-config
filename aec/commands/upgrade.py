"""aec upgrade -- apply available upgrades to installed items."""

import shutil
from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.config import get_repo_root
from ..lib.manifest_v2 import (
    load_manifest,
    save_manifest,
    get_installed,
    record_install,
    is_stale,
)
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import version_is_newer, hash_skill_directory


def _manifest_path() -> Path:
    """Compute manifest path dynamically so tests can monkeypatch Path.home()."""
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_upgrade(yes: bool = False, dry_run: bool = False) -> None:
    """Upgrade installed items to latest available versions."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    mp = _manifest_path()
    manifest = load_manifest(mp)

    # Staleness warning
    if is_stale(manifest) and not dry_run:
        Console.warning("Sources may be stale.")
        if not yes:
            try:
                resp = input("Run `aec update` first? [Y/n]: ").strip().lower()
            except EOFError:
                resp = "n"
            if resp != "n":
                from .update import run_update

                run_update()
                manifest = load_manifest(mp)

    source_dirs = get_source_dirs()
    any_upgraded = False

    Console.print("Upgrading global scope...")
    if _upgrade_scope(manifest, "global", source_dirs, yes, dry_run):
        any_upgraded = True
    else:
        Console.print("  (up to date)")

    local_repo = find_tracked_repo()
    if local_repo:
        Console.print(f"\nUpgrading {local_repo} (current repo)...")
        repo_key = str(local_repo.resolve())
        if _upgrade_scope(manifest, repo_key, source_dirs, yes, dry_run):
            any_upgraded = True
        else:
            Console.print("  (up to date)")

    if not dry_run:
        save_manifest(manifest, mp)

    # Offer to upgrade other repos
    all_repos = get_all_tracked_repos()
    other_repos = [r for r in all_repos if r != local_repo]
    if other_repos and not dry_run:
        outdated_repos = _find_outdated_repos(manifest, other_repos, source_dirs)
        if outdated_repos:
            Console.print(
                f"\n{len(outdated_repos)} other tracked repo(s) have upgrades:"
            )
            for repo_path, count in outdated_repos:
                Console.print(f"  {repo_path}    {count} item(s) outdated")
            if not yes:
                try:
                    resp = input("\nUpgrade them too? [y/N/list]: ").strip().lower()
                except EOFError:
                    resp = "n"
                if resp == "y":
                    for repo_path, _ in outdated_repos:
                        Console.print(f"\nUpgrading {repo_path}...")
                        _upgrade_scope(
                            manifest,
                            str(repo_path),
                            source_dirs,
                            yes=True,
                            dry_run=False,
                        )
                    save_manifest(manifest, mp)

    if not any_upgraded and not dry_run:
        Console.print("\nEverything is up to date.")

    # Quick-scan notification for global scope
    if not dry_run:
        try:
            from ..lib.discovery_hooks import quick_scan_notification
            from ..lib.scope import Scope
            scope = Scope(is_global=True, repo_path=None)
            quick_scan_notification(scope)
        except ImportError:
            pass


def _target_base(scope: str, item_type: str) -> Path:
    """Determine the target directory for an item type in a given scope."""
    if scope == "global":
        if item_type == "skills":
            return Path.home() / ".claude" / "skills"
        elif item_type == "agents":
            return Path.home() / ".claude" / "agents"
        else:
            return Path.home() / ".agent-tools" / "rules"
    else:
        repo_path = Path(scope)
        if item_type == "skills":
            return repo_path / ".claude" / "skills"
        elif item_type == "agents":
            return repo_path / ".claude" / "agents"
        else:
            return repo_path / ".agent-rules"


def _upgrade_scope(
    manifest: dict,
    scope: str,
    source_dirs: dict,
    yes: bool,
    dry_run: bool,
) -> bool:
    """Upgrade all items in a scope. Returns True if anything was upgraded."""
    upgraded = False
    for item_type, source_dir in source_dirs.items():
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        installed = get_installed(manifest, scope, item_type)
        target = _target_base(scope, item_type)

        for name, info in installed.items():
            if name not in available:
                continue
            avail_v = available[name].get("version", "0.0.0")
            inst_v = info.get("version", "0.0.0")
            if not version_is_newer(avail_v, inst_v):
                continue

            src_path = source_dir / available[name].get("path", name)
            dst_path = target / name

            if dry_run:
                Console.print(
                    f"  would upgrade {item_type[:-1]}  {name}  {inst_v} -> {avail_v}"
                )
                upgraded = True
                continue

            # Check for local modifications
            if dst_path.exists() and not yes:
                current_hash = (
                    hash_skill_directory(dst_path) if dst_path.is_dir() else ""
                )
                recorded_hash = info.get("contentHash", "")
                if current_hash and recorded_hash and current_hash != recorded_hash:
                    try:
                        resp = (
                            input(
                                f"  {name} has local modifications. Overwrite? [y/N]: "
                            )
                            .strip()
                            .lower()
                        )
                    except EOFError:
                        resp = "n"
                    if resp != "y":
                        Console.info(f"  Skipped: {name}")
                        continue

            if dst_path.exists():
                if dst_path.is_dir():
                    shutil.rmtree(dst_path)
                else:
                    dst_path.unlink()

            target.mkdir(parents=True, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns(".*"))
            else:
                shutil.copy2(src_path, dst_path)

            content_hash = hash_skill_directory(dst_path) if dst_path.is_dir() else ""
            record_install(manifest, scope, item_type, name, avail_v, content_hash)
            Console.success(f"  {item_type[:-1]}  {name}  {inst_v} -> {avail_v}")
            upgraded = True

    return upgraded


def _find_outdated_repos(
    manifest: dict, repos: list[Path], source_dirs: dict
) -> list[tuple[Path, int]]:
    """Find repos with outdated items. Returns list of (repo_path, count)."""
    results = []
    for repo_path in repos:
        repo_key = str(repo_path.resolve())
        count = 0
        for item_type, source_dir in source_dirs.items():
            if not source_dir or not source_dir.exists():
                continue
            available = discover_available(source_dir, item_type)
            installed = get_installed(manifest, repo_key, item_type)
            for name, info in installed.items():
                if name in available:
                    if version_is_newer(
                        available[name].get("version", "0.0.0"),
                        info.get("version", "0.0.0"),
                    ):
                        count += 1
        if count > 0:
            results.append((repo_path, count))
    return results
