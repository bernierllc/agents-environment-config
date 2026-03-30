# Skill Versioning & Copy-Based Installation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace symlink-based skill installation with copy-based installation, add per-skill versioning, and provide `aec skills` CLI commands for managing installed skills.

**Architecture:** New `aec/lib/skills_manifest.py` handles manifest I/O, SKILL.md frontmatter parsing, version comparison, and content hashing. New `aec/commands/skills.py` provides the CLI commands. Existing `install.py` and `agent_tools.py` are modified to integrate the new flow. All state lives in `~/.agents-environment-config/installed-skills.json`.

**Tech Stack:** Python 3.9+, Typer (with argparse fallback), shutil, hashlib, json. No PyYAML — uses a simple hand-rolled frontmatter parser (key: value on single lines).

**Prerequisites:**
- The `skills-manifest.json` in the claude-skills repo must have a `path` field for each skill entry (needed for `discover_available_skills()` to resolve source directories for nested skills like `document-skills/docx`). Update `scripts/generate-manifest.py` and regenerate before starting.
- Missing Bernier LLC skills (commit, gdocs, ux-audit, verification-writer) should be pushed to the claude-skills repo.

**Spec:** `docs/superpowers/specs/2026-03-30-skill-versioning-spec.md`

---

### Task 1: Create `aec/lib/skills_manifest.py` — Core Library

**Files:**
- Create: `aec/lib/skills_manifest.py`
- Create: `tests/test_skills_manifest.py`

This is the foundation module. All other tasks depend on it.

- [ ] **Step 1: Write failing tests for `parse_skill_frontmatter()`**

```python
# tests/test_skills_manifest.py
"""Tests for skills manifest library."""

import json
import tempfile
from pathlib import Path

import pytest


class TestParseSkillFrontmatter:
    """Test SKILL.md frontmatter parsing."""

    def test_parses_complete_frontmatter(self, temp_dir: Path):
        skill_dir = temp_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: my-skill\n"
            "description: A test skill\n"
            "version: 1.2.3\n"
            "author: Test Author\n"
            "---\n"
            "# My Skill\n"
            "Instructions here.\n"
        )
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result["name"] == "my-skill"
        assert result["description"] == "A test skill"
        assert result["version"] == "1.2.3"
        assert result["author"] == "Test Author"

    def test_missing_version_defaults_to_0_0_0(self, temp_dir: Path):
        skill_dir = temp_dir / "old-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: old-skill\n"
            "description: No version field\n"
            "---\n"
            "# Old Skill\n"
        )
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result["version"] == "0.0.0"

    def test_no_skill_md_returns_none(self, temp_dir: Path):
        skill_dir = temp_dir / "empty"
        skill_dir.mkdir()
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result is None

    def test_invalid_frontmatter_returns_none(self, temp_dir: Path):
        skill_dir = temp_dir / "bad"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here")
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skills_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aec.lib.skills_manifest'`

- [ ] **Step 3: Implement `parse_skill_frontmatter()`**

```python
# aec/lib/skills_manifest.py
"""Skills manifest management: read/write installed-skills.json, parse SKILL.md frontmatter."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _parse_yaml_frontmatter(text: str) -> Optional[dict]:
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
    fm = _parse_yaml_frontmatter(text)
    if not fm or "name" not in fm:
        return None

    # Default version to 0.0.0 if missing
    if "version" not in fm:
        fm["version"] = "0.0.0"

    return fm
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills_manifest.py::TestParseSkillFrontmatter -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Write failing tests for `parse_version()` and `version_is_newer()`**

```python
class TestVersionComparison:
    """Test semver comparison."""

    def test_parse_version(self):
        from aec.lib.skills_manifest import parse_version

        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("0.0.0") == (0, 0, 0)
        assert parse_version("10.20.30") == (10, 20, 30)

    def test_version_is_newer(self):
        from aec.lib.skills_manifest import version_is_newer

        assert version_is_newer("1.1.0", "1.0.0") is True
        assert version_is_newer("2.0.0", "1.9.9") is True
        assert version_is_newer("1.0.1", "1.0.0") is True
        assert version_is_newer("1.0.0", "1.0.0") is False
        assert version_is_newer("0.9.0", "1.0.0") is False
```

- [ ] **Step 6: Implement version comparison**

```python
def parse_version(version_str: str) -> tuple:
    """Parse a semver string into a comparable tuple."""
    return tuple(int(x) for x in version_str.split("."))


