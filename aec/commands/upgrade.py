"""aec upgrade -- apply available upgrades to installed items."""

import shutil
from pathlib import Path

from ..lib.claude_plugins import is_claude_managed
from ..lib.console import Console
from ..lib.prompt_catalog.install_flow_area import item_prompt_id
from ..lib.prompt_catalog.maintenance_area import (
    UPGRADE_OTHER_REPOS,
    UPGRADE_OVERWRITE_LOCAL_PREFIX,
    UPGRADE_PLUGINS_CONFIRM,
    UPGRADE_RUN_UPDATE_FIRST,
)
from ..lib.prompts import prompt
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
            resp = prompt(
                UPGRADE_RUN_UPDATE_FIRST,
                "Run `aec update` first? [Y/n]: ",
                type="yes_no",
                default=True,
            ).strip().lower()
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
                resp = prompt(
                    UPGRADE_OTHER_REPOS,
                    "\nUpgrade them too? [y/N]: ",
                    type="yes_no",
                    default=False,
                )
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
        record_install(manifest, scope, "skills", vc.name, dep_ver, dep_hash, installed_as="dependency")
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
            record_install(manifest, scope, "skills", d.name, dep_ver, dep_hash, installed_as="dependency")
            record_item_install_pertype("skill", d.name, dep_ver, dep_hash)
            Console.success(f"  Installed new dep: {d.name} {dep_ver}")

    return True


def _upgrade_plugins(
    manifest: dict,
    scope: str,
    source_dir: Path,
    installed: dict,
    available: dict,
    yes: bool,
    dry_run: bool,
) -> bool:
    """Upgrade plugins through their installer, never by copying files.

    - Claude Code marketplace plugins: Claude Code decides what is newer.
      Each one goes through ``claude plugin update`` (a no-op when current)
      and the version Claude Code reports is recorded; the catalog's pinned
      version is not consulted. Running ``aec upgrade`` is the request, so
      there is no extra prompt: this is Claude Code's own update.
    - Plugins recorded under another install type (e.g. ponytail's old
      per-tool entry) are re-installed when the catalog version is newer,
      after one batch confirmation (skipped with ``--yes``).

    Both honor ``plugins.execution: instructions-only`` and a missing
    ``claude``. A record only advances when the commands succeeded.
    """
    from ..lib.claude_plugins import is_claude_managed

    managed = [(n, i) for n, i in installed.items() if is_claude_managed(i)]
    stale = [
        (n, i) for n, i in installed.items()
        if not is_claude_managed(i) and n in available
        and version_is_newer(available[n].get("version", "0.0.0"), i.get("version", "0.0.0"))
    ]
    upgraded = False
    if managed and _update_claude_plugins(manifest, scope, source_dir, managed, available, dry_run):
        upgraded = True
    if stale and _reinstall_plugins(manifest, scope, source_dir, stale, available, yes, dry_run):
        upgraded = True
    return upgraded


def _resolve_plugin_id(name: str, info: dict, source_dir: Path, available: dict) -> str:
    """The Claude Code plugin id for a recorded plugin (record first, then catalog)."""
    from ..lib.loadout import LoadoutError, load_loadout

    if info.get("pluginId"):
        return info["pluginId"]
    if name not in available:
        return ""
    try:
        manifest_def = load_loadout(source_dir / available[name].get("path", name))
    except LoadoutError:
        return ""
    return manifest_def.get("install", {}).get("plugin", "")


def _update_claude_plugins(
    manifest: dict, scope: str, source_dir: Path, managed: list, available: dict, dry_run: bool,
) -> bool:
    from ..lib.claude_plugins import commands_blocked, marketplace_of, refresh_marketplace, update_plugin
    from ..lib.manifest_v2 import record_plugin_install
    from ..lib.preferences import get_setting

    targets = []
    for name, info in managed:
        plugin_id = _resolve_plugin_id(name, info, source_dir, available)
        if not plugin_id:
            Console.warning(f"Plugin {name}: no Claude Code plugin id recorded or in the catalog; skipping.")
            continue
        targets.append((name, info, plugin_id))
    if not targets:
        return False

    blocked = commands_blocked(get_setting("plugins.execution"))
    if blocked:
        for _, _, plugin_id in targets:
            Console.print(f"  {blocked}; run manually -> claude plugin update {plugin_id}")
        return False
    if dry_run:
        for _, _, plugin_id in targets:
            Console.print(f"  would run: claude plugin update {plugin_id}")
        return True

    for marketplace in sorted({marketplace_of(pid) for _, _, pid in targets}):
        if not refresh_marketplace(marketplace):
            Console.warning(f"Could not refresh marketplace {marketplace}; updating from its cached catalog.")

    upgraded = False
    for name, info, plugin_id in targets:
        # A plugin recorded in several scopes is updated once per scope; Claude
        # Code installs at user scope, so repeats are harmless no-ops.
        result = update_plugin(plugin_id)
        if not result["ok"]:
            detail = f": {result['message']}" if result["message"] else ""
            Console.error(
                f"claude plugin update {plugin_id} failed{detail}; left at {info.get('version', '?')}."
            )
            continue
        new_v = result["new"] or info.get("version", "0.0.0")
        if result["outcome"] == "up_to_date":
            Console.info(f"Plugin {name} is up to date ({new_v}).")
        else:
            Console.success(
                f"Updated plugin {name} {result['old'] or info.get('version', '?')} -> {new_v} "
                "(restart Claude Code to apply)"
            )
            upgraded = True
        if new_v != info.get("version") or not info.get("pluginId"):
            record_plugin_install(
                manifest, scope, name, new_v,
                install_type="marketplace", targets=info.get("targets", ["claude"]),
                installed_as=info.get("installedAs", "explicit"), plugin_id=plugin_id,
            )
            record_item_install_pertype("plugin", name, new_v)
    return upgraded


