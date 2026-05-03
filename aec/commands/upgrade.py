"""aec upgrade -- apply available upgrades to installed items."""

import shutil
from pathlib import Path
from typing import Optional

from ..lib.console import Console
from ..lib.config import get_repo_root
from ..lib.filesystem import installed_dst_path, resolve_installed_path
from ..lib.installed_store import record_item_install as record_item_install_pertype
from ..lib.manifest_v2 import (
    load_manifest,
    save_manifest,
    get_installed,
    record_install,
    is_stale,
)
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import (
    version_is_newer,
    hash_skill_directory,
    plan_skill_directory_replace,
)
from ..lib.skill_dependencies import resolve_install_graph
from ..lib.dep_approval_prompt import prompt_dep_upgrade_conflict, prompt_dep_install


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


def _repair_extensionless_agents(
    manifest: dict,
    scope: str,
    target: Path,
    dry_run: bool,
) -> int:
    """Rename bare agent files (missing .md) to .md. Returns count of repairs."""
    repaired = 0
    installed = get_installed(manifest, scope, "agents")
    for name in installed:
        bare = target / name
        md_path = target / (name + ".md")
        if bare.exists() and bare.is_file() and not md_path.exists():
            if dry_run:
                Console.print(f"  would rename agent  {name}  (missing .md extension)")
            else:
                bare.rename(md_path)
                Console.info(f"  repaired agent  {name}  (renamed to {name}.md)")
            repaired += 1
    return repaired


