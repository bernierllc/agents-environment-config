"""Skills commands: aec skills {list|install|uninstall|update}"""

import shutil
from pathlib import Path
from typing import List, Optional

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console, get_repo_root, AEC_HOME, CLAUDE_DIR
from ..lib.skills_manifest import (
    discover_available_skills,
    load_installed_manifest,
    save_installed_manifest,
    rebuild_manifest_from_installed,
    hash_skill_directory,
    version_is_newer,
    parse_skill_frontmatter,
)

if HAS_TYPER:
    app = typer.Typer(help="Manage Claude Code skills")
else:
    app = None

INSTALLED_MANIFEST = AEC_HOME / "installed-skills.json"


def _default_source_dir() -> Optional[Path]:
    repo = get_repo_root()
    return repo / ".claude" / "skills" if repo else None


def _default_installed_dir() -> Path:
    return CLAUDE_DIR / "skills"


def _parse_selection(text: str, max_num: int) -> set:
    """Parse user selection input like 'a', 'n', '1,3,5-8' into a set of numbers."""
    text = text.strip().lower()
    if text in ("a", "all"):
        return set(range(1, max_num + 1))
    if text in ("n", "none", ""):
        return set()

    result = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for i in range(int(start), int(end) + 1):
                    if 1 <= i <= max_num:
                        result.add(i)
            except ValueError:
                continue
        else:
            try:
                num = int(part)
                if 1 <= num <= max_num:
                    result.add(num)
            except ValueError:
                continue
    return result


def list_skills(
    source_dir: Optional[Path] = None,
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
) -> None:
    """Show all available and installed skills."""
    if source_dir is None:
        source_dir = _default_source_dir()
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.error("Skills source not found. Run 'aec install' first.")
        return

    available = discover_available_skills(source_dir)
    manifest = load_installed_manifest(manifest_path)
    installed = manifest.get("skills", {})

    # Collect all skill names
    all_names = sorted(set(list(available.keys()) + list(installed.keys())))

    # Find unmanaged skills in installed dir
    unmanaged = []
    if installed_dir.exists():
        for item in sorted(installed_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                if item.name not in available and item.name not in installed:
                    unmanaged.append(item.name)

    Console.header("Skills (source: agents-environment-config)")

    # Table header
    Console.print(f"  {'Name':<28} {'Installed':<12} {'Available':<12} Status")
    Console.print(f"  {'─' * 70}")

    update_count = 0
    installed_count = 0
    not_installed_count = 0

    for name in all_names:
        avail_version = available.get(name, {}).get("version", "—")
        inst_version = installed.get(name, {}).get("version", "—")

        if name in installed and name in available:
            installed_count += 1
            if version_is_newer(avail_version, inst_version):
                status = "update available"
                update_count += 1
            else:
                status = "up to date"
        elif name in installed:
            installed_count += 1
            status = "installed (not in source)"
        else:
            not_installed_count += 1
            status = "available"

        Console.print(f"  {name:<28} {inst_version:<12} {avail_version:<12} {status}")

    if unmanaged:
        Console.print()
        Console.print("  Other skills (not managed by AEC):")
        for name in unmanaged:
            Console.print(f"    {name}")

    Console.print()
    Console.print(
        f"  {installed_count} installed, {update_count} updates available, "
        f"{not_installed_count} not installed"
    )


def install_skills(
    names: List[str],
    source_dir: Optional[Path] = None,
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    yes: bool = False,
) -> None:
    """Install one or more skills by name."""
    if source_dir is None:
        source_dir = _default_source_dir()
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.error("Skills source not found. Run 'aec install' first.")
        raise SystemExit(1)

    available = discover_available_skills(source_dir)
    manifest = load_installed_manifest(manifest_path)

    # Ensure target dir exists
    installed_dir.mkdir(parents=True, exist_ok=True)

    for name in names:
        if name not in available:
            Console.error(f"Skill not found: {name}")
            Console.print(f"Available: {', '.join(sorted(available.keys()))}")
            raise SystemExit(1)

        skill_info = available[name]
        src = source_dir / skill_info.get("path", name)
        dst = installed_dir / name

        if dst.exists() and not yes:
            try:
                response = input(f"  {name} already exists. Overwrite? [y/N]: ").strip().lower()
            except EOFError:
                response = "n"
            if response != "y":
                Console.info(f"Skipped: {name}")
                continue

        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".*"))

        content_hash = hash_skill_directory(dst)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        manifest["skills"][name] = {
            "version": skill_info.get("version", "0.0.0"),
            "contentHash": content_hash,
            "installedAt": now,
            "source": "agents-environment-config",
        }

        Console.success(f"Installed: {name} ({skill_info.get('version', '0.0.0')})")

    save_installed_manifest(manifest, manifest_path)


