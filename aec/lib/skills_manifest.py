"""Skills manifest management: read/write installed-skills.json, parse SKILL.md frontmatter."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def parse_yaml_frontmatter(text: str) -> Optional[dict]:
    """Parse YAML frontmatter from a markdown file.

    Simple parser that handles key: value pairs without requiring PyYAML.
    Supports string values only (which is all SKILL.md uses).
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None

    result = {}
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        colon_idx = line.find(":")
        if colon_idx == -1:
            continue
        key = line[:colon_idx].strip()
        value = line[colon_idx + 1:].strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        result[key] = value
    return result


def parse_skill_frontmatter(skill_dir: Path) -> Optional[dict]:
    """Parse SKILL.md frontmatter from a skill directory.

    Returns dict with name, description, version, author, or None if
    SKILL.md is missing or has no valid frontmatter.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    text = skill_md.read_text(encoding="utf-8")
    fm = parse_yaml_frontmatter(text)
    if not fm or "name" not in fm:
        return None

    # Default version to 0.0.0 if missing
    if "version" not in fm:
        fm["version"] = "0.0.0"

    return fm


def parse_version(version_str: str) -> tuple:
    """Parse a semver string into a comparable tuple."""
    return tuple(int(x) for x in version_str.split("."))


def version_is_newer(available: str, installed: str) -> bool:
    """Return True if available version is newer than installed."""
    return parse_version(available) > parse_version(installed)


def hash_skill_directory(path: Path) -> str:
    """Compute SHA-256 hash of all non-hidden files in a skill directory."""
    hasher = hashlib.sha256()
    for filepath in sorted(path.rglob("*")):
        if filepath.is_file() and not any(
            part.startswith(".") for part in filepath.relative_to(path).parts
        ):
            hasher.update(str(filepath.relative_to(path)).encode())
            hasher.update(filepath.read_bytes())
    return f"sha256:{hasher.hexdigest()}"


MANIFEST_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_installed_manifest(path: Path) -> dict:
    """Load installed-skills.json, returning empty manifest if missing/corrupt."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "skills" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "manifestVersion": MANIFEST_VERSION,
        "installedAt": _now_iso(),
        "updatedAt": _now_iso(),
        "skills": {},
    }


def save_installed_manifest(manifest: dict, path: Path) -> None:
    """Write installed-skills.json to disk."""
    manifest["updatedAt"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _scan_skill_paths(source_dir: Path) -> dict:
    """Scan source directory to build a name -> relative path mapping."""
    paths = {}
    for item in sorted(source_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if (item / "SKILL.md").exists():
            fm = parse_skill_frontmatter(item)
            if fm:
                paths[fm["name"]] = item.name
            continue
        # Check nested (e.g., document-skills/docx/)
        for sub in sorted(item.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            if (sub / "SKILL.md").exists():
                sub_fm = parse_skill_frontmatter(sub)
                if sub_fm:
                    paths[sub_fm["name"]] = f"{item.name}/{sub.name}"
    return paths


def discover_available_skills(source_dir: Path) -> dict:
    """Discover available skills from the skills source directory.

    Prefers skills-manifest.json if present. Falls back to scanning directories.
    Returns dict of skill_name -> {version, description, author, path}.
    """
    # Load manifest entries if available (used as base, not as gate)
    manifest_file = source_dir / "skills-manifest.json"
    manifest_skills = {}
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "skills" in data:
                manifest_skills = data["skills"]
                needs_path = [k for k, v in manifest_skills.items() if "path" not in v]
                if needs_path:
                    scanned = _scan_skill_paths(source_dir)
                    for name in needs_path:
                        manifest_skills[name]["path"] = scanned.get(name, name)
        except (json.JSONDecodeError, OSError):
            pass

    # Scan directories for skills not in the manifest (catches newly added skills)
    skills = dict(manifest_skills)
    for item in sorted(source_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue

        # Check if this directory itself is a skill
        fm = parse_skill_frontmatter(item)
        if fm:
            if fm["name"] not in skills:
                skills[fm["name"]] = {
                    "version": fm.get("version", "0.0.0"),
                    "description": fm.get("description", ""),
                    "author": fm.get("author", ""),
                    "path": item.name,
                }
            continue

        # Check for nested skills (e.g., document-skills/docx/)
        for sub in sorted(item.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sub_fm = parse_skill_frontmatter(sub)
            if sub_fm and sub_fm["name"] not in skills:
                skills[sub_fm["name"]] = {
                    "version": sub_fm.get("version", "0.0.0"),
                    "description": sub_fm.get("description", ""),
                    "author": sub_fm.get("author", ""),
                    "path": f"{item.name}/{sub.name}",
                }

    return skills


def rebuild_manifest_from_installed(
    skills_dir: Path,
    known_skill_names: Optional[set] = None,
) -> dict:
    """Rebuild installed manifest by scanning ~/.claude/skills/.

    Used when installed-skills.json is missing or corrupt.
    Only includes skills whose names appear in known_skill_names
    (from the source manifest) to avoid claiming non-AEC skills.
    If known_skill_names is None, includes all skills with SKILL.md.
    """
    manifest = {
        "manifestVersion": MANIFEST_VERSION,
        "installedAt": _now_iso(),
        "updatedAt": _now_iso(),
        "skills": {},
    }

    if not skills_dir.exists():
        return manifest

    for item in sorted(skills_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if known_skill_names is not None and item.name not in known_skill_names:
            continue
        fm = parse_skill_frontmatter(item)
        if fm:
            manifest["skills"][fm["name"]] = {
                "version": fm.get("version", "0.0.0"),
                "contentHash": hash_skill_directory(item),
                "installedAt": _now_iso(),
                "source": "agents-environment-config",
            }

    return manifest
