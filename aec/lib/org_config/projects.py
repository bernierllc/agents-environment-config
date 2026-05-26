"""Per-project overlay matching (Phase 4a).

An org config may carry ``projects[]`` overlays that scope a policy delta to
specific repositories, matched by git remote or working directory. Matching is
first-overlay-wins; remotes are normalized to a canonical ``host:owner/repo``
form so the scp and https spellings of the same repo compare equal.
"""
from __future__ import annotations

import os
from fnmatch import fnmatch
from typing import Optional

from .schema import ProjectOverlay, ProjectProfile

_SCHEMES = ("https://", "http://", "ssh://", "git://", "git+ssh://")


def normalize_git_remote(remote: str) -> str:
    """Canonicalize a git remote URL to ``host:owner/repo``."""
    s = remote.strip()
    for scheme in _SCHEMES:
        if s.startswith(scheme):
            s = s[len(scheme):]
            break
    if "@" in s:
        s = s.split("@", 1)[1]  # drop user (e.g. git@)
    if s.endswith(".git"):
        s = s[:-4]
    s = s.rstrip("/")
    for i, ch in enumerate(s):
        if ch in ":/":
            return f"{s[:i]}:{s[i + 1:]}"
    return s


def _dir_matches(repo_path: str, pattern: str) -> bool:
    target = os.path.abspath(os.path.expanduser(repo_path))
    return fnmatch(target, os.path.expanduser(pattern))


def match_project(
    overlays: list[ProjectOverlay],
    *,
    repo_path: Optional[str],
    git_remote: Optional[str],
) -> Optional[ProjectProfile]:
    """Return the first overlay's profile that matches, or None.

    git_remote is checked before directory; an overlay declaring both still
    matches via directory when no remote is known.
    """
    norm_remote = normalize_git_remote(git_remote) if git_remote else None
    for overlay in overlays:
        m = overlay.match
        if m.git_remote and norm_remote and fnmatch(norm_remote, normalize_git_remote(m.git_remote)):
            return overlay.profile
        if m.directory and repo_path and _dir_matches(repo_path, m.directory):
            return overlay.profile
    return None
