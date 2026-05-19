> Status: shipped via PR #50 on 2026-05-12

# AEC Agent Blurb Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `aec configure-agent` — a versioned, hashed, consent-gated instruction block writer that teaches AI agents which AEC operations they may run autonomously vs. ask-first, written into per-scope agent files (CLAUDE.md, AGENTS.md, GEMINI.md, QWEN.md, Cursor MDC, etc.).

**Architecture:** Single source of truth is `<scope>/.aec/agent-blurb.json`. The agent file is a render target with `<!-- aec-blurb:start ... -->` / `<!-- aec-blurb:end -->` delimiters. The renderer is a pure function of `(profile/matrix, scope, AEC version, shipped template)`. Drift is detected by comparing three independent SHA256 hashes: shipped template, stored content, on-disk content. Install/update flows offer the feature with Y/n consent; the dedicated `aec configure-agent` subcommand is the canonical entry point for re-targeting, refreshing, or removing.

**Tech Stack:** Python 3.9+, typer (CLI), pytest (real-filesystem tests via `temp_dir` / `mock_home` fixtures — no internal mocks per project standards), existing AEC libs: `atomic_write`, `scope`, `registry`, `configurable_instructions` (sibling pattern), `agent_files`.

**Spec:** `docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|----------------|
| `aec/lib/agent_blurb/__init__.py` | Public API surface re-exports |
| `aec/lib/agent_blurb/profile.py` | Profile constants, matrix expansion, command classification (read-only / additive / destructive) |
| `aec/lib/agent_blurb/config.py` | Load/save `.aec/agent-blurb.json` per scope; JSON schema |
| `aec/lib/agent_blurb/decline.py` | Load/save `.aec/agent-blurb-decline.json` (separate file per "one concern per file") |
| `aec/lib/agent_blurb/render.py` | Pure render function; SHA256 helpers; deterministic output |
| `aec/lib/agent_blurb/markers.py` | Locate / extract / replace block between `<!-- aec-blurb:start ... -->` / `<!-- aec-blurb:end -->` |
| `aec/lib/agent_blurb/drift.py` | Compute drift state from (shipped, stored, on-disk) hashes |
| `aec/lib/agent_blurb/targets.py` | Discover detected agent files per scope (via `agents.json` + `agent_files.py`) |
| `aec/lib/agent_blurb/templates/blurb_v1.md.tmpl` | Shipped prose template (schema v1) |
| `aec/commands/configure_agent.py` | CLI command implementation (`aec configure-agent` and subflags) |
| `tests/lib/agent_blurb/test_profile.py` | Profile / matrix / classification tests |
| `tests/lib/agent_blurb/test_config.py` | JSON schema load/save/round-trip tests |
| `tests/lib/agent_blurb/test_decline.py` | Decline-state tests |
| `tests/lib/agent_blurb/test_render.py` | Golden render tests, hash determinism |
| `tests/lib/agent_blurb/test_markers.py` | Marker parsing edge cases |
| `tests/lib/agent_blurb/test_drift.py` | All 5 drift states |
| `tests/lib/agent_blurb/test_targets.py` | Agent-file discovery per scope |
| `tests/commands/test_configure_agent.py` | End-to-end CLI tests |

### Modified files

| File | Change |
|------|--------|
| `aec/cli.py` | Register `configure-agent` typer command |
| `aec/commands/install_cmd.py` | After install, if no blurb config exists and user hasn't declined, offer it |
| `aec/commands/update.py` | After update, run drift check; if drifted, offer refresh |
| `aec/commands/doctor.py` | Surface blurb drift state in health output |
| `docs/qa-verification.md` | Add manual verification steps (install prompt, drift states, refresh idempotency, remove flow) |
| `pyproject.toml` | No change expected (no new deps) |

### Why this decomposition

- Each module under `aec/lib/agent_blurb/` has one responsibility. Render is pure; markers handle text wrangling; drift is a state machine over hashes; config is just JSON I/O. The CLI orchestrates them.
- The split mirrors `aec/lib/org_config/` and `aec/lib/schedulers/` — established AEC pattern of grouping a feature's libs into a subdir.
- Test files mirror lib files 1:1 so coverage gaps are obvious.

---

## Coverage rule

The project enforces `--cov-fail-under=65`. Every new module must have unit tests before integration. Run `pytest` (no `--watch`) at the end of each task.

---

## Task 1: Profile model + command classification

**Files:**
- Create: `aec/lib/agent_blurb/__init__.py`
- Create: `aec/lib/agent_blurb/profile.py`
- Create: `tests/lib/agent_blurb/__init__.py`
- Create: `tests/lib/agent_blurb/test_profile.py`

- [ ] **Step 1: Write failing test**

```python
# tests/lib/agent_blurb/test_profile.py
"""Tests for profile model and command classification."""

import pytest
from aec.lib.agent_blurb.profile import (
    PROFILES,
    DEFAULT_PROFILE,
    READ_ONLY_COMMANDS,
    DESTRUCTIVE_COMMANDS,
    ITEM_TYPES,
    expand_profile,
    classify_command,
    CommandClass,
)


class TestProfiles:
    def test_default_profile_is_balanced(self):
        assert DEFAULT_PROFILE == "balanced"

    def test_three_named_profiles_exist(self):
        assert set(PROFILES.keys()) == {"conservative", "balanced", "permissive"}

    def test_balanced_matrix(self):
        assert PROFILES["balanced"] == {
            "agents":   {"additive": "ask"},
            "skills":   {"additive": "auto"},
            "rules":    {"additive": "auto"},
            "packages": {"additive": "ask"},
            "plugins":  {"additive": "ask"},
        }

    def test_conservative_is_all_ask(self):
        for itype in ITEM_TYPES:
            assert PROFILES["conservative"][itype]["additive"] == "ask"

    def test_permissive_is_all_auto(self):
        for itype in ITEM_TYPES:
            assert PROFILES["permissive"][itype]["additive"] == "auto"

    def test_item_types_match_spec(self):
        assert ITEM_TYPES == ("agents", "skills", "rules", "packages", "plugins")


class TestExpandProfile:
    def test_named_profile_returns_matrix(self):
        m = expand_profile("balanced")
        assert m == PROFILES["balanced"]

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            expand_profile("nope")

    def test_returned_matrix_is_copy_not_reference(self):
        m = expand_profile("balanced")
        m["agents"]["additive"] = "auto"
        assert PROFILES["balanced"]["agents"]["additive"] == "ask"


class TestClassifyCommand:
    @pytest.mark.parametrize("cmd", ["list", "status", "doctor", "search", "info"])
    def test_read_only(self, cmd):
        assert classify_command(cmd) == CommandClass.READ_ONLY

    @pytest.mark.parametrize("cmd", ["install", "add"])
    def test_additive(self, cmd):
        assert classify_command(cmd) == CommandClass.ADDITIVE

    @pytest.mark.parametrize("cmd", ["remove", "uninstall", "update", "upgrade", "reset", "init"])
    def test_destructive(self, cmd):
        assert classify_command(cmd) == CommandClass.DESTRUCTIVE

    def test_unknown_command_defaults_destructive(self):
        """Unknown commands are conservatively classified as destructive."""
        assert classify_command("hypothetical-future-command") == CommandClass.DESTRUCTIVE


class TestReadOnlyAndDestructiveSets:
    def test_init_is_destructive(self):
        assert "init" in DESTRUCTIVE_COMMANDS
        assert "init" not in READ_ONLY_COMMANDS

    def test_update_is_destructive(self):
        assert "update" in DESTRUCTIVE_COMMANDS
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_profile.py -v`
Expected: ImportError (module does not exist yet).

- [ ] **Step 3: Implement profile module**

```python
# aec/lib/agent_blurb/__init__.py
"""AEC Agent Blurb — versioned instruction block management."""
```

```python
# aec/lib/agent_blurb/profile.py
"""Profile model, command classification, and matrix expansion.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §7.
"""

from copy import deepcopy
from enum import Enum
from typing import Dict, Tuple

ITEM_TYPES: Tuple[str, ...] = ("agents", "skills", "rules", "packages", "plugins")

DEFAULT_PROFILE = "balanced"

PROFILES: Dict[str, Dict[str, Dict[str, str]]] = {
    "conservative": {it: {"additive": "ask"} for it in ITEM_TYPES},
    "balanced": {
        "agents":   {"additive": "ask"},
        "skills":   {"additive": "auto"},
        "rules":    {"additive": "auto"},
        "packages": {"additive": "ask"},
        "plugins":  {"additive": "ask"},
    },
    "permissive": {it: {"additive": "auto"} for it in ITEM_TYPES},
}


class CommandClass(str, Enum):
    READ_ONLY = "read_only"
    ADDITIVE = "additive"
    DESTRUCTIVE = "destructive"


READ_ONLY_COMMANDS = frozenset({
    "list", "status", "doctor", "search", "info", "outdated",
})

ADDITIVE_COMMANDS = frozenset({"install", "add"})

DESTRUCTIVE_COMMANDS = frozenset({
    "remove", "uninstall", "update", "upgrade", "reset", "init", "untrack",
})