def version_is_newer(available: str, installed: str) -> bool:
    """Return True if available version is newer than installed."""
    return parse_version(available) > parse_version(installed)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills_manifest.py::TestVersionComparison -v`
Expected: All PASS

- [ ] **Step 8: Write failing tests for `hash_skill_directory()`**

```python
class TestContentHashing:
    """Test skill directory hashing."""

    def test_hash_produces_sha256_prefix(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        result = hash_skill_directory(skill_dir)
        assert result.startswith("sha256:")

    def test_hash_ignores_hidden_files(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest2"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        hash_before = hash_skill_directory(skill_dir)
        (skill_dir / ".DS_Store").write_text("junk")
        hash_after = hash_skill_directory(skill_dir)
        assert hash_before == hash_after

    def test_hash_changes_on_content_change(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest3"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        hash_before = hash_skill_directory(skill_dir)
        (skill_dir / "SKILL.md").write_text("# Changed")
        hash_after = hash_skill_directory(skill_dir)
        assert hash_before != hash_after

    def test_hash_includes_subdirectory_files(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest4"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        hash_before = hash_skill_directory(skill_dir)
        refs = skill_dir / "references"
        refs.mkdir()
        (refs / "guide.md").write_text("Guide content")
        hash_after = hash_skill_directory(skill_dir)
        assert hash_before != hash_after
```

- [ ] **Step 9: Implement `hash_skill_directory()`**

```python
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
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills_manifest.py::TestContentHashing -v`
Expected: All PASS

- [ ] **Step 11: Write failing tests for manifest I/O**

```python
class TestManifestIO:
    """Test installed-skills.json read/write."""

    def test_load_empty_manifest(self, temp_dir: Path):
        from aec.lib.skills_manifest import load_installed_manifest

        result = load_installed_manifest(temp_dir / "nonexistent.json")
        assert result["manifestVersion"] == 1
        assert result["skills"] == {}

    def test_save_and_load_manifest(self, temp_dir: Path):
        manifest_path = temp_dir / "installed-skills.json"
        from aec.lib.skills_manifest import (
            load_installed_manifest,
            save_installed_manifest,
        )

        manifest = load_installed_manifest(manifest_path)
        manifest["skills"]["test-skill"] = {
            "version": "1.0.0",
            "contentHash": "sha256:abc123",
            "installedAt": "2026-03-30T14:00:00Z",
            "source": "agents-environment-config",
        }
        save_installed_manifest(manifest, manifest_path)

        reloaded = load_installed_manifest(manifest_path)
        assert "test-skill" in reloaded["skills"]
        assert reloaded["skills"]["test-skill"]["version"] == "1.0.0"

    def test_load_corrupt_manifest_returns_empty(self, temp_dir: Path):
        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text("not valid json{{{")
        from aec.lib.skills_manifest import load_installed_manifest

        result = load_installed_manifest(manifest_path)
        assert result["skills"] == {}
```

- [ ] **Step 12: Implement manifest I/O**

```python
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
```

- [ ] **Step 13: Run all tests to verify they pass**

Run: `python -m pytest tests/test_skills_manifest.py -v`
Expected: All PASS

- [ ] **Step 14: Write failing tests for `discover_available_skills()`**

```python
class TestDiscoverAvailableSkills:
    """Test skill discovery from source directory."""

    def test_discovers_top_level_skills(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        skill_a = source / "skill-a"
        skill_a.mkdir()
        (skill_a / "SKILL.md").write_text(
            "---\nname: skill-a\ndescription: Skill A\nversion: 1.0.0\n---\n"
        )
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert "skill-a" in result
        assert result["skill-a"]["version"] == "1.0.0"
        assert result["skill-a"]["path"] == "skill-a"

    def test_discovers_nested_skills(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        group = source / "document-skills"
        group.mkdir()
        docx = group / "docx"
        docx.mkdir()
        (docx / "SKILL.md").write_text(
            "---\nname: docx\ndescription: Word docs\nversion: 1.0.0\n---\n"
        )
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert "docx" in result
        assert result["docx"]["path"] == "document-skills/docx"

    def test_skips_non_skill_directories(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        (source / "scripts").mkdir()
        (source / "assets").mkdir()
        (source / "README.md").write_text("# README")
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert result == {}

    def test_uses_manifest_json_when_available(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        manifest = {
            "manifestVersion": 1,
            "generatedAt": "2026-03-30T12:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "2.0.0",
                    "description": "From manifest",
                    "author": "Test",
                    "path": "my-skill",
                }
            },
        }
        (source / "skills-manifest.json").write_text(json.dumps(manifest))
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert result["my-skill"]["version"] == "2.0.0"
```

- [ ] **Step 15: Implement `discover_available_skills()`**

```python
def discover_available_skills(source_dir: Path) -> dict:
    """Discover available skills from the skills source directory.

    Prefers skills-manifest.json if present. Falls back to scanning directories.
    Returns dict of skill_name -> {version, description, author, path}.
    """
    manifest_file = source_dir / "skills-manifest.json"
    if manifest_file.exists():
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "skills" in data:
                return data["skills"]
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: scan directories
    skills = {}
    for item in sorted(source_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue

        # Check if this directory itself is a skill
        fm = parse_skill_frontmatter(item)
        if fm:
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
            if sub_fm:
                skills[sub_fm["name"]] = {
                    "version": sub_fm.get("version", "0.0.0"),
                    "description": sub_fm.get("description", ""),
                    "author": sub_fm.get("author", ""),
                    "path": f"{item.name}/{sub.name}",
                }

    return skills
```

- [ ] **Step 16: Run all tests to verify they pass**

Run: `python -m pytest tests/test_skills_manifest.py -v`
Expected: All PASS

- [ ] **Step 17: Write failing test for `rebuild_manifest_from_installed()`**

```python
class TestManifestRecovery:
    """Test manifest rebuild from installed skills."""

    def test_rebuilds_from_installed_skills(self, temp_dir: Path):
        skills_dir = temp_dir / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill = skills_dir / "my-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: Test\nversion: 1.5.0\n---\n"
        )
        from aec.lib.skills_manifest import rebuild_manifest_from_installed

        manifest = rebuild_manifest_from_installed(skills_dir)
        assert "my-skill" in manifest["skills"]
        assert manifest["skills"]["my-skill"]["version"] == "1.5.0"
        assert manifest["skills"]["my-skill"]["contentHash"].startswith("sha256:")
```

- [ ] **Step 18: Implement `rebuild_manifest_from_installed()`**

```python
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
```

**Note:** When calling this during manifest recovery, pass the set of skill names from
`discover_available_skills()` so non-AEC skills are excluded.

- [ ] **Step 19: Run full test suite to verify nothing is broken**

Run: `python -m pytest tests/test_skills_manifest.py -v`
Expected: All PASS

- [ ] **Step 20: Commit**

```bash
git add aec/lib/skills_manifest.py tests/test_skills_manifest.py
git commit -m "feat(skills): add skills_manifest library for version tracking and discovery"
```

---

### Task 2: Register `skills_manifest` in `aec/lib/__init__.py`

**Files:**
- Modify: `aec/lib/__init__.py`

- [ ] **Step 1: Add imports to `__init__.py`**

Add to the imports section of `aec/lib/__init__.py`:

```python
from .skills_manifest import (
    parse_skill_frontmatter,
    parse_version,
    version_is_newer,
    hash_skill_directory,
    load_installed_manifest,
    save_installed_manifest,
    discover_available_skills,
    rebuild_manifest_from_installed,
)
```

Add to `__all__`:

```python
    # Skills manifest
    "parse_skill_frontmatter",
    "parse_version",
    "version_is_newer",
    "hash_skill_directory",
    "load_installed_manifest",
    "save_installed_manifest",
    "discover_available_skills",
    "rebuild_manifest_from_installed",
```

Note: `MANIFEST_VERSION` is intentionally NOT exported — it's an internal constant
used only within `skills_manifest.py`.

- [ ] **Step 2: Run existing test suite to verify nothing broken**

Run: `python -m pytest tests/ -v`
Expected: All existing tests still PASS

- [ ] **Step 3: Commit**

```bash
git add aec/lib/__init__.py
git commit -m "feat(skills): register skills_manifest exports in lib"
```

---

### Task 3: Create `aec/commands/skills.py` — CLI Commands

**Files:**
- Create: `aec/commands/skills.py`
- Create: `tests/test_skills_cmd.py`

- [ ] **Step 1: Write failing tests for `list_skills()`**

```python
# tests/test_skills_cmd.py
"""Tests for aec skills CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_skill(parent: Path, name: str, version: str = "1.0.0") -> Path:
    """Helper to create a skill directory with SKILL.md."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test {name}\nversion: {version}\nauthor: Test\n---\n# {name}\n"
    )
    return skill_dir


class TestListSkills:
    """Test aec skills list command."""

    def test_shows_available_and_installed(self, temp_dir: Path, capsys):
        # Setup source with 2 skills
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "skill-a", "1.0.0")
        _make_skill(source, "skill-b", "2.0.0")

        # Setup installed with 1 skill
        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "skill-a", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "skill-a": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import list_skills

        list_skills(
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
        )
        output = capsys.readouterr().out
        assert "skill-a" in output
        assert "skill-b" in output
        assert "up to date" in output
        assert "available" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_skills_cmd.py::TestListSkills -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `list_skills()`**

```python
# aec/commands/skills.py
"""Skills commands: aec skills {list|install|uninstall|update}"""

import shutil
from pathlib import Path
from typing import List, Optional

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console, get_repo_root, AEC_HOME, CLAUDE_DIR
from ..lib.skills_manifest import (
    discover_available_skills,
    load_installed_manifest,
    save_installed_manifest,
    rebuild_manifest_from_installed,
    hash_skill_directory,
    version_is_newer,
    parse_skill_frontmatter,
)

if HAS_TYPER:
    app = typer.Typer(help="Manage Claude Code skills")
else:
    app = None

INSTALLED_MANIFEST = AEC_HOME / "installed-skills.json"


def _default_source_dir() -> Optional[Path]:
    repo = get_repo_root()
    return repo / ".claude" / "skills" if repo else None


def _default_installed_dir() -> Path:
    return CLAUDE_DIR / "skills"


def list_skills(
    source_dir: Optional[Path] = None,
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
) -> None:
    """Show all available and installed skills."""
    if source_dir is None:
        source_dir = _default_source_dir()
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.error("Skills source not found. Run 'aec install' first.")
        return

    available = discover_available_skills(source_dir)
    manifest = load_installed_manifest(manifest_path)
    installed = manifest.get("skills", {})

    # Collect all skill names
    all_names = sorted(set(list(available.keys()) + list(installed.keys())))

    # Find unmanaged skills in installed dir
    unmanaged = []
    if installed_dir.exists():
        for item in sorted(installed_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                if item.name not in available and item.name not in installed:
                    unmanaged.append(item.name)

    Console.header("Skills (source: agents-environment-config)")

    # Table header
    Console.print(f"  {'Name':<28} {'Installed':<12} {'Available':<12} Status")
    Console.print(f"  {'─' * 70}")

    update_count = 0
    installed_count = 0
    not_installed_count = 0

    for name in all_names:
        avail_version = available.get(name, {}).get("version", "—")
        inst_version = installed.get(name, {}).get("version", "—")

        if name in installed and name in available:
            installed_count += 1
            if version_is_newer(avail_version, inst_version):
                status = "update available"
                update_count += 1
            else:
                status = "up to date"
        elif name in installed:
            installed_count += 1
            status = "installed (not in source)"
        else:
            not_installed_count += 1
            status = "available"

        Console.print(f"  {name:<28} {inst_version:<12} {avail_version:<12} {status}")

    if unmanaged:
        Console.print()
        Console.print("  Other skills (not managed by AEC):")
        for name in unmanaged:
            Console.print(f"    {name}")

    Console.print()
    Console.print(
        f"  {installed_count} installed, {update_count} updates available, "
        f"{not_installed_count} not installed"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_skills_cmd.py::TestListSkills -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for `install_skills()`**

```python
class TestInstallSkills:
    """Test aec skills install command."""

    def test_copies_skill_to_installed_dir(self, temp_dir: Path):
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "new-skill", "1.0.0")

        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()

        manifest_path = temp_dir / "installed-skills.json"

        from aec.commands.skills import install_skills

        install_skills(
            names=["new-skill"],
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )

        assert (installed_dir / "new-skill" / "SKILL.md").exists()

        manifest = json.loads(manifest_path.read_text())
        assert "new-skill" in manifest["skills"]
        assert manifest["skills"]["new-skill"]["version"] == "1.0.0"

    def test_errors_on_unknown_skill(self, temp_dir: Path):
        source = temp_dir / "source"
        source.mkdir()
        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        manifest_path = temp_dir / "installed-skills.json"

        from aec.commands.skills import install_skills

        with pytest.raises(SystemExit):
            install_skills(
                names=["nonexistent"],
                source_dir=source,
                installed_dir=installed_dir,
                manifest_path=manifest_path,
                yes=True,
            )
```

- [ ] **Step 6: Implement `install_skills()`**

```python
def install_skills(
    names: List[str],
    source_dir: Optional[Path] = None,
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    yes: bool = False,
) -> None:
    """Install one or more skills by name."""
    if source_dir is None:
        source_dir = _default_source_dir()
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.error("Skills source not found. Run 'aec install' first.")
        raise SystemExit(1)

    available = discover_available_skills(source_dir)
    manifest = load_installed_manifest(manifest_path)

    # Ensure target dir exists
    installed_dir.mkdir(parents=True, exist_ok=True)

    for name in names:
        if name not in available:
            Console.error(f"Skill not found: {name}")
            Console.print(f"Available: {', '.join(sorted(available.keys()))}")
            raise SystemExit(1)

        skill_info = available[name]
        src = source_dir / skill_info.get("path", name)
        dst = installed_dir / name

        if dst.exists() and not yes:
            try:
                response = input(f"  {name} already exists. Overwrite? [y/N]: ").strip().lower()
            except EOFError:
                response = "n"
            if response != "y":
                Console.info(f"Skipped: {name}")
                continue

        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".*"))

        content_hash = hash_skill_directory(dst)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        manifest["skills"][name] = {
            "version": skill_info.get("version", "0.0.0"),
            "contentHash": content_hash,
            "installedAt": now,
            "source": "agents-environment-config",
        }

        Console.success(f"Installed: {name} ({skill_info.get('version', '0.0.0')})")

    save_installed_manifest(manifest, manifest_path)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills_cmd.py::TestInstallSkills -v`
Expected: PASS

- [ ] **Step 8: Write failing tests for `uninstall_skills()`**

```python
class TestUninstallSkills:
    """Test aec skills uninstall command."""

    def test_removes_skill_directory_and_manifest_entry(self, temp_dir: Path):
        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "old-skill", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "old-skill": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import uninstall_skills

        uninstall_skills(
            names=["old-skill"],
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )

        assert not (installed_dir / "old-skill").exists()
        manifest = json.loads(manifest_path.read_text())
        assert "old-skill" not in manifest["skills"]
```

- [ ] **Step 9: Implement `uninstall_skills()`**

```python
def uninstall_skills(
    names: List[str],
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    yes: bool = False,
) -> None:
    """Uninstall one or more skills by name."""
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    manifest = load_installed_manifest(manifest_path)

    for name in names:
        skill_dir = installed_dir / name
        if not skill_dir.exists():
            Console.warning(f"Skill not found: {name}")
            continue

        if not yes:
            try:
                response = input(f"  Remove {name} from ~/.claude/skills/? [y/N]: ").strip().lower()
            except EOFError:
                response = "n"
            if response != "y":
                Console.info(f"Skipped: {name}")
                continue

        shutil.rmtree(skill_dir)
        manifest["skills"].pop(name, None)
        Console.success(f"Uninstalled: {name}")

    save_installed_manifest(manifest, manifest_path)
```

- [ ] **Step 10: Write failing tests for `update_skills()`**

```python
class TestUpdateSkills:
    """Test aec skills update command."""

    def test_updates_skill_with_newer_version(self, temp_dir: Path):
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "my-skill", "2.0.0")

        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "my-skill", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import update_skills

        update_skills(
            names=None,
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )

        manifest = json.loads(manifest_path.read_text())
        assert manifest["skills"]["my-skill"]["version"] == "2.0.0"

    def test_reports_no_updates_when_current(self, temp_dir: Path, capsys):
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "my-skill", "1.0.0")

        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "my-skill", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import update_skills

        update_skills(
            names=None,
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )
        output = capsys.readouterr().out
        assert "up to date" in output.lower()
