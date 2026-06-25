"""Portable, machine-independent manifest for ``aec export`` / ``aec apply``.

This is the user-facing, hand-editable description of a desired AEC setup —
distinct from the internal install-state lockfile in ``manifest_v2.py``. It is
deliberately stripped of machine-specific data (absolute paths, content hashes,
timestamps) so the same file reproduces a setup on any machine.
"""

import json
from pathlib import Path
from typing import Optional

from .config import VERSION, get_projects_dir

PORTABLE_SCHEMA_VERSION = 1
ITEM_TYPES = ("skills", "rules", "agents", "mcps", "plugins")
PROJECTS_TOKEN = "${PROJECTS}"


class PortableManifestError(Exception):
    """Raised when a portable manifest is malformed or unsupported."""


def relativize_repo_scope(abs_path: str, projects_dir: Optional[Path] = None) -> str:
    """Turn an absolute repo scope key into a portable, machine-independent token.

    Paths under the projects directory become ``${PROJECTS}/<rel>``; anything
    else falls back to the bare basename. An absolute path is never emitted.
    """
    if projects_dir is None:
        projects_dir = get_projects_dir()
    path = Path(abs_path)
    try:
        rel = path.resolve().relative_to(Path(projects_dir).resolve())
        return f"{PROJECTS_TOKEN}/{rel.as_posix()}"
    except ValueError:
        return path.name


def resolve_repo_token(
    token: str,
    *,
    projects_dir: Optional[Path] = None,
    tracked_repos: Optional[list] = None,
) -> Optional[Path]:
    """Resolve a portable repo token back to an absolute path on this machine.

    ``${PROJECTS}/x`` resolves against the local projects directory; a bare
    basename is matched against the tracked repos. Returns ``None`` when a bare
    token cannot be matched.
    """
    if projects_dir is None:
        projects_dir = get_projects_dir()
    if token.startswith(PROJECTS_TOKEN):
        rel = token[len(PROJECTS_TOKEN):].lstrip("/")
        return (Path(projects_dir) / rel).resolve()
    for repo in tracked_repos or []:
        if Path(repo).name == token:
            return Path(repo).resolve()
    return None


def _items_for_scope(scope_dict: dict, latest: bool) -> dict:
    """Render one scope's installed items as portable, sorted lists."""
    out: dict = {}
    for plural in ITEM_TYPES:
        entries = []
        for name, rec in sorted(scope_dict.get(plural, {}).items()):
            version = rec.get("version", "0.0.0") if isinstance(rec, dict) else "0.0.0"
            entry = {"name": name, "version": "latest" if latest else version}
            if plural == "mcps" and isinstance(rec, dict) and rec.get("package"):
                entry["package"] = rec["package"]
            entries.append(entry)
        if entries:
            out[plural] = entries
    return out


def build_portable_manifest(
    manifest: dict,
    *,
    latest: bool = False,
    include_repos: bool = True,
    projects_dir: Optional[Path] = None,
) -> dict:
    """Build a portable manifest dict from an internal v2 install-state manifest."""
    portable: dict = {
        "schemaVersion": PORTABLE_SCHEMA_VERSION,
        "generatedBy": f"aec {VERSION}",
        "global": _items_for_scope(manifest.get("global", {}), latest),
    }
    if include_repos:
        repos = []
        for abs_path, scope_dict in sorted(manifest.get("repos", {}).items()):
            scope_items = _items_for_scope(scope_dict, latest)
            if not scope_items:
                continue
            entry = {"path": relativize_repo_scope(abs_path, projects_dir)}
            entry.update(scope_items)
            repos.append(entry)
        if repos:
            portable["repos"] = repos
    return portable


def dump_manifest(portable: dict) -> str:
    """Serialize a portable manifest to text (JSON: stdlib, diffable, editable)."""
    return json.dumps(portable, indent=2) + "\n"


def load_portable_manifest(text: str) -> dict:
    """Parse and validate a portable manifest from text."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PortableManifestError(f"Manifest is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PortableManifestError("Manifest must be a JSON object.")
    version = data.get("schemaVersion")
    if version != PORTABLE_SCHEMA_VERSION:
        raise PortableManifestError(
            f"Unsupported schemaVersion: {version!r} (expected {PORTABLE_SCHEMA_VERSION})."
        )
    return data