def _reinstall_plugins(
    manifest: dict, scope: str, source_dir: Path, stale: list, available: dict, yes: bool, dry_run: bool,
) -> bool:
    import subprocess

    from ..lib.claude_plugins import installed_record
    from ..lib.config import detect_agents
    from ..lib.loadout import LoadoutError, load_loadout
    from ..lib.manifest_v2 import record_plugin_install
    from ..lib.plugin_install import install_plugin
    from ..lib.preferences import get_setting

    if dry_run:
        for name, info in stale:
            Console.print(
                f"  would upgrade plugin  {name}  {info.get('version', '0.0.0')} -> "
                f"{available[name].get('version', '0.0.0')}"
            )
        return True
    if not yes:
        names = ", ".join(name for name, _ in stale)
        resp = prompt(
            UPGRADE_PLUGINS_CONFIRM,
            f"Re-install {len(stale)} plugin(s) ({names})? [y/N]: ",
            type="yes_no",
            default=False,
        )
        if resp != "y":
            Console.info("Skipped plugins.")
            return False

    pref = get_setting("plugins.execution")
    detected = detect_agents()
    upgraded = False
    for name, info in stale:
        avail_v = available[name].get("version", "0.0.0")
        inst_v = info.get("version", "0.0.0")
        try:
            manifest_def = load_loadout(source_dir / available[name].get("path", name))
        except LoadoutError as exc:
            Console.warning(f"Invalid plugin '{name}': {exc}; skipping.")
            continue

        failed = []

        def runner(cmd):
            Console.print(f"  $ {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd)
            except OSError as exc:
                Console.error(f"Could not run {cmd[0]}: {exc}")
                failed.append(cmd)
                return None
            if result.returncode != 0:
                failed.append(cmd)
            return result

        result = install_plugin(
            manifest_def, detected,
            runner=runner, confirm=lambda *a: True, printer=Console.print, pref=pref,
        )
        if not result.get("executed"):
            Console.warning(
                f"{name} {inst_v} -> {avail_v} needs manual steps (printed above); "
                "left at its recorded version."
            )
            continue
        if failed:
            Console.error(f"Failed to upgrade plugin {name}: {' '.join(failed[0])} exited non-zero")
            continue
        new_v, plugin_id = installed_record(manifest_def, result)
        record_plugin_install(
            manifest, scope, name, new_v,
            install_type=result["install_type"], targets=result["targets"], plugin_id=plugin_id,
        )
        record_item_install_pertype("plugin", name, new_v)
        Console.success(f"Upgraded plugin {name} {inst_v} -> {new_v}")
        upgraded = True
    return upgraded


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
        if item_type == "plugins":
            # Plugins are installed by their own tooling, not copied files.
            if _upgrade_plugins(manifest, scope, source_dir, installed, available, yes, dry_run):
                upgraded = True
            continue
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
                        manifest, scope, item_type, name, avail_v, sh,
                        installed_as=info.get("installedAs", "explicit"),
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
                resp = prompt(
                    item_prompt_id(UPGRADE_OVERWRITE_LOCAL_PREFIX, name),
                    f"  {name} differs from install baseline and source; "
                    f"overwrite (lose local edits)? [y/N]: ",
                    type="yes_no",
                    default=False,
                ).strip().lower()
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
            record_install(
                manifest, scope, item_type, name, avail_v, content_hash,
                installed_as=info.get("installedAs", "explicit"),
            )

            # Dual-write to per-type installed file (best-effort during transition)
            record_item_install_pertype(item_type[:-1], name, avail_v, content_hash)

            Console.success(f"  {item_type[:-1]}  {name}  {inst_v} -> {avail_v}")

            # Refresh hooks (per-repo only). Remove old, install new from new tree.
            if scope != "global":
                try:
                    from ..lib.hooks.lifecycle import (
                        install_hooks_for_item,
                        remove_hooks_for_item,
                    )
                    repo_root = Path(scope)
                    remove_hooks_for_item(
                        item_type=item_type[:-1],
                        item_key=name,
                        repo_root=repo_root,
                    )
                    install_hooks_for_item(
                        item_type=item_type[:-1],
                        item_key=name,
                        item_version=avail_v,
                        item_dir=dst_path,
                        repo_root=repo_root,
                        allow_custom_check=yes,
                    )
                except PermissionError as e:
                    Console.warning(f"  hooks not refreshed: {e}")
                except Exception as e:  # noqa: BLE001
                    Console.warning(f"  hooks refresh failed for {name}: {e}")

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
                if item_type == "plugins" and is_claude_managed(info):
                    continue  # Claude Code tracks these; `aec upgrade` asks it.
                if name in available:
                    if version_is_newer(
                        available[name].get("version", "0.0.0"),
                        info.get("version", "0.0.0"),
                    ):
                        count += 1
        if count > 0:
            results.append((repo_path, count))
    return results