```

- [ ] **Step 11: Implement `update_skills()`**

```python
def update_skills(
    names: Optional[List[str]] = None,
    source_dir: Optional[Path] = None,
    installed_dir: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    yes: bool = False,
) -> None:
    """Update installed skills to latest available versions."""
    if source_dir is None:
        source_dir = _default_source_dir()
    if installed_dir is None:
        installed_dir = _default_installed_dir()
    if manifest_path is None:
        manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.error("Skills source not found. Run 'aec install' first.")
        raise SystemExit(1)

    available = discover_available_skills(source_dir)
    manifest = load_installed_manifest(manifest_path)
    installed = manifest.get("skills", {})

    # Determine which skills to check
    if names:
        to_check = {n: installed[n] for n in names if n in installed}
    else:
        to_check = dict(installed)

    updates = []
    for name, info in to_check.items():
        if name not in available:
            continue
        avail_version = available[name].get("version", "0.0.0")
        inst_version = info.get("version", "0.0.0")
        if version_is_newer(avail_version, inst_version):
            updates.append((name, inst_version, avail_version))

    if not updates:
        Console.success("All skills up to date.")
        return

    Console.print("Updates available:")
    for name, old_v, new_v in updates:
        Console.print(f"  {name}: {old_v} → {new_v}")

    if not yes:
        try:
            response = input("\nApply updates? [Y/n]: ").strip().lower()
        except EOFError:
            response = "n"
        if response == "n":
            Console.info("Update skipped.")
            return

    for name, old_v, new_v in updates:
        skill_dir = installed_dir / name
        skill_info = available[name]
        src = source_dir / skill_info.get("path", name)

        # Check for local modifications
        if skill_dir.exists():
            current_hash = hash_skill_directory(skill_dir)
            recorded_hash = installed.get(name, {}).get("contentHash", "")
            if current_hash != recorded_hash and not yes:
                try:
                    resp = input(f"  {name} has local modifications. Overwrite? [y/N]: ").strip().lower()
                except EOFError:
                    resp = "n"
                if resp != "y":
                    Console.info(f"Skipped: {name}")
                    continue

        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(src, skill_dir, ignore=shutil.ignore_patterns(".*"))

        content_hash = hash_skill_directory(skill_dir)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        manifest["skills"][name] = {
            "version": new_v,
            "contentHash": content_hash,
            "installedAt": now,
            "source": "agents-environment-config",
        }
        Console.success(f"Updated: {name} ({old_v} → {new_v})")

    save_installed_manifest(manifest, manifest_path)