def expand_profile(name: str) -> Dict[str, Dict[str, str]]:
    """Return a deep copy of the profile's matrix.

    Raises ValueError if name is not a known profile.
    """
    if name not in PROFILES:
        raise ValueError(f"Unknown profile: {name!r}")
    return deepcopy(PROFILES[name])


def classify_command(cmd: str) -> CommandClass:
    """Classify an AEC subcommand by its risk class.

    Unknown commands are conservatively classified as DESTRUCTIVE so future
    AEC versions that ship new commands fail closed (ask-first) until the
    blurb is refreshed.
    """
    if cmd in READ_ONLY_COMMANDS:
        return CommandClass.READ_ONLY
    if cmd in ADDITIVE_COMMANDS:
        return CommandClass.ADDITIVE
    return CommandClass.DESTRUCTIVE
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_profile.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/agent_blurb/__init__.py aec/lib/agent_blurb/profile.py tests/lib/agent_blurb/
git commit -m "feat(agent-blurb): add profile model and command classification"
```

---

## Task 2: Config schema + JSON I/O (`.aec/agent-blurb.json`)

**Files:**
- Create: `aec/lib/agent_blurb/config.py`
- Create: `tests/lib/agent_blurb/test_config.py`

- [ ] **Step 1: Write failing test**

```python
# tests/lib/agent_blurb/test_config.py
"""Tests for agent-blurb JSON config (source of truth per scope)."""

import json
import pytest
from pathlib import Path

from aec.lib.agent_blurb.config import (
    AgentBlurbConfig,
    TargetRecord,
    CONFIG_FILENAME,
    load_config,
    save_config,
    config_path,
    new_skeleton,
    SCHEMA_VERSION,
)


class TestConfigPath:
    def test_project_path(self, tmp_path):
        assert config_path(scope="project", root=tmp_path) == tmp_path / ".aec" / "agent-blurb.json"

    def test_global_path(self, mock_home):
        from aec.lib.agent_blurb.config import config_path
        assert config_path(scope="global") == mock_home / ".aec" / "agent-blurb.json"

    def test_invalid_scope_raises(self, tmp_path):
        with pytest.raises(ValueError):
            config_path(scope="nope", root=tmp_path)


class TestSkeleton:
    def test_new_skeleton_balanced(self):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        assert c["schema"] == SCHEMA_VERSION
        assert c["scope"] == "project"
        assert c["profile"] == "balanced"
        assert c["aec_version_last_write"] == "2.37.4"
        assert c["matrix"]["skills"]["additive"] == "auto"
        assert c["targets"] == []

    def test_new_skeleton_custom_matrix(self):
        matrix = {"agents": {"additive": "auto"}}
        c = new_skeleton(scope="global", profile="custom", aec_version="2.37.4",
                         matrix_override=matrix)
        assert c["profile"] == "custom"
        assert c["matrix"]["agents"]["additive"] == "auto"


class TestLoadSave:
    def test_round_trip(self, tmp_path):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        save_config(c, scope="project", root=tmp_path)
        loaded = load_config(scope="project", root=tmp_path)
        assert loaded == c

    def test_load_missing_returns_none(self, tmp_path):
        assert load_config(scope="project", root=tmp_path) is None

    def test_save_creates_parent_dir(self, tmp_path):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        save_config(c, scope="project", root=tmp_path)
        assert (tmp_path / ".aec" / "agent-blurb.json").exists()

    def test_corrupt_json_raises(self, tmp_path):
        path = tmp_path / ".aec" / "agent-blurb.json"
        path.parent.mkdir()
        path.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_config(scope="project", root=tmp_path)

    def test_target_record_round_trip(self, tmp_path):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        c["targets"].append({
            "agent_key": "claude",
            "path": "CLAUDE.md",
            "template_hash": "abc123",
            "content_hash": "def456",
            "written_at": "2026-05-12T14:03:00Z",
        })
        save_config(c, scope="project", root=tmp_path)
        loaded = load_config(scope="project", root=tmp_path)
        assert loaded["targets"][0]["agent_key"] == "claude"
        assert loaded["targets"][0]["path"] == "CLAUDE.md"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_config.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement config module**

```python
# aec/lib/agent_blurb/config.py
"""JSON source of truth for the agent blurb feature.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §5.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Optional, TypedDict, List, Dict

from aec.lib.atomic_write import atomic_write_text
from aec.lib.agent_blurb.profile import expand_profile, ITEM_TYPES

SCHEMA_VERSION = 1
CONFIG_FILENAME = "agent-blurb.json"


class TargetRecord(TypedDict):
    agent_key: str   # e.g. "claude", "codex", "gemini" — resolves to file via registry
    path: str        # relative to scope root (project: repo root; global: $HOME)
    template_hash: str
    content_hash: str
    written_at: str  # ISO 8601 UTC


class AgentBlurbConfig(TypedDict):
    schema: int
    aec_version_last_write: str
    scope: str  # "project" | "global"
    profile: str  # "conservative" | "balanced" | "permissive" | "custom"
    matrix: Dict[str, Dict[str, str]]
    targets: List[TargetRecord]


def config_path(scope: str, root: Optional[Path] = None) -> Path:
    """Return the path to the agent-blurb.json for the given scope.

    For project scope, `root` must be supplied (the repo root).
    For global scope, `root` is ignored and the path is rooted at Path.home().
    """
    if scope == "project":
        if root is None:
            raise ValueError("project scope requires root")
        return root / ".aec" / CONFIG_FILENAME
    if scope == "global":
        return Path.home() / ".aec" / CONFIG_FILENAME
    raise ValueError(f"Unknown scope: {scope!r}")


def new_skeleton(
    scope: str,
    profile: str,
    aec_version: str,
    matrix_override: Optional[Dict[str, Dict[str, str]]] = None,
) -> AgentBlurbConfig:
    """Create a fresh config dict.

    If profile is one of the named profiles, the matrix is generated from
    PROFILES. If profile is "custom", `matrix_override` is merged onto the
    `balanced` matrix as a starting point.
    """
    if profile == "custom":
        matrix = expand_profile("balanced")
        if matrix_override:
            for it, settings in matrix_override.items():
                if it in matrix:
                    matrix[it].update(settings)
    else:
        matrix = expand_profile(profile)

    return {
        "schema": SCHEMA_VERSION,
        "aec_version_last_write": aec_version,
        "scope": scope,
        "profile": profile,
        "matrix": matrix,
        "targets": [],
    }


def load_config(scope: str, root: Optional[Path] = None) -> Optional[AgentBlurbConfig]:
    """Load the agent-blurb config for a scope, or return None if missing."""
    path = config_path(scope, root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(
    data: AgentBlurbConfig, scope: str, root: Optional[Path] = None
) -> None:
    """Write the agent-blurb config atomically. Creates parent dirs."""
    path = config_path(scope, root)
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_config.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/agent_blurb/config.py tests/lib/agent_blurb/test_config.py
git commit -m "feat(agent-blurb): add json source-of-truth config with atomic write"
```

---

## Task 3: Decline state (separate concern file)

**Files:**
- Create: `aec/lib/agent_blurb/decline.py`
- Create: `tests/lib/agent_blurb/test_decline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/lib/agent_blurb/test_decline.py
"""Tests for agent-blurb decline state (separate sibling file)."""

import pytest

from aec.lib.agent_blurb.decline import (
    DECLINE_FILENAME,
    is_declined,
    record_decline,
    clear_decline,
    should_reprompt,
)


class TestDecline:
    def test_not_declined_by_default(self, tmp_path):
        assert is_declined(scope="project", root=tmp_path) is False

    def test_record_then_is_declined(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert is_declined(scope="project", root=tmp_path) is True

    def test_clear_removes_decline(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        clear_decline(scope="project", root=tmp_path)
        assert is_declined(scope="project", root=tmp_path) is False

    def test_should_reprompt_on_major_version_bump(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert should_reprompt(scope="project", root=tmp_path, current_version="3.0.0") is True

    def test_should_not_reprompt_on_minor_bump(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert should_reprompt(scope="project", root=tmp_path, current_version="2.38.0") is False

    def test_should_not_reprompt_on_patch_bump(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert should_reprompt(scope="project", root=tmp_path, current_version="2.37.5") is False

    def test_should_reprompt_if_never_declined(self, tmp_path):
        assert should_reprompt(scope="project", root=tmp_path, current_version="2.37.4") is True
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_decline.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# aec/lib/agent_blurb/decline.py
"""Decline state for the agent-blurb feature.

Stored in a sibling file rather than inside agent-blurb.json so that the
"one concern per file" rule holds (relevant for parallel agent safety).
See spec §5.1 and §13.1.
"""

import json
from pathlib import Path
from typing import Optional

from aec.lib.atomic_write import atomic_write_text

DECLINE_FILENAME = "agent-blurb-decline.json"


def _decline_path(scope: str, root: Optional[Path] = None) -> Path:
    if scope == "project":
        if root is None:
            raise ValueError("project scope requires root")
        return root / ".aec" / DECLINE_FILENAME
    if scope == "global":
        return Path.home() / ".aec" / DECLINE_FILENAME
    raise ValueError(f"Unknown scope: {scope!r}")


def is_declined(scope: str, root: Optional[Path] = None) -> bool:
    return _decline_path(scope, root).exists()


def record_decline(scope: str, aec_version: str, root: Optional[Path] = None) -> None:
    path = _decline_path(scope, root)
    atomic_write_text(
        path,
        json.dumps({"declined": True, "declined_at_version": aec_version}, indent=2) + "\n",
    )


def clear_decline(scope: str, root: Optional[Path] = None) -> None:
    path = _decline_path(scope, root)
    if path.exists():
        path.unlink()


def _major(version: str) -> int:
    return int(version.split(".")[0])


def should_reprompt(scope: str, current_version: str, root: Optional[Path] = None) -> bool:
    """Re-prompt only on major version bumps (per spec §13.1 default)."""
    path = _decline_path(scope, root)
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    declined_version = data.get("declined_at_version", "0.0.0")
    return _major(current_version) > _major(declined_version)
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_decline.py -v`

