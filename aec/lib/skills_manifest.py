"""Skills manifest management: read/write installed-skills.json, parse SKILL.md frontmatter."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, NamedTuple, Optional, Dict, Any


class SkillDep(NamedTuple):
    """A declared skill dependency from SKILL.md frontmatter."""

    name: str
    min_version: str
    reason: str


# Semver pattern: x.y.z where x, y, z are non-negative integers.
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _is_valid_semver(value: str) -> bool:
    return bool(_SEMVER_RE.match(value))


def parse_dependencies_block(text: str) -> List[SkillDep]:
    """Parse the ``dependencies.skills`` block from raw YAML frontmatter text.

    Handles only the exact shape:
        dependencies:
          skills:
            - name: <str>
              min_version: "<semver>"
              reason: "<str>"

    Returns an empty list if no ``dependencies`` block is present.

    Raises ValueError with a descriptive message if the block is present but
    malformed (missing required field, or min_version is not valid semver).

    Design note: we use a targeted line-by-line parser so we don't need PyYAML.
    All other frontmatter fields remain parsed by the existing regex scalar parser.

    Indentation requirement: this parser requires exact 2/4/6-space indentation —
    ``dependencies:`` at column 0, ``skills:`` at 2 spaces, list items (``- name:``)
    at 4 spaces, and continuation keys (``min_version:``, ``reason:``) at 6 spaces.
    This is the canonical format defined by the AEC SKILL.md spec.
    """
    # Extract the raw frontmatter block.
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return []

    fm_text = fm_match.group(1)
    lines = fm_text.split("\n")

    # Find the ``dependencies:`` key (unindented).
    dep_start = None
    for i, line in enumerate(lines):
        if re.match(r"^dependencies\s*:", line):
            dep_start = i
            break

    if dep_start is None:
        return []

    # Collect all lines that belong to the dependencies block (indented lines
    # after the ``dependencies:`` key, until we hit an unindented non-empty line).
    dep_lines = []
    for line in lines[dep_start + 1:]:
        if line == "" or line[0] == " " or line[0] == "\t":
            dep_lines.append(line)
        else:
            break  # Back at top-level key — dependencies block ended.

    # Find ``skills:`` within the block (indented by exactly 2 spaces).
    skills_start = None
    for i, line in enumerate(dep_lines):
        if re.match(r"^\s{2}skills\s*:", line):
            skills_start = i
            break

    if skills_start is None:
        # ``dependencies`` block exists but has no ``skills`` key — not an error,
        # just no skill deps.
        return []

    # Parse each ``- name: ...`` entry that follows ``skills:``.
    # Entries are indented by 4 spaces; item keys by 6 spaces.
    skill_lines = dep_lines[skills_start + 1:]

    deps: List[SkillDep] = []
    current: Dict[str, str] = {}

    def _flush_entry(entry: Dict[str, str]) -> SkillDep:
        """Validate and build a SkillDep from a parsed entry dict."""
        if "name" not in entry:
            raise ValueError(
                "dependencies.skills entry is missing required field 'name'"
            )
        if "reason" not in entry:
            raise ValueError(
                f"dependencies.skills entry '{entry.get('name', '?')}' "
                "is missing required field 'reason'"
            )
        if "min_version" not in entry:
            raise ValueError(
                f"dependencies.skills entry '{entry['name']}' "
                "is missing required field 'min_version'"
            )
        min_ver = entry["min_version"]
        if not _is_valid_semver(min_ver):
            raise ValueError(
                f"dependencies.skills entry '{entry['name']}' has invalid "
                f"min_version '{min_ver}' — expected semver x.y.z"
            )
        return SkillDep(
            name=entry["name"],
            min_version=min_ver,
            reason=entry["reason"],
        )

    for line in skill_lines:
        # New list item (indented 4 spaces, starts with ``-``).
        item_match = re.match(r"^\s{4}-\s+(\w+)\s*:\s*(.*)", line)
        if item_match:
            if current:
                deps.append(_flush_entry(current))
                current = {}
            key = item_match.group(1)
            value = item_match.group(2).strip()
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            current[key] = value
            continue

        # Continuation key within the current item (indented 6 spaces).
        cont_match = re.match(r"^\s{6}(\w+)\s*:\s*(.*)", line)
        if cont_match:
            key = cont_match.group(1)
            value = cont_match.group(2).strip()
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            current[key] = value
            continue

    if current:
        deps.append(_flush_entry(current))

    return deps


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

    Returns dict with name, description, version, author, dependencies, or None
    if SKILL.md is missing or has no valid frontmatter.

    Failure mode: if the ``dependencies`` block is present but malformed,
    ``parse_dependencies_block`` raises ``ValueError``. We catch it here and
    return ``None`` — a skill with corrupt metadata is treated as uninstallable,
    the same as missing frontmatter.
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

    # Parse dependencies block — ValueError means malformed metadata → uninstallable.
    try:
        fm["dependencies"] = parse_dependencies_block(text)
    except ValueError:
        return None

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


def build_skill_manifest_item(
    *,
    version: str,
    content_hash: str,
    installed_at: str,
    previous: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
    installed_as: str = "explicit",
) -> Dict[str, Any]:
    """Build a skill manifest entry with ``versionHashes`` history keyed by semver."""
    prev = previous or {}
    vhashes = dict(prev.get("versionHashes", {}))
    pv = prev.get("version")
    ph = prev.get("contentHash", "")
    if pv and ph and pv != version:
        vhashes[pv] = ph
    rec: Dict[str, Any] = {
        "version": version,
        "contentHash": content_hash,
        "installedAt": installed_at,
        "versionHashes": vhashes,
        "installedAs": installed_as,
    }
    if source is not None:
        rec["source"] = source
    return rec


def plan_skill_directory_replace(
    dst: Path,
    src: Path,
    installed_info: dict,
    *,
    assume_yes: bool,
) -> str:
    """Decide how to replace installed skill dir ``dst`` with source dir ``src``.

    Compares content hashes to the canonical source tree and to the last
    recorded install so that a stale ``contentHash`` (or an in-place copy of
    the new release) does not get misclassified as uncommitted local edits.

    Returns one of:
        ``absent``: ``dst`` is missing (perform a normal copy).
        ``sync_manifest``: ``dst`` already matches ``src``; refresh manifest only.
        ``overwrite``: safe to replace without prompting.
        ``prompt``: ask the user before overwriting.
    """
    if not dst.exists():
        return "absent"
    if not dst.is_dir() or not src.is_dir():
        return "overwrite" if assume_yes else "prompt"

    current = hash_skill_directory(dst)
    source = hash_skill_directory(src)
    if current == source:
        return "sync_manifest"
    if assume_yes:
        return "overwrite"

    recorded = installed_info.get("contentHash", "")
    inst_v = installed_info.get("version", "0.0.0")
    vhashes = installed_info.get("versionHashes") or {}

    if recorded and current == recorded:
        return "overwrite"
    if inst_v in vhashes and current == vhashes[inst_v]:
        return "overwrite"
    if not recorded:
        return "overwrite"
    return "prompt"


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

    _overlay_skill_metadata_from_skill_md(source_dir, skills)
    return skills


def _overlay_skill_metadata_from_skill_md(source_dir: Path, skills: dict) -> None:
    """Prefer SKILL.md frontmatter for version/description/author when the tree exists.

    skills-manifest.json can lag behind SKILL.md bumps; stale manifest versions would
    otherwise hide updates from `aec update` / `aec outdated`.
    """
    for name, info in list(skills.items()):
        rel = info.get("path") or name
        skill_dir = source_dir / rel
        if not skill_dir.is_dir():
            continue
        fm = parse_skill_frontmatter(skill_dir)
        if not fm:
            continue
        if "version" in fm:
            info["version"] = fm["version"]
        if fm.get("description"):
            info["description"] = fm["description"]
        if fm.get("author"):
            info["author"] = fm["author"]


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
