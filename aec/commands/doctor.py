"""Doctor command: aec doctor - Check installation health."""

from pathlib import Path
from typing import List, Tuple

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import (
    Console,
    get_repo_root,
    VERSION,
    IS_WINDOWS,
    IS_MACOS,
    IS_LINUX,
    AEC_HOME,
    AEC_SETUP_LOG,
    AGENT_TOOLS_DIR,
    CLAUDE_DIR,
    CURSOR_DIR,
    is_symlink,
    get_symlink_target,
    list_repos,
)


def _check(name: str, condition: bool, success_msg: str, failure_msg: str) -> bool:
    """Run a check and print result."""
    if condition:
        Console.success(f"{name}: {success_msg}")
        return True
    else:
        Console.error(f"{name}: {failure_msg}")
        return False


def _check_org_configurations() -> None:
    """Render the 'Org configurations' section.

    Doctor reports, it does not gate: errors discovering enrolled orgs
    surface as a red line but do not flip the overall pass/fail state.
    The section is omitted entirely when no orgs are enrolled, to avoid
    padding output with empty noise.
    """
    try:
        from ..lib.org_config import (
            OrgConfigError,
            OrgPaths,
            discover_enrolled_orgs,
        )
        from ..lib.org_config.rotation import rotation_status
        from ..lib.org_config.state import read_state
    except ImportError:
        # PyYAML extra not installed — silently skip.
        return

    paths = OrgPaths.default()
    try:
        orgs = discover_enrolled_orgs(paths)
    except OrgConfigError as exc:
        Console.header("Org configurations")
        Console.error(f"Failed to load enrolled org: {exc}")
        return

    if not orgs:
        return

    Console.header("Org configurations")
    for enrolled in orgs:
        cfg = enrolled.config
        Console.print(f"  org_id: {cfg.org_id}")
        Console.print(f"  config_version: {cfg.config_version}")
        if cfg.trust_mode == "unsigned":
            Console.warning(f"  trust_mode: {cfg.trust_mode} (no cryptographic verification)")
        else:
            Console.print(f"  trust_mode: {cfg.trust_mode}")
        state = read_state(paths, cfg.org_id)
        if state is not None:
            Console.print(f"  last_verified_at: {state.last_verified_at}")
            Console.print(f"  last_applied_at: {state.last_applied_at}")
            if state.pubkey_fingerprint:
                Console.print(f"  pubkey_fingerprint: {state.pubkey_fingerprint}")
            from datetime import datetime, timezone

            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            rs = rotation_status(
                pending=state.key_rotation_pending, now=now_iso, org_id=cfg.org_id
            )
            if rs.state == "warn":
                Console.warning(
                    f"  key rotation pending — {rs.days_remaining} days remaining "
                    f"(run: aec org trust-rotate {cfg.org_id})"
                )
            elif rs.state == "locked":
                Console.error(
                    f"  key rotation LOCKED (run: aec org trust-rotate {cfg.org_id})"
                )

    if len(orgs) > 1:
        from ..lib.org_config.reconcile import open_conflicts

        opens = open_conflicts(paths, prune=False)
        if opens:
            Console.subheader("Org conflicts")
            for oc in opens:
                c = oc.conflict
                participants = ", ".join(f"{p.org_id}={p.value}" for p in c.participants)
                Console.error(f"  {c.kind} on {c.subject}: {participants}")
            Console.print("  Run `aec org resolve` to decide.")


def _check_agent_blurb_drift(repo_root) -> None:
    """Report agent-blurb drift in the current project, if configured.

    Informational only — never flips the overall pass/fail state. Section is
    omitted entirely when the blurb feature is not configured for the project.
    """
    if repo_root is None:
        return
    try:
        from ..lib.agent_blurb.config import load_config
        from ..lib.agent_blurb.drift import compute_drift, DriftState
        from ..lib.agent_blurb.render import shipped_template_hash
    except ImportError:
        return

    cfg = load_config(scope="project", root=repo_root)
    if cfg is None:
        return

    Console.subheader("Agent Blurb")
    shipped = shipped_template_hash()
    any_drift = False
    for t in cfg.get("targets", []):
        target_path = repo_root / t["path"]
        if not target_path.exists():
            Console.warning(f"Target missing: {target_path}")
            any_drift = True
            continue
        state = compute_drift(
            on_disk_content=target_path.read_text(encoding="utf-8"),
            stored_template_hash=t["template_hash"],
            stored_content_hash=t["content_hash"],
            shipped_template_hash=shipped,
        )
        if state == DriftState.CLEAN:
            Console.success(f"{target_path}: clean")
        elif state == DriftState.UPSTREAM_UPDATE:
            Console.info(
                f"{target_path}: newer template available "
                f"(run: aec configure-agent --refresh)"
            )
            any_drift = True
        elif state == DriftState.MANUAL_EDIT:
            Console.warning(f"{target_path}: hand-edited")
            any_drift = True
        elif state == DriftState.CONFLICT:
            Console.warning(f"{target_path}: conflict (upstream + local edits)")
            any_drift = True
        else:  # NOT_INSTALLED
            Console.info(f"{target_path}: not installed")
    if not any_drift:
        Console.info("All blurbs up to date")