- [ ] **Step 5: Commit**

```bash
git add aec/lib/agent_blurb/decline.py tests/lib/agent_blurb/test_decline.py
git commit -m "feat(agent-blurb): add decline state with major-version reprompt"
```

---

## Task 4: Shipped template + renderer (pure function, hashable)

**Files:**
- Create: `aec/lib/agent_blurb/templates/blurb_v1.md.tmpl`
- Create: `aec/lib/agent_blurb/render.py`
- Create: `tests/lib/agent_blurb/test_render.py`
- Create: `tests/lib/agent_blurb/fixtures/expected_balanced_project.md`

- [ ] **Step 1: Write failing test**

```python
# tests/lib/agent_blurb/test_render.py
"""Golden + determinism tests for the renderer.

The renderer must be a pure function: identical inputs produce byte-identical
output. This guarantees content_hash is stable across runs and platforms.
"""

import hashlib
from pathlib import Path

import pytest

from aec.lib.agent_blurb.render import (
    render_block,
    sha256_short,
    shipped_template_hash,
    BLOCK_VERSION,
    SCHEMA_VERSION,
)


FIXTURES = Path(__file__).parent / "fixtures"


class TestSha256Short:
    def test_deterministic(self):
        assert sha256_short("hello") == sha256_short("hello")

    def test_length_is_16(self):
        assert len(sha256_short("hello")) == 16

    def test_different_inputs_differ(self):
        assert sha256_short("a") != sha256_short("b")


class TestShippedTemplateHash:
    def test_stable_across_calls(self):
        a = shipped_template_hash()
        b = shipped_template_hash()
        assert a == b


class TestRenderBlock:
    def test_balanced_project_golden(self):
        matrix = {
            "agents":   {"additive": "ask"},
            "skills":   {"additive": "auto"},
            "rules":    {"additive": "auto"},
            "packages": {"additive": "ask"},
            "plugins":  {"additive": "ask"},
        }
        body = render_block(
            scope="project",
            profile="balanced",
            matrix=matrix,
            aec_version="2.37.4",
        )
        # Idempotent
        body2 = render_block(
            scope="project",
            profile="balanced",
            matrix=matrix,
            aec_version="2.37.4",
        )
        assert body == body2

    def test_block_contains_required_markers(self):
        matrix = {it: {"additive": "ask"} for it in ("agents","skills","rules","packages","plugins")}
        body = render_block(
            scope="project", profile="conservative", matrix=matrix, aec_version="2.37.4"
        )
        assert "<!-- aec-blurb:start" in body
        assert "<!-- aec-blurb:end -->" in body
        assert "schema=1" in body
        assert "aec=2.37.4" in body
        assert "profile=conservative" in body
        assert "scope=project" in body

    def test_block_lists_auto_commands(self):
        matrix = {it: {"additive": "auto"} for it in ("agents","skills","rules","packages","plugins")}
        body = render_block(
            scope="project", profile="permissive", matrix=matrix, aec_version="2.37.4"
        )
        # Read-only always auto
        assert "aec list" in body
        # Permissive: all additive auto
        assert "aec add skill" in body
        assert "aec add agent" in body
        # Destructive always ask
        assert "aec remove" in body  # in the ask list section
        assert "aec update" in body

    def test_content_hash_in_marker_matches_body(self):
        """The content-hash in the marker is over the rendered body content
        excluding the marker line itself."""
        matrix = {it: {"additive": "ask"} for it in ("agents","skills","rules","packages","plugins")}
        body = render_block(
            scope="project", profile="conservative", matrix=matrix, aec_version="2.37.4"
        )
        # Extract content-hash from marker and verify it matches a recomputed hash
        import re
        m = re.search(r"content-hash=([a-f0-9]+)", body)
        assert m is not None
        claimed = m.group(1)
        # Recompute over the inner body (between start marker line and end marker)
        from aec.lib.agent_blurb.render import extract_inner_body, content_hash_of
        inner = extract_inner_body(body)
        assert content_hash_of(inner) == claimed

    def test_changing_profile_changes_content_hash(self):
        m1 = {it: {"additive": "ask"} for it in ("agents","skills","rules","packages","plugins")}
        m2 = {it: {"additive": "auto"} for it in ("agents","skills","rules","packages","plugins")}
        b1 = render_block(scope="project", profile="conservative", matrix=m1, aec_version="2.37.4")
        b2 = render_block(scope="project", profile="permissive", matrix=m2, aec_version="2.37.4")
        assert b1 != b2
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_render.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement template + renderer**

Create `aec/lib/agent_blurb/templates/blurb_v1.md.tmpl` containing the prose framing from spec §4.1 (the `## AEC — Agent Environment Config` heading and "How to interpret this block" paragraph). The allow/deny lists are generated, NOT in the template.

```markdown
{{!-- aec/lib/agent_blurb/templates/blurb_v1.md.tmpl --}}
## AEC — Agent Environment Config

AEC (`agents-environment-config`) is a CLI that manages five item types
across multiple AI agents: agents, skills, rules, packages, and plugins.

You may use AEC to manage these items as part of your workflow, within the
boundaries listed below. Run `aec --help` for full command reference.

### Operations you may run without asking

{{AUTO_LIST}}

### Operations that require explicit user permission

{{ASK_LIST}}

### How to interpret this block

This block is managed by AEC. Do not hand-edit between the start/end markers;
use `aec configure-agent` to change scope or profile. The `content-hash` in
the start marker is recomputed on every render; if you must hand-edit, run
`aec configure-agent --check` to see the drift report and `--refresh` to
re-render.
```

```python
# aec/lib/agent_blurb/render.py
"""Pure renderer for the agent blurb block.

Determinism guarantees:
- Same inputs -> byte-identical output.
- No timestamps in body content; only stored in the JSON config.
- Lists are emitted in fixed-sorted order.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §4.
"""

import hashlib
from pathlib import Path
from typing import Dict

from aec.lib.agent_blurb.profile import (
    ITEM_TYPES,
    READ_ONLY_COMMANDS,
    DESTRUCTIVE_COMMANDS,
)

BLOCK_VERSION = "v1"
SCHEMA_VERSION = 1

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "blurb_v1.md.tmpl"

START_MARKER_PREFIX = "<!-- aec-blurb:start"
END_MARKER = "<!-- aec-blurb:end -->"


def sha256_short(text: str) -> str:
    """Return the first 16 hex chars of SHA256(text)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _read_template() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def shipped_template_hash() -> str:
    return sha256_short(_read_template())


def _format_auto_list(matrix: Dict[str, Dict[str, str]]) -> str:
    lines = []
    # Read-only first, always auto
    for cmd in sorted(READ_ONLY_COMMANDS):
        lines.append(f"- `aec {cmd}` — read-only (always auto)")
    # Additive per matrix
    for itype in ITEM_TYPES:
        if matrix[itype]["additive"] == "auto":
            lines.append(f"- `aec add {itype[:-1]} <name>` — install a {itype[:-1]} ({itype}: additive=auto)")
    return "\n".join(lines)


def _format_ask_list(matrix: Dict[str, Dict[str, str]]) -> str:
    lines = []
    for itype in ITEM_TYPES:
        if matrix[itype]["additive"] == "ask":
            lines.append(f"- `aec add {itype[:-1]} <name>` ({itype}: additive=ask)")
    # Destructive always ask
    for cmd in sorted(DESTRUCTIVE_COMMANDS):
        lines.append(f"- `aec {cmd}` — destructive (always ask)")
    return "\n".join(lines)


def _render_body(matrix: Dict[str, Dict[str, str]]) -> str:
    """Render the body content between start and end markers (excluding markers)."""
    tmpl = _read_template()
    return (
        tmpl
        .replace("{{AUTO_LIST}}", _format_auto_list(matrix))
        .replace("{{ASK_LIST}}", _format_ask_list(matrix))
    )


def content_hash_of(inner_body: str) -> str:
    return sha256_short(inner_body)


def render_block(
    scope: str, profile: str, matrix: Dict[str, Dict[str, str]], aec_version: str
) -> str:
    """Render the full block including start/end markers.

    The start marker contains: block-version, schema, aec version,
    template-hash, content-hash, profile, scope.
    """
    inner = _render_body(matrix)
    tmpl_hash = shipped_template_hash()
    content_hash = content_hash_of(inner)
    start = (
        f"{START_MARKER_PREFIX} {BLOCK_VERSION} "
        f"schema={SCHEMA_VERSION} aec={aec_version} "
        f"template-hash={tmpl_hash} content-hash={content_hash} "
        f"profile={profile} scope={scope} -->"
    )
    return f"{start}\n{inner}\n{END_MARKER}\n"


def extract_inner_body(block: str) -> str:
    """Given a full rendered block, return just the body between markers.

    Used to verify content-hash claims and for hashing on-disk blocks.
    """
    lines = block.splitlines()
    try:
        start_idx = next(i for i, ln in enumerate(lines) if ln.startswith(START_MARKER_PREFIX))
        end_idx = next(i for i, ln in enumerate(lines) if ln.strip() == END_MARKER)
    except StopIteration:
        raise ValueError("Block is missing start or end marker")
    return "\n".join(lines[start_idx + 1:end_idx])
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_render.py -v`

