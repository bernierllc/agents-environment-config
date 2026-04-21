"""Scope resolution for AEC commands.

Determines whether a command operates on the local repo or global scope.
Write commands default to local; read commands show all applicable scopes.

IMPORTANT: All paths are computed dynamically via Path.home() at call time,
not from precomputed module-level constants. This ensures monkeypatch in
tests can redirect the home directory.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ScopeError(Exception):
    """Raised when scope cannot be resolved (e.g., not in repo without -g)."""
    pass


@dataclass
class Scope:
    """Resolved scope for a command."""
    is_global: bool
    repo_path: Optional[Path]

    @property
    def is_local(self) -> bool:
        return not self.is_global

    @property
    def skills_dir(self) -> Path:
        if self.is_global:
            return Path.home() / ".claude" / "skills"
        assert self.repo_path is not None
        return self.repo_path / ".claude" / "skills"

    @property
    def agents_dir(self) -> Path:
        if self.is_global:
            return Path.home() / ".claude" / "agents"
        assert self.repo_path is not None
        return self.repo_path / ".claude" / "agents"

    @property
    def rules_dir(self) -> Path:
        if self.is_global:
            return Path.home() / ".agent-tools" / "rules"
        assert self.repo_path is not None
        return self.repo_path / ".agent-rules"


def find_tracked_repo(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from start (default cwd) to find a tracked repo.

    A directory is considered a tracked repo if it appears in the setup log
    AND has a .claude/ or .agent-rules/ directory or .aec.json file.
    """
    if start is None:
        start = Path.cwd()
    tracked = _load_tracked_paths()
    current = start.resolve()
    for _ in range(20):
        if current in tracked:
            if (current / ".claude").is_dir() or (current / ".agent-rules").is_dir() or (current / ".aec.json").is_file():
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def resolve_scope(global_flag: bool) -> Scope:
    """Resolve scope from the -g flag and current working directory.

    - global_flag=True -> global scope (paths under ~/.claude/, ~/.agent-tools/)
    - global_flag=False in tracked repo -> local scope (paths under repo)
    - global_flag=False outside tracked repo -> ScopeError
    """
    if global_flag:
        return Scope(is_global=True, repo_path=None)
    repo = find_tracked_repo()
    if repo is None:
        raise ScopeError(
            "Not in a tracked repo. Use `-g` for global install, "
            "or `cd` into a project first."
        )
    return Scope(is_global=False, repo_path=repo)


def get_all_tracked_repos() -> list[Path]:
    """Return all tracked repo paths that exist on disk."""
    return [p for p in _load_tracked_paths() if p.exists()]


def _setup_log_path() -> Path:
    """Return the path to the setup log, computed dynamically."""
    return Path.home() / ".agents-environment-config" / "setup-repo-locations.txt"


def _load_tracked_paths() -> set[Path]:
    """Load tracked repo paths, preferring JSON store with txt fallback.

    Delegates to tracked_repos.load_tracked_repos() for the JSON path,
    falling back to the legacy txt file if JSON doesn't exist.
    """
    from .tracked_repos import load_tracked_repos, _tracked_repos_path

    json_path = _tracked_repos_path()
    if json_path.exists():
        data = load_tracked_repos()
        return {Path(p).resolve() for p in data["repos"]}
    return _load_tracked_paths_from_txt()


def _load_tracked_paths_from_txt() -> set[Path]:
    """Load tracked paths from legacy setup-repo-locations.txt.

    Each line has format: timestamp|version|absolute_path
    """
    log = _setup_log_path()
    if not log.exists():
        return set()
    paths: set[Path] = set()
    content = log.read_text().strip()
    if not content:
        return paths
    for line in content.split("\n"):
        parts = line.split("|")
        if len(parts) >= 3:
            paths.add(Path(parts[2]).resolve())
    return paths