```

- [ ] **Step 12: Run all skills command tests**

Run: `python -m pytest tests/test_skills_cmd.py -v`
Expected: All PASS

- [ ] **Step 13: Add Typer and argparse command registration**

Add to `aec/commands/skills.py`:
- Typer app with `list`, `install`, `uninstall`, `update` commands
- Each command accepts `--yes`/`-y` flag
- `install` and `uninstall` take `names` as variadic arguments

- [ ] **Step 14: Commit**

```bash
git add aec/commands/skills.py tests/test_skills_cmd.py
git commit -m "feat(skills): add aec skills CLI commands (list, install, uninstall, update)"
```

---

### Task 4: Register `aec skills` in CLI

**Files:**
- Modify: `aec/cli.py`

- [ ] **Step 1: Add Typer registration**

In the Typer section of `cli.py` (around line 39), add:

```python
from .commands import skills
app.add_typer(skills.app, name="skills", help="Manage Claude Code skills")
```

- [ ] **Step 2: Add argparse fallback**

In the argparse section, add a `skills` subparser with `list`, `install`, `uninstall`, `update` sub-subparsers. Follow the pattern used by `repo` and `preferences`.

Add to the dispatch section:

```python
elif args.command == "skills":
    from .commands import skills as skills_cmd
    if args.skills_command == "list":
        skills_cmd.list_skills()
    elif args.skills_command == "install":
        skills_cmd.install_skills(names=args.names, yes=args.yes)
    elif args.skills_command == "uninstall":
        skills_cmd.uninstall_skills(names=args.names, yes=args.yes)
    elif args.skills_command == "update":
        skills_cmd.update_skills(names=args.name, yes=args.yes)
    else:
        skills_parser.print_help()
