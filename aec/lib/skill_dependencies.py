"""Pure dependency resolution for skill installs.

Given a target skill name, the available catalog, and the installed manifest,
resolves what needs to be installed, what is already satisfied, what is missing,
and what has version conflicts.  No side effects — easy to unit-test.
"""

from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from .console import Console
from .skills_manifest import parse_skill_frontmatter, parse_version


class DepToInstall(NamedTuple):
    name: str
    reason: str     # from the declaring skill's SkillDep.reason


class VersionConflict(NamedTuple):
    name: str           # dep skill name
    required_min: str   # min_version declared by the dependant skill
    installed_ver: str  # currently installed version of the dep


class ResolvedGraph(NamedTuple):
    to_install: List[DepToInstall]        # ordered: deps before dependents, excluding already-satisfied
    already_satisfied: List[str]          # dep names already at satisfying version
    missing: List[str]                    # dep names not found in catalog at all
    version_conflicts: List[VersionConflict]  # deps installed but below required min_version
    cycles: List[List[str]]               # non-empty = unresolvable graph


def resolve_install_graph(
    target: str,
    available: dict,
    installed: dict,
    source_dir: Path,
) -> ResolvedGraph:
    """Walk the dependency graph of ``target`` and return what needs to happen.

    Args:
        target: Name of the skill being installed.
        available: Catalog dict — ``{skill_name: {version, description, author, path}}``.
        installed: Installed skills for the target scope —
            ``{skill_name: {version, contentHash, installedAt}}``.
        source_dir: Root of the skills source tree; used to read each SKILL.md.

    Returns:
        A :class:`ResolvedGraph` describing what the installer should do.
    """
    to_install: List[DepToInstall] = []
    already_satisfied: List[str] = []
    missing: List[str] = []
    version_conflicts: List[VersionConflict] = []
    cycles: List[List[str]] = []

    # DFS state
    visited: Dict[str, str] = {}   # name -> "in_progress" | "done"

    def _visit(name: str, path: List[str]) -> None:
        """Depth-first traversal starting from *name*.

        ``path`` tracks the current ancestor chain for cycle detection.
        We do NOT add *name* itself to any output list here — the caller
        (``resolve_install_graph``) is responsible for the target; _visit
        handles *deps* of a skill, not the skill itself.
        """
        if name in visited:
            if visited[name] == "in_progress":
                # Cycle detected — record the cycle path
                cycle_start = path.index(name)
                cycles.append(path[cycle_start:] + [name])
            # Either a cycle or already fully processed — don't re-process.
            return

        if name not in available:
            if name not in missing:
                missing.append(name)
            visited[name] = "done"
            return

        visited[name] = "in_progress"
        path.append(name)

        # Read this skill's own deps
        skill_path = source_dir / available[name]["path"]
        if not skill_path.exists():
            # Warn but don't fail — catalog may lag disk state
            Console.warning(f"  Dependency resolution: {name} not found at {skill_path}, skipping its transitive deps")
            deps = []
        else:
            fm = parse_skill_frontmatter(skill_path)
            deps = fm.get("dependencies", []) if fm else []

        for dep in deps:
            dep_name = dep.name
            dep_min = dep.min_version

            if dep_name in visited and visited[dep_name] != "in_progress":
                # Already fully resolved (possibly already in to_install / already_satisfied)
                continue

            if dep_name not in available:
                if dep_name not in missing:
                    missing.append(dep_name)
                continue

            if dep_name in installed:
                installed_ver = installed[dep_name].get("version", "0.0.0")
                if parse_version(installed_ver) >= parse_version(dep_min):
                    if dep_name not in already_satisfied:
                        already_satisfied.append(dep_name)
                    visited[dep_name] = "done"
                    continue
                else:
                    if not any(vc.name == dep_name for vc in version_conflicts):
                        version_conflicts.append(
                            VersionConflict(
                                name=dep_name,
                                required_min=dep_min,
                                installed_ver=installed_ver,
                            )
                        )
                    visited[dep_name] = "done"
                    continue

            # Recurse into dep's own deps first (topo order: deps before dependents)
            _visit(dep_name, path)

            # After recursion, if not already accounted for, queue for install
            installed_names = [d.name for d in to_install]
            conflict_names = [vc.name for vc in version_conflicts]
            if (
                dep_name not in installed_names
                and dep_name not in already_satisfied
                and dep_name not in conflict_names
                and dep_name not in missing
            ):
                to_install.append(DepToInstall(name=dep_name, reason=dep.reason))
                visited[dep_name] = "done"

        path.pop()
        visited[name] = "done"

    # Resolve target's direct + transitive deps
    _visit(target, [])

    return ResolvedGraph(
        to_install=to_install,
        already_satisfied=already_satisfied,
        missing=missing,
        version_conflicts=version_conflicts,
        cycles=cycles,
    )