- [ ] **Step 5: Commit**

```bash
git add aec/lib/agent_blurb/templates/ aec/lib/agent_blurb/render.py tests/lib/agent_blurb/test_render.py
git commit -m "feat(agent-blurb): add deterministic renderer with hashed markers"
```

---

## Task 5: Marker parsing — locate / extract / replace block in agent files

**Files:**
- Create: `aec/lib/agent_blurb/markers.py`
- Create: `tests/lib/agent_blurb/test_markers.py`

- [ ] **Step 1: Write failing test**

```python
# tests/lib/agent_blurb/test_markers.py
"""Tests for finding/replacing the blurb block inside agent files."""

import pytest

from aec.lib.agent_blurb.markers import (
    find_block,
    replace_block,
    BlockNotFoundError,
    MalformedBlockError,
)


CLEAN_FILE_NO_BLOCK = """# CLAUDE.md

Some user content.

More content here.
"""

CLEAN_FILE_WITH_BLOCK = """# CLAUDE.md

Some user content.

<!-- aec-blurb:start v1 schema=1 aec=2.37.4 template-hash=abc content-hash=def profile=balanced scope=project -->
Body content
across lines
<!-- aec-blurb:end -->

After the block.
"""

DUPLICATE_START = """# CLAUDE.md
<!-- aec-blurb:start v1 ... -->
body
<!-- aec-blurb:end -->
<!-- aec-blurb:start v1 ... -->
body2
<!-- aec-blurb:end -->
"""

MISSING_END = """# CLAUDE.md
<!-- aec-blurb:start v1 ... -->
body, never ends
"""


class TestFindBlock:
    def test_no_block_returns_none(self):
        assert find_block(CLEAN_FILE_NO_BLOCK) is None

    def test_finds_existing_block(self):
        loc = find_block(CLEAN_FILE_WITH_BLOCK)
        assert loc is not None
        block = CLEAN_FILE_WITH_BLOCK[loc.start:loc.end]
        assert block.startswith("<!-- aec-blurb:start")
        assert block.rstrip().endswith("<!-- aec-blurb:end -->")

    def test_duplicate_start_raises(self):
        with pytest.raises(MalformedBlockError, match="duplicate"):
            find_block(DUPLICATE_START)

    def test_missing_end_raises(self):
        with pytest.raises(MalformedBlockError, match="missing end"):
            find_block(MISSING_END)


class TestReplaceBlock:
    def test_replace_existing(self):
        new_block = "<!-- aec-blurb:start v1 NEW -->\nnew body\n<!-- aec-blurb:end -->\n"
        result = replace_block(CLEAN_FILE_WITH_BLOCK, new_block)
        assert "Body content" not in result
        assert "new body" in result
        # Surrounding content preserved
        assert "Some user content." in result
        assert "After the block." in result

    def test_append_when_missing(self):
        new_block = "<!-- aec-blurb:start v1 NEW -->\nnew body\n<!-- aec-blurb:end -->\n"
        result = replace_block(CLEAN_FILE_NO_BLOCK, new_block)
        assert "new body" in result
        # Original content preserved
        assert "Some user content." in result
        # Appended at end with separating newline
        assert result.endswith(new_block)

    def test_replace_does_not_corrupt_surrounding(self):
        new_block = "<!-- aec-blurb:start v1 X -->\nx\n<!-- aec-blurb:end -->\n"
        result = replace_block(CLEAN_FILE_WITH_BLOCK, new_block)
        lines = result.splitlines()
        assert "# CLAUDE.md" in lines
        assert "After the block." in lines
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_markers.py -v`

- [ ] **Step 3: Implement**

```python
# aec/lib/agent_blurb/markers.py
"""Find / replace the agent-blurb block inside agent instruction files.

The block is delimited by:
  <!-- aec-blurb:start ... -->
  ...
  <!-- aec-blurb:end -->

Surrounding user content is never modified.
"""

from dataclasses import dataclass
from typing import Optional

from aec.lib.agent_blurb.render import START_MARKER_PREFIX, END_MARKER


class BlockNotFoundError(Exception):
    pass


class MalformedBlockError(Exception):
    pass


@dataclass
class BlockLocation:
    start: int  # index of '<' of start marker
    end: int    # index just after newline following end marker


def find_block(content: str) -> Optional[BlockLocation]:
    """Locate a single well-formed block. Raises MalformedBlockError on duplicates
    or unclosed blocks. Returns None if no block exists.
    """
    starts = []
    pos = 0
    while True:
        idx = content.find(START_MARKER_PREFIX, pos)
        if idx == -1:
            break
        starts.append(idx)
        pos = idx + 1
    if not starts:
        return None
    if len(starts) > 1:
        raise MalformedBlockError(f"duplicate aec-blurb start markers at offsets {starts}")
    start = starts[0]
    end_idx = content.find(END_MARKER, start)
    if end_idx == -1:
        raise MalformedBlockError("aec-blurb start found but missing end marker")
    end = end_idx + len(END_MARKER)
    # Include the trailing newline if present, so replacement is clean
    if end < len(content) and content[end] == "\n":
        end += 1
    return BlockLocation(start=start, end=end)


def replace_block(content: str, new_block: str) -> str:
    """Replace the existing block with new_block, or append if none exists.

    `new_block` must end with a newline.
    """
    loc = find_block(content)
    if loc is None:
        if content and not content.endswith("\n"):
            content += "\n"
        if content and not content.endswith("\n\n"):
            content += "\n"
        return content + new_block
    return content[:loc.start] + new_block + content[loc.end:]
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_markers.py -v`

- [ ] **Step 5: Commit**

```bash
git add aec/lib/agent_blurb/markers.py tests/lib/agent_blurb/test_markers.py
git commit -m "feat(agent-blurb): add block markers with malformed-input guards"
```

---

## Task 6: Drift detection state machine

**Files:**
- Create: `aec/lib/agent_blurb/drift.py`
- Create: `tests/lib/agent_blurb/test_drift.py`

- [ ] **Step 1: Write failing test**

```python
# tests/lib/agent_blurb/test_drift.py
"""Tests for drift detection (spec §6.1)."""

import pytest

from aec.lib.agent_blurb.drift import DriftState, compute_drift


class TestCompute:
    def test_not_installed_when_marker_missing(self):
        state = compute_drift(
            on_disk_content="# CLAUDE.md\n",
            stored_template_hash=None,
            stored_content_hash=None,
            shipped_template_hash="abc",
        )
        assert state == DriftState.NOT_INSTALLED

    def test_clean_when_all_match(self):
        state = compute_drift(
            on_disk_content=_make_block(template="abc", content="def"),
            stored_template_hash="abc",
            stored_content_hash="def",
            shipped_template_hash="abc",
        )
        assert state == DriftState.CLEAN

    def test_upstream_update_when_template_changed(self):
        state = compute_drift(
            on_disk_content=_make_block(template="OLD", content="def"),
            stored_template_hash="OLD",
            stored_content_hash="def",
            shipped_template_hash="NEW",
        )
        assert state == DriftState.UPSTREAM_UPDATE

    def test_manual_edit_when_on_disk_differs(self):
        state = compute_drift(
            on_disk_content=_make_block(template="abc", content="EDITED"),
            stored_template_hash="abc",
            stored_content_hash="def",
            shipped_template_hash="abc",
        )
        assert state == DriftState.MANUAL_EDIT

    def test_conflict_when_both_changed(self):
        state = compute_drift(
            on_disk_content=_make_block(template="OLD", content="EDITED"),
            stored_template_hash="OLD",
            stored_content_hash="def",
            shipped_template_hash="NEW",
        )
        assert state == DriftState.CONFLICT


def _make_block(template: str, content: str) -> str:
    return (
        f"<!-- aec-blurb:start v1 schema=1 aec=2.37.4 "
        f"template-hash={template} content-hash={content} "
        f"profile=balanced scope=project -->\n"
        f"body\n"
        f"<!-- aec-blurb:end -->\n"
    )
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_drift.py -v`

- [ ] **Step 3: Implement**