```

- [ ] **Step 3: Run CLI smoke test**

Run: `aec skills list` and `aec skills --help`
Expected: Help text shows and list runs without error

- [ ] **Step 4: Commit**

```bash
git add aec/cli.py
git commit -m "feat(skills): register aec skills command group in CLI"
```

---

### Task 5: Modify `agent_tools.setup()` — Remove Skills Symlinks

**Files:**
- Modify: `aec/commands/agent_tools.py:109-113`
- Modify: `aec/commands/agent_tools.py:146-162`
- Modify: `tests/test_dry_run.py` (if it tests skills symlink creation)

- [ ] **Step 1: Remove skills from the repo symlinks list**

In `agent_tools.py` line 112, remove the skills entry from the `symlinks` list:

```python
# BEFORE (line 112):
(repo_root / ".claude" / "skills", AGENT_TOOLS_DIR / "skills" / "agents-environment-config", "Skills"),

# AFTER: Remove this line entirely
```

- [ ] **Step 2: Remove skills from the Claude symlinks list**

In `agent_tools.py` lines 149-150, remove the skills entry from `claude_links`:

```python
# BEFORE (lines 149-150):
(AGENT_TOOLS_DIR / "skills" / "agents-environment-config",
 CLAUDE_DIR / "skills" / "agents-environment-config", "Claude skills"),

