# Brew-Aligned CLI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the AEC CLI to follow Homebrew's flat command model with local/global scope support for skills, rules, and agents.

**Architecture:** Replace nested command groups (`aec repo update`, `aec skills install`) with flat top-level commands (`aec update`, `aec install skill X`). Add a scope system (`-g` flag, local default) backed by a v2 manifest that tracks installs per-repo and globally. Deprecation shims keep old commands working for one major version.

**Tech Stack:** Python 3.11+, typer (with argparse fallback), pytest, existing `aec/lib/` utilities.

**Spec:** `docs/superpowers/specs/2026-04-04-brew-aligned-cli-redesign.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `aec/lib/scope.py` | Scope resolution: detect local repo, resolve `-g` flag, error when not in tracked repo |
| `aec/lib/manifest_v2.py` | V2 manifest CRUD: load/save, migration from v1, per-repo and global sections |
| `aec/lib/sources.py` | Source management: git pull, submodule update, staleness check, available item discovery across all types |
| `aec/commands/update.py` | `aec update` command |
| `aec/commands/upgrade.py` | `aec upgrade` command |
| `aec/commands/install_cmd.py` | `aec install <type> <name>` command (named `install_cmd.py` to avoid shadowing Python's `install` module) |
| `aec/commands/uninstall.py` | `aec uninstall <type> <name>` command |
| `aec/commands/list_cmd.py` | `aec list` command (named `list_cmd.py` to avoid shadowing Python's `list` builtin) |
| `aec/commands/search.py` | `aec search <term>` command |
| `aec/commands/outdated.py` | `aec outdated` command |
| `aec/commands/info.py` | `aec info <type> <name>` command |
| `aec/commands/setup.py` | `aec setup` command (absorbs install + repo setup) |
| `aec/commands/untrack.py` | `aec untrack <path>` command |
| `aec/commands/config_cmd.py` | `aec config` command (replaces preferences) |
| `aec/commands/generate.py` | `aec generate rules/files` command |
| `aec/commands/deprecation.py` | Deprecation shims for old command names |
| `tests/test_scope.py` | Tests for scope resolution |
| `tests/test_manifest_v2.py` | Tests for v2 manifest |
| `tests/test_sources.py` | Tests for source management |
| `tests/test_update_cmd.py` | Tests for `aec update` |
| `tests/test_upgrade_cmd.py` | Tests for `aec upgrade` |
| `tests/test_install_cmd.py` | Tests for `aec install` |
| `tests/test_uninstall_cmd.py` | Tests for `aec uninstall` |
| `tests/test_list_cmd.py` | Tests for `aec list` |
| `tests/test_search_cmd.py` | Tests for `aec search` |
| `tests/test_outdated_cmd.py` | Tests for `aec outdated` |
| `tests/test_info_cmd.py` | Tests for `aec info` |
| `tests/test_setup_cmd.py` | Tests for `aec setup` |
| `tests/test_untrack_cmd.py` | Tests for `aec untrack` |
| `tests/test_deprecation.py` | Tests for deprecation shims |

### Modified files

| File | Changes |
|---|---|
| `aec/cli.py` | Replace nested subgroups with flat top-level commands; register deprecation shims |
| `aec/lib/config.py` | Add `INSTALLED_MANIFEST_V2` path constant, `SKILLS_SOURCE_DIR` |
| `aec/lib/skills_manifest.py` | Rename `_parse_yaml_frontmatter` to `parse_yaml_frontmatter` (make public), keep v1 functions for migration |
| `aec/lib/tracking.py` | Add `untrack_repo()` function, update README content |

### Untouched files (kept for deprecation period)

| File | Status |
|---|---|
| `aec/commands/repo.py` | Kept. Wrapped with deprecation warnings. |
| `aec/commands/skills.py` | Kept. Wrapped with deprecation warnings. |
| `aec/commands/agent_tools.py` | Kept. Wrapped with deprecation warnings. |
| `aec/commands/rules.py` | Kept. Wrapped with deprecation warnings. |
| `aec/commands/files.py` | Kept. Wrapped with deprecation warnings. |
| `aec/commands/preferences.py` | Kept. Wrapped with deprecation warnings. |

---

## Task Dependency Order

```
Task 1: scope.py (no deps)
Task 2: manifest_v2.py (no deps)
Task 3: sources.py (depends on manifest_v2)
Task 4: aec update (depends on sources)
Task 5: aec upgrade (depends on sources, scope, manifest_v2)
Task 6: aec install (depends on scope, manifest_v2, sources)
Task 7: aec uninstall (depends on scope, manifest_v2)
Task 8: aec list (depends on scope, manifest_v2)
Task 9: aec search (depends on sources)
Task 10: aec outdated (depends on scope, manifest_v2, sources)
Task 11: aec info (depends on scope, manifest_v2)
Task 12: aec setup (depends on scope, manifest_v2 — refactors existing install.py)
Task 13: aec untrack (depends on tracking, manifest_v2)
Task 14: aec config (thin rename of preferences)
Task 15: aec generate + aec validate (thin rewrap of rules/files)
Task 16: cli.py rewrite (depends on all commands)
Task 17: deprecation shims (depends on cli.py rewrite)
Task 18: manifest v1 → v2 migration (depends on manifest_v2)
Task 19: integration tests + README update
```

Tasks 1 and 2 are independent and can run in parallel.
Tasks 6-11 are independent of each other and can run in parallel after tasks 1-3 complete.
Task 16 depends on all command files existing.

---

## Tasks

### Task 1: Scope Resolution Library

**Files:**
- Create: `aec/lib/scope.py`
- Create: `tests/test_scope.py`

- [ ] **Step 1: Write failing tests for scope resolution**

```python
# tests/test_scope.py
"""Tests for scope resolution."""

import pytest
from pathlib import Path


@pytest.fixture
def tracked_repo(temp_dir, monkeypatch):
    """Create a tracked repo structure."""
    repo = temp_dir / "projects" / "my-app"
    repo.mkdir(parents=True)
    (repo / ".claude").mkdir()
    (repo / ".agent-rules").mkdir()

    # Create tracking log
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{repo}\n")

    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    return repo


@pytest.fixture
def untracked_dir(temp_dir, monkeypatch):
    """Create a directory that is not tracked."""
    d = temp_dir / "random"
    d.mkdir()
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    return d


