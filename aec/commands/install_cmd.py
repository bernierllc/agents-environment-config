"""aec install <type> <name> -- install a skill, rule, or agent."""

import shutil
from pathlib import Path

from ..lib import Console
from ..lib.config import get_repo_root
from ..lib.manifest_v2 import load_manifest, save_manifest, record_install
from ..lib.scope import resolve_scope, ScopeError
from ..lib.sources import discover_available, get_source_dirs
from ..lib.skills_manifest import hash_skill_directory

VALID_TYPES = ("skill", "rule", "agent")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def _manifest_path() -> Path:
    """Compute manifest path dynamically so tests can monkeypatch Path.home()."""
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_install(
    item_type: str,
    name: str,
    global_flag: bool = False,
    yes: bool = False,
) -> None:
    """Install a skill, rule, or agent to local or global scope."""
    if item_type not in VALID_TYPES:
        Console.error(f"Unknown type: {item_type}. Must be one of: {', '.join(VALID_TYPES)}")
        raise SystemExit(1)

    plural = TYPE_TO_PLURAL[item_type]

    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        raise SystemExit(1)

    source_dirs = get_source_dirs()
    source_dir = source_dirs.get(plural)
    if not source_dir or not source_dir.exists():
        Console.error(f"No {plural} source found.")
        raise SystemExit(1)

    available = discover_available(source_dir, plural)
    if name not in available:
        Console.error(f"{item_type.title()} not found: {name}")
        if available:
            Console.print(f"Available: {', '.join(sorted(available.keys()))}")
        raise SystemExit(1)

    item_info = available[name]
    src = source_dir / item_info.get("path", name)
    target_dir = getattr(scope, f"{plural}_dir")
    dst = target_dir / name

    scope_label = "globally" if scope.is_global else f"to {scope.repo_path}"
    Console.print(f"Installing {name} v{item_info.get('version', '?')} {scope_label}...")

    if dst.exists() and not yes:
        try:
            resp = input(f"  {name} already exists. Overwrite? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    target_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".*"))
    else:
        shutil.copy2(src, dst)

    content_hash = hash_skill_directory(dst) if dst.is_dir() else ""
    manifest_file = _manifest_path()
    manifest = load_manifest(manifest_file)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())
    record_install(
        manifest, scope_key, plural, name,
        item_info.get("version", "0.0.0"), content_hash,
    )
    save_manifest(manifest, manifest_file)

    Console.success(f"Installed {name} v{item_info.get('version', '0.0.0')}")