# AFTER: Remove these two lines entirely
```

- [ ] **Step 3: Update the summary output**

In the summary section (around line 205), change:

```python
Console.print("  ├── skills/")
Console.print("  │   └── agents-environment-config/ → repo/.claude/skills/")
```

to:

```python
Console.print("  ├── skills/")
Console.print("  │   └── [managed by: aec skills]")
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All PASS (update any tests that assert on the skills symlink)

- [ ] **Step 5: Commit**

```bash
git add aec/commands/agent_tools.py
git commit -m "refactor(skills): remove skills symlink creation from agent_tools.setup()"
```

---

### Task 6: Add Symlink Cleanup to `install.py`

**Files:**
- Modify: `aec/commands/install.py`
- Create: `tests/test_skills_cleanup.py`

- [ ] **Step 1: Write failing test for symlink cleanup**

```python
# tests/test_skills_cleanup.py
"""Tests for skills symlink cleanup during install."""

import os
from pathlib import Path

import pytest


class TestSymlinkCleanup:
    """Test legacy symlink removal."""

    def test_removes_aec_skills_symlink_from_claude(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Create the AEC symlink
        target = agent_tools_skills / "agents-environment-config"
        target.mkdir()
        link = claude_skills / "agents-environment-config"
        link.symlink_to(target)

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        assert not link.exists()

    def test_does_not_remove_non_aec_symlinks(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Create a non-AEC symlink at the same name but pointing elsewhere
        other_target = temp_dir / "some-other-place"
        other_target.mkdir()
        link = claude_skills / "agents-environment-config"
        link.symlink_to(other_target)

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        # Should NOT be removed — it doesn't point to agent-tools
        assert link.exists()

    def test_leaves_real_directories_alone(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Real directory, not a symlink
        real = claude_skills / "braingrid-cli"
        real.mkdir()

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        assert real.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skills_cleanup.py -v`
Expected: FAIL — `ImportError: cannot import name '_cleanup_legacy_symlinks'`

- [ ] **Step 3: Implement `_cleanup_legacy_symlinks()` in install.py**

```python
from typing import Optional

def _cleanup_legacy_symlinks(
    claude_skills_dir: Optional[Path] = None,
    agent_tools_skills_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> None:
    """Remove AEC-created skill symlinks from known paths.

    Only removes symlinks whose targets contain 'agent-tools' or
    'agents-environment-config' in the resolution chain.
    """
    if claude_skills_dir is None:
        from ..lib import CLAUDE_DIR
        claude_skills_dir = CLAUDE_DIR / "skills"
    if agent_tools_skills_dir is None:
        from ..lib import AGENT_TOOLS_DIR
        agent_tools_skills_dir = AGENT_TOOLS_DIR / "skills"

    targets = [
        claude_skills_dir / "agents-environment-config",
        agent_tools_skills_dir / "agents-environment-config",
    ]

    for link_path in targets:
        if not link_path.is_symlink():
            continue
        resolved = str(link_path.resolve())
        if "agent-tools" in resolved or "agents-environment-config" in resolved:
            if dry_run:
                Console.info(f"Would remove legacy symlink: {link_path}")
            else:
                link_path.unlink()
                Console.success(f"Cleaned up legacy symlink: {link_path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills_cleanup.py -v`
Expected: All PASS

- [ ] **Step 5: Integrate cleanup and skills step into `install()`**

In `install.py`, after the agent-tools setup section (around line 298) and before detecting agents (line 301), add:

```python
    # Clean up legacy skill symlinks
    with Console.section("Cleaning up legacy symlinks...", collapse=not dry_run):
        _cleanup_legacy_symlinks(dry_run=dry_run)
        if not dry_run:
            Console.success("Legacy symlink cleanup complete")

    # Skills install/update step
    with Console.section("Skills management...", collapse=False):
        from .skills import install_step
        install_step(dry_run=dry_run)
```

- [ ] **Step 5.5: Write failing tests for `_parse_selection()` and `install_step()`**

Add to `tests/test_skills_cleanup.py`:

```python
class TestParseSelection:
    """Test range/selection parsing for skill install prompt."""

    def test_parse_all(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("a", 10) == set(range(1, 11))
        assert _parse_selection("all", 10) == set(range(1, 11))

    def test_parse_none(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("n", 10) == set()
        assert _parse_selection("none", 10) == set()

    def test_parse_single_numbers(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,3,5", 10) == {1, 3, 5}

    def test_parse_ranges(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1-3,7", 10) == {1, 2, 3, 7}

    def test_parse_mixed(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,3-5,8", 10) == {1, 3, 4, 5, 8}

    def test_ignores_out_of_range(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,99", 5) == {1}

    def test_empty_input_returns_empty(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("", 10) == set()
```

- [ ] **Step 5.6: Implement `_parse_selection()`**

Add to `aec/commands/skills.py`:

```python
def _parse_selection(text: str, max_num: int) -> set:
    """Parse user selection input like 'a', 'n', '1,3,5-8' into a set of numbers."""
    text = text.strip().lower()
    if text in ("a", "all"):
        return set(range(1, max_num + 1))
    if text in ("n", "none", ""):
        return set()

    result = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                for i in range(int(start), int(end) + 1):
                    if 1 <= i <= max_num:
                        result.add(i)
            except ValueError:
                continue
        else:
            try:
                num = int(part)
                if 1 <= num <= max_num:
                    result.add(num)
            except ValueError:
                continue
    return result
```

- [ ] **Step 6: Implement `install_step()` in skills.py**

```python
def install_step(dry_run: bool = False) -> None:
    """Interactive skills install/update step for aec install.

    On first install: shows numbered list, lets user select.
    On subsequent: shows updates and new skills only.
    In dry-run: reports what would happen without prompting.
    """
    source_dir = _default_source_dir()
    installed_dir = _default_installed_dir()
    manifest_path = INSTALLED_MANIFEST

    if source_dir is None or not source_dir.exists():
        Console.info("Skills source not available — skipping")
        return

    available = discover_available_skills(source_dir)
    if not available:
        Console.info("No skills found in source")
        return

    # Load or recover manifest
    manifest = load_installed_manifest(manifest_path)
    if not manifest["skills"] and installed_dir.exists():
        # Attempt recovery from existing installed skills
        known_names = set(available.keys())
        manifest = rebuild_manifest_from_installed(installed_dir, known_names)
        if manifest["skills"]:
            save_installed_manifest(manifest, manifest_path)
            Console.info(f"Recovered manifest with {len(manifest['skills'])} skills")

    installed = manifest.get("skills", {})
    installed_dir.mkdir(parents=True, exist_ok=True)

    # Determine what's new and what's updated
    new_skills = {k: v for k, v in available.items() if k not in installed}
    updates = {}
    for name, info in installed.items():
        if name in available:
            avail_v = available[name].get("version", "0.0.0")
            inst_v = info.get("version", "0.0.0")
            if version_is_newer(avail_v, inst_v):
                updates[name] = (inst_v, avail_v)

    if not new_skills and not updates:
        Console.success("All skills up to date")
        return

    first_install = len(installed) == 0

    if dry_run:
        if updates:
            Console.info(f"Would offer {len(updates)} skill update(s)")
            for name, (old_v, new_v) in updates.items():
                Console.info(f"  {name}: {old_v} → {new_v}")
        if new_skills:
            Console.info(f"Would offer {len(new_skills)} new skill(s)")
        return

    if first_install:
        # Show all available skills numbered
        skill_list = sorted(available.keys())
        Console.print("\nAvailable skills:\n")
        for i, name in enumerate(skill_list, 1):
            info = available[name]
            desc = info.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            Console.print(f"  {i:>3}. {name} ({info.get('version', '?')}) — {desc}")

        Console.print()
        try:
            response = input(f"Install: [a]ll, [n]one, or enter numbers (e.g. 1,3,5-8): ").strip()
        except EOFError:
            response = "n"

        selected = _parse_selection(response, len(skill_list))
        names_to_install = [skill_list[i - 1] for i in sorted(selected)]

        if names_to_install:
            install_skills(
                names=names_to_install,
                source_dir=source_dir,
                installed_dir=installed_dir,
                manifest_path=manifest_path,
                yes=True,
            )
        else:
            Console.info("No skills selected")
    else:
        # Show updates and new skills
        if updates:
            Console.print("\nSkill updates available:")
            for name, (old_v, new_v) in sorted(updates.items()):
                Console.print(f"  {name}: {old_v} → {new_v}")

        if new_skills:
            Console.print("\nNew skills available:")
            for name in sorted(new_skills.keys()):
                info = new_skills[name]
                desc = info.get("description", "")
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                Console.print(f"  {name} ({info.get('version', '?')}) — {desc}")

        Console.print()
        try:
            response = input("Install updates and new skills? [a]ll, [s]elect, [S]kip: ").strip().lower()
        except EOFError:
            response = "s"

        if response == "a" or response == "all":
            all_names = list(updates.keys()) + list(new_skills.keys())
            if updates:
                update_skills(
                    names=list(updates.keys()),
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
            if new_skills:
                install_skills(
                    names=list(new_skills.keys()),
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
        elif response == "s" or response == "select":
            # Show numbered list of changes
            items = []
            for name, (old_v, new_v) in sorted(updates.items()):
                items.append((name, f"update {old_v} → {new_v}"))
            for name in sorted(new_skills.keys()):
                items.append((name, f"new ({new_skills[name].get('version', '?')})"))

            for i, (name, label) in enumerate(items, 1):
                Console.print(f"  {i:>3}. {name} — {label}")

            try:
                sel = input("Enter numbers (e.g. 1,3,5-8): ").strip()
            except EOFError:
                sel = ""

            selected = _parse_selection(sel, len(items))
            selected_names = [items[i - 1][0] for i in sorted(selected)]

            update_names = [n for n in selected_names if n in updates]
            new_names = [n for n in selected_names if n in new_skills]

            if update_names:
                update_skills(
                    names=update_names,
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
            if new_names:
                install_skills(
                    names=new_names,
                    source_dir=source_dir,
                    installed_dir=installed_dir,
                    manifest_path=manifest_path,
                    yes=True,
                )
        else:
            Console.info("Skipped skills step")
```

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add aec/commands/install.py aec/commands/skills.py tests/test_skills_cleanup.py
git commit -m "feat(skills): add symlink cleanup and skills step to install flow"
```

---

### Task 7: Update `aec doctor` — Skills Health Checks

**Files:**
- Modify: `aec/commands/doctor.py`

- [ ] **Step 1: Add skills health checks after the existing "Agent Directories" section**

Insert a new section in `run_doctor()` (after line 172, before line 175):

```python
    # Check: Skills installation
    Console.subheader("Skills")

    from ..lib import AEC_HOME
    from ..lib.skills_manifest import load_installed_manifest

    manifest_path = AEC_HOME / "installed-skills.json"
    checks_total += 1
    if manifest_path.exists():
        try:
            manifest = load_installed_manifest(manifest_path)
            skill_count = len(manifest.get("skills", {}))
            Console.success(f"installed-skills.json valid ({skill_count} skills tracked)")
            checks_passed += 1

            # Verify each tracked skill exists on disk
            for name, info in manifest.get("skills", {}).items():
                skill_dir = CLAUDE_DIR / "skills" / name
                checks_total += 1
                if skill_dir.exists():
                    Console.success(f"  {name} ({info.get('version', '?')})")
                    checks_passed += 1
                else:
                    Console.error(f"  {name} tracked but directory missing")
                    issues.append(f"Skill '{name}' in manifest but missing from ~/.claude/skills/")
        except Exception as e:
            Console.error(f"installed-skills.json: {e}")
            issues.append("installed-skills.json is corrupt")
    else:
        Console.info("installed-skills.json not found (run: aec skills install)")
        checks_passed += 1  # OK on first run

    # Check for stale AEC symlinks
    checks_total += 1
    stale_link = CLAUDE_DIR / "skills" / "agents-environment-config"
    if stale_link.is_symlink():
        Console.error("Legacy symlink found: ~/.claude/skills/agents-environment-config")
        issues.append("Legacy skills symlink still exists (fix with: aec install)")
    else:
        Console.success("No legacy skills symlinks")
        checks_passed += 1