def uninstall_skills(
    names: List[str],
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    yes: bool = False,
) -> None:
    """Uninstall one or more skills by name."""
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    manifest = load_installed_manifest(manifest_path)

    for name in names:
        skill_dir = installed_dir / name
        if not skill_dir.exists():
            Console.warning(f"Skill not found: {name}")
            continue

        if not yes:
            try:
                response = input(f"  Remove {name} from ~/.claude/skills/? [y/N]: ").strip().lower()
            except EOFError:
                response = "n"
            if response != "y":
                Console.info(f"Skipped: {name}")
                continue

        shutil.rmtree(skill_dir)
        manifest["skills"].pop(name, None)
        Console.success(f"Uninstalled: {name}")

    save_installed_manifest(manifest, manifest_path)


def update_skills(
    names: Optional[List[str]] = None,
    source_dir: Optional[Path] = None,
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    yes: bool = False,
) -> None:
    """Update installed skills to latest available versions."""
    if source_dir is None:
        source_dir = _default_source_dir()
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.error("Skills source not found. Run 'aec install' first.")
        raise SystemExit(1)

    available = discover_available_skills(source_dir)
    manifest = load_installed_manifest(manifest_path)
    installed = manifest.get("skills", {})

    # Determine which skills to check
    if names:
        to_check = {n: installed[n] for n in names if n in installed}
    else:
        to_check = dict(installed)

    updates = []
    for name, info in to_check.items():
        if name not in available:
            continue
        avail_version = available[name].get("version", "0.0.0")
        inst_version = info.get("version", "0.0.0")
        if version_is_newer(avail_version, inst_version):
            updates.append((name, inst_version, avail_version))

    if not updates:
        Console.success("All skills up to date.")
        return

    Console.print("Updates available:")
    for name, old_v, new_v in updates:
        Console.print(f"  {name}: {old_v} \u2192 {new_v}")

    if not yes:
        try:
            response = input("\nApply updates? [Y/n]: ").strip().lower()
        except EOFError:
            response = "n"
        if response == "n":
            Console.info("Update skipped.")
            return

    for name, old_v, new_v in updates:
        skill_dir = installed_dir / name
        skill_info = available[name]
        src = source_dir / skill_info.get("path", name)

        # Check for local modifications
        if skill_dir.exists():
            current_hash = hash_skill_directory(skill_dir)
            recorded_hash = installed.get(name, {}).get("contentHash", "")
            if current_hash != recorded_hash and not yes:
                try:
                    resp = input(f"  {name} has local modifications. Overwrite? [y/N]: ").strip().lower()
                except EOFError:
                    resp = "n"
                if resp != "y":
                    Console.info(f"Skipped: {name}")
                    continue

        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(src, skill_dir, ignore=shutil.ignore_patterns(".*"))

        content_hash = hash_skill_directory(skill_dir)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        manifest["skills"][name] = {
            "version": new_v,
            "contentHash": content_hash,
            "installedAt": now,
            "source": "agents-environment-config",
        }
        Console.success(f"Updated: {name} ({old_v} \u2192 {new_v})")

    save_installed_manifest(manifest, manifest_path)