```python
# aec/lib/agent_blurb/drift.py
"""Drift detection between shipped template, stored config, and on-disk content.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §6.
"""

import re
from enum import Enum
from typing import Optional

from aec.lib.agent_blurb.markers import find_block


class DriftState(str, Enum):
    CLEAN = "clean"
    NOT_INSTALLED = "not_installed"
    UPSTREAM_UPDATE = "upstream_update"
    MANUAL_EDIT = "manual_edit"
    CONFLICT = "conflict"


_MARKER_RE = re.compile(
    r"template-hash=([a-f0-9]+).*?content-hash=([a-f0-9]+)",
    re.DOTALL,
)


def _extract_hashes(on_disk_block: str) -> tuple[Optional[str], Optional[str]]:
    m = _MARKER_RE.search(on_disk_block)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def compute_drift(
    on_disk_content: str,
    stored_template_hash: Optional[str],
    stored_content_hash: Optional[str],
    shipped_template_hash: str,
) -> DriftState:
    """Compute drift state from the three signals."""
    try:
        loc = find_block(on_disk_content)
    except Exception:
        return DriftState.CONFLICT  # malformed -> treat as conflict
    if loc is None or stored_template_hash is None or stored_content_hash is None:
        return DriftState.NOT_INSTALLED

    block = on_disk_content[loc.start:loc.end]
    on_disk_tmpl, on_disk_content_hash = _extract_hashes(block)

    template_changed = shipped_template_hash != stored_template_hash
    edited_on_disk = on_disk_content_hash != stored_content_hash

    if not template_changed and not edited_on_disk:
        return DriftState.CLEAN
    if template_changed and not edited_on_disk:
        return DriftState.UPSTREAM_UPDATE
    if not template_changed and edited_on_disk:
        return DriftState.MANUAL_EDIT
    return DriftState.CONFLICT
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_drift.py -v`

- [ ] **Step 5: Commit**

```bash
git add aec/lib/agent_blurb/drift.py tests/lib/agent_blurb/test_drift.py
git commit -m "feat(agent-blurb): add five-state drift detector"
```

---

## Task 7: Target discovery — which agent files exist per scope

**Files:**
- Create: `aec/lib/agent_blurb/targets.py`
- Create: `tests/lib/agent_blurb/test_targets.py`

- [ ] **Step 1: Read existing code**

Before implementing, read `aec/lib/agent_files.py` and `aec/lib/configurable_instructions.py:get_agent_global_file` / `get_agent_project_file` to understand how agent file paths are resolved from `agents.json`. Reuse those helpers; do NOT duplicate.

- [ ] **Step 2: Write failing test**

```python
# tests/lib/agent_blurb/test_targets.py
"""Tests for discovering which agent files exist per scope."""

import pytest
from pathlib import Path

from aec.lib.agent_blurb.targets import discover_targets, AgentTarget


class TestDiscoverTargets:
    def test_project_scope_only_returns_existing(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# c\n")
        (tmp_path / "AGENTS.md").write_text("# a\n")
        targets = discover_targets(scope="project", root=tmp_path)
        paths = {t.path.name for t in targets}
        assert "CLAUDE.md" in paths
        assert "AGENTS.md" in paths
        assert "GEMINI.md" not in paths  # not created

    def test_global_scope(self, mock_home):
        # mock_home is a tmpdir set as Path.home()
        claude_dir = mock_home / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("# g\n")
        targets = discover_targets(scope="global")
        paths = [str(t.path) for t in targets]
        assert str(claude_dir / "CLAUDE.md") in paths

    def test_empty_when_no_files(self, tmp_path):
        targets = discover_targets(scope="project", root=tmp_path)
        assert targets == []

    def test_target_has_agent_key(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# c\n")
        targets = discover_targets(scope="project", root=tmp_path)
        assert targets[0].agent_key == "claude-code"


class TestResolvePathForAgentKey:
    def test_project(self, tmp_path):
        from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
        # Project scope resolution returns the would-be path even if not on disk.
        p = resolve_path_for_agent_key("claude-code", scope="project", root=tmp_path)
        assert p == tmp_path / "CLAUDE.md"

    def test_global(self, mock_home):
        from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
        p = resolve_path_for_agent_key("claude-code", scope="global")
        assert mock_home in p.parents or p.is_relative_to(mock_home)

    def test_unknown_agent_raises(self, tmp_path):
        from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
        with pytest.raises(KeyError):
            resolve_path_for_agent_key("not-a-real-agent", scope="project", root=tmp_path)
```

- [ ] **Step 3: Verify failure**

Run: `pytest tests/lib/agent_blurb/test_targets.py -v`

- [ ] **Step 4: Implement**

```python
# aec/lib/agent_blurb/targets.py
"""Discover which agent files exist on disk for a given scope."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from aec.lib.configurable_instructions import (
    get_agent_global_file,
    get_agent_project_file,
)
from aec.lib.registry import load_agent_registry


@dataclass
class AgentTarget:
    agent_key: str
    path: Path


def discover_targets(scope: str, root: Optional[Path] = None) -> List[AgentTarget]:
    """Return all existing agent files for the scope, in registry order."""
    registry = load_agent_registry()
    out: List[AgentTarget] = []
    for agent_key in registry.get("agents", {}).keys():
        path = resolve_path_for_agent_key(agent_key, scope=scope, root=root)
        if path and path.exists():
            out.append(AgentTarget(agent_key=agent_key, path=path))
    return out


def resolve_path_for_agent_key(
    agent_key: str, scope: str, root: Optional[Path] = None,
) -> Path:
    """Return the canonical file path for an agent_key in a scope.

    Used both at discovery time (to find existing files) and at refresh/check
    time (to round-trip a TargetRecord back to an absolute path even if the
    file has been moved or recreated).

    Raises KeyError if the agent_key is unknown to the registry.
    """
    registry = load_agent_registry()
    if agent_key not in registry.get("agents", {}):
        raise KeyError(f"Unknown agent_key: {agent_key!r}")
    if scope == "project":
        if root is None:
            raise ValueError("project scope requires root")
        return get_agent_project_file(agent_key, root)
    if scope == "global":
        return get_agent_global_file(agent_key)
    raise ValueError(f"Unknown scope: {scope!r}")
```

- [ ] **Step 5: Verify pass**

Run: `pytest tests/lib/agent_blurb/test_targets.py -v`

If `get_agent_project_file` doesn't exist with the expected signature, read its actual signature first and adapt the call site.

- [ ] **Step 6: Commit**

```bash
git add aec/lib/agent_blurb/targets.py tests/lib/agent_blurb/test_targets.py
git commit -m "feat(agent-blurb): discover detected agent files per scope"
```

---

## Task 8: `aec configure-agent` CLI command (interactive + flags)

**Files:**
- Create: `aec/commands/configure_agent.py`
- Modify: `aec/cli.py` (register the typer command)
- Create: `tests/commands/test_configure_agent.py`

This is the largest task — split into sub-steps.

- [ ] **Step 1: Read existing patterns**

Read `aec/commands/install_cmd.py`, `aec/commands/doctor.py`, and `aec/commands/config_cmd.py` to mirror prompt style, exit codes, and how typer commands are registered in `aec/cli.py`.

- [ ] **Step 2: Write failing test (non-interactive flags first)**

```python
# tests/commands/test_configure_agent.py
"""End-to-end tests for `aec configure-agent`.

Real-filesystem; no mocks of internals. Per project standards.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec.cli import app
from aec.lib.agent_blurb.config import load_config
from aec.lib.agent_blurb.markers import find_block


runner = CliRunner()


@pytest.fixture
def project_with_agent_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\n\nuser content\n")
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\n")
    return tmp_path


class TestRefreshFlag:
    def test_check_exits_nonzero_when_no_config(self, project_with_agent_files):
        result = runner.invoke(app, ["configure-agent", "--check"])
        assert result.exit_code != 0

    def test_dry_run_writes_nothing(self, project_with_agent_files, monkeypatch):
        monkeypatch.setenv("AEC_NONINTERACTIVE", "1")
        result = runner.invoke(
            app,
            ["configure-agent",
             "--scope", "project",
             "--profile", "balanced",
             "--agent-files", "all",
             "--dry-run"],
        )
        assert result.exit_code == 0
        # No file written
        assert not (project_with_agent_files / ".aec" / "agent-blurb.json").exists()

    def test_install_writes_config_and_block(self, project_with_agent_files):
        result = runner.invoke(
            app,
            ["configure-agent",
             "--scope", "project",
             "--profile", "balanced",
             "--agent-files", "all",
             "--yes"],
        )
        assert result.exit_code == 0, result.output
        cfg = load_config(scope="project", root=project_with_agent_files)
        assert cfg is not None
        assert cfg["profile"] == "balanced"
        # Block present in CLAUDE.md
        content = (project_with_agent_files / "CLAUDE.md").read_text()
        assert find_block(content) is not None
        # User content preserved
        assert "user content" in content


class TestIdempotency:
    def test_refresh_twice_byte_identical(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        first = (project_with_agent_files / "CLAUDE.md").read_text()
        runner.invoke(app, ["configure-agent", "--refresh", "--scope", "project"])
        second = (project_with_agent_files / "CLAUDE.md").read_text()
        assert first == second


class TestRemove:
    def test_remove_strips_block_preserves_content(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        result = runner.invoke(app, ["configure-agent", "--remove",
                                     "--scope", "project", "--yes"])
        assert result.exit_code == 0
        content = (project_with_agent_files / "CLAUDE.md").read_text()
        assert find_block(content) is None
        assert "user content" in content
        assert not (project_with_agent_files / ".aec" / "agent-blurb.json").exists()


class TestCheckAfterInstall:
    def test_check_clean_after_install(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        result = runner.invoke(app, ["configure-agent", "--check", "--scope", "project"])
        assert result.exit_code == 0

    def test_check_detects_manual_edit(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        # Hand-edit inside the block
        p = project_with_agent_files / "CLAUDE.md"
        text = p.read_text()
        edited = text.replace("you may run", "YOU SHALL RUN")  # touch body
        p.write_text(edited)
        if edited != text:
            result = runner.invoke(app, ["configure-agent", "--check", "--scope", "project"])
            assert result.exit_code != 0
            assert "manual" in result.output.lower() or "drift" in result.output.lower()
```

