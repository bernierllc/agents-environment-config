"""Scope-aware global uninstall: find repos that own their own copy of an item.

A repo-scoped install overrides the global one for that repo and is owned
independently, so a global uninstall must never silently reap repo installs.
These helpers surface the affected repos and resolve the non-interactive
`--repos all|none|<paths>` selection.
"""

from pathlib import Path
from typing import Optional


def find_repos_with_install(manifest: dict, plural_type: str, name: str) -> list[str]:
    """Repo paths (sorted) whose scope has a `plural_type` install named `name`."""
    repos = manifest.get("repos", {})
    return sorted(
        repo for repo, scope in repos.items()
        if name in (scope.get(plural_type) or {})
    )


def resolve_repos_flag(value: Optional[str], candidates: list[str]) -> list[str]:
    """Resolve the non-interactive --repos flag to a subset of candidate repos.

    None / "none" -> nothing; "all" -> every candidate; otherwise a comma- or
    space-separated list of paths, kept only where they match a candidate.
    """
    if value is None or value.strip().lower() == "none":
        return []
    if value.strip().lower() == "all":
        return list(candidates)
    cand_set = {str(Path(c)) for c in candidates}
    wanted = [p.strip() for p in value.replace(",", " ").split()]
    return [str(Path(p)) for p in wanted if str(Path(p)) in cand_set]
