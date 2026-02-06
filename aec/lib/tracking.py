"""Track which repositories have been set up."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, NamedTuple, Optional

from .config import AEC_HOME, AEC_SETUP_LOG, AEC_README, VERSION


class TrackedRepo(NamedTuple):
    """A repository tracked in the setup log."""
    timestamp: str
    version: str
    path: Path
    exists: bool


def init_aec_home() -> None:
    """
    Initialize ~/.agents-environment-config/ directory.

    Creates the directory, README, and setup log file if they don't exist.
    """
    # Create directory
    AEC_HOME.mkdir(parents=True, exist_ok=True)

    # Create README if missing
    if not AEC_README.exists():
        AEC_README.write_text(_get_readme_content())

    # Create log file if missing
    if not AEC_SETUP_LOG.exists():
        AEC_SETUP_LOG.touch()


def log_setup(project_dir: Path) -> None:
    """
    Log a project setup to the tracking file.

    Args:
        project_dir: The project directory that was set up
    """
    init_aec_home()

    # Get absolute path
    abs_path = Path(project_dir).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Read existing entries, filter out this path
    entries = []
    if AEC_SETUP_LOG.exists():
        content = AEC_SETUP_LOG.read_text().strip()
        if content:
            for line in content.split("\n"):
                if line and not line.endswith(f"|{abs_path}"):
                    entries.append(line)

    # Add new entry: timestamp|version|path
    entries.append(f"{timestamp}|{VERSION}|{abs_path}")

    # Write back
    AEC_SETUP_LOG.write_text("\n".join(entries) + "\n")


def is_logged(project_dir: Path) -> bool:
    """
    Check if a project is in the setup log.

    Args:
        project_dir: The project directory to check

    Returns:
        True if the project is tracked
    """
    if not AEC_SETUP_LOG.exists():
        return False

    abs_path = str(Path(project_dir).resolve())
    content = AEC_SETUP_LOG.read_text()
    return f"|{abs_path}" in content


def get_version(project_dir: Path) -> Optional[str]:
    """
    Get the logged version for a project.

    Args:
        project_dir: The project directory to look up

    Returns:
        The version string, or None if not found
    """
    if not AEC_SETUP_LOG.exists():
        return None

    abs_path = str(Path(project_dir).resolve())

    for line in AEC_SETUP_LOG.read_text().strip().split("\n"):
        if line.endswith(f"|{abs_path}"):
            parts = line.split("|")
            if len(parts) >= 2:
                return parts[1]

    return None


def list_repos() -> List[TrackedRepo]:
    """
    List all tracked repositories.

    Returns:
        List of TrackedRepo objects
    """
    if not AEC_SETUP_LOG.exists():
        return []

    repos = []
    content = AEC_SETUP_LOG.read_text().strip()

    if not content:
        return []

    for line in content.split("\n"):
        if not line:
            continue

        parts = line.split("|")
        if len(parts) >= 3:
            path = Path(parts[2])
            repos.append(TrackedRepo(
                timestamp=parts[0],
                version=parts[1],
                path=path,
                exists=path.exists(),
            ))

    return repos


def _get_readme_content() -> str:
    """Return the README content for ~/.agents-environment-config/"""
    return '''# Why is this directory here?

This directory (`~/.agents-environment-config/`) was created by the [agents-environment-config](https://github.com/bernierllc/agents-environment-config) repository CLI.

## Purpose

This directory stores local state and configuration for the agents-environment-config tooling:

| File | Purpose |
|------|---------|
| `setup-repo-locations.txt` | Tracks which project directories have been set up with agent files |
| `README.md` | This file - explains the directory's purpose |

## What is agents-environment-config?

It's a repository that provides:
- Shared rules and standards for AI coding agents (Claude, Cursor, Codex, Gemini, Qwen)
- Setup scripts for configuring new projects with agent files
- Migration tools for keeping agent configurations up to date

## Why track setup locations?

When you run `aec repo setup` to configure a project with agent files, the CLI records the project path here. This allows:

1. **Cascading updates** - When agent file formats change, run `aec repo update --all` to update all your projects at once
2. **Re-run detection** - If you run setup on a project that's already configured, the CLI can offer to check for updates instead of re-copying files
3. **Inventory** - Run `aec repo list` to see all projects you've configured

## CLI Commands

```bash
# List all tracked projects
python -m aec repo list

# Update all tracked projects
python -m aec repo update --all

# Update a specific project
python -m aec repo update /path/to/project
```

## Can I delete this directory?

Yes, but:
- You'll lose the list of configured projects
- The directory will be recreated next time you run any aec command
- Your actual projects are not affected

## Questions?

See the [agents-environment-config repository](https://github.com/bernierllc/agents-environment-config) for documentation.
'''