def run_doctor() -> Tuple[bool, List[str]]:
    """
    Check installation health.

    Returns:
        Tuple of (all_passed, list of issues)
    """
    Console.header("AEC Health Check")

    issues: List[str] = []
    checks_passed = 0
    checks_total = 0

    # Platform info
    Console.print(f"Platform: ", end="")
    if IS_MACOS:
        Console.print("macOS")
    elif IS_WINDOWS:
        Console.print("Windows")
    elif IS_LINUX:
        Console.print("Linux")
    else:
        Console.print("Unknown")
    Console.print(f"Version: {VERSION}")
    Console.print()

    # Check 1: Repository found
    Console.subheader("Repository")
    checks_total += 1
    repo_root = get_repo_root()
    if repo_root:
        Console.success(f"Repository found: {repo_root}")
        checks_passed += 1
    else:
        Console.error("Repository not found")
        issues.append("agents-environment-config repository not found")

    # Check 2: AEC Home directory
    Console.subheader("Configuration Directory")
    checks_total += 1
    if AEC_HOME.exists():
        Console.success(f"~/.agents-environment-config/ exists")
        checks_passed += 1

        # Check setup log
        checks_total += 1
        if AEC_SETUP_LOG.exists():
            repos = list_repos()
            Console.success(f"Setup log exists ({len(repos)} tracked repos)")
            checks_passed += 1
        else:
            Console.warning("Setup log not found (will be created on first repo setup)")
            checks_passed += 1  # This is OK
    else:
        Console.warning("~/.agents-environment-config/ not found (will be created on first use)")
        checks_passed += 1  # This is OK for first run

    # Check 3: Agent Tools directory
    Console.subheader("Agent Tools Directory")
    checks_total += 1
    if AGENT_TOOLS_DIR.exists():
        Console.success("~/.agent-tools/ exists")
        checks_passed += 1

        # Check marker
        marker = AGENT_TOOLS_DIR / ".aec-managed"
        checks_total += 1
        if marker.exists():
            Console.success(".aec-managed marker present")
            checks_passed += 1
        else:
            Console.warning(".aec-managed marker not found")
            issues.append("~/.agent-tools/ exists but isn't marked as AEC-managed")

        # Check subdirectories
        for subdir in ["rules", "agents", "skills", "commands"]:
            subdir_path = AGENT_TOOLS_DIR / subdir
            checks_total += 1
            if subdir_path.exists():
                Console.success(f"~/.agent-tools/{subdir}/ exists")
                checks_passed += 1

                # Check for our symlink
                our_link = subdir_path / "agents-environment-config"
                if is_symlink(our_link):
                    target = get_symlink_target(our_link)
                    Console.success(f"  └─ agents-environment-config -> {target}")
                else:
                    Console.info(f"  └─ agents-environment-config not linked")
            else:
                Console.warning(f"~/.agent-tools/{subdir}/ not found")
                issues.append(f"~/.agent-tools/{subdir}/ directory missing")
    else:
        Console.warning("~/.agent-tools/ not found")
        Console.info(f"  Run: {Console.cmd('aec agent-tools setup')}")
        issues.append("~/.agent-tools/ directory not set up")

    # Check 4: Agent-specific directories
    Console.subheader("Agent Directories")

    # Claude
    checks_total += 1
    if CLAUDE_DIR.exists():
        Console.success("~/.claude/ exists")
        checks_passed += 1

        # Check agents symlink (still symlink-based)
        agents_link = CLAUDE_DIR / "agents" / "agents-environment-config"
        if is_symlink(agents_link):
            target = get_symlink_target(agents_link)
            Console.success(f"  └─ agents/agents-environment-config -> {target}")
        else:
            Console.info(f"  └─ agents/agents-environment-config not linked")

        # Check for extensionless agent files (Claude Code ignores them)
        agents_dir = CLAUDE_DIR / "agents"
        if agents_dir.exists():
            bare_agents = [
                f.name
                for f in agents_dir.iterdir()
                if f.is_file() and f.suffix != ".md"
            ]
            if bare_agents:
                Console.error(
                    f"  └─ {len(bare_agents)} agent file(s) missing .md extension "
                    f"(Claude Code will not load them)"
                )
                for ba in bare_agents:
                    Console.info(f"       {ba}")
                Console.info(f"       Fix with: aec upgrade")
                issues.append(
                    f"{len(bare_agents)} agent file(s) in ~/.claude/agents/ lack .md extension "
                    f"(run: aec upgrade)"
                )

        # Check skills (now managed by aec skills, not symlinks)
        skills_link = CLAUDE_DIR / "skills" / "agents-environment-config"
        if skills_link.is_symlink():
            Console.warning(f"  └─ skills/agents-environment-config (legacy symlink, run: aec install)")
        else:
            Console.success(f"  └─ skills/ (managed by: aec skills)")
    else:
        Console.info("~/.claude/ not found (Claude Code may not be installed)")
        checks_passed += 1  # OK if not installed

    # Cursor
    checks_total += 1
    if CURSOR_DIR.exists():
        Console.success("~/.cursor/ exists")
        checks_passed += 1

        # Only check rules - global commands are broken in Cursor
        # See: https://forum.cursor.com/t/commands-are-not-detected-in-the-global-cursor-directory/150967
        link_path = CURSOR_DIR / "rules" / "agents-environment-config"
        if is_symlink(link_path):
            target = get_symlink_target(link_path)
            Console.success(f"  └─ rules/agents-environment-config -> {target}")
        else:
            Console.info(f"  └─ rules/agents-environment-config not linked")
    else:
        Console.info("~/.cursor/ not found (Cursor may not be installed)")
        checks_passed += 1  # OK if not installed

    # Check: Skills installation
    Console.subheader("Skills")

    from ..lib.manifest_v2 import load_manifest
    from ..lib.config import INSTALLED_MANIFEST_V2

    checks_total += 1
    if INSTALLED_MANIFEST_V2.exists():
        try:
            manifest = load_manifest(INSTALLED_MANIFEST_V2)
            global_skills = manifest["global"]["skills"]
            skill_count = len(global_skills)
            Console.success(f"installed-manifest.json valid ({skill_count} skills tracked)")
            checks_passed += 1

            # Verify each tracked skill exists on disk
            for name, info in global_skills.items():
                skill_dir = CLAUDE_DIR / "skills" / name
                checks_total += 1
                if skill_dir.exists():
                    Console.success(f"  {name} ({info.get('version', '?')})")
                    checks_passed += 1
                else:
                    Console.error(f"  {name} tracked but directory missing")
                    issues.append(f"Skill '{name}' in manifest but missing from ~/.claude/skills/")
        except Exception as e:
            Console.error(f"installed-manifest.json: {e}")
            issues.append("installed-manifest.json is corrupt")
    else:
        Console.info("installed-manifest.json not found (run: aec install)")
        checks_passed += 1  # OK on first run

    # Check for stale AEC symlinks
    checks_total += 1
    stale_link = CLAUDE_DIR / "skills" / "agents-environment-config"
    if stale_link.is_symlink():
        Console.error("Legacy symlink found: ~/.claude/skills/agents-environment-config")
        issues.append("Legacy skills symlink still exists (fix with: aec install)")
    else:
        Console.success("No legacy skills symlinks")
        checks_passed += 1

    # Check 5: Hook key casing in tracked repos
    Console.subheader("Hook Configuration")
    repos_with_bad_hooks = []
    tracked = list_repos()
    if tracked:
        from ..lib.hooks import repair_hook_keys, HOOK_KEY_FIXES
        import json
        from ..lib.hooks import AGENT_HOOK_CONFIGS

        for repo in tracked:
            if not repo.exists:
                continue
            for agent_key, fixes in HOOK_KEY_FIXES.items():
                if agent_key not in AGENT_HOOK_CONFIGS:
                    continue
                config_path = repo.path / AGENT_HOOK_CONFIGS[agent_key]["config_path"]
                if not config_path.exists():
                    continue
                try:
                    data = json.loads(config_path.read_text())
                    hooks = data.get("hooks", {})
                    if isinstance(hooks, dict):
                        bad_keys = [k for k in fixes if k in hooks]
                        if bad_keys:
                            repos_with_bad_hooks.append((repo.path, agent_key, bad_keys))
                except (json.JSONDecodeError, OSError):
                    pass

        checks_total += 1
        if repos_with_bad_hooks:
            for path, agent, keys in repos_with_bad_hooks:
                Console.error(f"Bad hook keys in {path}: {', '.join(keys)}")
            issues.append(
                f"{len(repos_with_bad_hooks)} repo(s) have camelCase hook keys "
                f"(fix with: aec repo update --all)"
            )
        else:
            Console.success("All hook configs use correct PascalCase keys")
            checks_passed += 1

        # Check 5b: malformed hook entry structure (flat shape)
        from ..lib.hooks import detect_hook_structure_issues

        repos_with_bad_structure: list = []
        for repo in tracked:
            if not repo.exists:
                continue
            structure_issues = detect_hook_structure_issues(repo.path)
            for agent_key, problems in structure_issues.items():
                repos_with_bad_structure.append((repo.path, agent_key, problems))

        checks_total += 1
        if repos_with_bad_structure:
            for path, agent, problems in repos_with_bad_structure:
                for problem in problems:
                    Console.error(f"Malformed hook in {path} ({agent}): {problem}")
            issues.append(
                f"{len(repos_with_bad_structure)} repo(s) have malformed hook "
                f"entry shapes (fix with: aec repo update --all)"
            )
        else:
            Console.success("All hook entries use correct nested structure")
            checks_passed += 1

        # Check 5c: agent config path occupied by a file (blocks hook install)
        from ..lib.hooks.installer import config_dir_blocked, _AGENT_CONFIG_DIR

        blocked_dirs: list = []
        for repo in tracked:
            if not repo.exists:
                continue
            for agent_key in _AGENT_CONFIG_DIR:
                conflict = config_dir_blocked(repo.path, agent_key)
                if conflict is not None:
                    blocked_dirs.append((conflict, agent_key))

        checks_total += 1
        if blocked_dirs:
            for path, agent in blocked_dirs:
                Console.error(
                    f"{path} is a file, not the {agent} config directory "
                    f"(blocks {agent} hooks; move it aside, e.g. mv {path} {path}.bak)"
                )
            issues.append(
                f"{len(blocked_dirs)} agent config path(s) are files, not "
                f"directories (hooks for those agents are skipped)"
            )
        else:
            Console.success("All agent config paths are directories")
            checks_passed += 1
    else:
        Console.info("No tracked repos to check")

    # Check 6: .agent-rules/ directory (if in repo)
    if repo_root:
        Console.subheader("Rule Files")
        agent_rules_dir = repo_root / ".agent-rules"
        cursor_rules_dir = repo_root / ".cursor" / "rules"

        checks_total += 1
        if agent_rules_dir.exists():
            md_files = list(agent_rules_dir.rglob("*.md"))
            Console.success(f".agent-rules/ exists ({len(md_files)} rule files)")
            checks_passed += 1

            # Check parity
            if cursor_rules_dir.exists():
                mdc_files = [f for f in cursor_rules_dir.rglob("*.mdc") if f.name != "README.mdc"]
                if len(md_files) == len(mdc_files):
                    Console.success(f"Rule count matches .cursor/rules/ ({len(mdc_files)} files)")
                else:
                    Console.warning(f"Rule count mismatch: {len(md_files)} vs {len(mdc_files)}")
                    Console.info(f"  Run: {Console.cmd('aec rules generate')}")
        else:
            Console.warning(".agent-rules/ not found")
            Console.info(f"  Run: {Console.cmd('aec rules generate')}")
            issues.append(".agent-rules/ directory not generated")

    # Check 7: Version check status
    Console.subheader("Update Check")
    from ..lib.preferences import get_preference
    update_pref = get_preference("update_check")
    if update_pref is False:
        Console.info("Automatic update checking is disabled")
        Console.print(f"    Enable with: {Console.cmd('aec preferences set update_check on')}")
    else:
        Console.success("Automatic update checking is enabled")
        from ..lib.version_check import VERSION_CACHE_FILE
        if VERSION_CACHE_FILE.exists():
            try:
                import json as _json
                cache_data = _json.loads(VERSION_CACHE_FILE.read_text())
                Console.info(f"Last checked: {cache_data.get('last_check', 'unknown')}")
                Console.info(f"Latest known: v{cache_data.get('latest_version', 'unknown')}")
            except Exception:
                pass

    # Org configurations (Phase 1: 0 or 1 enrolled org)
    _check_org_configurations()

    # Agent blurb drift (informational; never gates pass/fail)
    _check_agent_blurb_drift(repo_root)

    # Summary
    Console.header("Summary")
    all_passed = len(issues) == 0

    if all_passed:
        Console.success(f"All checks passed! ({checks_passed}/{checks_total})")
    else:
        Console.warning(f"{checks_passed}/{checks_total} checks passed")
        Console.print()
        Console.print("Issues found:")
        for issue in issues:
            Console.print(f"  - {issue}")
        Console.print()
        Console.print(f"To fix most issues, run: {Console.cmd('aec install')}")

    return all_passed, issues