- [ ] **Step 3: Verify failure**

Run: `pytest tests/commands/test_configure_agent.py -v`

- [ ] **Step 4: Implement the command**

Build incrementally. The command supports these modes:
- Interactive (no flags): scope multi-select, agent-file all-or-pick, profile prompt(s), confirmation
- `--check` (CI mode, non-interactive): exit nonzero on any non-clean drift
- `--refresh` (non-interactive): re-render from existing config
- `--remove` (interactive unless `--yes`): strip block and delete config
- `--dry-run`: print plan, write nothing
- `--scope project|global|both`, `--profile <name>`, `--agent-files all|<csv>`, `--yes`

```python
# aec/commands/configure_agent.py
"""`aec configure-agent` — write/refresh/remove the agent blurb block."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

from aec import __version__
from aec.lib.agent_blurb.config import (
    load_config, save_config, new_skeleton, config_path,
)
from aec.lib.agent_blurb.decline import record_decline
from aec.lib.agent_blurb.drift import DriftState, compute_drift
from aec.lib.agent_blurb.markers import find_block, replace_block
from aec.lib.agent_blurb.profile import PROFILES, DEFAULT_PROFILE
from aec.lib.agent_blurb.render import (
    render_block, shipped_template_hash, sha256_short, extract_inner_body,
)
from aec.lib.agent_blurb.targets import discover_targets, AgentTarget
from aec.lib.atomic_write import atomic_write_text
from aec.lib.console import Console


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_scopes(scope: Optional[str], interactive: bool) -> List[str]:
    if scope == "both":
        return ["project", "global"]
    if scope in ("project", "global"):
        return [scope]
    if not interactive:
        raise typer.BadParameter("--scope is required in non-interactive mode")
    # interactive prompts: see prompt_scopes below
    return _prompt_scopes()


def _prompt_scopes() -> List[str]:
    in_repo = Path.cwd().joinpath(".git").exists()  # crude; replace with scope.find_tracked_repo
    default = "project" if in_repo else "global"
    typer.echo("Where to install the blurb?")
    typer.echo("  1) project context")
    typer.echo("  2) global context")
    typer.echo("  3) both")
    raw = typer.prompt(f"Select (default: {default})", default=default)
    if raw in ("1", "project"):
        return ["project"]
    if raw in ("2", "global"):
        return ["global"]
    if raw in ("3", "both"):
        return ["project", "global"]
    raise typer.BadParameter(f"Invalid scope: {raw}")


def _prompt_profile() -> str:
    typer.echo("Choose a profile:")
    for name in ("conservative", "balanced", "permissive", "custom"):
        marker = " (default)" if name == DEFAULT_PROFILE else ""
        typer.echo(f"  - {name}{marker}")
    raw = typer.prompt("profile", default=DEFAULT_PROFILE)
    if raw not in PROFILES and raw != "custom":
        raise typer.BadParameter(f"Unknown profile: {raw}")
    return raw


def _resolve_targets(
    scope: str, root: Optional[Path], agent_files: Optional[str],
    interactive: bool = False,
) -> List[AgentTarget]:
    """Resolve the list of targets for a scope.

    Selection precedence:
      1. `agent_files == "all"` or no flag in non-interactive mode → all detected
      2. `agent_files` csv (file basenames or agent_keys) → filtered
      3. Interactive + no flag → prompt with "All / Let me choose" then
         multi-select checklist (spec §3.2).
    """
    detected = discover_targets(scope=scope, root=root)
    if agent_files == "all":
        return detected
    if agent_files:
        wanted = {x.strip() for x in agent_files.split(",")}
        return [t for t in detected if t.path.name in wanted or t.agent_key in wanted]
    if not interactive:
        return detected
    return _prompt_agent_files(detected)


def _prompt_agent_files(detected: List[AgentTarget]) -> List[AgentTarget]:
    """Interactive picker per spec §3.2: All / Let me choose."""
    typer.echo("Apply blurb to which agent files?")
    typer.echo("  1) All detected")
    typer.echo("  2) Let me choose")
    raw = typer.prompt("Select", default="1")
    if raw in ("1", "all"):
        return detected
    selected: List[AgentTarget] = []
    typer.echo("Pick targets (y/n for each):")
    for t in detected:
        if typer.confirm(f"  include {t.path.name} ({t.agent_key})?", default=True):
            selected.append(t)
    return selected


def _scope_root(scope: str) -> Path:
    """Resolve the root for a scope. Project = cwd; global = $HOME."""
    return Path.cwd() if scope == "project" else Path.home()


def _relpath_for(target: AgentTarget, scope: str) -> str:
    """Stable relative path from the scope root for round-trip storage."""
    return str(target.path.relative_to(_scope_root(scope)))


def _resolve_target_path(record: dict, scope: str,
                         root: Optional[Path] = None) -> Path:
    """Resolve a stored TargetRecord back to an absolute path.

    Preferred path: use agent_key + scope to call into the targets module,
    falling back to <scope_root>/<path> for legacy records missing agent_key.
    `root` is required for project scope (passed through to the targets module).
    """
    from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
    project_root = root if scope == "project" else None
    if record.get("agent_key"):
        return resolve_path_for_agent_key(
            record["agent_key"], scope=scope, root=project_root,
        )
    base = project_root if scope == "project" else Path.home()
    return base / record["path"]


def _write_target(target: AgentTarget, block: str, content_hash: str,
                  tmpl_hash: str, scope: str) -> dict:
    original = target.path.read_text(encoding="utf-8")
    new_content = replace_block(original, block)
    atomic_write_text(target.path, new_content)
    return {
        "agent_key": target.agent_key,
        "path": _relpath_for(target, scope),
        "template_hash": tmpl_hash,
        "content_hash": content_hash,
        "written_at": _now_iso(),
    }


def _check_drift_for_scope(scope: str, root: Optional[Path]) -> int:
    cfg = load_config(scope=scope, root=root)
    if cfg is None:
        Console.error(f"No blurb config for scope={scope}")
        return 2
    shipped = shipped_template_hash()
    exit_code = 0
    for t in cfg.get("targets", []):
        target_path = _resolve_target_path(t, scope=scope, root=root)
        if not target_path.exists():
            Console.warn(f"Target missing: {target_path}")
            exit_code = max(exit_code, 1)
            continue
        on_disk = target_path.read_text(encoding="utf-8")
        state = compute_drift(
            on_disk_content=on_disk,
            stored_template_hash=t["template_hash"],
            stored_content_hash=t["content_hash"],
            shipped_template_hash=shipped,
        )
        if state == DriftState.CLEAN:
            Console.success(f"{target_path}: clean")
        else:
            Console.warn(f"{target_path}: {state.value}")
            exit_code = max(exit_code, 1)
    return exit_code


def run_configure_agent(
    scope: Optional[str],
    profile: Optional[str],
    agent_files: Optional[str],
    check: bool,
    refresh: bool,
    remove: bool,
    dry_run: bool,
    yes: bool,
) -> int:
    """Main dispatch. Returns shell exit code."""
    if check:
        scopes = ["project", "global"] if scope in (None, "both") else [scope]
        rc = 0
        for s in scopes:
            root = Path.cwd() if s == "project" else None
            rc = max(rc, _check_drift_for_scope(s, root))
        return rc

    interactive = not (yes or refresh or remove)
    scopes = _resolve_scopes(scope, interactive)

    if remove:
        return _do_remove(scopes, yes=yes)

    if refresh:
        return _do_refresh(scopes, yes=yes)

    # Per-scope profile prompting (spec §3.3): each scope gets its own choice
    # unless a CLI --profile is supplied (which then applies to every scope).
    scope_profiles = {}
    for s in scopes:
        if profile is not None:
            scope_profiles[s] = profile
        elif interactive:
            Console.info(f"Profile for scope={s}:")
            scope_profiles[s] = _prompt_profile()
        else:
            scope_profiles[s] = DEFAULT_PROFILE

    return _do_install(
        scopes=scopes,
        scope_profiles=scope_profiles,
        agent_files=agent_files,
        dry_run=dry_run,
        yes=yes,
        interactive=interactive,
    )


def _do_install(scopes, scope_profiles, agent_files, dry_run, yes, interactive) -> int:
    for s in scopes:
        root = Path.cwd() if s == "project" else None
        profile = scope_profiles[s]
        targets = _resolve_targets(s, root, agent_files, interactive=interactive)
        if not targets:
            Console.warn(f"No agent files detected for scope={s}; skipping")
            continue
        cfg = new_skeleton(scope=s, profile=profile, aec_version=__version__)
        if dry_run:
            Console.info(f"[dry-run] would write to: {[str(t.path) for t in targets]}")
            continue
        if not yes:
            Console.info(f"About to write to: {[str(t.path) for t in targets]}")
            if not typer.confirm("Proceed?", default=True):
                Console.info("Aborted.")
                return 1
        block = render_block(scope=s, profile=profile, matrix=cfg["matrix"],
                             aec_version=__version__)
        tmpl_hash = shipped_template_hash()
        content_hash = sha256_short(extract_inner_body(block))
        for t in targets:
            record = _write_target(t, block, content_hash, tmpl_hash, scope=s)
            cfg["targets"].append(record)
        save_config(cfg, scope=s, root=root)
        Console.success(f"Blurb installed for scope={s}")
    return 0


def _do_refresh(scopes, yes: bool = False) -> int:
    """Re-render the blurb from stored config.

    Per spec §6.2: never silently overwrite manual edits. Before writing each
    target, compute drift; on MANUAL_EDIT or CONFLICT, require --yes or an
    interactive confirmation. UPSTREAM_UPDATE proceeds without prompt (that
    is the whole point of refresh).
    """
    shipped = shipped_template_hash()
    for s in scopes:
        root = Path.cwd() if s == "project" else None
        cfg = load_config(scope=s, root=root)
        if cfg is None:
            Console.warn(f"No config for scope={s}; skipping")
            continue
        block = render_block(scope=s, profile=cfg["profile"],
                             matrix=cfg["matrix"], aec_version=__version__)
        tmpl_hash = shipped_template_hash()
        content_hash = sha256_short(extract_inner_body(block))
        new_targets = []
        for t in cfg["targets"]:
            target_path = _resolve_target_path(t, scope=s, root=root)
            if not target_path.exists():
                Console.warn(f"Skipping missing target: {target_path}")
                continue
            original = target_path.read_text(encoding="utf-8")
            state = compute_drift(
                on_disk_content=original,
                stored_template_hash=t["template_hash"],
                stored_content_hash=t["content_hash"],
                shipped_template_hash=shipped,
            )
            if state in (DriftState.MANUAL_EDIT, DriftState.CONFLICT):
                Console.warn(f"{target_path}: {state.value} — refresh would overwrite local edits")
                if not yes and not typer.confirm("Overwrite?", default=False):
                    Console.info(f"Skipped {target_path}")
                    new_targets.append(t)  # preserve old record untouched
                    continue
            atomic_write_text(target_path, replace_block(original, block))
            new_targets.append({**t, "template_hash": tmpl_hash,
                                "content_hash": content_hash,
                                "written_at": _now_iso()})
        cfg["targets"] = new_targets
        cfg["aec_version_last_write"] = __version__
        save_config(cfg, scope=s, root=root)
        Console.success(f"Refreshed scope={s}")
    return 0


def _do_remove(scopes, yes: bool) -> int:
    for s in scopes:
        root = Path.cwd() if s == "project" else None
        cfg = load_config(scope=s, root=root)
        if cfg is None:
            Console.info(f"No config for scope={s}; nothing to remove")
            continue
        if not yes and not typer.confirm(
                f"Remove blurb from {len(cfg['targets'])} files in scope={s}?",
                default=False):
            continue
        for t in cfg["targets"]:
            target_path = _resolve_target_path(t, scope=s, root=root)
            if not target_path.exists():
                continue
            original = target_path.read_text(encoding="utf-8")
            loc = find_block(original)
            if loc:
                atomic_write_text(target_path, original[:loc.start] + original[loc.end:])
        path = config_path(scope=s, root=root)
        if path.exists():
            path.unlink()
        Console.success(f"Removed blurb for scope={s}")
    return 0
```