```

- [ ] **Step 2: Update the existing Claude skills symlink check**

In the existing "Agent Directories" section (around line 148), the current code checks for and reports on the skills symlink as expected. Change it to report the symlink as a legacy issue instead of a success:

```python
# In the Claude section, replace the skills symlink check:
link_path = CLAUDE_DIR / "skills" / "agents-environment-config"
if link_path.is_symlink():
    Console.warning(f"  └─ skills/agents-environment-config (legacy symlink, run: aec install)")
else:
    Console.success(f"  └─ skills/ (managed by: aec skills)")
```

- [ ] **Step 3: Run doctor to verify output**

Run: `aec doctor`
Expected: Shows new "Skills" section with current state

- [ ] **Step 4: Commit**

```bash
git add aec/commands/doctor.py
git commit -m "feat(skills): add skills health checks to aec doctor"
```

---

### Task 8: Update `install.py` Summary and Final Integration

**Files:**
- Modify: `aec/commands/install.py` (final summary section)

- [ ] **Step 1: Update the "What was set up" summary**

In the final summary section of `install()` (around line 370), add skills info:

```python
        Console.print("What was set up:")
        Console.print(f"  - ~/.agents-environment-config/  (local config)")
        Console.print(f"  - ~/.agent-tools/                (shared agent content)")
        Console.print(f"  - ~/.claude/skills/              (installed skills)")
        Console.print(f"  - .agent-rules/                  (frontmatter-stripped rules)")
```

Update "Next steps":

```python
        Console.print("Next steps:")
        Console.print(f"  1. Setup a project: {Console.cmd('aec repo setup <project>')}")
        Console.print(f"  2. Manage skills:   {Console.cmd('aec skills list')}")
        Console.print(f"  3. Check health:    {Console.cmd('aec doctor')}")
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Run `aec install --dry-run` end-to-end**

Run: `aec install --dry-run`
Expected: Shows new skills step in dry-run output, no errors

- [ ] **Step 4: Commit**

```bash
git add aec/commands/install.py
git commit -m "feat(skills): update install summary with skills management info"
```

---

### Task 9: End-to-End Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run `aec doctor` and verify skills section**

Run: `aec doctor`
Expected: Shows "Skills" section, reports legacy symlink if present

- [ ] **Step 3: Run `aec skills list`**

Run: `aec skills list`
Expected: Shows available skills from submodule, installed skills, and "Other skills" section

- [ ] **Step 4: Test install flow — install a skill**

Run: `aec skills install brand-guidelines --yes`
Expected: Copies to `~/.claude/skills/brand-guidelines/`, updates manifest

- [ ] **Step 5: Test update flow**

Run: `aec skills update`
Expected: Reports "All skills up to date" (since we just installed latest)

- [ ] **Step 6: Test uninstall flow**

Run: `aec skills uninstall brand-guidelines --yes`
Expected: Removes directory and manifest entry

- [ ] **Step 7: Run `aec install --dry-run` end-to-end**

Run: `aec install --dry-run`
Expected: Full flow runs without errors, shows skills step

- [ ] **Step 8: Final commit if any cleanup needed**

Stage only the specific files that were modified, then commit:

```bash
git commit -m "chore(skills): end-to-end verification cleanup"
```