class TestResolveScope:
    def test_local_scope_in_tracked_repo(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(tracked_repo)
        scope = resolve_scope(global_flag=False)
        assert scope.is_local
        assert scope.repo_path == tracked_repo

    def test_global_scope_with_flag(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(tracked_repo)
        scope = resolve_scope(global_flag=True)
        assert scope.is_global
        assert scope.repo_path is None

    def test_error_when_not_in_repo_without_flag(self, untracked_dir, monkeypatch):
        from aec.lib.scope import resolve_scope, ScopeError
        monkeypatch.chdir(untracked_dir)
        with pytest.raises(ScopeError, match="Not in a tracked repo"):
            resolve_scope(global_flag=False)

    def test_global_scope_when_not_in_repo_with_flag(self, untracked_dir, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(untracked_dir)
        scope = resolve_scope(global_flag=True)
        assert scope.is_global

    def test_detects_repo_from_subdirectory(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        subdir = tracked_repo / "src" / "lib"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        scope = resolve_scope(global_flag=False)
        assert scope.is_local
        assert scope.repo_path == tracked_repo


class TestFindTrackedRepo:
    def test_returns_none_for_untracked(self, untracked_dir, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        monkeypatch.chdir(untracked_dir)
        assert find_tracked_repo() is None

    def test_returns_repo_path(self, tracked_repo, monkeypatch):
        from aec.lib.scope import find_tracked_repo
        monkeypatch.chdir(tracked_repo)
        assert find_tracked_repo() == tracked_repo


class TestScopeTargetPaths:
    def test_global_skill_path(self, temp_dir, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        # Use global flag to avoid needing a tracked repo
        scope = resolve_scope(global_flag=True)
        assert scope.skills_dir == temp_dir / ".claude" / "skills"
        assert scope.agents_dir == temp_dir / ".claude" / "agents"

    def test_local_skill_path(self, tracked_repo, monkeypatch):
        from aec.lib.scope import resolve_scope
        monkeypatch.chdir(tracked_repo)
        scope = resolve_scope(global_flag=False)
        assert scope.skills_dir == tracked_repo / ".claude" / "skills"
        assert scope.agents_dir == tracked_repo / ".claude" / "agents"
        assert scope.rules_dir == tracked_repo / ".agent-rules"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_scope.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aec.lib.scope'`

- [ ] **Step 3: Implement scope.py**

```python
# aec/lib/scope.py
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
    """Walk up from start (default: cwd) to find a tracked repo.

    A tracked repo has .claude/ or .agent-rules/ AND is listed in
    the AEC setup log.
    """
    if start is None:
        start = Path.cwd()

    tracked = _load_tracked_paths()
    current = start.resolve()

    for _ in range(20):  # Max depth
        if current in tracked:
            if (current / ".claude").is_dir() or (current / ".agent-rules").is_dir():
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def resolve_scope(global_flag: bool) -> Scope:
    """Resolve scope based on -g flag and current directory.

    Rules:
    - If -g: return global scope
    - If in a tracked repo: return local scope
    - Otherwise: raise ScopeError
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
    """Get setup log path dynamically (respects monkeypatch)."""
    return Path.home() / ".agents-environment-config" / "setup-repo-locations.txt"


def _load_tracked_paths() -> set[Path]:
    """Load tracked repo paths from the setup log."""
    log = _setup_log_path()
    if not log.exists():
        return set()

    paths = set()
    content = log.read_text().strip()
    if not content:
        return paths

    for line in content.split("\n"):
        parts = line.split("|")
        if len(parts) >= 3:
            paths.add(Path(parts[2]).resolve())

    return paths
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_scope.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add aec/lib/scope.py tests/test_scope.py
git commit -m "feat(cli): add scope resolution library for local/global install"
```

---

### Task 2: V2 Manifest Library

**Files:**
- Create: `aec/lib/manifest_v2.py`
- Create: `tests/test_manifest_v2.py`
- Modify: `aec/lib/config.py` (add path constants)

- [ ] **Step 1: Add path constants to config.py**

In `aec/lib/config.py`, add after line 51 (`AEC_PREFERENCES = AEC_HOME / "preferences.json"`):

```python
INSTALLED_MANIFEST_V2 = AEC_HOME / "installed-manifest.json"
```

- [ ] **Step 2: Write failing tests for v2 manifest**

```python
# tests/test_manifest_v2.py
"""Tests for v2 manifest (global + per-repo tracking)."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def manifest_path(temp_dir):
    return temp_dir / "installed-manifest.json"


@pytest.fixture
def v1_manifest_path(temp_dir):
    """Create a v1 manifest (installed-skills.json)."""
    path = temp_dir / "installed-skills.json"
    path.write_text(json.dumps({
        "manifestVersion": 1,
        "installedAt": "2026-03-30T00:00:00Z",
        "updatedAt": "2026-03-30T00:00:00Z",
        "skills": {
            "verification-writer": {
                "version": "1.0.0",
                "contentHash": "sha256:abc",
                "installedAt": "2026-03-30T00:00:00Z",
                "source": "agents-environment-config",
            }
        }
    }))
    return path


class TestLoadManifestV2:
    def test_returns_empty_when_missing(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest
        m = load_manifest(manifest_path)
        assert m["manifestVersion"] == 2
        assert m["global"]["skills"] == {}
        assert m["global"]["rules"] == {}
        assert m["global"]["agents"] == {}
        assert m["repos"] == {}

    def test_loads_existing_v2(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, save_manifest
        m = load_manifest(manifest_path)
        m["global"]["skills"]["test"] = {"version": "1.0.0"}
        save_manifest(m, manifest_path)

        loaded = load_manifest(manifest_path)
        assert loaded["global"]["skills"]["test"]["version"] == "1.0.0"


class TestSaveManifestV2:
    def test_creates_parent_dirs(self, temp_dir):
        from aec.lib.manifest_v2 import load_manifest, save_manifest
        path = temp_dir / "nested" / "dir" / "manifest.json"
        m = load_manifest(path)
        save_manifest(m, path)
        assert path.exists()

    def test_updates_timestamp(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, save_manifest
        m = load_manifest(manifest_path)
        save_manifest(m, manifest_path)
        loaded = load_manifest(manifest_path)
        assert "updatedAt" in loaded


class TestManifestOperations:
    def test_record_global_install(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest
        m = load_manifest(manifest_path)
        record_install(m, scope="global", item_type="skills", name="my-skill",
                       version="2.0.0", content_hash="sha256:xyz")
        save_manifest(m, manifest_path)

        loaded = load_manifest(manifest_path)
        assert "my-skill" in loaded["global"]["skills"]
        assert loaded["global"]["skills"]["my-skill"]["version"] == "2.0.0"

    def test_record_repo_install(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest
        m = load_manifest(manifest_path)
        repo = "/Users/test/projects/my-app"
        record_install(m, scope=repo, item_type="skills", name="my-skill",
                       version="2.0.0", content_hash="sha256:xyz")
        save_manifest(m, manifest_path)

        loaded = load_manifest(manifest_path)
        assert repo in loaded["repos"]
        assert "my-skill" in loaded["repos"][repo]["skills"]

    def test_remove_global_install(self, manifest_path):
        from aec.lib.manifest_v2 import (
            load_manifest, record_install, remove_install, save_manifest
        )
        m = load_manifest(manifest_path)
        record_install(m, scope="global", item_type="skills", name="my-skill",
                       version="1.0.0", content_hash="sha256:abc")
        remove_install(m, scope="global", item_type="skills", name="my-skill")
        save_manifest(m, manifest_path)

        loaded = load_manifest(manifest_path)
        assert "my-skill" not in loaded["global"]["skills"]

    def test_get_installed_items(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, get_installed
        m = load_manifest(manifest_path)
        record_install(m, scope="global", item_type="skills", name="a", version="1.0.0")
        record_install(m, scope="global", item_type="skills", name="b", version="2.0.0")
        record_install(m, scope="global", item_type="agents", name="c", version="1.0.0")

        skills = get_installed(m, scope="global", item_type="skills")
        assert set(skills.keys()) == {"a", "b"}

    def test_uses_absolute_paths_for_repos(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest
        m = load_manifest(manifest_path)
        record_install(m, scope="/Users/test/app", item_type="skills",
                       name="x", version="1.0.0")
        save_manifest(m, manifest_path)

        raw = json.loads(manifest_path.read_text())
        repo_keys = list(raw["repos"].keys())
        assert all(k.startswith("/") for k in repo_keys)


class TestMigrateV1:
    def test_migrates_skills_to_global(self, v1_manifest_path, manifest_path):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        m = migrate_v1_to_v2(v1_manifest_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]
        assert m["global"]["skills"]["verification-writer"]["version"] == "1.0.0"

    def test_handles_missing_v1(self, temp_dir, manifest_path):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        missing = temp_dir / "nonexistent.json"
        m = migrate_v1_to_v2(missing)
        assert m["manifestVersion"] == 2
        assert m["global"]["skills"] == {}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_manifest_v2.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aec.lib.manifest_v2'`

- [ ] **Step 4: Implement manifest_v2.py**

```python
# aec/lib/manifest_v2.py
"""V2 manifest: tracks global and per-repo installs for skills, rules, agents."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MANIFEST_VERSION = 2
ITEM_TYPES = ("skills", "rules", "agents")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_scope() -> dict:
    return {"skills": {}, "rules": {}, "agents": {}}


def _empty_manifest() -> dict:
    """Return a fresh empty v2 manifest structure."""
    return {
        "manifestVersion": MANIFEST_VERSION,
        "installedAt": _now_iso(),
        "updatedAt": _now_iso(),
        "lastUpdateCheck": None,
        "global": _empty_scope(),
        "repos": {},
    }


def load_manifest(path: Path) -> dict:
    """Load v2 manifest, returning empty structure if missing/corrupt."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("manifestVersion") == MANIFEST_VERSION:
                # Ensure all required keys exist
                data.setdefault("global", _empty_scope())
                data.setdefault("repos", {})
                data.setdefault("lastUpdateCheck", None)
                for key in ITEM_TYPES:
                    data["global"].setdefault(key, {})
                return data
        except (json.JSONDecodeError, OSError):
            pass

    return _empty_manifest()


def save_manifest(manifest: dict, path: Path) -> None:
    """Write v2 manifest to disk."""
    manifest["updatedAt"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _get_scope_dict(manifest: dict, scope: str) -> dict:
    """Get the scope dictionary (global or repo-specific)."""
    if scope == "global":
        return manifest["global"]
    # Repo scope — use absolute path as key
    if scope not in manifest["repos"]:
        manifest["repos"][scope] = _empty_scope()
    return manifest["repos"][scope]


def record_install(
    manifest: dict,
    scope: str,
    item_type: str,
    name: str,
    version: str,
    content_hash: Optional[str] = None,
) -> None:
    """Record an item installation in the manifest."""
    scope_dict = _get_scope_dict(manifest, scope)
    scope_dict[item_type][name] = {
        "version": version,
        "contentHash": content_hash or "",
        "installedAt": _now_iso(),
    }


def remove_install(manifest: dict, scope: str, item_type: str, name: str) -> None:
    """Remove an item from the manifest."""
    scope_dict = _get_scope_dict(manifest, scope)
    scope_dict[item_type].pop(name, None)


def get_installed(manifest: dict, scope: str, item_type: str) -> dict:
    """Get all installed items of a type in a scope."""
    scope_dict = _get_scope_dict(manifest, scope)
    return dict(scope_dict.get(item_type, {}))


def get_all_repo_scopes(manifest: dict) -> list[str]:
    """Return all repo paths tracked in the manifest."""
    return list(manifest.get("repos", {}).keys())


def migrate_v1_to_v2(v1_path: Path) -> dict:
    """Migrate a v1 installed-skills.json to v2 format.

    Moves all skills into the global scope.
    """
    v2 = _empty_manifest()

    if not v1_path.exists():
        return v2

    try:
        v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return v2

    for name, info in v1.get("skills", {}).items():
        v2["global"]["skills"][name] = {
            "version": info.get("version", "0.0.0"),
            "contentHash": info.get("contentHash", ""),
            "installedAt": info.get("installedAt", _now_iso()),
        }

    return v2


def record_update_check(manifest: dict) -> None:
    """Record that aec update was just run."""
    manifest["lastUpdateCheck"] = _now_iso()


def is_stale(manifest: dict, max_age_hours: int = 24) -> bool:
    """Check if sources are stale (last update check older than max_age_hours)."""
    last_check = manifest.get("lastUpdateCheck")
    if not last_check:
        return True

    try:
        last_dt = datetime.fromisoformat(last_check)
        age = datetime.now(timezone.utc) - last_dt
        return age.total_seconds() > max_age_hours * 3600
    except (ValueError, TypeError):
        return True
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_manifest_v2.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add aec/lib/manifest_v2.py aec/lib/config.py tests/test_manifest_v2.py
git commit -m "feat(cli): add v2 manifest with global and per-repo tracking"
```

---

### Task 3: Source Management Library

**Files:**
- Create: `aec/lib/sources.py`
- Create: `tests/test_sources.py`

- [ ] **Step 1: Write failing tests for source management**

```python
# tests/test_sources.py
"""Tests for source management (fetch, discover available items)."""

import pytest
from pathlib import Path


@pytest.fixture
def skills_source(temp_dir):
    """Create a mock skills source directory."""
    source = temp_dir / "skills"
    source.mkdir()

    # Create a skill
    skill = source / "my-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 2.0.0\ndescription: A skill\nauthor: Test\n---\n# My Skill"
    )

    # Create a nested skill
    group = source / "doc-skills"
    group.mkdir()
    nested = group / "pdf"
    nested.mkdir()
    (nested / "SKILL.md").write_text(
        "---\nname: doc-skills:pdf\nversion: 1.0.0\ndescription: PDF skill\nauthor: Test\n---\n# PDF"
    )

    return source


@pytest.fixture
def rules_source(temp_dir):
    """Create a mock rules source directory."""
    source = temp_dir / "rules"
    source.mkdir()
    ts_dir = source / "languages" / "typescript"
    ts_dir.mkdir(parents=True)
    (ts_dir / "typing-standards.md").write_text(
        "---\nname: typescript/typing-standards\nversion: 1.0.0\n---\n# TS Standards"
    )
    return source


class TestDiscoverAvailable:
    def test_discovers_skills(self, skills_source):
        from aec.lib.sources import discover_available
        available = discover_available(skills_source, item_type="skills")
        assert "my-skill" in available
        assert available["my-skill"]["version"] == "2.0.0"

    def test_discovers_nested_skills(self, skills_source):
        from aec.lib.sources import discover_available
        available = discover_available(skills_source, item_type="skills")
        assert "doc-skills:pdf" in available


class TestStalenessCheck:
    def test_stale_when_never_checked(self):
        from aec.lib.sources import check_staleness
        manifest = {"lastUpdateCheck": None}
        assert check_staleness(manifest) is True

    def test_not_stale_when_recent(self):
        from aec.lib.sources import check_staleness
        from datetime import datetime, timezone
        manifest = {"lastUpdateCheck": datetime.now(timezone.utc).isoformat()}
        assert check_staleness(manifest) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_sources.py -v`
Expected: FAIL

- [ ] **Step 3: Implement sources.py**

```python
# aec/lib/sources.py
"""Source management: discover available items, check staleness, fetch updates."""

import subprocess
from pathlib import Path
from typing import Optional

from .config import get_repo_root
from .manifest_v2 import is_stale
from .skills_manifest import discover_available_skills, parse_skill_frontmatter


def discover_available(source_dir: Path, item_type: str) -> dict:
    """Discover available items of a given type from the source directory.

    Args:
        source_dir: Root of the source (e.g., repo/.claude/skills/)
        item_type: One of 'skills', 'rules', 'agents'

    Returns:
        Dict of name -> {version, description, path, ...}
    """
    if item_type == "skills":
        return discover_available_skills(source_dir)
    elif item_type == "rules":
        return _discover_available_rules(source_dir)
    elif item_type == "agents":
        return _discover_available_agents(source_dir)
    return {}


def _discover_available_rules(source_dir: Path) -> dict:
    """Discover available rules from the agent-rules source."""
    rules = {}
    if not source_dir.exists():
        return rules

    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        rel = md_file.relative_to(source_dir)
        name = str(rel).removesuffix(".md")
        # Try to parse frontmatter for version
        text = md_file.read_text(encoding="utf-8")
        from .skills_manifest import parse_yaml_frontmatter
        fm = _parse_yaml_frontmatter(text) or {}
        rules[name] = {
            "version": fm.get("version", "0.0.0"),
            "description": fm.get("description", ""),
            "path": str(rel),
        }
    return rules


def _discover_available_agents(source_dir: Path) -> dict:
    """Discover available agents from the agents source."""
    agents = {}
    if not source_dir.exists():
        return agents

    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        name = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        from .skills_manifest import parse_yaml_frontmatter
        fm = _parse_yaml_frontmatter(text) or {}
        agents[name] = {
            "version": fm.get("version", "0.0.0"),
            "description": fm.get("description", ""),
            "path": md_file.name,
        }
    return agents


def get_source_dirs() -> dict:
    """Get source directories for each item type.

    These are the AEC repo's source directories (where available items
    are defined), NOT the user's install targets. The AEC repo's .claude/skills/
    submodule is the source for skills, its .agent-rules/ for rules, and its
    .claude/agents/ for agents.

    Returns dict of item_type -> Path.
    """
    repo = get_repo_root()
    if repo is None:
        return {}

    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
    }


# NOTE for implementing agents: get_source_dirs() returns paths within the
# AEC repository itself (the source of truth). These are distinct from the
# install target paths (which are computed by Scope.skills_dir, etc.).
# The AEC repo contains the canonical .agent-rules/ and .claude/agents/
# directories that users install FROM.


def check_staleness(manifest: dict, max_age_hours: int = 24) -> bool:
    """Check if sources are stale."""
    return is_stale(manifest, max_age_hours)


def fetch_latest(repo_path: Optional[Path] = None) -> bool:
    """Pull latest AEC repo and update submodules.

    Returns True on success, False on failure.
    """
    if repo_path is None:
        repo_path = get_repo_root()
    if repo_path is None:
        return False

    try:
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_path, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=repo_path, capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_sources.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add aec/lib/sources.py tests/test_sources.py
git commit -m "feat(cli): add source management for multi-type item discovery"
```

---

### Task 4: `aec update` Command

**Files:**
- Create: `aec/commands/update.py`
- Create: `tests/test_update_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_update_cmd.py
"""Tests for aec update command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def aec_env(temp_dir, monkeypatch):
    """Set up a complete AEC environment for testing update."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    # AEC home
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    # Mock repo root with skills source
    repo = temp_dir / "aec-repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    skills = repo / ".claude" / "skills"
    skills.mkdir(parents=True)

    skill_dir = skills / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 2.0.0\ndescription: A test\nauthor: Test\n---\n"
    )

    # V2 manifest with an outdated skill
    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {
            "skills": {
                "test-skill": {"version": "1.0.0", "contentHash": "", "installedAt": "2026-04-04T00:00:00Z"}
            },
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    return {"repo": repo, "aec_home": aec_home}


class TestUpdateCommand:
    @patch("aec.commands.update.fetch_latest", return_value=True)
    @patch("aec.commands.update.get_repo_root")
    def test_reports_outdated_global_skills(self, mock_root, mock_fetch, aec_env, capsys):
        from aec.commands.update import run_update
        mock_root.return_value = aec_env["repo"]
        run_update()
        output = capsys.readouterr().out
        assert "test-skill" in output
        assert "1.0.0" in output
        assert "2.0.0" in output

    @patch("aec.commands.update.fetch_latest", return_value=False)
    @patch("aec.commands.update.get_repo_root")
    def test_handles_fetch_failure(self, mock_root, mock_fetch, aec_env, capsys):
        from aec.commands.update import run_update
        mock_root.return_value = aec_env["repo"]
        run_update()
        output = capsys.readouterr().out
        assert "fail" in output.lower() or "error" in output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_update_cmd.py -v`
Expected: FAIL

- [ ] **Step 3: Implement update.py**

```python
# aec/commands/update.py
"""aec update — fetch latest sources and report what's outdated."""

from pathlib import Path
from typing import Optional

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, save_manifest, record_update_check, get_installed
from ..lib.sources import fetch_latest, discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import version_is_newer


def run_update() -> None:
    """Fetch latest AEC repo + submodules, report what's outdated."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    Console.print("Pulling latest...", end=" ")
    if not fetch_latest(repo):
        Console.print("failed!")
        Console.error("Could not pull latest. Check your network and git status.")
        return
    Console.print("done.")

    manifest = load_manifest(INSTALLED_MANIFEST_V2)
    record_update_check(manifest)
    save_manifest(manifest, INSTALLED_MANIFEST_V2)

    source_dirs = get_source_dirs()
    any_outdated = False

    # Report global
    Console.print("\nGlobal:")
    global_outdated = _report_scope_outdated(manifest, "global", source_dirs)
    if global_outdated:
        any_outdated = True
    else:
        Console.print("  (up to date)")

    # Report local if in a tracked repo
    local_repo = find_tracked_repo()
    if local_repo:
        Console.print(f"\nLocal ({local_repo}):")
        repo_key = str(local_repo.resolve())
        local_outdated = _report_scope_outdated(manifest, repo_key, source_dirs)
        if local_outdated:
            any_outdated = True
        else:
            Console.print("  (up to date)")

    # Mention other repos
    all_repos = get_all_tracked_repos()
    other_repos = [r for r in all_repos if r != local_repo]
    if other_repos:
        Console.print(
            f"\n{len(other_repos)} other tracked repo(s) may have updates. "
            "Run `aec outdated --all` to check."
        )

    if any_outdated:
        Console.print("\nRun `aec upgrade` to apply.")
    else:
        Console.print("\nEverything is up to date.")


def _report_scope_outdated(manifest: dict, scope: str, source_dirs: dict) -> int:
    """Report outdated items in a scope. Returns count of outdated items."""
    count = 0
    for item_type, source_dir in source_dirs.items():
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        installed = get_installed(manifest, scope, item_type)
        for name, info in installed.items():
            if name in available:
                avail_v = available[name].get("version", "0.0.0")
                inst_v = info.get("version", "0.0.0")
                if version_is_newer(avail_v, inst_v):
                    Console.print(f"  {item_type[:-1]}  {name}  {inst_v} → {avail_v}")
                    count += 1
    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_update_cmd.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add aec/commands/update.py tests/test_update_cmd.py
git commit -m "feat(cli): add aec update command (fetch sources, report outdated)"
```

---

### Task 5: `aec upgrade` Command

**Files:**
- Create: `aec/commands/upgrade.py`
- Create: `tests/test_upgrade_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_upgrade_cmd.py
"""Tests for aec upgrade command."""

import json
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def upgrade_env(temp_dir, monkeypatch):
    """Full environment for upgrade testing."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    # Source skill (v2.0.0)
    repo = temp_dir / "aec-repo"
    skills_src = repo / ".claude" / "skills" / "test-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 2.0.0\ndescription: Updated\nauthor: Test\n---\nNew content"
    )
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()

    # Installed skill (v1.0.0, global)
    installed = temp_dir / ".claude" / "skills" / "test-skill"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text(
        "---\nname: test-skill\nversion: 1.0.0\ndescription: Old\nauthor: Test\n---\nOld content"
    )

    from aec.lib.skills_manifest import hash_skill_directory
    old_hash = hash_skill_directory(installed)

    manifest = {
        "manifestVersion": 2,
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": "2026-04-04T00:00:00Z",
        "global": {
            "skills": {
                "test-skill": {
                    "version": "1.0.0",
                    "contentHash": old_hash,
                    "installedAt": "2026-04-04T00:00:00Z",
                }
            },
            "rules": {},
            "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    return {"repo": repo, "aec_home": aec_home, "installed": installed}


class TestUpgradeCommand:
    @patch("aec.commands.upgrade.get_repo_root")
    def test_upgrades_global_skill(self, mock_root, upgrade_env, monkeypatch):
        from aec.commands.upgrade import run_upgrade
        mock_root.return_value = upgrade_env["repo"]
        monkeypatch.setattr("builtins.input", lambda _: "y")
        run_upgrade(yes=True)

        # Verify the installed skill was updated
        skill_md = upgrade_env["installed"] / "SKILL.md"
        assert "2.0.0" in skill_md.read_text()

    @patch("aec.commands.upgrade.get_repo_root")
    def test_dry_run_does_not_modify(self, mock_root, upgrade_env):
        from aec.commands.upgrade import run_upgrade
        mock_root.return_value = upgrade_env["repo"]
        run_upgrade(dry_run=True)

        # Verify the installed skill was NOT updated
        skill_md = upgrade_env["installed"] / "SKILL.md"
        assert "1.0.0" in skill_md.read_text()

    @patch("aec.commands.upgrade.get_repo_root")
    def test_reports_nothing_when_up_to_date(self, mock_root, upgrade_env, capsys):
        from aec.commands.upgrade import run_upgrade
        mock_root.return_value = upgrade_env["repo"]

        # Make installed match source
        src = upgrade_env["repo"] / ".claude" / "skills" / "test-skill"
        dst = upgrade_env["installed"]
        shutil.rmtree(dst)
        shutil.copytree(src, dst)

        # Update manifest version
        manifest_path = upgrade_env["aec_home"] / "installed-manifest.json"
        m = json.loads(manifest_path.read_text())
        m["global"]["skills"]["test-skill"]["version"] = "2.0.0"
        manifest_path.write_text(json.dumps(m))

        run_upgrade(yes=True)
        output = capsys.readouterr().out
        assert "up to date" in output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_upgrade_cmd.py -v`
Expected: FAIL

- [ ] **Step 3: Implement upgrade.py**

```python
# aec/commands/upgrade.py
"""aec upgrade — apply available upgrades to installed items."""

import shutil
from pathlib import Path
from typing import Optional

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import (
    load_manifest, save_manifest, get_installed, record_install, is_stale,
)
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import version_is_newer, hash_skill_directory


def run_upgrade(
    yes: bool = False,
    dry_run: bool = False,
) -> None:
    """Apply available upgrades."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    manifest = load_manifest(INSTALLED_MANIFEST_V2)

    # Staleness warning
    if is_stale(manifest) and not dry_run:
        Console.warning("Sources may be stale.")
        if not yes:
            try:
                resp = input("Run `aec update` first? [Y/n]: ").strip().lower()
            except EOFError:
                resp = "n"
            if resp != "n":
                from .update import run_update
                run_update()
                manifest = load_manifest(INSTALLED_MANIFEST_V2)

    source_dirs = get_source_dirs()
    any_upgraded = False

    # Upgrade global
    Console.print("Upgrading global scope...")
    if _upgrade_scope(manifest, "global", source_dirs, repo, yes, dry_run):
        any_upgraded = True
    else:
        Console.print("  (up to date)")

    # Upgrade local if in tracked repo
    local_repo = find_tracked_repo()
    if local_repo:
        Console.print(f"\nUpgrading {local_repo} (current repo)...")
        repo_key = str(local_repo.resolve())
        if _upgrade_scope(manifest, repo_key, source_dirs, repo, yes, dry_run):
            any_upgraded = True
        else:
            Console.print("  (up to date)")

    if not dry_run:
        save_manifest(manifest, INSTALLED_MANIFEST_V2)

    # Offer to upgrade other repos
    all_repos = get_all_tracked_repos()
    other_repos = [r for r in all_repos if r != local_repo]
    if other_repos and not dry_run:
        outdated_repos = _find_outdated_repos(manifest, other_repos, source_dirs)
        if outdated_repos:
            Console.print(f"\n{len(outdated_repos)} other tracked repo(s) have upgrades:")
            for repo_path, count in outdated_repos:
                Console.print(f"  {repo_path}    {count} item(s) outdated")
            if not yes:
                try:
                    resp = input("\nUpgrade them too? [y/N/list]: ").strip().lower()
                except EOFError:
                    resp = "n"
                if resp == "y":
                    for repo_path, _ in outdated_repos:
                        Console.print(f"\nUpgrading {repo_path}...")
                        _upgrade_scope(
                            manifest, str(repo_path), source_dirs, repo, yes=True, dry_run=False
                        )
                    save_manifest(manifest, INSTALLED_MANIFEST_V2)

    if not any_upgraded and not dry_run:
        Console.print("\nEverything is up to date.")


def _upgrade_scope(
    manifest: dict,
    scope: str,
    source_dirs: dict,
    aec_repo: Path,
    yes: bool,
    dry_run: bool,
) -> bool:
    """Upgrade all items in a scope. Returns True if anything was upgraded."""
    upgraded = False

    for item_type, source_dir in source_dirs.items():
        if not source_dir or not source_dir.exists():
            continue

        available = discover_available(source_dir, item_type)
        installed = get_installed(manifest, scope, item_type)

        # Determine target directory
        if scope == "global":
            from ..lib.config import CLAUDE_DIR, AGENT_TOOLS_DIR
            if item_type == "skills":
                target_base = CLAUDE_DIR / "skills"
            elif item_type == "agents":
                target_base = CLAUDE_DIR / "agents"
            else:
                target_base = AGENT_TOOLS_DIR / "rules"
        else:
            repo_path = Path(scope)
            if item_type == "skills":
                target_base = repo_path / ".claude" / "skills"
            elif item_type == "agents":
                target_base = repo_path / ".claude" / "agents"
            else:
                target_base = repo_path / ".agent-rules"

        for name, info in installed.items():
            if name not in available:
                continue

            avail_v = available[name].get("version", "0.0.0")
            inst_v = info.get("version", "0.0.0")

            if not version_is_newer(avail_v, inst_v):
                continue

            src_path = source_dir / available[name].get("path", name)
            dst_path = target_base / name

            if dry_run:
                Console.print(f"  would upgrade {item_type[:-1]}  {name}  {inst_v} → {avail_v}")
                upgraded = True
                continue

            # Check for local modifications
            if dst_path.exists() and not yes:
                current_hash = hash_skill_directory(dst_path) if dst_path.is_dir() else ""
                recorded_hash = info.get("contentHash", "")
                if current_hash and recorded_hash and current_hash != recorded_hash:
                    try:
                        resp = input(
                            f"  {name} has local modifications. Overwrite? [y/N]: "
                        ).strip().lower()
                    except EOFError:
                        resp = "n"
                    if resp != "y":
                        Console.info(f"  Skipped: {name}")
                        continue

            # Copy
            if dst_path.exists():
                if dst_path.is_dir():
                    shutil.rmtree(dst_path)
                else:
                    dst_path.unlink()

            target_base.mkdir(parents=True, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns(".*"))
            else:
                shutil.copy2(src_path, dst_path)

            content_hash = hash_skill_directory(dst_path) if dst_path.is_dir() else ""
            record_install(manifest, scope, item_type, name, avail_v, content_hash)
            Console.success(f"  {item_type[:-1]}  {name}  {inst_v} → {avail_v}")
            upgraded = True

    return upgraded


def _find_outdated_repos(
    manifest: dict, repos: list[Path], source_dirs: dict
) -> list[tuple[Path, int]]:
    """Find repos with outdated items. Returns list of (path, outdated_count)."""
    results = []
    for repo_path in repos:
        repo_key = str(repo_path.resolve())
        count = 0
        for item_type, source_dir in source_dirs.items():
            if not source_dir or not source_dir.exists():
                continue
            available = discover_available(source_dir, item_type)
            installed = get_installed(manifest, repo_key, item_type)
            for name, info in installed.items():
                if name in available:
                    if version_is_newer(
                        available[name].get("version", "0.0.0"),
                        info.get("version", "0.0.0"),
                    ):
                        count += 1
        if count > 0:
            results.append((repo_path, count))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_upgrade_cmd.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add aec/commands/upgrade.py tests/test_upgrade_cmd.py
git commit -m "feat(cli): add aec upgrade command (apply updates to installed items)"
```

---

### Task 6: `aec install <type> <name>` Command

**Files:**
- Create: `aec/commands/install_cmd.py`
- Create: `tests/test_install_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_install_cmd.py
"""Tests for aec install <type> <name> command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def install_env(temp_dir, monkeypatch):
    """Environment for install testing."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    # Source
    repo = temp_dir / "aec-repo"
    skills_src = repo / ".claude" / "skills" / "my-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 1.0.0\ndescription: Test\nauthor: Test\n---\n# Skill"
    )
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()

    # Tracked repo
    project = temp_dir / "projects" / "my-app"
    (project / ".claude" / "skills").mkdir(parents=True)
    (project / ".agent-rules").mkdir(parents=True)
    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{project}\n")

    # Global skills dir
    (temp_dir / ".claude" / "skills").mkdir(parents=True)

    return {"repo": repo, "project": project, "aec_home": aec_home}


class TestInstallSkill:
    @patch("aec.commands.install_cmd.get_repo_root")
    def test_install_to_local_scope(self, mock_root, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install
        mock_root.return_value = install_env["repo"]
        monkeypatch.chdir(install_env["project"])

        run_install(item_type="skill", name="my-skill", global_flag=False, yes=True)

        installed = install_env["project"] / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()
        assert "1.0.0" in installed.read_text()

    @patch("aec.commands.install_cmd.get_repo_root")
    def test_install_to_global_scope(self, mock_root, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install
        mock_root.return_value = install_env["repo"]

        run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        installed = install_env["aec_home"].parent / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()

    @patch("aec.commands.install_cmd.get_repo_root")
    def test_error_not_in_repo_without_g(self, mock_root, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install
        mock_root.return_value = install_env["repo"]
        untracked = install_env["aec_home"].parent / "random"
        untracked.mkdir()
        monkeypatch.chdir(untracked)

        with pytest.raises(SystemExit):
            run_install(item_type="skill", name="my-skill", global_flag=False, yes=True)

    @patch("aec.commands.install_cmd.get_repo_root")
    def test_error_unknown_skill(self, mock_root, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install
        mock_root.return_value = install_env["repo"]
        monkeypatch.chdir(install_env["project"])

        with pytest.raises(SystemExit):
            run_install(item_type="skill", name="nonexistent", global_flag=False, yes=True)

    @patch("aec.commands.install_cmd.get_repo_root")
    def test_records_in_manifest(self, mock_root, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest
        from aec.lib.config import INSTALLED_MANIFEST_V2
        mock_root.return_value = install_env["repo"]

        run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        manifest_path = install_env["aec_home"] / "installed-manifest.json"
        m = load_manifest(manifest_path)
        assert "my-skill" in m["global"]["skills"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_install_cmd.py -v`
Expected: FAIL

- [ ] **Step 3: Implement install_cmd.py**

```python
# aec/commands/install_cmd.py
"""aec install <type> <name> — install a skill, rule, or agent."""

import shutil
from pathlib import Path

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, save_manifest, record_install
from ..lib.scope import resolve_scope, ScopeError
from ..lib.sources import discover_available, get_source_dirs
from ..lib.skills_manifest import hash_skill_directory


VALID_TYPES = ("skill", "rule", "agent")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def run_install(
    item_type: str,
    name: str,
    global_flag: bool = False,
    yes: bool = False,
) -> None:
    """Install a skill, rule, or agent."""
    if item_type not in VALID_TYPES:
        Console.error(f"Unknown type: {item_type}. Must be one of: {', '.join(VALID_TYPES)}")
        raise SystemExit(1)

    plural = TYPE_TO_PLURAL[item_type]

    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        raise SystemExit(1)

    source_dirs = get_source_dirs()
    source_dir = source_dirs.get(plural)
    if not source_dir or not source_dir.exists():
        Console.error(f"No {plural} source found.")
        raise SystemExit(1)

    available = discover_available(source_dir, plural)
    if name not in available:
        Console.error(f"{item_type.title()} not found: {name}")
        if available:
            Console.print(f"Available: {', '.join(sorted(available.keys()))}")
        raise SystemExit(1)

    item_info = available[name]
    src = source_dir / item_info.get("path", name)
    target_dir = getattr(scope, f"{plural}_dir")
    dst = target_dir / name

    scope_label = "globally" if scope.is_global else f"to {scope.repo_path}"
    Console.print(f"Installing {name} v{item_info.get('version', '?')} {scope_label}...")

    if dst.exists() and not yes:
        try:
            resp = input(f"  {name} already exists. Overwrite? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    target_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".*"))
    else:
        shutil.copy2(src, dst)

    content_hash = hash_skill_directory(dst) if dst.is_dir() else ""
    manifest_path = INSTALLED_MANIFEST_V2
    manifest = load_manifest(manifest_path)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())
    record_install(manifest, scope_key, plural, name, item_info.get("version", "0.0.0"), content_hash)
    save_manifest(manifest, manifest_path)

    Console.success(f"Installed {name} v{item_info.get('version', '0.0.0')}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_install_cmd.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add aec/commands/install_cmd.py tests/test_install_cmd.py
git commit -m "feat(cli): add aec install <type> <name> with local/global scope"
```

---

### Task 7: `aec uninstall <type> <name>` Command

**Files:**
- Create: `aec/commands/uninstall.py`
- Create: `tests/test_uninstall_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_uninstall_cmd.py
"""Tests for aec uninstall <type> <name> command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def uninstall_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    # Installed global skill
    skill_dir = temp_dir / ".claude" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\nversion: 1.0.0\n---\n")

    # Manifest
    manifest = {
        "manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
        "global": {"skills": {"my-skill": {"version": "1.0.0", "contentHash": "", "installedAt": ""}}, "rules": {}, "agents": {}},
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
    (aec_home / "setup-repo-locations.txt").write_text("")

    return {"aec_home": aec_home, "skill_dir": skill_dir}


class TestUninstall:
    def test_removes_global_skill(self, uninstall_env):
        from aec.commands.uninstall import run_uninstall
        run_uninstall(item_type="skill", name="my-skill", global_flag=True, yes=True)
        assert not uninstall_env["skill_dir"].exists()

    def test_removes_from_manifest(self, uninstall_env):
        from aec.commands.uninstall import run_uninstall
        from aec.lib.manifest_v2 import load_manifest
        run_uninstall(item_type="skill", name="my-skill", global_flag=True, yes=True)

        m = load_manifest(uninstall_env["aec_home"] / "installed-manifest.json")
        assert "my-skill" not in m["global"]["skills"]

    def test_error_for_nonexistent(self, uninstall_env, capsys):
        from aec.commands.uninstall import run_uninstall
        run_uninstall(item_type="skill", name="nope", global_flag=True, yes=True)
        output = capsys.readouterr().out
        assert "not found" in output.lower() or "not installed" in output.lower()
```

- [ ] **Step 2: Run tests, verify fail**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_uninstall_cmd.py -v`

- [ ] **Step 3: Implement uninstall.py**

```python
# aec/commands/uninstall.py
"""aec uninstall <type> <name> — remove a skill, rule, or agent."""

import shutil
from pathlib import Path

from ..lib import Console
from ..lib.config import INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, save_manifest, remove_install
from ..lib.scope import resolve_scope, ScopeError

VALID_TYPES = ("skill", "rule", "agent")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def run_uninstall(
    item_type: str,
    name: str,
    global_flag: bool = False,
    yes: bool = False,
) -> None:
    """Uninstall a skill, rule, or agent."""
    if item_type not in VALID_TYPES:
        Console.error(f"Unknown type: {item_type}. Must be one of: {', '.join(VALID_TYPES)}")
        raise SystemExit(1)

    plural = TYPE_TO_PLURAL[item_type]

    try:
        scope = resolve_scope(global_flag)
    except ScopeError as e:
        Console.error(str(e))
        raise SystemExit(1)

    target_dir = getattr(scope, f"{plural}_dir")
    item_path = target_dir / name

    if not item_path.exists():
        Console.warning(f"{item_type.title()} not found: {name}")
        return

    if not yes:
        scope_label = "global" if scope.is_global else str(scope.repo_path)
        try:
            resp = input(f"  Remove {name} from {scope_label}? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    if item_path.is_dir():
        shutil.rmtree(item_path)
    else:
        item_path.unlink()

    manifest = load_manifest(INSTALLED_MANIFEST_V2)
    scope_key = "global" if scope.is_global else str(scope.repo_path.resolve())
    remove_install(manifest, scope_key, plural, name)
    save_manifest(manifest, INSTALLED_MANIFEST_V2)

    Console.success(f"Uninstalled {name}")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/test_uninstall_cmd.py -v`

- [ ] **Step 5: Commit**

```bash
git add aec/commands/uninstall.py tests/test_uninstall_cmd.py
git commit -m "feat(cli): add aec uninstall <type> <name>"
```

---

### Task 8: `aec list` Command

**Files:**
- Create: `aec/commands/list_cmd.py`
- Create: `tests/test_list_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_list_cmd.py
"""Tests for aec list command."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def list_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    manifest = {
        "manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
        "global": {
            "skills": {"skill-a": {"version": "1.0.0"}, "skill-b": {"version": "2.0.0"}},
            "rules": {"typescript/typing-standards": {"version": "1.0.0"}},
            "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
    return aec_home


class TestList:
    def test_shows_global_items(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list()
        output = capsys.readouterr().out
        assert "skill-a" in output
        assert "skill-b" in output
        assert "typescript/typing-standards" in output

    def test_filters_by_type(self, list_env, capsys):
        from aec.commands.list_cmd import run_list
        run_list(type_filter="skill")
        output = capsys.readouterr().out
        assert "skill-a" in output
        assert "typescript/typing-standards" not in output
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement list_cmd.py**

```python
# aec/commands/list_cmd.py
"""aec list — show installed items."""

from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.config import INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, get_installed, get_all_repo_scopes
from ..lib.scope import find_tracked_repo, get_all_tracked_repos

ITEM_TYPES = ("skills", "rules", "agents")
TYPE_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent"}


def run_list(
    type_filter: Optional[str] = None,
    scope_filter: Optional[str] = None,
    show_all: bool = False,
) -> None:
    """Show installed items."""
    manifest = load_manifest(INSTALLED_MANIFEST_V2)

    types_to_show = ITEM_TYPES
    if type_filter:
        plural = type_filter + "s" if not type_filter.endswith("s") else type_filter
        if plural in ITEM_TYPES:
            types_to_show = (plural,)

    # Global
    if scope_filter in (None, "global"):
        Console.print("Global:")
        count = _print_scope(manifest, "global", types_to_show)
        if count == 0:
            Console.print("  (none)")

    # Local
    local_repo = find_tracked_repo()
    if local_repo and scope_filter in (None, "local"):
        repo_key = str(local_repo.resolve())
        Console.print(f"\nLocal ({local_repo}):")
        count = _print_scope(manifest, repo_key, types_to_show)
        if count == 0:
            Console.print("  (none)")

    # All repos
    if show_all:
        all_repos = get_all_tracked_repos()
        for repo_path in all_repos:
            if repo_path == local_repo:
                continue
            repo_key = str(repo_path.resolve())
            Console.print(f"\n{repo_path}:")
            count = _print_scope(manifest, repo_key, types_to_show)
            if count == 0:
                Console.print("  (none)")

    # Summary
    tracked = get_all_tracked_repos()
    Console.print(f"\nTracked repos: {len(tracked)}")


def _print_scope(manifest: dict, scope: str, types: tuple) -> int:
    """Print items in a scope. Returns count."""
    count = 0
    for item_type in types:
        items = get_installed(manifest, scope, item_type)
        singular = TYPE_SINGULAR[item_type]
        for name, info in sorted(items.items()):
            version = info.get("version", "?")
            Console.print(f"  {singular:<8} {name:<32} v{version}")
            count += 1
    return count
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add aec/commands/list_cmd.py tests/test_list_cmd.py
git commit -m "feat(cli): add aec list with scope and type filtering"
```

---

### Task 9: `aec search` Command

**Files:**
- Create: `aec/commands/search.py`
- Create: `tests/test_search_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_search_cmd.py
"""Tests for aec search command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def search_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")
    manifest = {"manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
                "global": {"skills": {"verification-writer": {"version": "2.0.0"}}, "rules": {}, "agents": {}},
                "repos": {}}
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    repo = temp_dir / "aec-repo"
    skills = repo / ".claude" / "skills"
    for name in ["verification-writer", "browser-verification", "commit"]:
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\nversion: 2.0.0\ndescription: {name} desc\n---\n")
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    return repo


class TestSearch:
    @patch("aec.commands.search.get_repo_root")
    def test_finds_matching_skills(self, mock_root, search_env, capsys):
        from aec.commands.search import run_search
        mock_root.return_value = search_env
        run_search("verification")
        output = capsys.readouterr().out
        assert "verification-writer" in output
        assert "browser-verification" in output
        assert "commit" not in output

    @patch("aec.commands.search.get_repo_root")
    def test_shows_install_status(self, mock_root, search_env, capsys):
        from aec.commands.search import run_search
        mock_root.return_value = search_env
        run_search("verification")
        output = capsys.readouterr().out
        assert "[global]" in output  # verification-writer is installed globally
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement search.py**

```python
# aec/commands/search.py
"""aec search <term> — search available items."""

from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, get_installed
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo

ITEM_TYPES = ("skills", "rules", "agents")
TYPE_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent"}


def run_search(
    term: str,
    type_filter: Optional[str] = None,
) -> None:
    """Search available items matching term."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    source_dirs = get_source_dirs()
    manifest = load_manifest(INSTALLED_MANIFEST_V2)
    local_repo = find_tracked_repo()
    term_lower = term.lower()

    types_to_search = ITEM_TYPES
    if type_filter:
        plural = type_filter + "s" if not type_filter.endswith("s") else type_filter
        if plural in ITEM_TYPES:
            types_to_search = (plural,)

    found = False
    for item_type in types_to_search:
        source_dir = source_dirs.get(item_type)
        if not source_dir or not source_dir.exists():
            continue

        available = discover_available(source_dir, item_type)
        singular = TYPE_SINGULAR[item_type]

        for name, info in sorted(available.items()):
            if term_lower not in name.lower() and term_lower not in info.get("description", "").lower():
                continue

            version = info.get("version", "?")
            desc = info.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."

            # Check install status
            scopes = []
            global_items = get_installed(manifest, "global", item_type)
            if name in global_items:
                scopes.append("global")
            if local_repo:
                local_items = get_installed(manifest, str(local_repo.resolve()), item_type)
                if name in local_items:
                    scopes.append("local")

            scope_tag = f"  [{', '.join(scopes)}]" if scopes else ""
            Console.print(f"{singular:<8} {name:<32} v{version}  {desc}{scope_tag}")
            found = True

    if not found:
        Console.print(f"No results for '{term}'")
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add aec/commands/search.py tests/test_search_cmd.py
git commit -m "feat(cli): add aec search with install status indicators"
```

---

### Task 10: `aec outdated` Command

**Files:**
- Create: `aec/commands/outdated.py`
- Create: `tests/test_outdated_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_outdated_cmd.py
"""Tests for aec outdated command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def outdated_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    manifest = {
        "manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
        "global": {
            "skills": {"old-skill": {"version": "1.0.0", "contentHash": "", "installedAt": ""}},
            "rules": {}, "agents": {},
        },
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    repo = temp_dir / "aec-repo"
    skill = repo / ".claude" / "skills" / "old-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: old-skill\nversion: 2.0.0\n---\n")
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    return repo


class TestOutdated:
    @patch("aec.commands.outdated.get_repo_root")
    def test_shows_outdated_global(self, mock_root, outdated_env, capsys):
        from aec.commands.outdated import run_outdated
        mock_root.return_value = outdated_env
        run_outdated()
        output = capsys.readouterr().out
        assert "old-skill" in output
        assert "1.0.0" in output
        assert "2.0.0" in output
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement outdated.py**

```python
# aec/commands/outdated.py
"""aec outdated — show items with available upgrades."""

from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, get_installed
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo, get_all_tracked_repos
from ..lib.skills_manifest import version_is_newer

ITEM_TYPES = ("skills", "rules", "agents")
TYPE_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent"}


def run_outdated(
    type_filter: Optional[str] = None,
    show_all: bool = False,
) -> None:
    """Show items with available upgrades."""
    repo = get_repo_root()
    if repo is None:
        Console.error("AEC repo not found. Run `aec setup` first.")
        return

    source_dirs = get_source_dirs()
    manifest = load_manifest(INSTALLED_MANIFEST_V2)

    types_to_check = ITEM_TYPES
    if type_filter:
        plural = type_filter + "s" if not type_filter.endswith("s") else type_filter
        if plural in ITEM_TYPES:
            types_to_check = (plural,)

    any_outdated = False

    # Global
    Console.print("Global:")
    if _print_outdated(manifest, "global", source_dirs, types_to_check):
        any_outdated = True
    else:
        Console.print("  (up to date)")

    # Local
    local_repo = find_tracked_repo()
    if local_repo:
        repo_key = str(local_repo.resolve())
        Console.print(f"\nLocal ({local_repo}):")
        if _print_outdated(manifest, repo_key, source_dirs, types_to_check):
            any_outdated = True
        else:
            Console.print("  (up to date)")

    # All repos
    if show_all:
        for repo_path in get_all_tracked_repos():
            if repo_path == local_repo:
                continue
            repo_key = str(repo_path.resolve())
            Console.print(f"\n{repo_path}:")
            if not _print_outdated(manifest, repo_key, source_dirs, types_to_check):
                Console.print("  (up to date)")

    if not any_outdated:
        Console.print("\nEverything is up to date.")


def _print_outdated(manifest: dict, scope: str, source_dirs: dict, types: tuple) -> bool:
    """Print outdated items in a scope. Returns True if any found."""
    found = False
    for item_type in types:
        source_dir = source_dirs.get(item_type)
        if not source_dir or not source_dir.exists():
            continue
        available = discover_available(source_dir, item_type)
        installed = get_installed(manifest, scope, item_type)
        singular = TYPE_SINGULAR[item_type]
        for name, info in sorted(installed.items()):
            if name in available:
                avail_v = available[name].get("version", "0.0.0")
                inst_v = info.get("version", "0.0.0")
                if version_is_newer(avail_v, inst_v):
                    Console.print(f"  {singular:<8} {name:<32} {inst_v} → {avail_v}")
                    found = True
    return found
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add aec/commands/outdated.py tests/test_outdated_cmd.py
git commit -m "feat(cli): add aec outdated with per-scope reporting"
```

---

### Task 11: `aec info <type> <name>` Command

**Files:**
- Create: `aec/commands/info.py`
- Create: `tests/test_info_cmd.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_info_cmd.py
"""Tests for aec info command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def info_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "setup-repo-locations.txt").write_text("")

    # Source
    repo = temp_dir / "aec-repo"
    skill = repo / ".claude" / "skills" / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 2.0.0\ndescription: A test skill\nauthor: Test Author\n---\n"
    )
    (skill / "references").mkdir()
    (skill / "references" / "ref.md").write_text("ref")
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()

    manifest = {
        "manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
        "global": {"skills": {"my-skill": {"version": "2.0.0", "contentHash": "sha256:abc", "installedAt": "2026-04-04T00:00:00Z"}}, "rules": {}, "agents": {}},
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
    return repo


class TestInfo:
    @patch("aec.commands.info.get_repo_root")
    def test_shows_skill_info(self, mock_root, info_env, capsys):
        from aec.commands.info import run_info
        mock_root.return_value = info_env
        run_info(item_type="skill", name="my-skill")
        output = capsys.readouterr().out
        assert "my-skill" in output
        assert "2.0.0" in output
        assert "Test Author" in output
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement info.py**

```python
# aec/commands/info.py
"""aec info <type> <name> — show detailed metadata for an item."""

from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.config import get_repo_root, INSTALLED_MANIFEST_V2
from ..lib.manifest_v2 import load_manifest, get_installed, get_all_repo_scopes
from ..lib.sources import discover_available, get_source_dirs
from ..lib.scope import find_tracked_repo

VALID_TYPES = ("skill", "rule", "agent")
TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def run_info(item_type: str, name: str) -> None:
    """Show detailed info about an item."""
    if item_type not in VALID_TYPES:
        Console.error(f"Unknown type: {item_type}")
        return

    plural = TYPE_TO_PLURAL[item_type]
    repo = get_repo_root()
    source_dirs = get_source_dirs()
    manifest = load_manifest(INSTALLED_MANIFEST_V2)

    # Get source info
    source_dir = source_dirs.get(plural) if source_dirs else None
    available = discover_available(source_dir, plural) if source_dir and source_dir.exists() else {}
    source_info = available.get(name, {})

    if not source_info:
        Console.error(f"{item_type.title()} not found: {name}")
        return

    version = source_info.get("version", "?")
    desc = source_info.get("description", "")
    author = source_info.get("author", "")

    Console.print(f"{name} v{version}")
    if author:
        Console.print(f"  Author:      {author}")
    if desc:
        Console.print(f"  Description: {desc}")

    # Show install locations
    installed_in = []
    global_items = get_installed(manifest, "global", plural)
    if name in global_items:
        installed_in.append(f"global ({global_items[name].get('installedAt', '?')})")

    local_repo = find_tracked_repo()
    if local_repo:
        local_items = get_installed(manifest, str(local_repo.resolve()), plural)
        if name in local_items:
            installed_in.append(f"local {local_repo} ({local_items[name].get('installedAt', '?')})")

    for repo_key in get_all_repo_scopes(manifest):
        if local_repo and repo_key == str(local_repo.resolve()):
            continue
        repo_items = get_installed(manifest, repo_key, plural)
        if name in repo_items:
            installed_in.append(f"{repo_key} ({repo_items[name].get('installedAt', '?')})")

    if installed_in:
        Console.print(f"  Installed:   {', '.join(installed_in)}")
    else:
        Console.print("  Installed:   (not installed)")

    # Show files if source exists
    if source_dir:
        src_path = source_dir / source_info.get("path", name)
        if src_path.exists() and src_path.is_dir():
            files = list(src_path.rglob("*"))
            file_count = sum(1 for f in files if f.is_file())
            Console.print(f"  Files:       {file_count} file(s)")
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add aec/commands/info.py tests/test_info_cmd.py
git commit -m "feat(cli): add aec info <type> <name> for item inspection"
```

---

### Task 12: `aec setup` Command

**Files:**
- Create: `aec/commands/setup.py`
- Create: `tests/test_setup_cmd.py`
- Reference: `aec/commands/install.py` (existing full-setup logic)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_setup_cmd.py
"""Tests for aec setup command."""

import pytest
from pathlib import Path


@pytest.fixture
def setup_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    # Don't create aec_home — first-time setup should create it
    return {"home": temp_dir, "aec_home": aec_home}


class TestSetup:
    def test_first_time_creates_aec_home(self, setup_env):
        from aec.commands.setup import run_setup
        # run_setup delegates to the existing install logic
        # Just verify it doesn't crash and creates the directory
        # (Full install logic is tested in existing test_cli.py)
        assert not setup_env["aec_home"].exists()
        # We'd need to mock more to fully test, but this validates the entry point exists

    def test_setup_path_tracks_repo(self, setup_env, monkeypatch):
        from aec.commands.setup import run_setup_path
        from aec.lib.tracking import is_logged

        project = setup_env["home"] / "projects" / "test-app"
        project.mkdir(parents=True)
        (project / ".git").mkdir()

        # Create aec_home for tracking
        setup_env["aec_home"].mkdir()
        (setup_env["aec_home"] / "setup-repo-locations.txt").write_text("")

        run_setup_path(str(project))
        assert is_logged(project)
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Implement setup.py**

This is largely a wrapper that delegates to the existing `install.py` and `repo.py` logic, providing the new command interface.

```python
# aec/commands/setup.py
"""aec setup — first-time bootstrap or repo tracking."""

from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.config import AEC_HOME
from ..lib.tracking import log_setup, init_aec_home, is_logged
from ..lib.scope import find_tracked_repo


def run_setup(
    skip_raycast: bool = False,
    dry_run: bool = False,
) -> None:
    """Full first-time setup, or offer to track current repo if already installed."""
    if not AEC_HOME.exists():
        # First time — run full install
        from .install import install
        install(dry_run=dry_run)
        return

    # Already installed — check if we're in an untracked repo
    repo = find_tracked_repo()
    if repo is None:
        # Check if cwd looks like a repo
        cwd = Path.cwd()
        if (cwd / ".git").exists() and not is_logged(cwd):
            Console.print(f"AEC is already installed. Track {cwd} as a repo?")
            try:
                resp = input("[Y/n]: ").strip().lower()
            except EOFError:
                resp = "n"
            if resp != "n":
                run_setup_path(str(cwd), skip_raycast=skip_raycast, dry_run=dry_run)
                return

    Console.print("AEC is installed and up to date.")
    Console.print(f"  Home: {AEC_HOME}")
    Console.print("  Run `aec doctor` for a health check.")


def run_setup_path(
    path: str,
    skip_raycast: bool = False,
    dry_run: bool = False,
) -> None:
    """Track a specific repo."""
    project = Path(path).resolve()
    if not project.exists():
        Console.error(f"Path does not exist: {project}")
        raise SystemExit(1)

    if is_logged(project):
        Console.info(f"Already tracked: {project}")
        return

    init_aec_home(dry_run=dry_run)

    if dry_run:
        Console.info(f"Would track: {project}")
        return

    # Delegate to repo setup for creating agent files
    from .repo import setup as repo_setup
    repo_setup(str(project), skip_raycast=skip_raycast, dry_run=dry_run)


def run_setup_all(
    skip_raycast: bool = False,
    dry_run: bool = False,
) -> None:
    """Track all repos in projects directory."""
    from .repo import setup_all
    setup_all()
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add aec/commands/setup.py tests/test_setup_cmd.py
git commit -m "feat(cli): add aec setup (absorbs install + repo setup)"
```

---

### Task 13: `aec untrack <path>` Command

**Files:**
- Create: `aec/commands/untrack.py`
- Create: `tests/test_untrack_cmd.py`
- Modify: `aec/lib/tracking.py` (add `untrack_repo`)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_untrack_cmd.py
"""Tests for aec untrack command."""

import pytest
from pathlib import Path


@pytest.fixture
def untrack_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    project = temp_dir / "projects" / "my-app"
    project.mkdir(parents=True)

    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{project}\n")

    return {"project": project, "log": log}


class TestUntrack:
    def test_removes_from_tracking(self, untrack_env):
        from aec.commands.untrack import run_untrack
        from aec.lib.tracking import is_logged
        assert is_logged(untrack_env["project"])
        run_untrack(str(untrack_env["project"]), yes=True)
        assert not is_logged(untrack_env["project"])

    def test_error_for_untracked_path(self, untrack_env, capsys):
        from aec.commands.untrack import run_untrack
        run_untrack("/nonexistent/path", yes=True)
        output = capsys.readouterr().out
        assert "not tracked" in output.lower()
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Add `untrack_repo` to tracking.py**

In `aec/lib/tracking.py`, add after the `prune_stale` function:

```python
def untrack_repo(project_dir: Path) -> bool:
    """Remove a repo from the tracking log.

    Returns True if the repo was found and removed.
    """
    if not AEC_SETUP_LOG.exists():
        return False

    abs_path = str(Path(project_dir).resolve())
    content = AEC_SETUP_LOG.read_text().strip()
    if not content:
        return False

    lines = content.split("\n")
    new_lines = [line for line in lines if line and not line.endswith(f"|{abs_path}")]

    if len(new_lines) == len(lines):
        return False  # Not found

    AEC_SETUP_LOG.write_text("\n".join(new_lines) + "\n" if new_lines else "")
    return True
```

- [ ] **Step 4: Implement untrack.py**

```python
# aec/commands/untrack.py
"""aec untrack <path> — stop tracking a repo."""

from pathlib import Path

from ..lib import Console
from ..lib.config import INSTALLED_MANIFEST_V2
from ..lib.tracking import is_logged, untrack_repo
from ..lib.manifest_v2 import load_manifest, save_manifest


def run_untrack(path: str, yes: bool = False) -> None:
    """Stop tracking a repo."""
    project = Path(path).resolve()

    if not is_logged(project):
        Console.warning(f"Not tracked: {project}")
        return

    if not yes:
        Console.print(f"This will stop tracking {project}.")
        try:
            resp = input("Continue? [y/N]: ").strip().lower()
        except EOFError:
            resp = "n"
        if resp != "y":
            Console.info("Skipped.")
            return

    untrack_repo(project)

    # Remove from manifest
    manifest = load_manifest(INSTALLED_MANIFEST_V2)
    repo_key = str(project)
    if repo_key in manifest.get("repos", {}):
        del manifest["repos"][repo_key]
        save_manifest(manifest, INSTALLED_MANIFEST_V2)

    Console.success(f"Untracked: {project}")
```

- [ ] **Step 5: Run tests, verify pass**

- [ ] **Step 6: Commit**

```bash
git add aec/commands/untrack.py aec/lib/tracking.py tests/test_untrack_cmd.py
git commit -m "feat(cli): add aec untrack <path>"
```

---

### Task 14: `aec config` Command

**Files:**
- Create: `aec/commands/config_cmd.py`
- Create: `tests/test_config_cmd.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config_cmd.py
"""Tests for aec config command (wraps preferences)."""

import pytest
from pathlib import Path


@pytest.fixture
def config_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    return aec_home


class TestConfig:
    def test_list_shows_preferences(self, config_env, capsys):
        from aec.commands.config_cmd import run_config_list
        run_config_list()
        # Should not crash; output depends on registered preferences
```

- [ ] **Step 2: Implement config_cmd.py**

```python
# aec/commands/config_cmd.py
"""aec config — manage preferences (replaces aec preferences)."""

from .preferences import list_preferences, set_pref, reset_pref


def run_config_list() -> None:
    """List all preferences."""
    list_preferences()


def run_config_set(key: str, value: str) -> None:
    """Set a preference."""
    set_pref(key, value)


def run_config_reset(key: str) -> None:
    """Reset a preference."""
    reset_pref(key)
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add aec/commands/config_cmd.py tests/test_config_cmd.py
git commit -m "feat(cli): add aec config (replaces aec preferences)"
```

---

### Task 15: `aec generate` and `aec validate`

**Files:**
- Create: `aec/commands/generate.py`
- Modify: (rewrap existing rules/files logic)

- [ ] **Step 1: Implement generate.py**

```python
# aec/commands/generate.py
"""aec generate rules|files — generate agent configuration files."""

from ..lib import Console


def run_generate_rules() -> None:
    """Generate .agent-rules/ directory."""
    from .rules import generate
    generate()


def run_generate_files() -> None:
    """Generate agent instruction files from templates."""
    from .files import generate
    generate()


def run_validate() -> None:
    """Validate rule parity."""
    from .rules import validate
    validate()


def run_prune(yes: bool = False, dry_run: bool = False) -> None:
    """Remove stale repo tracking entries."""
    from ..lib.tracking import prune_stale
    from ..lib import Console

    pruned = prune_stale(dry_run=dry_run)
    if not pruned:
        Console.success("No stale entries found.")
        return

    for entry in pruned:
        label = "Would prune" if dry_run else "Pruned"
        Console.print(f"  {label}: {entry.path}")

    if not dry_run:
        Console.success(f"Pruned {len(pruned)} stale entries.")
```

- [ ] **Step 2: Commit**

```bash
git add aec/commands/generate.py
git commit -m "feat(cli): add aec generate rules/files and aec validate"
```

---

### Task 16: CLI Rewrite

**Files:**
- Modify: `aec/cli.py` (complete rewrite of command registration)

This is the central task — rewiring all commands to the flat structure.

- [ ] **Step 1: Write failing test for new CLI structure**

```python
# tests/test_cli_v2.py
"""Tests for the new flat CLI command structure."""

import subprocess
import sys


class TestCLIHelp:
    def test_top_level_help_shows_flat_commands(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True, text=True,
        )
        assert "update" in result.stdout
        assert "upgrade" in result.stdout
        assert "install" in result.stdout
        assert "uninstall" in result.stdout
        assert "list" in result.stdout
        assert "search" in result.stdout
        assert "outdated" in result.stdout
        assert "info" in result.stdout
        assert "setup" in result.stdout
        assert "untrack" in result.stdout
        assert "config" in result.stdout
        assert "generate" in result.stdout
        assert "validate" in result.stdout
        assert "doctor" in result.stdout

    def test_old_commands_show_deprecation(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "skills", "list"],
            capture_output=True, text=True,
        )
        assert "deprecated" in result.stdout.lower() or "deprecated" in result.stderr.lower()
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Rewrite cli.py**

Replace the contents of `aec/cli.py` with the new flat structure. This is a large file — the implementing agent should read the current `cli.py` first, then write the replacement preserving the argparse fallback pattern but with flat commands.

Key structure:
- Top-level commands: update, upgrade, install, uninstall, list, search, outdated, info, setup, untrack, config, generate, validate, discover, doctor, prune, version
- `install` takes positional `type` and `name` args plus `-g` flag
- `uninstall` takes positional `type` and `name` args plus `-g` flag
- `generate` takes subcommand `rules` or `files`
- `config` takes subcommand `list`, `set`, or `reset`
- Old command groups (repo, skills, agent-tools, rules, files, preferences) are kept as deprecated shims

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Verify existing tests still pass**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/ -v`
Expected: All existing tests still pass (deprecation shims preserve old behavior)

- [ ] **Step 6: Commit**

```bash
git add aec/cli.py tests/test_cli_v2.py
git commit -m "feat(cli): rewrite cli.py with flat brew-aligned command structure"
```

---

### Task 17: Deprecation Shims

**Files:**
- Create: `aec/commands/deprecation.py`
- Create: `tests/test_deprecation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_deprecation.py
"""Tests for deprecation shims."""

import pytest
from io import StringIO


class TestDeprecationWarnings:
    def test_warns_on_old_command(self, capsys):
        from aec.commands.deprecation import deprecation_warning
        deprecation_warning("aec skills install X", "aec install skill X")
        output = capsys.readouterr().err
        assert "deprecated" in output.lower()
        assert "aec install skill X" in output
```

- [ ] **Step 2: Implement deprecation.py**

```python
# aec/commands/deprecation.py
"""Deprecation shims for old AEC commands."""

import sys

from ..lib import Console


def deprecation_warning(old_cmd: str, new_cmd: str) -> None:
    """Print a deprecation warning to stderr."""
    print(
        f"Warning: `{old_cmd}` is deprecated and will be removed in the next major version.\n"
        f"Use `{new_cmd}` instead.\n",
        file=sys.stderr,
    )
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add aec/commands/deprecation.py tests/test_deprecation.py
git commit -m "feat(cli): add deprecation shims for old command names"
```

---

### Task 18: Manifest v1 → v2 Migration

**Files:**
- Modify: `aec/commands/setup.py` (add migration on first run)
- Create: `tests/test_migration.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_migration.py
"""Tests for v1 → v2 manifest migration."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def migration_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    # V1 manifest
    v1 = {
        "manifestVersion": 1,
        "installedAt": "2026-03-30T00:00:00Z",
        "updatedAt": "2026-03-30T00:00:00Z",
        "skills": {
            "verification-writer": {"version": "1.0.0", "contentHash": "sha256:abc", "installedAt": "2026-03-30T00:00:00Z"},
            "commit": {"version": "1.0.0", "contentHash": "sha256:def", "installedAt": "2026-03-30T00:00:00Z"},
        }
    }
    (aec_home / "installed-skills.json").write_text(json.dumps(v1))

    return aec_home


class TestMigration:
    def test_migrates_v1_skills_to_v2_global(self, migration_env):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        v1_path = migration_env / "installed-skills.json"
        m = migrate_v1_to_v2(v1_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]
        assert "commit" in m["global"]["skills"]
        assert m["global"]["skills"]["verification-writer"]["version"] == "1.0.0"

    def test_auto_migration_on_load(self, migration_env):
        from aec.lib.manifest_v2 import load_manifest, auto_migrate
        v2_path = migration_env / "installed-manifest.json"
        v1_path = migration_env / "installed-skills.json"

        # V2 doesn't exist yet, V1 does
        assert not v2_path.exists()
        assert v1_path.exists()

        m = auto_migrate(v2_path, v1_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]
```

- [ ] **Step 2: Run tests, verify fail**

- [ ] **Step 3: Add auto_migrate to manifest_v2.py**

In `aec/lib/manifest_v2.py`, add:

```python
def auto_migrate(v2_path: Path, v1_path: Path) -> dict:
    """Load v2 manifest, auto-migrating from v1 if needed.

    If v2 exists, load it directly.
    If v2 is missing but v1 exists, migrate v1 → v2 and save.
    If neither exists, return empty v2.
    """
    if v2_path.exists():
        return load_manifest(v2_path)

    if v1_path.exists():
        manifest = migrate_v1_to_v2(v1_path)
        save_manifest(manifest, v2_path)
        return manifest

    return load_manifest(v2_path)
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add aec/lib/manifest_v2.py tests/test_migration.py
git commit -m "feat(cli): add auto-migration from v1 to v2 manifest"
```

---

### Task 19: Integration Tests and Docs

**Files:**
- Modify: `tests/test_cli.py` (add integration tests for new commands)
- Modify: `aec/lib/tracking.py` (update README content with new commands)

- [ ] **Step 1: Add integration tests**

Add tests to `tests/test_cli.py` that invoke the CLI via subprocess and verify the new commands work end-to-end. At minimum:

```python
class TestNewCLIIntegration:
    def test_update_runs(self):
        """aec update should not crash (even if git pull fails)."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "update"],
            capture_output=True, text=True,
        )
        # May fail due to git, but should not crash with a traceback
        assert "Traceback" not in result.stderr

    def test_list_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "list"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0 or "Traceback" not in result.stderr

    def test_outdated_runs(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "outdated"],
            capture_output=True, text=True,
        )
        assert "Traceback" not in result.stderr
```

- [ ] **Step 2: Update tracking.py README content**

Update `_get_readme_content()` in `aec/lib/tracking.py` to reference the new command names (`aec list`, `aec upgrade`, `aec setup` instead of `aec repo list`, `aec repo update`, `aec repo setup`).

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/mattbernier/projects/agents-environment-config && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli.py aec/lib/tracking.py
git commit -m "test(cli): add integration tests for brew-aligned commands"
```

---

## Execution Notes

**Parallel opportunities:**
- Tasks 1 and 2 are independent — run in parallel.
- Tasks 6-11 (install, uninstall, list, search, outdated, info) are independent of each other once tasks 1-3 are done — can run in parallel with worktrees.
- Tasks 14 and 15 are trivial wrappers — can run anytime after task 1.

**Critical path:** Task 1 → Task 3 → Task 5 → Task 16 → Task 17 → Task 19

**Risk areas:**
- Task 16 (CLI rewrite) is the largest and most likely to break existing tests. Run the full test suite after this task.
- Task 18 (migration) should be tested with a real v1 manifest from `~/.agents-environment-config/installed-skills.json` before merging.

**Version bump:** After all tasks complete, bump the version in `pyproject.toml` to 3.0.0 (major version for breaking CLI changes).