- [ ] **Step 5: Register in `aec/cli.py`**

Add (right after another `@app.command(...)`):

```python
@app.command("configure-agent")
def configure_agent_cmd(
    scope: Optional[str] = typer.Option(None, "--scope", help="project|global|both"),
    profile: Optional[str] = typer.Option(None, "--profile", help="conservative|balanced|permissive|custom"),
    agent_files: Optional[str] = typer.Option(None, "--agent-files", help="all|<csv>"),
    check: bool = typer.Option(False, "--check", help="Exit non-zero on drift"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-render from stored config"),
    remove: bool = typer.Option(False, "--remove", help="Remove the blurb and config"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan; write nothing"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
):
    """Manage the AEC agent-instruction blurb."""
    from .commands.configure_agent import run_configure_agent
    raise typer.Exit(run_configure_agent(
        scope=scope, profile=profile, agent_files=agent_files,
        check=check, refresh=refresh, remove=remove, dry_run=dry_run, yes=yes,
    ))
```

- [ ] **Step 6: Verify pass**

Run: `pytest tests/commands/test_configure_agent.py -v`

Iterate on the implementation until all tests pass. Common gotchas:
- `discover_targets` uses `Path.cwd()` for project root; tests use `monkeypatch.chdir(tmp_path)` to redirect.
- All target-path round-tripping goes through `targets.resolve_path_for_agent_key`; never reconstruct paths inline.

- [ ] **Step 7: Run full suite + commit**

```bash
pytest -x
git add aec/commands/configure_agent.py aec/cli.py tests/commands/test_configure_agent.py
git commit -m "feat(agent-blurb): add aec configure-agent CLI with all flags"
```

---

## Task 9: Install/update integration

**Files:**
- Modify: `aec/commands/install_cmd.py`
- Modify: `aec/commands/update.py`
- Modify: `aec/commands/doctor.py`
- Create: `tests/commands/test_install_blurb_prompt.py`
- Create: `tests/commands/test_update_blurb_drift.py`
- Modify: `tests/test_doctor_cmd.py`

- [ ] **Step 1: Read existing install/update flows**

Read `aec/commands/install_cmd.py:run_install` and `aec/commands/update.py:run_update` to find the natural insertion point (after primary action completes, before the trailing summary).

- [ ] **Step 2: Write failing tests**

```python
# tests/commands/test_install_blurb_prompt.py
"""After a successful install, AEC offers the agent-blurb feature unless declined."""

from typer.testing import CliRunner
from aec.cli import app
from aec.lib.agent_blurb.config import load_config


def test_install_offers_blurb_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# c\n")
    # Direct helper call; `accept=True` mimics user saying yes at the prompt.
    from aec.commands.install_cmd import maybe_offer_blurb
    maybe_offer_blurb(root=tmp_path, accept=True)
    assert load_config(scope="project", root=tmp_path) is not None


def test_install_skips_blurb_when_declined(tmp_path):
    from aec.commands.install_cmd import maybe_offer_blurb
    from aec.lib.agent_blurb.decline import record_decline
    record_decline(scope="project", aec_version="2.37.4", root=tmp_path)
    maybe_offer_blurb(root=tmp_path, accept=False)
    assert load_config(scope="project", root=tmp_path) is None
```

```python
# tests/commands/test_update_blurb_drift.py
"""After update, AEC surfaces drift and offers refresh."""

from aec.commands.update import check_blurb_drift
from aec.lib.agent_blurb.config import save_config, new_skeleton


def test_update_reports_no_config_silently(tmp_path):
    # No config -> no output, no error
    result = check_blurb_drift(root=tmp_path)
    assert result == 0


def test_update_reports_upstream_change(tmp_path, monkeypatch):
    cfg = new_skeleton(scope="project", profile="balanced", aec_version="1.0.0")
    cfg["targets"].append({
        "agent_key": "claude",
        "path": "CLAUDE.md", "template_hash": "OLD", "content_hash": "X",
        "written_at": "2026-01-01T00:00:00Z",
    })
    save_config(cfg, scope="project", root=tmp_path)
    (tmp_path / "CLAUDE.md").write_text(
        '<!-- aec-blurb:start v1 schema=1 aec=1.0.0 template-hash=OLD content-hash=X profile=balanced scope=project -->\nbody\n<!-- aec-blurb:end -->\n'
    )
    # shipped template hash != "OLD" -> upstream update
    rc = check_blurb_drift(root=tmp_path)
    assert rc == 0  # informational, non-fatal
```

- [ ] **Step 3: Verify failures**

Run: `pytest tests/commands/test_install_blurb_prompt.py tests/commands/test_update_blurb_drift.py -v`

- [ ] **Step 4: Add helpers**

In `aec/commands/install_cmd.py`, append (after existing `run_install`):

