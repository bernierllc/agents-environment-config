"""Source management: discover items, check staleness, fetch updates."""

import json
import subprocess
from pathlib import Path
from typing import Optional

from .config import get_repo_root
from .manifest_v2 import is_stale
from .skills_manifest import discover_available_skills, parse_yaml_frontmatter


def discover_available(source_dir: Path, item_type: str) -> dict:
    """Discover available items of a given type from the source directory.

    Args:
        source_dir: Root of the source (e.g., repo/.claude/skills/)
        item_type: One of 'skills', 'rules', 'agents', 'mcps'

    Returns:
        Dict of name -> {version, description, path, ...}
    """
    if not source_dir.exists():
        return {}
    if item_type == "skills":
        return discover_available_skills(source_dir)
    elif item_type == "rules":
        return _discover_available_rules(source_dir)
    elif item_type == "agents":
        return _discover_available_agents(source_dir)
    elif item_type == "mcps":
        return _discover_available_mcps(source_dir)
    elif item_type == "plugins":
        return _discover_available_plugins(source_dir)
    return {}


def _discover_available_rules(source_dir: Path) -> dict:
    """Discover available rules from the agent-rules source.

    Only includes files with valid frontmatter containing name and version.
    """
    rules = {}
    if not source_dir.exists():
        return rules
    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        text = md_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text)
        if not fm or "name" not in fm or "version" not in fm:
            continue
        rel = md_file.relative_to(source_dir)
        name = fm["name"]
        rules[name] = {
            "version": fm["version"],
            "description": fm.get("description", ""),
            "path": str(rel),
        }
    return rules


def _discover_available_agents(source_dir: Path) -> dict:
    """Discover available agents from the agents source.

    Only includes files with valid frontmatter containing name and version.
    Files without proper frontmatter (README, CONTRIBUTING, etc.) are skipped.
    """
    agents = {}
    if not source_dir.exists():
        return agents
    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        text = md_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text)
        if not fm or "name" not in fm or "version" not in fm:
            continue
        name = md_file.stem
        rel = md_file.relative_to(source_dir)
        agents[name] = {
            "version": fm["version"],
            "description": fm.get("description", ""),
            "author": fm.get("author", ""),
            "division": fm.get("division", ""),
            "path": str(rel),
        }
    return agents


def _discover_available_mcps(source_dir: Path) -> dict:
    """Discover available MCP servers from the mcp-servers source directory.

    Each MCP server is a subdirectory containing an mcp.json file with at
    minimum 'name' and 'version' fields.
    """
    mcps = {}
    if not source_dir.exists():
        return mcps
    for mcp_dir in sorted(source_dir.iterdir()):
        if not mcp_dir.is_dir() or mcp_dir.name.startswith("."):
            continue
        mcp_file = mcp_dir / "mcp.json"
        if not mcp_file.exists():
            continue
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "name" not in data or "version" not in data:
            continue
        name = data["name"]
        mcps[name] = {
            "version": data["version"],
            "description": data.get("description", ""),
            "path": mcp_dir.name,
        }
    return mcps


def _discover_available_plugins(source_dir: Path) -> dict:
    """Discover available plugins from the vendored plugin registry.

    Each plugin is a subdirectory containing a loadout manifest. A malformed
    manifest is skipped (mirrors ``_discover_available_mcps``, which catches the
    parse error and continues rather than aborting the whole scan).
    """
    from .loadout import LoadoutError, find_loadout_file, load_loadout

    plugins = {}
    if not source_dir.exists():
        return plugins
    for plugin_dir in sorted(source_dir.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        if find_loadout_file(plugin_dir) is None:
            continue
        try:
            data = load_loadout(plugin_dir)
        except LoadoutError:
            continue
        plugins[data["name"]] = {
            "version": data["version"],
            "description": data.get("description", ""),
            "path": plugin_dir.name,
            "install_type": data.get("install_type", ""),
        }
    return plugins


def get_source_dirs(root: Optional[Path] = None) -> dict:
    """Get source directories for each item type from the AEC repo.

    These are the AEC repo's source directories (where available items
    are defined), NOT the user's install targets. `root` picks a checkout of
    the aec repo other than the installed one (a worktree of it, say).

    Returns dict of item_type -> Path.
    """
    repo = root or get_repo_root()
    if repo is None:
        return {}
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
        "mcps": repo / "mcp-servers",
        "plugins": repo / "plugins",
    }


def check_staleness(manifest: dict, max_age_hours: int = 24) -> bool:
    """Check if sources are stale."""
    return is_stale(manifest, max_age_hours)