def _check_and_upgrade_dep_conflicts(
    target: str,
    new_version: str,
    manifest: dict,
    scope: str,
    available: dict,
    source_dir: Path,
    target_dir: Path,
    yes: bool,
    dry_run: bool,
) -> bool:
    """Check dep constraints of the new skill version and resolve any conflicts.

    Reads the NEW skill's SKILL.md (from source_dir) and compares each declared
    dependency's min_version against the currently installed version.  For each
    conflict the user is prompted to upgrade the dep first; declining aborts the
    target skill upgrade.

    Returns True if the upgrade should proceed, False to skip this skill.
    """
    installed_skills = get_installed(manifest, scope, "skills")
    graph = resolve_install_graph(target, available, installed_skills, source_dir)

    if not graph.version_conflicts and not graph.to_install and not graph.missing and not graph.cycles:
        return True

    if graph.missing:
        Console.warning(
            f"  Skipping upgrade of {target}: required deps not in catalog: "
            + ", ".join(graph.missing)
        )
        return False

    if graph.cycles:
        for cycle in graph.cycles:
            Console.warning(f"  Dependency cycle: {' → '.join(cycle)}")
        Console.warning(f"  Skipping upgrade of {target} due to dependency cycle.")
        return False

    # Version conflicts: installed dep is below the new target's min_version
    for vc in graph.version_conflicts:
        if dry_run:
            Console.print(
                f"  would upgrade dep  {vc.name}  {vc.installed_ver} -> "
                f">={vc.required_min}  (required by {target} {new_version})"
            )
            continue

        approved = prompt_dep_upgrade_conflict(
            target, new_version, vc.name, vc.required_min, vc.installed_ver,
            assume_yes=yes,
        )
        if not approved:
            Console.info(f"  Skipped upgrade of {target} (dep constraint not met).")
            return False

        if vc.name not in available:
            Console.warning(f"  Cannot upgrade {vc.name}: not found in catalog.")
            return False

        dep_avail = available[vc.name]
        dep_src = source_dir / dep_avail.get("path", vc.name)
        dep_existing = resolve_installed_path(target_dir, vc.name)
        dep_dst = installed_dst_path(target_dir, vc.name, dep_src)

        if dep_existing.exists():
            if dep_existing.is_dir():
                shutil.rmtree(dep_existing)
            else:
                dep_existing.unlink()

        target_dir.mkdir(parents=True, exist_ok=True)
        if dep_src.is_dir():
            shutil.copytree(dep_src, dep_dst, ignore=shutil.ignore_patterns(".*"))
        else:
            shutil.copy2(dep_src, dep_dst)

        dep_hash = hash_skill_directory(dep_dst) if dep_dst.is_dir() else ""
        dep_ver = dep_avail.get("version", "0.0.0")
        record_install(manifest, scope, "skills", vc.name, dep_ver, dep_hash)
        record_item_install_pertype("skill", vc.name, dep_ver, dep_hash)
        Console.success(f"  Upgraded dep: {vc.name}  {vc.installed_ver} -> {dep_ver}")

    # New deps introduced by the upgraded version (not previously required)
    if graph.to_install and not dry_run:
        deps_to_prompt = [
            {
                "name": d.name,
                "version": available[d.name].get("version", "0.0.0"),
                "reason": d.reason,
            }
            for d in graph.to_install
        ]
        approved = prompt_dep_install(target, new_version, deps_to_prompt, assume_yes=yes)
        if not approved:
            Console.info(f"  Skipped upgrade of {target} (new dep install declined).")
            return False

        for d in graph.to_install:
            dep_avail = available[d.name]
            dep_src = source_dir / dep_avail.get("path", d.name)
            dep_existing = resolve_installed_path(target_dir, d.name)
            dep_dst = installed_dst_path(target_dir, d.name, dep_src)

            if dep_existing.exists():
                if dep_existing.is_dir():
                    shutil.rmtree(dep_existing)
                else:
                    dep_existing.unlink()

            target_dir.mkdir(parents=True, exist_ok=True)
            if dep_src.is_dir():
                shutil.copytree(dep_src, dep_dst, ignore=shutil.ignore_patterns(".*"))
            else:
                shutil.copy2(dep_src, dep_dst)

            dep_hash = hash_skill_directory(dep_dst) if dep_dst.is_dir() else ""
            dep_ver = dep_avail.get("version", "0.0.0")
            record_install(manifest, scope, "skills", d.name, dep_ver, dep_hash)
            record_item_install_pertype("skill", d.name, dep_ver, dep_hash)
            Console.success(f"  Installed new dep: {d.name} {dep_ver}")

    return True


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

        if item_type == "agents" and target.exists():
            repaired = _repair_extensionless_agents(manifest, scope, target, dry_run)
            if repaired and not dry_run:
                upgraded = True

        for name, info in installed.items():
            if name not in available:
                continue
            avail_v = available[name].get("version", "0.0.0")
            inst_v = info.get("version", "0.0.0")
            if not version_is_newer(avail_v, inst_v):
                continue

            src_path = source_dir / available[name].get("path", name)
            dst_path = installed_dst_path(target, name, src_path)
            existing_path = resolve_installed_path(target, name)

            if dry_run:
                Console.print(
                    f"  would upgrade {item_type[:-1]}  {name}  {inst_v} -> {avail_v}"
                )
                if item_type == "skills":
                    _check_and_upgrade_dep_conflicts(
                        name, avail_v, manifest, scope, available,
                        source_dir, target, yes, dry_run=True,
                    )
                upgraded = True
                continue

            # For skills, resolve dep constraints of the new version before upgrading
            if item_type == "skills":
                if not _check_and_upgrade_dep_conflicts(
                    name, avail_v, manifest, scope, available,
                    source_dir, target, yes, dry_run=False,
                ):
                    continue

            do_prompt = False
            if item_type == "skills" and src_path.is_dir() and existing_path.exists():
                plan = plan_skill_directory_replace(
                    existing_path, src_path, info, assume_yes=yes
                )
                if plan == "sync_manifest":
                    sh = hash_skill_directory(src_path)
                    record_install(
                        manifest, scope, item_type, name, avail_v, sh
                    )
                    record_item_install_pertype(
                        item_type[:-1], name, avail_v, sh
                    )
                    Console.info(
                        f"  {item_type[:-1]}  {name}  {inst_v} -> {avail_v}  "
                        "(tree matched source; manifest updated)"
                    )
                    upgraded = True
                    continue
                do_prompt = plan == "prompt"
            elif existing_path.exists() and not yes:
                current_hash = (
                    hash_skill_directory(existing_path) if existing_path.is_dir() else ""
                )
                recorded_hash = info.get("contentHash", "")
                if (
                    current_hash
                    and recorded_hash
                    and current_hash != recorded_hash
                ):
                    do_prompt = True

            if do_prompt:
                try:
                    resp = (
                        input(
                            f"  {name} differs from install baseline and source; "
                            f"overwrite (lose local edits)? [y/N]: "
                        )
                        .strip()
                        .lower()
                    )
                except EOFError:
                    resp = "n"
                if resp != "y":
                    Console.info(f"  Skipped: {name}")
                    continue

            if existing_path.exists():
                if existing_path.is_dir():
                    shutil.rmtree(existing_path)
                else:
                    existing_path.unlink()

            target.mkdir(parents=True, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns(".*"))
            else:
                shutil.copy2(src_path, dst_path)

            content_hash = hash_skill_directory(dst_path) if dst_path.is_dir() else ""
            record_install(manifest, scope, item_type, name, avail_v, content_hash)

            # Dual-write to per-type installed file (best-effort during transition)
            record_item_install_pertype(item_type[:-1], name, avail_v, content_hash)

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
