"""Git operations for aec CLI."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple


def is_git_repo(path: Path) -> bool:
    """
    Check if a directory is a git repository.

    Args:
        path: Directory to check

    Returns:
        True if it's a git repository
    """
    git_dir = path / ".git"
    return git_dir.exists() or git_dir.is_file()  # .git can be a file for submodules


def clone_repo(
    org: str,
    repo_name: str,
    target_dir: Path,
) -> Tuple[bool, str]:
    """
    Clone a repository from GitHub.

    Args:
        org: GitHub organization/user
        repo_name: Repository name
        target_dir: Where to clone to

    Returns:
        Tuple of (success, message)
    """
    url = f"git@github.com:{org}/{repo_name}.git"

    try:
        result = subprocess.run(
            ["git", "clone", url, str(target_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return True, f"Cloned from {org}/{repo_name}"
        else:
            return False, result.stderr.strip()

    except FileNotFoundError:
        return False, "git command not found"
    except Exception as e:
        return False, str(e)


def init_submodules(repo_dir: Path) -> Tuple[bool, str]:
    """
    Initialize git submodules.

    Args:
        repo_dir: Repository root directory

    Returns:
        Tuple of (success, message)
    """
    try:
        result = subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return True, "Submodules initialized"
        else:
            return False, result.stderr.strip()

    except Exception as e:
        return False, str(e)


def update_submodule(repo_dir: Path, submodule_path: str) -> Tuple[bool, Optional[str]]:
    """
    Update a specific submodule to latest from remote.

    Args:
        repo_dir: Repository root directory
        submodule_path: Relative path to submodule

    Returns:
        Tuple of (success, new_commit_hash or error message)
    """
    submodule_dir = repo_dir / submodule_path

    if not submodule_dir.exists():
        return False, "Submodule directory not found"

    try:
        # Fetch and checkout latest
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False, result.stderr.strip()

        # Get default branch
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            default_branch = result.stdout.strip().split("/")[-1]
        else:
            default_branch = "main"

        # Checkout latest
        result = subprocess.run(
            ["git", "checkout", f"origin/{default_branch}"],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False, result.stderr.strip()

        # Get current commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
        )

        commit_hash = result.stdout.strip() if result.returncode == 0 else "unknown"
        return True, commit_hash

    except Exception as e:
        return False, str(e)


def has_gitmodules(repo_dir: Path) -> bool:
    """Check if repository has .gitmodules file."""
    return (repo_dir / ".gitmodules").exists()
