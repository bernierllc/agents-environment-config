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
        Console.info(f"  Run: {Console.cmd('python -m aec agent-tools setup')}")
        issues.append("~/.agent-tools/ directory not set up")

    # Check 4: Agent-specific directories
    Console.subheader("Agent Directories")

    # Claude
    checks_total += 1
    if CLAUDE_DIR.exists():
        Console.success("~/.claude/ exists")
        checks_passed += 1

        for subdir in ["agents", "skills"]:
            link_path = CLAUDE_DIR / subdir / "agents-environment-config"
            if is_symlink(link_path):
                target = get_symlink_target(link_path)
                Console.success(f"  └─ {subdir}/agents-environment-config -> {target}")
            else:
                Console.info(f"  └─ {subdir}/agents-environment-config not linked")
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

    # Check 5: .agent-rules/ directory (if in repo)
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
                    Console.info(f"  Run: {Console.cmd('python -m aec rules generate')}")
        else:
            Console.warning(".agent-rules/ not found")
            Console.info(f"  Run: {Console.cmd('python -m aec rules generate')}")
            issues.append(".agent-rules/ directory not generated")

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
        Console.print(f"To fix most issues, run: {Console.cmd('python -m aec install')}")

    return all_passed, issues
