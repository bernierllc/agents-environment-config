"""aec install <type> <name> -- install a skill, rule, or agent."""

import json
import shutil
from pathlib import Path

from ..lib import Console
from ..lib.config import get_repo_root
from ..lib.hooks import get_verification_playwright_hook
from ..lib.manifest_v2 import load_manifest, save_manifest, record_install
from ..lib.scope import resolve_scope, Scope, ScopeError
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

    # Quick-scan notification for global installs
    if global_flag:
        try:
            from ..lib.discovery_hooks import quick_scan_notification
            quick_scan_notification(scope)
        except ImportError:
            pass

    # Skill-specific post-install steps
    if item_type == "skill" and name == "playwright-test-generator":
        _post_install_playwright_pipeline(name, scope, yes=yes)


def _post_install_playwright_pipeline(name: str, scope: Scope, yes: bool = False) -> None:
    """Post-install for playwright-test-generator: copy scripts, write hook, create manifests."""
    if scope.is_global:
        return

    repo_path = scope.repo_path
    if repo_path is None:
        return

    verification_dir = repo_path / "docs" / "verification"
    if not verification_dir.exists():
        Console.info("No docs/verification/ directory found — skipping pipeline setup.")
        return

    if not yes:
        try:
            resp = input(
                "This project has verification docs. "
                "Copy pipeline scripts to scripts/verification-playwright/? [y/N]: "
            ).strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped pipeline scripts.")
            return

    # Copy scripts, excluding dev artifacts
    skill_scripts = scope.skills_dir / name / "scripts"
    skip_names = {"__tests__", "node_modules", "package.json", "package-lock.json", ".gitignore"}

    pipeline_dst = repo_path / "scripts" / "verification-playwright"
    if skill_scripts.is_dir():
        pipeline_dst.mkdir(parents=True, exist_ok=True)
        for item in skill_scripts.iterdir():
            if item.name in skip_names:
                continue
            dst_item = pipeline_dst / item.name
            if item.is_dir():
                if dst_item.exists():
                    shutil.rmtree(dst_item)
                shutil.copytree(item, dst_item, ignore=shutil.ignore_patterns(".*"))
            else:
                shutil.copy2(item, dst_item)
        # Minimal package.json for ES module support
        runtime_pkg = pipeline_dst / "package.json"
        if not runtime_pkg.exists():
            runtime_pkg.write_text('{"type": "module"}\n')
        Console.success(f"Copied pipeline scripts to {pipeline_dst}")
    else:
        Console.warning("Skill has no scripts/ directory to copy.")
        return

    # Create default manifest files
    manifest_dir = repo_path / "tests" / "verification-playwright" / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    config_path = manifest_dir / "config.json"
    if not config_path.exists():
        default_config = {
            "version": "1.0",
            "dry_run": True,
            "tiers": {
                "gate": {
                    "trigger": "pre-commit", "branches": "*",
                    "browsers": ["chromium"], "depths": ["smoke", "standard"],
                    "maxTests": 30, "timeoutMs": 60000,
                },
                "thorough": {
                    "trigger": "pre-push", "branches": ["staging", "develop"],
                    "browsers": ["chromium", "firefox", "webkit"],
                    "depths": ["smoke", "standard", "deep"],
                    "maxTests": 100, "timeoutMs": 300000,
                },
                "full": {
                    "trigger": "pre-push", "branches": ["main", "production"],
                    "browsers": ["chromium", "firefox", "webkit", "Mobile Chrome", "Mobile Safari"],
                    "depths": ["smoke", "standard", "deep"],
                    "maxTests": None, "timeoutMs": None,
                },
            },
            "test_isolation": {
                "strategy": "serial", "cleanup": "after-each",
                "notes": "Default. Configure per project needs.",
            },
        }
        config_path.write_text(json.dumps(default_config, indent=2) + "\n")

    index_path = manifest_dir / "import-index.json"
    if not index_path.exists():
        index_path.write_text(json.dumps({"version": "1.0", "entries": {}}, indent=2) + "\n")

    # Write PostToolUse hook to .claude/settings.json
    settings_path = repo_path / ".claude" / "settings.json"
    hook_config = get_verification_playwright_hook()

    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
    else:
        existing = {}
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    existing_hooks = existing.setdefault("hooks", {})
    existing_post = existing_hooks.setdefault("PostToolUse", [])
    new_hook_entry = hook_config["hooks"]["PostToolUse"][0]

    # Avoid duplicates
    new_cmd = new_hook_entry["hooks"][0]["command"]
    already_present = any(
        h.get("hooks", [{}])[0].get("command") == new_cmd
        for h in existing_post
        if isinstance(h, dict)
    )
    if not already_present:
        existing_post.append(new_hook_entry)

    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    Console.success(f"Wrote PostToolUse hook to {settings_path}")

    # Copy hook templates and wire into git hooks
    skill_templates = scope.skills_dir / name / "templates" / "hooks"
    hooks_dst = pipeline_dst / "hooks"
    if skill_templates.is_dir():
        hooks_dst.mkdir(parents=True, exist_ok=True)
        for hook_file in skill_templates.iterdir():
            dst_hook = hooks_dst / hook_file.name
            shutil.copy2(hook_file, dst_hook)
            dst_hook.chmod(0o755)

        # Wire into project's hook framework
        _wire_git_hooks(repo_path)
        Console.success(f"Installed git hooks (pre-commit, pre-push)")

    Console.print(f"\nPipeline setup summary:")
    Console.print(f"  Scripts: {pipeline_dst}")
    Console.print(f"  Hook:    {settings_path}")
    Console.print(f"  Git:     pre-commit (gate tier), pre-push (thorough/full tiers)")
    Console.print(f"  Trigger: edits to docs/verification/ will auto-sync Playwright tests")


_HOOK_SOURCE_LINE = "source scripts/verification-playwright/hooks/{hook}.sh 2>/dev/null || true"
_HOOK_BEGIN = "# BEGIN verification-playwright"
_HOOK_END = "# END verification-playwright"


def _wire_git_hooks(repo_path: Path) -> None:
    """Wire verification-playwright into the project's git hook framework."""
    for hook_name in ("pre-commit", "pre-push"):
        source_line = _HOOK_SOURCE_LINE.format(hook=hook_name)
        block = f"{_HOOK_BEGIN}\n{source_line}\n{_HOOK_END}\n"

        # Husky
        husky_hook = repo_path / ".husky" / hook_name
        if husky_hook.exists():
            content = husky_hook.read_text()
            if _HOOK_BEGIN not in content:
                husky_hook.write_text(content.rstrip() + "\n\n" + block)
            continue

        # Lefthook
        for lefthook_file in (".lefthookrc.yml", ".lefthookrc.yaml", "lefthook.yml"):
            lefthook_path = repo_path / lefthook_file
            if lefthook_path.exists():
                # Don't auto-edit YAML — just inform
                Console.info(f"  Add verification-playwright to {lefthook_file} manually")
                break
        else:
            # Raw .git/hooks
            git_hook = repo_path / ".git" / "hooks" / hook_name
            if git_hook.exists():
                content = git_hook.read_text()
                if _HOOK_BEGIN not in content:
                    git_hook.write_text(content.rstrip() + "\n\n" + block)
            else:
                git_hook.parent.mkdir(parents=True, exist_ok=True)
                git_hook.write_text(f"#!/usr/bin/env bash\n\n{block}")
                git_hook.chmod(0o755)