def fetch_latest(repo_path: Optional[Path] = None) -> None:
    """Pull latest AEC repo and update submodules to remote branch tips.

    Uses ``git submodule update --remote`` so skills/agents track the latest
    commits on their default branches (same as the post-merge hook), not only
    the superproject's recorded gitlinks.

    Raises ``RepoSyncError`` naming the cause and the fix when git fails.
    """
    from .errors import RepoSyncError

    if repo_path is None:
        repo_path = get_repo_root()
    if repo_path is None:
        raise RepoSyncError(
            "AEC repo not found.", fix=["Run `aec setup` to clone and register it."],
        )
    from . import debug as _debug
    pull = ["git", "pull", "--ff-only"]
    submodules = ["git", "submodule", "update", "--init", "--recursive", "--remote"]
    for cmd in (pull, submodules):
        try:
            subprocess.run(cmd, cwd=repo_path, capture_output=True, check=True, text=True)
        except FileNotFoundError as exc:
            raise RepoSyncError(
                "git is not installed or not on PATH.",
                fix=["Install git (https://git-scm.com/downloads), then run `aec update` again."],
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            _debug.log_subprocess_failure(
                cmd=cmd, returncode=exc.returncode,
                stdout=exc.stdout if isinstance(exc.stdout, str) else None,
                stderr=stderr or None, note=f"fetch_latest in {repo_path}",
            )
            raise _diagnose_sync_failure(repo_path, cmd, stderr) from exc


def _ahead_behind(repo_path: Path) -> Optional[tuple]:
    """Return (local-only commits, upstream-only commits), or None if unknown."""
    done = subprocess.run(
        ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
        cwd=repo_path, capture_output=True, text=True,
    )
    parts = done.stdout.split()
    if done.returncode != 0 or len(parts) != 2:
        return None  # no upstream or detached HEAD: the caller's message covers it
    return int(parts[0]), int(parts[1])


def _diagnose_sync_failure(repo_path: Path, cmd: list, stderr: str):
    """Turn a failed git command into a RepoSyncError with the steps that fix it."""
    from .errors import RepoSyncError

    text = stderr.lower()
    cd = f"cd {repo_path}"
    # git's "hint:" lines restate generic options; our fix steps replace them
    detail = "\n".join(
        line for line in stderr.strip().splitlines() if not line.startswith("hint:")
    ) or None
    rerun = "Run `aec update` again."

    if cmd[1] == "submodule":
        return RepoSyncError(
            "Updating the AEC skill/agent submodules failed.",
            detail=detail,
            fix=[
                cd,
                "git submodule status   # a '+' or 'U' marks the submodule in trouble",
                "Commit or discard local changes inside that submodule directory.",
                rerun,
            ],
        )
    if "not possible to fast-forward" in text or "diverg" in text:
        counts = _ahead_behind(repo_path)
        which = (
            f"{counts[0]} local commit(s) not on the remote, and the remote has {counts[1]} new one(s)"
            if counts else "local commits not on the remote, and the remote has new ones"
        )
        return RepoSyncError(
            f"Your AEC checkout has diverged from the remote: {which}. "
            "`aec update` only fast-forwards, so it will not merge them for you.",
            detail=detail,
            fix=[
                cd,
                "git log --oneline @{u}..HEAD   # see your local-only commits",
                "To keep them on top of the remote: git pull --rebase",
                "To drop them (back them up first): git branch backup/aec-local HEAD && git reset --hard @{u}",
                rerun,
            ],
        )
    if "would be overwritten" in text or "local changes" in text:
        return RepoSyncError(
            "Uncommitted changes in your AEC checkout block the update.",
            detail=detail,
            fix=[
                cd,
                "git status   # see which files changed",
                "Commit them, or set them aside: git stash push -m before-aec-update",
                rerun,
                "If you stashed: git stash pop",
            ],
        )
    if "no tracking information" in text or "not currently on a branch" in text:
        return RepoSyncError(
            "Your AEC checkout is not on a branch that tracks the remote.",
            detail=detail,
            fix=[cd, "git switch main", rerun],
        )
    if any(s in text for s in (
        "could not resolve host", "could not read from remote", "permission denied",
        "authentication failed", "connection timed out", "unable to access",
    )):
        return RepoSyncError(
            "Could not reach the AEC remote (network or git credentials).",
            detail=detail,
            fix=[
                "Check your network connection.",
                f"Test access: git -C {repo_path} fetch",
                "If that asks for or rejects credentials, fix your SSH key or git credential helper.",
                rerun,
            ],
        )
    return RepoSyncError(
        f"`{' '.join(cmd)}` failed in your AEC checkout.",
        detail=detail,
        fix=[cd, f"Run `{' '.join(cmd)}` yourself to see the full error and resolve it.", rerun],
    )