```python
def maybe_offer_blurb(root, accept: bool = False) -> None:
    """Offer the agent-blurb feature if not configured and not declined.

    Called from run_install after successful installation. `accept` short-circuits
    the prompt (used by tests and CI; respect AEC_NONINTERACTIVE env var).
    """
    from aec import __version__
    from aec.lib.agent_blurb.config import load_config
    from aec.lib.agent_blurb.decline import should_reprompt, record_decline
    from aec.commands.configure_agent import run_configure_agent

    if load_config(scope="project", root=root) is not None:
        return  # already configured
    if not should_reprompt(scope="project", current_version=__version__, root=root):
        return  # declined recently

    if not accept:
        # interactive prompt elided here; pseudocode:
        accept = _prompt_yes_no(
            "AEC can add instructions to your agent files. Add now?", default=True,
        )

    if not accept:
        record_decline(scope="project", aec_version=__version__, root=root)
        return

    run_configure_agent(
        scope="project", profile=None, agent_files="all",
        check=False, refresh=False, remove=False, dry_run=False, yes=True,
    )
```

In `aec/commands/update.py`, add:

```python
def check_blurb_drift(root) -> int:
    """Check blurb drift after an update. Informational; returns 0 on success."""
    from aec.lib.agent_blurb.config import load_config
    from aec.lib.agent_blurb.drift import compute_drift, DriftState
    from aec.lib.agent_blurb.render import shipped_template_hash
    from aec.lib.console import Console

    cfg = load_config(scope="project", root=root)
    if cfg is None:
        return 0
    shipped = shipped_template_hash()
    for t in cfg.get("targets", []):
        target_path = root / t["path"]
        if not target_path.exists():
            continue
        state = compute_drift(
            on_disk_content=target_path.read_text(encoding="utf-8"),
            stored_template_hash=t["template_hash"],
            stored_content_hash=t["content_hash"],
            shipped_template_hash=shipped,
        )
        if state == DriftState.UPSTREAM_UPDATE:
            Console.info(f"{target_path}: AEC blurb has a newer template — run "
                         f"`aec configure-agent --refresh` to update.")
        elif state == DriftState.MANUAL_EDIT:
            Console.warn(f"{target_path}: blurb has been hand-edited.")
        elif state == DriftState.CONFLICT:
            Console.warn(f"{target_path}: blurb conflict (upstream + local edits).")
    return 0
```

Then wire `maybe_offer_blurb` into `run_install` (call it once at the end) and `check_blurb_drift` into `run_update`.

In `aec/commands/doctor.py`, in the function that prints health output, add a section that calls `_check_drift_for_scope` from `configure_agent` (or a refactored helper) and prints the result.

- [ ] **Step 5: Verify pass**

Run: `pytest -x tests/commands/`

- [ ] **Step 6: Commit**

```bash
git add aec/commands/install_cmd.py aec/commands/update.py aec/commands/doctor.py \
        tests/commands/test_install_blurb_prompt.py tests/commands/test_update_blurb_drift.py \
        tests/test_doctor_cmd.py
git commit -m "feat(agent-blurb): integrate into install/update/doctor flows"
```

---

## Task 10: QA verification doc + final sweep

**Files:**
- Modify: `docs/qa-verification.md`
- Run: full test suite + coverage gate

- [ ] **Step 1: Read existing qa-verification.md structure**

Check the existing format; add a new section that matches.

- [ ] **Step 2: Add verification section**

Append to `docs/qa-verification.md`:

```markdown
## Agent Blurb (`aec configure-agent`)

### Install-time prompt
1. In a fresh repo with a `CLAUDE.md`, run `aec install skill foo` (any installable).
2. Verify prompt offers to add agent blurb. Accept.
3. Verify `<repo>/.aec/agent-blurb.json` is created.
4. Verify `CLAUDE.md` contains an `<!-- aec-blurb:start ... -->` block with valid hashes.

### Drift detection (each of the 5 states)
1. **clean** — immediately after install, run `aec configure-agent --check`; exit 0.
2. **not_installed** — delete `.aec/agent-blurb.json` and run `--check`; exit non-zero.
3. **upstream_update** — manually edit the stored `template_hash` in `.aec/agent-blurb.json` to a bogus value; `--check` reports upstream update.
4. **manual_edit** — hand-edit text inside the block in `CLAUDE.md`; `--check` reports manual edit.
5. **conflict** — combine 3 and 4; `--check` reports conflict.

### Refresh idempotency
1. Run `aec configure-agent --refresh` twice.
2. Verify the second run produces no diff in `CLAUDE.md`.

### Remove
1. Run `aec configure-agent --remove --yes`.
2. Verify block is gone from `CLAUDE.md`, surrounding user content preserved.
3. Verify `.aec/agent-blurb.json` is deleted.

### Both-scope install
1. Run `aec configure-agent --scope both --profile balanced --agent-files all --yes`.
2. Verify both `<repo>/.aec/agent-blurb.json` and `~/.aec/agent-blurb.json` exist.

### Decline persistence
1. On first prompt, decline.
2. Run another `aec install` — verify no prompt.
3. Bump AEC major version (e.g., locally edit `aec/__init__.py` `__version__`).
4. Run another `aec install` — verify prompt returns.
```

- [ ] **Step 3: Add contract test — every rendered command exists in `aec --help`**

Create `tests/lib/agent_blurb/test_render_contract.py`:

```python
"""Spec §10.3: every command name listed in the blurb must exist in aec --help.

Prevents drift between the renderer's command vocabulary and the actual CLI.
"""

import re
import subprocess

from aec.lib.agent_blurb.profile import (
    READ_ONLY_COMMANDS, ADDITIVE_COMMANDS, DESTRUCTIVE_COMMANDS,
)


def _aec_commands() -> set[str]:
    out = subprocess.run(
        ["aec", "--help"], check=True, capture_output=True, text=True,
    ).stdout
    # Typer help lists commands one per line, e.g. "  install   Install ..."
    cmds: set[str] = set()
    for line in out.splitlines():
        m = re.match(r"^\s{2,}([a-z][a-z0-9-]+)\s{2,}", line)
        if m:
            cmds.add(m.group(1))
    return cmds


def test_every_classified_command_is_real():
    real = _aec_commands()
    classified = READ_ONLY_COMMANDS | ADDITIVE_COMMANDS | DESTRUCTIVE_COMMANDS
    missing = classified - real
    # `untrack` etc. may legitimately not yet exist — but the spec says all
    # commands the blurb names MUST be real. Fail loudly on drift.
    assert not missing, f"Classified commands missing from `aec --help`: {missing}"
```

Run: `pytest tests/lib/agent_blurb/test_render_contract.py -v`
Expected: PASS. If it fails, either add the missing command, remove it from
the classifier set, or mark the test xfail with a tracked plan file (no
silent patch).

- [ ] **Step 4: Run full test suite**

```bash
pytest
```

Expected: all tests pass, coverage ≥ 65%.

- [ ] **Step 5: Run repo's existing checks**

```bash
python3 scripts/audit-project-rules.py
python3 scripts/validate-rule-parity.py
```

- [ ] **Step 6: Commit final touches**

```bash
git add docs/qa-verification.md tests/lib/agent_blurb/test_render_contract.py
git commit -m "docs(qa): add agent-blurb verification checklist and contract test"
```

- [ ] **Step 7: Push branch and open PR**

```bash
git push -u origin <branch-name>
gh pr create --title "feat(agent-blurb): aec configure-agent with versioned, hashed blurb" --body "$(cat <<'EOF'
## Summary
- Adds `aec configure-agent` per spec `docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md`.
- Versioned, hashed, consent-gated instruction block in agent files.
- Integrates into `aec install`, `aec update`, `aec doctor`.

## Test plan
- [ ] `pytest` passes (coverage ≥ 65%)
- [ ] Manual verification via `docs/qa-verification.md` § Agent Blurb
- [ ] Install-time prompt offered when missing
- [ ] Decline persistence across runs (until major version bump)
- [ ] All 5 drift states report correctly
- [ ] Refresh is idempotent

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Done criteria

- All 10 tasks committed individually.
- `pytest` passes with coverage ≥ 65%.
- `aec configure-agent --help`, `aec configure-agent --check`, `aec configure-agent --refresh`, `aec configure-agent --remove`, `aec configure-agent --dry-run` all behave per spec.
- `aec install` offers the feature when missing; respects decline.
- `aec update` surfaces drift; never silently overwrites manual edits.
- `aec doctor` surfaces drift state.
- `docs/qa-verification.md` includes the new section.

## Out of scope reminders (do not implement)

- Enforcement layer / hook that blocks ask-first commands at runtime.
- Org-defined profile defaults via overlay (spec §13.4 — future).
- Per-agent (Claude vs. Cursor) profile differentiation.
- Sourcing the read-only command list from `aec` introspection (spec §13.3 — v2).
- File locking on `.aec/agent-blurb.json` for concurrent invocations (spec §9 — accepted risk in v1; atomic_write_text guarantees no partial files but not last-writer-wins protection).
- Matrix evolution prompts on `aec update` when a new item type is added (spec §7.3 — defer to v2; v1 fills in unknown item types with the profile's default at refresh time).
- Cursor `.cursor/rules/aec.mdc` target (spec §13.2 — v1 ships with the four agent files registered in `agents.json` only: CLAUDE.md, AGENTS.md, GEMINI.md, QWEN.md).