def install_step(dry_run: bool = False) -> None:
    """Interactive skills install/update step for aec install.

    On first install: shows numbered list, lets user select.
    On subsequent: shows updates and new skills only.
    In dry-run: reports what would happen without prompting.
    """
    source_dir = _default_source_dir()
    installed_dir = _default_installed_dir()
    manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.info("Skills source not available \u2014 skipping")
        return

    available = discover_available_skills(source_dir)
    if not available:
        Console.info("No skills found in source")
        return

    # Load or recover manifest
    manifest = load_installed_manifest(manifest_path)
    if not manifest["skills"] and installed_dir.exists():
        # Attempt recovery from existing installed skills
        known_names = set(available.keys())
        manifest = rebuild_manifest_from_installed(installed_dir, known_names)
        if manifest["skills"]:
            save_installed_manifest(manifest, manifest_path)
            Console.info(f"Recovered manifest with {len(manifest['skills'])} skills")

    installed = manifest.get("skills", {})
    installed_dir.mkdir(parents=True, exist_ok=True)

    # Determine what's new and what's updated
    new_skills = {k: v for k, v in available.items() if k not in installed}
    updates = {}
    for name, info in installed.items():
        if name in available:
            avail_v = available[name].get("version", "0.0.0")
            inst_v = info.get("version", "0.0.0")
            if version_is_newer(avail_v, inst_v):
                updates[name] = (inst_v, avail_v)

    if not new_skills and not updates:
        Console.success("All skills up to date")
        return

    first_install = len(installed) == 0

    if dry_run:
        if updates:
            Console.info(f"Would offer {len(updates)} skill update(s)")
            for name, (old_v, new_v) in updates.items():
                Console.info(f"  {name}: {old_v} \u2192 {new_v}")
        if new_skills:
            Console.info(f"Would offer {len(new_skills)} new skill(s)")
        return

    if first_install:
        # Show all available skills numbered
        skill_list = sorted(available.keys())
        Console.print("\nAvailable skills:\n")
        for i, name in enumerate(skill_list, 1):
            info = available[name]
            desc = info.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            Console.print(f"  {i:>3}. {name} ({info.get('version', '?')}) \u2014 {desc}")

        Console.print()
        try:
            response = input("Install: [a]ll, [n]one, or enter numbers (e.g. 1,3,5-8): ").strip()
        except EOFError:
            response = "n"

        selected = _parse_selection(response, len(skill_list))
        names_to_install = [skill_list[i - 1] for i in sorted(selected)]

        if names_to_install:
            install_skills(
                names=names_to_install,
                source_dir=source_dir,
                installed_dir=installed_dir,
                manifest_path=manifest_path,
                yes=True,
            )
        else:
            Console.info("No skills selected")
    else:
        # Show updates and new skills
        if updates:
            Console.print("\nSkill updates available:")
            for name, (old_v, new_v) in sorted(updates.items()):
                Console.print(f"  {name}: {old_v} \u2192 {new_v}")

        if new_skills:
            Console.print("\nNew skills available:")
            for name in sorted(new_skills.keys()):
                info = new_skills[name]
                desc = info.get("description", "")
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                Console.print(f"  {name} ({info.get('version', '?')}) \u2014 {desc}")

        Console.print()
        try:
            response = input("Install updates and new skills? [a]ll, [s]elect, [S]kip: ").strip().lower()
        except EOFError:
            response = "s"

        if response == "a" or response == "all":
            if updates:
                update_skills(
                    names=list(updates.keys()),
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
            if new_skills:
                install_skills(
                    names=list(new_skills.keys()),
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
        elif response == "s" or response == "select":
            # Show numbered list of changes
            items = []
            for name, (old_v, new_v) in sorted(updates.items()):
                items.append((name, f"update {old_v} \u2192 {new_v}"))
            for name in sorted(new_skills.keys()):
                items.append((name, f"new ({new_skills[name].get('version', '?')})"))

            for i, (name, label) in enumerate(items, 1):
                Console.print(f"  {i:>3}. {name} \u2014 {label}")

            try:
                sel = input("Enter numbers (e.g. 1,3,5-8): ").strip()
            except EOFError:
                sel = ""

            selected = _parse_selection(sel, len(items))
            selected_names = [items[i - 1][0] for i in sorted(selected)]

            update_names = [n for n in selected_names if n in updates]
            new_names = [n for n in selected_names if n in new_skills]

            if update_names:
                update_skills(
                    names=update_names,
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
            if new_names:
                install_skills(
                    names=new_names,
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
        else:
            Console.info("Skipped skills step")


# Typer command decorators
if HAS_TYPER:

    @app.command("list")
    def list_cmd():
        """List all available and installed skills."""
        list_skills()

    @app.command("install")
    def install_cmd(
        names: List[str] = typer.Argument(..., help="Skill name(s) to install"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
    ):
        """Install one or more skills."""
        install_skills(names=names, yes=yes)

    @app.command("uninstall")
    def uninstall_cmd(
        names: List[str] = typer.Argument(..., help="Skill name(s) to uninstall"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
    ):
        """Uninstall one or more skills."""
        uninstall_skills(names=names, yes=yes)

    @app.command("update")
    def update_cmd(
        names: Optional[List[str]] = typer.Argument(None, help="Skill name(s) to update (all if omitted)"),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts"),
    ):
        """Update installed skills to latest versions."""
        update_skills(names=names, yes=yes)
