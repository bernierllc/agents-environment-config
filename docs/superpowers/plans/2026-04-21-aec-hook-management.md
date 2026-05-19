# AEC Hooks — Foundation + Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phases 1 and 2 of the AEC hook management system: a `hooks.json` schema, validator, event-vocabulary translator, idempotent installer, per-item state files, drift detection, tiered upgrade prompts, and `aec hooks …` CLI — without breaking the legacy `aec/lib/hooks.py` lint-hook generator.

**Spec:** `docs/superpowers/specs/2026-04-21-aec-hook-management-design.md`

---

## Status as of 2026-05-19 (read this first)

This plan was originally written 2026-04-21. Since then, PR #37 (`Worktree aec hook management`) and PR #38 (`feat(hooks): installer tasks 9d–9g`) merged into main and shipped as **v2.32.0**. Main is currently at **v2.38.1**. The two worktrees that produced this work (`worktree-aec-hook-management` and `worktree-aec-hooks-drift-upgrade`) are now 48–50 commits behind main and are being deleted as part of this completion effort — they hold no work that isn't already in main other than this plan file and its spec, both of which have been relocated here.

The body of this document (Tasks 0–15 below) is preserved verbatim as the original intent. The unchecked checkboxes in the body are **stale** — do not treat individual `- [ ]` markers in Tasks 0–9g as accurate. Use this status section as the source of truth for what is done vs. what remains.

### Already shipped on main

Verified by directory inspection of `aec/lib/hooks/`, `aec/commands/hooks_cmd.py`, and `tests/test_hooks_*.py` on main at HEAD `f29e704`:

- **Task 0** — `aec/lib/hooks/` is a package (`__init__.py` re-exports legacy symbols). Legacy importers in `repo.py`, `doctor.py`, `install.py`, `install_cmd.py` still work.
- **Task 1** — `aec/lib/hooks/schema.py` with `HooksFile`, `GenericHook`, `AgentOverride`, `WhenPredicate`, `load_hooks_file`, `HooksSchemaError`. Tests: `tests/test_hooks_schema.py`.
- **Task 2** — `aec/lib/hooks/validator.py` with `ValidationError`, `ValidationWarning`, `validate_hooks_file`. Tests: `tests/test_hooks_validator.py`.
- **Task 3** — `aec/lib/hooks/translator.py` with `translate_to_agent`. Tests: `tests/test_hooks_translator.py`.
- **Task 4** — `aec/lib/hooks/predicates.py` with `evaluate_when`, `WhenResult`. Tests: `tests/test_hooks_predicates.py`.
- **Task 5** — `aec hooks validate` CLI in `aec/commands/hooks_cmd.py`. Tests: `tests/test_hooks_cli.py`.
- **Task 6** — `aec/lib/hooks/fingerprint.py` with `fingerprint_hook`. Tests: `tests/test_hooks_fingerprint.py`.
- **Task 7** — `aec/lib/hooks/state.py` with `ItemHookState`, `load_state`, `save_state`, `remove_state`, `mark_version_skipped`, `is_version_skipped`, `list_installed_items`. Tests: `tests/test_hooks_state.py`.
- **Task 8** — `aec/lib/hooks/git_blocks.py` with `write_block`, `remove_block`. Tests: `tests/test_hooks_git_blocks.py`.
- **Tasks 9a–9g** — `aec/lib/hooks/installer.py` with `install_item_hooks`, `remove_item_hooks`, and `_install_claude`/`_install_gemini`/`_install_cursor`/`_install_git` + matching remove helpers + `_resolve_script_commands` + `when`-predicate partitioning. Tests: `tests/test_hooks_installer.py`, `tests/test_hooks_installer_merge.py`.

That is everything from **Phase 1 Foundation** plus **Phase 2 Installer Library**. The library is complete and tested as a library.

### The gap — why hooks are not actually installing or removing yet

**No caller invokes `install_item_hooks` or `remove_item_hooks`.** Grep across `aec/commands/` confirms zero call-sites. So:

- `aec install <skill>` does not install hooks even if the skill ships a `hooks.json`.
- `aec upgrade` does not re-install or upgrade hooks for items that changed.
- `aec uninstall <skill>` does not remove hooks the skill previously installed; if hooks were ever installed by some other path, they would be orphaned.
- `aec hooks` CLI surface is only `validate`. No `list`, `install`, `upgrade`, `remove`, `diff`, `repair`, `skip-version` — and crucially, no top-level `aec run-script` command, which the installer's `command` rewriter emits into hook bodies. A hook installed today that references `aec run-script ...` would fail to execute.

### Remaining work to wrap up this effort

In priority order. Tasks marked **(scope add)** were not in the original 2026-04-21 plan and are being added now because the user explicitly required uninstall coverage.

1. **Task 12h — Top-level `aec run-script`** (must come first; the installer emits this command into hook bodies, so without it no installed hook can actually run). See body §Task 12h.
2. **Task 13 — Wire `install_item_hooks` into `aec install`** via `_install_item_hooks_if_present(item_dir, item_type, item_key, item_version, repo_root)` in `aec/commands/install_cmd.py` (and `aec/commands/install.py` if Step 1 of that task shows it's still live).
3. **Task 16 — Wire `remove_item_hooks` into `aec uninstall`** (scope add). New section appended below the original Task 15. Same shape as Task 13 but for the uninstall path in `aec/commands/uninstall.py:run_uninstall`. Without this, uninstalling a hooks-shipping item leaves Claude/Gemini/Cursor settings and `.aec/installed-hooks/<type>.<key>.json` orphaned.
4. **Task 14 — Wire upgrade flow** into `aec/commands/upgrade.py:run_upgrade`. Requires Tasks 10 + 11 (drift detection + tiered prompts), so this is the largest remaining chunk. If we want a minimum-viable upgrade now, the simplest version is: detect `state.item_version != current item version`, call `remove_item_hooks` then `install_item_hooks` with `--yes` semantics, skip the tiered diff UX. The original Task 14 spec (with prompts) can ship as a follow-up.
5. **Task 10 — `drift.py`** (required by Task 14's full version and by `aec hooks diff`).
6. **Task 11 — `prompts.py`** (required by Task 14's full version).
7. **Task 12a–12g — Remaining `aec hooks` subcommands** (list/install/upgrade/remove/diff/repair/skip-version). These are user-facing diagnostics and manual recovery tools; not blocking for the install/uninstall flow.
8. **Task 15 — pre-push validator guard.** Useful but optional; current pre-push tooling does not run `aec hooks validate`.
9. **Task 13 fixture skill** — `tests/fixtures/skills/hooks-fixture-skill/` needs creating; required for the integration test in Task 13.

### Minimum viable to declare the user's success criteria met

> "Hooks are actually installing when items that have hooks are installed or upgraded; and hooks get properly uninstalled when items are uninstalled."

That maps to: **Task 12h + Task 13 + Task 16 + minimum-viable Task 14** (the "remove + re-install on version bump" variant). Everything else can ship after.

### Branch and worktree cleanup

- `worktree-aec-hook-management` — delete after this commit lands. Its only unique content was this plan + spec, now copied to `plans/` and `docs/superpowers/specs/`.
- `worktree-aec-hooks-drift-upgrade` — delete after this commit lands. Identical to hook-management plus the v2.32.0 release commit, all of which is in main.
- Both local worktrees under `.claude/worktrees/` should be `git worktree remove`d.
- No open PRs reference either branch (confirmed via `gh pr list`).

---

## Scope

- **In:** Phase 1 (library foundation + `aec hooks validate`) and Phase 2 (install/upgrade/remove lifecycle, state, CLI).
- **Out:** Phase 0 audits (separate work), Phase 3 deprecation, Phase 4 Cursor migration, Phase 5 rule promotion, Phase 6 first consumers, Phase 7 docs. Plan files for those follow separately.

### Explicit divergence from spec §2.1 exit criteria

Spec §2.1 says Phase 2's exit includes deleting `aec/lib/hooks.py` and confirming no callers reference it. **This plan does NOT meet that criterion.** The legacy file is converted to `aec/lib/hooks/__init__.py` (Task 0) with all symbols re-exported. The eight importers in `aec/commands/install_cmd.py`, `aec/commands/install.py`, `aec/commands/repo.py` (four sites), and `aec/commands/doctor.py` (two sites) stay on the legacy surface. A companion **Phase 3 plan** is required to reach the spec-defined Phase-2 exit; do not close out the spec based on this plan alone. See decision P1-D6.

## Architecture

- Convert existing `aec/lib/hooks.py` into `aec/lib/hooks/__init__.py` so the new package can introduce submodules (`schema.py`, `validator.py`, `translator.py`, `installer.py`, `state.py`, …) while every existing importer of `aec.lib.hooks.LANGUAGE_HOOKS` / `detect_languages` / `generate_hook_config` / `write_hook_config` / `repair_hook_keys` / `AGENT_HOOK_CONFIGS` / `HOOK_KEY_FIXES` / `get_verification_playwright_hook` keeps working unchanged. Existing imports use `from aec.lib.hooks import X` (not `from aec.lib import X`), so the package form preserves them.
- Reuse `aec/lib/scope.py` verbatim for script path resolution — it already provides `Scope`, `find_tracked_repo()`, `resolve_scope()`, and `get_all_tracked_repos()`.
- **State is per-item.** Each installed item has its own file at `.aec/installed-hooks/<item_type>.<item_key>.json`, matching the concurrency-safe per-file pattern established by `aec/lib/installed_store.py` and documented in the user memory entry `feedback_multi_agent_concurrency.md`. Parallel `aec install` calls modifying different items never write to the same file. (This diverges from spec §3.1 which shows a single-file shape; see decision P1-D9.)

**Tech Stack:** Python 3.11+, Typer (CLI), dataclasses, hashlib (SHA-256 fingerprints), json, pathlib, pytest, rich (console output). No new runtime dependencies.

**Assumed skills/context:**
- Read `~/.agent-tools/rules/agents-environment-config/frameworks/testing/standards.md` before writing tests.
- Read `~/.agent-tools/rules/agents-environment-config/languages/python/` before adding Python type hints.
- Run `pytest tests/ -q` to establish baseline: all green expected.

---

## File Plan

### New files

| Path | Purpose |
|---|---|
| `aec/lib/hooks/__init__.py` | Replaces `aec/lib/hooks.py`; preserves legacy exports (created in Task 0) |
| `aec/lib/hooks/schema.py` | `HooksFile`, `GenericHook`, `AgentOverride`, `WhenPredicate`, `load_hooks_file` (Task 1) |
| `aec/lib/hooks/validator.py` | `ValidationError`, `ValidationWarning`, `validate_hooks_file` (Task 2) |
| `aec/lib/hooks/translator.py` | Event vocabulary → per-agent concrete hook entries (Task 3) |
| `aec/lib/hooks/predicates.py` | `evaluate_when(WhenPredicate, repo_root) -> WhenResult` (Task 4) |
| `aec/lib/hooks/fingerprint.py` | `fingerprint_hook(dict) -> str` (stable SHA-256 of canonical JSON) (Task 6) |
| `aec/lib/hooks/state.py` | `ItemHookState` load/save (per-item `.aec/installed-hooks/<type>.<key>.json`) (Task 7) |
| `aec/lib/hooks/git_blocks.py` | Read/write delimited `# >>> AEC:BEGIN … # <<< AEC:END` blocks (Task 8) |
| `aec/lib/hooks/installer.py` | `install_item_hooks`, `remove_item_hooks`, `upgrade_item_hooks` (Tasks 9a-9g) |
| `aec/lib/hooks/drift.py` | `detect_drift(state, repo_root) -> list[DriftReport]` (Task 10) |
| `aec/lib/hooks/prompts.py` | Tiered upgrade prompt UI (Y/n/d/s/v + per-hook y/n/d/q) (Tasks 11a-11d) |
| `aec/commands/hooks_cmd.py` | Typer sub-app: `aec hooks validate` (Task 5) + `list/install/upgrade/remove/diff/repair/skip-version` (Tasks 12a-12g) |
| `aec/commands/run_script_cmd.py` | Top-level `aec run-script` command dispatcher (Task 12h) — **separate module to avoid `aec/cli.py ↔ hooks_cmd.py` circular import** |
| `tests/test_hooks_schema.py` | Schema dataclass + loader tests (Task 1) |
| `tests/test_hooks_validator.py` | Validation rule tests (Task 2) |
| `tests/test_hooks_translator.py` | Event vocabulary translation tests (Task 3) |
| `tests/test_hooks_predicates.py` | `when` predicate evaluation tests (Task 4) |
| `tests/test_hooks_fingerprint.py` | Fingerprint stability tests (Task 6) |
| `tests/test_hooks_state.py` | State file read/write tests (Task 7) |
| `tests/test_hooks_git_blocks.py` | Delimited-block read/write tests (Task 8) |
| `tests/test_hooks_installer.py` | Installer integration tests (real temp repos) (Tasks 9a-9g) |
| `tests/test_hooks_installer_merge.py` | Unit tests for `_merge_claude`/`_merge_gemini`/`_merge_cursor` helpers (Task 9a) |
| `tests/test_hooks_drift.py` | Drift-detection tests (Task 10) |
| `tests/test_hooks_prompts.py` | Tiered prompt flow tests (monkeypatched input) (Tasks 11a-11d) |
| `tests/test_hooks_cli.py` | Typer CliRunner tests for `aec hooks …` (Tasks 5, 12a-12h) |
| `tests/fixtures/hooks/minimal.json` | Minimal valid `hooks.json` (Task 1) |
| `tests/fixtures/hooks/invalid_duplicate_ids.json` | Negative fixture (Task 2) |
| `tests/fixtures/hooks/invalid_unknown_event.json` | Negative fixture (Task 2) |
| `tests/fixtures/hooks/invalid_empty_command.json` | Negative fixture (Task 2) |
| `tests/fixtures/hooks/invalid_custom_check_newline.json` | Negative fixture (Task 2) |
| `tests/fixtures/hooks/invalid_unknown_git_hook.json` | Negative fixture (Task 2) |
| `tests/fixtures/skills/hooks-fixture-skill/SKILL.md` | Minimal real skill shipping a `hooks.json` for installer integration tests (Task 13) |
| `tests/fixtures/skills/hooks-fixture-skill/hooks.json` | Fixture skill's hooks file (Task 13) |
| `tests/fixtures/skills/hooks-fixture-skill/scripts/demo.sh` | Fixture script resolved via `aec run-script` (Task 13) |

### Modified files

| Path | Change |
|---|---|
| `aec/cli.py` | (a) Register `hooks_app` sub-Typer as a **first-class** command group. The correct insertion point is **after `app.command(...)(version_cmd)` at line 331 and BEFORE the `# Deprecated command groups (kept as shims)` comment at line 333**. Everything from line 338 onward (`repo_app`, `skills_app`, `agent_tools_app`, `rules_app`, `files_app`, `prefs_app`) is marked `deprecated=True` — DO NOT insert `hooks_app` inside that block. (b) Register top-level `run-script` command via `from .commands.run_script_cmd import run_script; app.command("run-script")(run_script)`. Both live inside the `if HAS_TYPER:` block. The module-level `app` object stays — there is **no `build_app()` function** in this file; tests import `app` directly. |
| `aec/commands/install_cmd.py` | Add `_install_item_hooks_if_present(item_dir, item_type, item_key, item_version, repo_root)` helper; wire into the generic install flow. `_post_install_playwright_pipeline` becomes a guarded no-op shim (Task 13). |
| `aec/commands/install.py` | **Investigation step in Task 13** determines whether this legacy installer is still active for any item type. If yes, add the same `_install_item_hooks_if_present` call; if dead code path, document and leave untouched. |
| `aec/commands/upgrade.py` | After the existing per-item version bump in `run_upgrade`, call `installer.upgrade_item_hooks(...)` per upgraded item; surface `prompts.prompt_upgrade` results. (Task 14) |

### Unchanged but referenced (must stay green after every task)

| Path | Why referenced |
|---|---|
| `aec/lib/__init__.py` | Re-exports `LANGUAGE_HOOKS`, `AGENT_HOOK_CONFIGS`, `detect_languages`, `generate_hook_config`, `write_hook_config` from `aec.lib.hooks`. Package conversion keeps this working because existing call-sites use `from aec.lib.hooks import X`, not `from aec.lib import X`. Do NOT modify. |
| `aec/lib/scope.py` | Reused read-only for script path resolution in Task 9. Do not modify. |
| `aec/lib/installed_store.py` | Reference pattern for per-type/per-item store. Do not modify. |
| `aec/lib/atomic_write.py` | Use `atomic_write_json` from Task 7 onward. Do not modify. |
| `tests/test_hooks.py`, `tests/test_repair_hook_keys.py`, `tests/test_repo_hooks.py`, `tests/test_discovery_hooks.py`, `tests/test_catalog_hashes_hook.py` | Legacy behavior coverage; must pass byte-identical before/after Task 0 and after every subsequent task. |
| `aec/commands/repo.py`, `aec/commands/doctor.py`, `aec/commands/install.py` | Import legacy symbols from `aec.lib.hooks`; kept working via the re-exports in the new `__init__.py`. |

### Deleted files

| Path | When |
|---|---|
| `aec/lib/hooks.py` | Replaced by `aec/lib/hooks/__init__.py` at Task 0 via `git mv` (same content, new location) |

---

## Phase 1 — Library Foundation + Validate CLI

### Task 0: Relocate `aec/lib/hooks.py` to `aec/lib/hooks/__init__.py`

**Goal:** Enable adding submodules under `aec/lib/hooks/` without breaking any existing importer. Zero behavior change.

**Files:**
- Delete: `aec/lib/hooks.py`
- Create: `aec/lib/hooks/__init__.py` (byte-for-byte identical content after the move)

- [ ] **Step 1: Establish baseline — all tests green.**

```bash
pytest tests/ -q 2>&1 | tail -20
```
Expected: 100% pass. Record the total count for comparison.

- [ ] **Step 2: Clear stale bytecode and type caches** — prevents `.pyc` shadowing during the module→package transition.

```bash
find aec tests -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
rm -rf .mypy_cache/ .pytest_cache/ || true
```

- [ ] **Step 3: Verify build/packaging config doesn't require manual package registration.**

```bash
grep -n "packages\s*=\|find_packages\|aec\.lib" pyproject.toml setup.py setup.cfg 2>/dev/null || echo "no explicit package list"
```
Expected: either no explicit list (implicit namespace discovery picks up `aec.lib.hooks` package automatically), or an explicit entry for `aec.lib` that covers subpackages. If explicit packages are listed and `aec.lib.hooks` is NOT covered, **stop** and add it before Step 4.

- [ ] **Step 4: Move file.**

```bash
git mv aec/lib/hooks.py aec/lib/hooks/__init__.py
```
(git creates the intermediate directory; no `mkdir` needed.)

- [ ] **Step 5: If project is installed in editable mode, reinstall.**

```bash
python -c "import aec, sys; sys.exit(0 if 'site-packages' in aec.__file__ else 1)" && pip install -e . --no-deps || echo "non-editable install; skipping"
```

- [ ] **Step 6: Run tests to confirm no regression.**

```bash
pytest tests/ -q 2>&1 | tail -20
```
Expected: same pass count as Step 1. If any test fails, the relocation broke something — investigate before proceeding.

- [ ] **Step 7: Commit.**

```bash
git add -A
git commit -m "refactor(hooks): relocate hooks.py to hooks/__init__.py for package expansion"
```

---

### Task 1: Schema dataclasses + loader

**Files:**
- Create: `aec/lib/hooks/schema.py`
- Create: `tests/test_hooks_schema.py`
- Create: `tests/fixtures/hooks/minimal.json`

Note on the `match` field: per spec §1.2, `match` is a glob whose semantics depend on event. The translator in Task 3 does **not yet** surface `match` — it is parsed into the schema for forward compatibility but silently dropped during translation in P1. This is called out in decision P1-D10 and documented in the docstring on `GenericHook.match`. A future plan will decide how to surface it.

- [ ] **Step 1: Write failing test — minimal load.**

```python
# tests/test_hooks_schema.py
"""Tests for aec.lib.hooks.schema — HooksFile and load_hooks_file."""

import json
from pathlib import Path

import pytest


class TestLoadHooksFile:
    def test_loads_minimal_hooks_file(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        minimal = {
            "$schema": "https://bernierllc.io/schemas/aec-hooks-v1.json",
            "version": "1.0.0",
            "hooks": [],
        }
        path = tmp_path / "hooks.json"
        path.write_text(json.dumps(minimal))

        hf = load_hooks_file(path)

        assert hf.version == "1.0.0"
        assert hf.hooks == []
        assert hf.claude == []
        assert hf.cursor == []
        assert hf.gemini == []
        assert hf.git == []

    def test_loads_generic_hook_fields(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        data = {
            "$schema": "https://bernierllc.io/schemas/aec-hooks-v1.json",
            "version": "1.2.0",
            "hooks": [{
                "id": "check",
                "event": "on_file_edit",
                "match": "**/*.py",
                "command": "aec run-script foo check.sh",
                "description": "Lint Python files",
                "blocking": False,
                "timeout_ms": 3000,
                "when": {"repo_has_any": ["pyproject.toml"]},
            }],
        }
        (tmp_path / "hooks.json").write_text(json.dumps(data))

        hf = load_hooks_file(tmp_path / "hooks.json")

        assert len(hf.hooks) == 1
        h = hf.hooks[0]
        assert h.id == "check"
        assert h.event == "on_file_edit"
        assert h.match == "**/*.py"
        assert h.command == "aec run-script foo check.sh"
        assert h.description == "Lint Python files"
        assert h.blocking is False
        assert h.timeout_ms == 3000
        assert h.when is not None
        assert h.when.repo_has_any == ["pyproject.toml"]

    def test_defaults_blocking_to_false(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        data = {
            "$schema": "x",
            "version": "1.0.0",
            "hooks": [{
                "id": "x",
                "event": "on_file_edit",
                "command": "echo hi",
                "description": "d",
            }],
        }
        (tmp_path / "hooks.json").write_text(json.dumps(data))
        hf = load_hooks_file(tmp_path / "hooks.json")
        assert hf.hooks[0].blocking is False
        assert hf.hooks[0].timeout_ms == 5000

    def test_raises_on_missing_file(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        with pytest.raises(FileNotFoundError):
            load_hooks_file(tmp_path / "missing.json")

    def test_raises_on_invalid_json(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file, HooksSchemaError

        (tmp_path / "hooks.json").write_text("not json {")
        with pytest.raises(HooksSchemaError):
            load_hooks_file(tmp_path / "hooks.json")

    def test_loads_all_generic_events(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file, GENERIC_EVENTS
        events = sorted(GENERIC_EVENTS)
        data = {
            "$schema": "x", "version": "1.0.0",
            "hooks": [
                {"id": f"h{i}", "event": ev, "command": "c", "description": "d"}
                for i, ev in enumerate(events)
            ],
        }
        (tmp_path / "hooks.json").write_text(json.dumps(data))
        hf = load_hooks_file(tmp_path / "hooks.json")
        assert {h.event for h in hf.hooks} == set(events)
```

- [ ] **Step 2: Run test — verify fail.**

```bash
pytest tests/test_hooks_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'aec.lib.hooks.schema'`.

- [ ] **Step 3: Implement `schema.py`.**

```python
# aec/lib/hooks/schema.py
"""hooks.json schema — dataclasses and loader.

Provides strongly-typed dataclasses for the hooks.json authoring surface and
a loader that parses JSON into them. Validation beyond basic shape/type checks
lives in validator.py.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional


class HooksSchemaError(ValueError):
    """Raised when a hooks.json file cannot be parsed into the schema."""


GENERIC_EVENTS = frozenset({
    "on_file_edit",
    "on_file_read",
    "pre_tool_use",
    "session_start",
    "pre_commit",
    "pre_push",
})


@dataclass
class WhenPredicate:
    repo_has: List[str] = field(default_factory=list)
    repo_has_any: List[str] = field(default_factory=list)
    repo_lacks: List[str] = field(default_factory=list)
    custom_check: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["WhenPredicate"]:
        if data is None:
            return None
        return cls(
            repo_has=list(data.get("repo_has", []) or []),
            repo_has_any=list(data.get("repo_has_any", []) or []),
            repo_lacks=list(data.get("repo_lacks", []) or []),
            custom_check=data.get("custom_check"),
        )


@dataclass
class GenericHook:
    id: str
    event: str
    command: str
    description: str
    # Reserved for v2: a glob whose interpretation depends on event. Parsed but
    # NOT surfaced by the P1 translator. See plan decision P1-D10.
    match: Optional[str] = None
    blocking: bool = False
    timeout_ms: int = 5000
    when: Optional[WhenPredicate] = None

    @classmethod
    def from_dict(cls, data: dict) -> "GenericHook":
        try:
            return cls(
                id=data["id"],
                event=data["event"],
                command=data["command"],
                description=data["description"],
                match=data.get("match"),
                blocking=bool(data.get("blocking", False)),
                timeout_ms=int(data.get("timeout_ms", 5000)),
                when=WhenPredicate.from_dict(data.get("when")),
            )
        except KeyError as e:
            raise HooksSchemaError(f"GenericHook missing required field: {e}") from e


@dataclass
class AgentOverride:
    """Raw per-agent hook payload, passed through verbatim by the translator."""
    agent: str  # "claude" | "cursor" | "gemini" | "git"
    payload: dict
    id: Optional[str] = None


@dataclass
class HooksFile:
    version: str
    hooks: List[GenericHook] = field(default_factory=list)
    claude: List[AgentOverride] = field(default_factory=list)
    cursor: List[AgentOverride] = field(default_factory=list)
    gemini: List[AgentOverride] = field(default_factory=list)
    git: List[AgentOverride] = field(default_factory=list)
    schema_url: Optional[str] = None
    source_path: Optional[Path] = None


def load_hooks_file(path: Path) -> HooksFile:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HooksSchemaError(f"{path}: invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise HooksSchemaError(f"{path}: top-level must be an object")
    if "version" not in data:
        raise HooksSchemaError(f"{path}: missing required field 'version'")

    generic = [GenericHook.from_dict(h) for h in data.get("hooks", []) or []]

    def _overrides(key: str) -> List[AgentOverride]:
        raw_list = data.get(key, []) or []
        return [
            AgentOverride(agent=key, payload=item, id=item.get("id"))
            for item in raw_list
        ]

    return HooksFile(
        version=str(data["version"]),
        hooks=generic,
        claude=_overrides("claude"),
        cursor=_overrides("cursor"),
        gemini=_overrides("gemini"),
        git=_overrides("git"),
        schema_url=data.get("$schema"),
        source_path=path,
    )
```

- [ ] **Step 4: Run test — verify pass.**

```bash
pytest tests/test_hooks_schema.py -v
```

- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/schema.py tests/test_hooks_schema.py tests/fixtures/hooks/minimal.json
git commit -m "feat(hooks): add hooks.json schema dataclasses and loader"
```

---

### Task 2: Validator

**Files:**
- Create: `aec/lib/hooks/validator.py`
- Create: `tests/test_hooks_validator.py`
- Create: `tests/fixtures/hooks/invalid_duplicate_ids.json`, `invalid_unknown_event.json`, `invalid_empty_command.json`, `invalid_custom_check_newline.json`, `invalid_unknown_git_hook.json`

Validation rules from spec §1.6:
1. `version` MUST match item frontmatter `version` (caller passes expected version).
2. `id` MUST be unique across `hooks` and all per-agent override arrays.
3. `event` MUST be in `GENERIC_EVENTS`.
4. `command` MUST be non-empty.
5. `when.custom_check` MUST NOT contain newlines.
6. Per-agent override that mirrors a generic event emits a **warning** (not error).
7. Git-array hooks MUST target a recognized git hook name.
8. `aec run-script <item> <script>` command form — script existence check is **deferred to install**, NOT enforced by the validator.

- [ ] **Step 1: Create negative fixtures.**

Create each fixture JSON file under `tests/fixtures/hooks/` with the shape that triggers exactly one violation. See [fixture content spec](#fixture-content-spec) below. Example for `invalid_duplicate_ids.json`:

```json
{
  "$schema": "x", "version": "1.0.0",
  "hooks": [
    {"id": "dup", "event": "on_file_edit", "command": "c", "description": "d"},
    {"id": "dup", "event": "on_file_edit", "command": "c", "description": "d"}
  ]
}
```

- [ ] **Step 2: Write failing tests.**

```python
# tests/test_hooks_validator.py
import json
import pytest

from aec.lib.hooks.schema import (
    HooksFile, GenericHook, AgentOverride, WhenPredicate, load_hooks_file,
)

FIX = lambda name: f"tests/fixtures/hooks/{name}"


class TestValidateHooksFile:
    def _make(self, **overrides):
        return HooksFile(version="1.0.0", hooks=[], **overrides)

    def test_valid_minimal_file_has_no_errors(self):
        from aec.lib.hooks.validator import validate_hooks_file
        errs, _ = validate_hooks_file(self._make(), expected_version="1.0.0")
        assert errs == []

    def test_version_mismatch_is_error(self):
        from aec.lib.hooks.validator import validate_hooks_file
        errs, _ = validate_hooks_file(self._make(), expected_version="2.0.0")
        assert any("version" in e.message.lower() for e in errs)

    def test_duplicate_ids_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_duplicate_ids.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("duplicate id" in e.message.lower() for e in errs)

    def test_unknown_event_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_unknown_event.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("event" in e.message.lower() for e in errs)

    def test_empty_command_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_empty_command.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("command" in e.message.lower() for e in errs)

    def test_custom_check_newline_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_custom_check_newline.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("newline" in e.message.lower() for e in errs)

    def test_unknown_git_hook_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_unknown_git_hook.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("git hook" in e.message.lower() for e in errs)

    def test_agent_override_mirroring_generic_is_warning(self):
        from aec.lib.hooks.validator import validate_hooks_file
        override = AgentOverride(
            agent="claude",
            payload={"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "echo"}]},
            id="mirror",
        )
        hf = HooksFile(version="1.0.0", claude=[override])
        errs, warns = validate_hooks_file(hf, expected_version="1.0.0")
        assert errs == []
        assert any("generic" in w.message.lower() for w in warns)

    def test_validator_does_not_check_script_existence(self, tmp_path):
        from aec.lib.hooks.validator import validate_hooks_file
        h = GenericHook(
            id="x", event="on_file_edit",
            command="aec run-script some-skill missing-script.sh",
            description="d",
        )
        hf = HooksFile(version="1.0.0", hooks=[h])
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert errs == []

    def test_duplicate_across_generic_and_override_is_error(self):
        from aec.lib.hooks.validator import validate_hooks_file
        h = GenericHook(id="shared", event="on_file_edit", command="c", description="d")
        override = AgentOverride(agent="claude", payload={"matcher": "X"}, id="shared")
        hf = HooksFile(version="1.0.0", hooks=[h], claude=[override])
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("duplicate id" in e.message.lower() for e in errs)
```

- [ ] **Step 3: Verify fail** — `pytest tests/test_hooks_validator.py -v` → ImportError.

- [ ] **Step 4: Implement `validator.py`** (see Task 2 body in reference implementation at bottom of plan for full code; logic follows spec §1.6 directly).

- [ ] **Step 5: Verify pass.**
- [ ] **Step 6: Commit.**

```bash
git add aec/lib/hooks/validator.py tests/test_hooks_validator.py tests/fixtures/hooks/invalid_*.json
git commit -m "feat(hooks): add hooks.json validator with spec 1.6 rules"
```

#### Fixture content spec (Task 2)

Each invalid fixture has the shape of a valid hooks.json EXCEPT the one violating field:

- **invalid_duplicate_ids.json** — two `hooks` entries with `id: "dup"`.
- **invalid_unknown_event.json** — single hook with `event: "on_unicorn_moment"`.
- **invalid_empty_command.json** — single hook with `command: ""`.
- **invalid_custom_check_newline.json** — single hook with `when: {"custom_check": "line1\nline2"}`.
- **invalid_unknown_git_hook.json** — single `git` override with `hook_name: "bogus-hook"`.

---

### Task 3: Event-vocabulary translator

**Files:** `aec/lib/hooks/translator.py`, `tests/test_hooks_translator.py`

Implements the translation table from spec §1.3, producing concrete per-agent payloads. Translator does NOT write to disk. Covers **every cell** of the §1.3 matrix: each generic event × each agent.

Translator skip matrix (must be covered by tests):

| Event ↓ / Agent → | claude | gemini | cursor | git |
|---|---|---|---|---|
| `on_file_edit` | PostToolUse Edit\|Write\|MultiEdit | AfterTool write_file\|replace | afterFileEdit | skip |
| `on_file_read` | PostToolUse Read | AfterTool read_file | skip | skip |
| `pre_tool_use` | PreToolUse | BeforeTool | skip | skip |
| `session_start` | SessionStart | SessionStart | skip | skip |
| `pre_commit` | skip | skip | skip | pre-commit |
| `pre_push` | skip | skip | skip | pre-push |

- [ ] **Step 1: Write failing tests.** Include a parametrized matrix test asserting every skip cell actually returns `[]`:

```python
# tests/test_hooks_translator.py (excerpt)
import pytest
from aec.lib.hooks.schema import HooksFile, GenericHook, AgentOverride

SKIP_MATRIX = [
    ("on_file_edit", "git"),
    ("on_file_read", "cursor"), ("on_file_read", "git"),
    ("pre_tool_use", "cursor"), ("pre_tool_use", "git"),
    ("session_start", "cursor"), ("session_start", "git"),
    ("pre_commit", "claude"), ("pre_commit", "gemini"), ("pre_commit", "cursor"),
    ("pre_push", "claude"), ("pre_push", "gemini"), ("pre_push", "cursor"),
]


@pytest.mark.parametrize("event,agent", SKIP_MATRIX)
def test_skip_matrix(event, agent):
    from aec.lib.hooks.translator import translate_to_agent
    h = GenericHook(id="x", event=event, command="c", description="d")
    hf = HooksFile(version="1.0.0", hooks=[h])
    assert translate_to_agent(hf, agent, resolved_commands={"x": "c"}) == []


class TestTranslateClaude:
    def test_on_file_edit_maps_to_PostToolUse(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit", command="echo hi",
                        description="d", match="**/*.py")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"x": "echo hi"})
        assert len(entries) == 1
        e = entries[0]
        assert e["event_key"] == "PostToolUse"
        assert e["payload"]["matcher"] == "Edit|Write|MultiEdit"
        assert e["payload"]["hooks"][0]["command"] == "echo hi"
        assert e["source_hook_id"] == "x"
        # P1-D10: match is parsed by schema but must NOT leak into the translated payload
        assert "match" not in e["payload"]
        assert "match" not in e["payload"]["hooks"][0]
        # And the source hook did carry `match` — so this is a real drop, not absence
        assert h.match == "**/*.py"

    def test_on_file_read_maps_to_PostToolUse_Read(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="r", event="on_file_read", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"r": "c"})
        assert entries[0]["event_key"] == "PostToolUse"
        assert entries[0]["payload"]["matcher"] == "Read"

    def test_pre_tool_use_maps_to_PreToolUse_without_matcher(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="p", event="pre_tool_use", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"p": "c"})
        assert entries[0]["event_key"] == "PreToolUse"
        assert "matcher" not in entries[0]["payload"]

    def test_session_start_maps_to_SessionStart(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="s", event="session_start", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"s": "c"})
        assert entries[0]["event_key"] == "SessionStart"


class TestTranslateGemini:
    def test_on_file_edit_maps_to_AfterTool(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "gemini", resolved_commands={"x": "c"})
        assert entries[0]["event_key"] == "AfterTool"
        assert entries[0]["payload"]["matcher"] == "write_file|replace"

    def test_pre_tool_use_maps_to_BeforeTool(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="p", event="pre_tool_use", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "gemini", resolved_commands={"p": "c"})
        assert entries[0]["event_key"] == "BeforeTool"


class TestTranslateCursor:
    def test_on_file_edit_maps_to_afterFileEdit(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "cursor", resolved_commands={"x": "c"})
        assert entries[0]["event_key"] == "afterFileEdit"


class TestTranslateGit:
    def test_pre_commit_maps_to_pre_commit_hook(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="pre_commit", command="lint.sh", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "git", resolved_commands={"x": "lint.sh"})
        assert entries[0]["event_key"] == "pre-commit"
        assert entries[0]["payload"]["command"] == "lint.sh"

    def test_pre_push_maps_to_pre_push_hook(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="pre_push", command="checks.sh", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "git", resolved_commands={"x": "checks.sh"})
        assert entries[0]["event_key"] == "pre-push"


class TestOverridesPassThroughVerbatim:
    def test_claude_override_shape_unchanged(self):
        from aec.lib.hooks.translator import translate_to_agent
        override = AgentOverride(
            agent="claude",
            id="custom",
            payload={"matcher": "SubagentStop", "hooks": [{"command": "x"}]},
        )
        hf = HooksFile(version="1.0.0", claude=[override])
        entries = translate_to_agent(hf, "claude", resolved_commands={})
        assert entries[-1]["payload"]["matcher"] == "SubagentStop"
        assert entries[-1]["source_hook_id"] == "custom"
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement `translator.py`** (identical to the reference impl shown in earlier review; unchanged core logic).

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/translator.py tests/test_hooks_translator.py
git commit -m "feat(hooks): translate generic events to agent-native payloads"
```

---

### Task 4: `when` predicate evaluator

**Files:** `aec/lib/hooks/predicates.py`, `tests/test_hooks_predicates.py`

Spec §1.4: `repo_has`, `repo_has_any`, `repo_lacks`, `custom_check`. Evaluator returns `WhenResult` (applied / skipped + reason). Empty predicate → applied.

**Security note (P1-D8):** `custom_check` runs arbitrary shell with user credentials. The installer (Task 9b) requires explicit user confirmation on first install of any item whose `hooks.json` contains `custom_check`. The evaluator itself simply executes; confirmation policy lives in the installer.

- [ ] **Step 1: Write failing tests.**

```python
# tests/test_hooks_predicates.py
from pathlib import Path
import pytest

from aec.lib.hooks.schema import WhenPredicate


class TestEvaluateWhen:
    def test_empty_predicate_applies(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate()
        result = evaluate_when(pred, tmp_path)
        assert result.applied is True

    def test_repo_has_match(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "pyproject.toml").write_text("")
        pred = WhenPredicate(repo_has=["pyproject.toml"])
        assert evaluate_when(pred, tmp_path).applied is True

    def test_repo_has_missing_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(repo_has=["pyproject.toml"])
        result = evaluate_when(pred, tmp_path)
        assert result.applied is False
        assert "pyproject.toml" in result.reason

    def test_repo_has_any_matches_one(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "package.json").write_text("")
        pred = WhenPredicate(repo_has_any=["tsconfig.json", "package.json"])
        assert evaluate_when(pred, tmp_path).applied is True

    def test_repo_has_any_all_missing_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(repo_has_any=["a.txt", "b.txt"])
        assert evaluate_when(pred, tmp_path).applied is False

    def test_repo_lacks_passes_when_absent(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(repo_lacks=["forbidden.txt"])
        assert evaluate_when(pred, tmp_path).applied is True

    def test_repo_lacks_skips_when_present(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "forbidden.txt").write_text("")
        pred = WhenPredicate(repo_lacks=["forbidden.txt"])
        assert evaluate_when(pred, tmp_path).applied is False

    def test_custom_check_true_applies(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(custom_check="true")
        assert evaluate_when(pred, tmp_path).applied is True

    def test_custom_check_false_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(custom_check="false")
        result = evaluate_when(pred, tmp_path)
        assert result.applied is False

    def test_custom_check_timeout_skips(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        pred = WhenPredicate(custom_check="sleep 10")
        # Installer passes short timeout in tests; evaluator accepts `timeout_s`.
        result = evaluate_when(pred, tmp_path, timeout_s=1)
        assert result.applied is False
        assert "timeout" in result.reason.lower()

    def test_combined_all_must_apply(self, tmp_path):
        from aec.lib.hooks.predicates import evaluate_when
        (tmp_path / "pyproject.toml").write_text("")
        pred = WhenPredicate(repo_has=["pyproject.toml"], repo_lacks=["forbidden.txt"])
        assert evaluate_when(pred, tmp_path).applied is True
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement `predicates.py`.** Real subprocess invocation for `custom_check` per global testing rule (no mocking internal APIs). Default timeout 5s; accept `timeout_s` override for test ergonomics.

```python
# aec/lib/hooks/predicates.py
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .schema import WhenPredicate


@dataclass
class WhenResult:
    applied: bool
    reason: str = ""


def evaluate_when(pred: WhenPredicate | None, repo_root: Path, timeout_s: int = 5) -> WhenResult:
    if pred is None:
        return WhenResult(True, "")
    for rel in pred.repo_has:
        if not (repo_root / rel).exists():
            return WhenResult(False, f"missing required path: {rel}")
    if pred.repo_has_any:
        if not any((repo_root / rel).exists() for rel in pred.repo_has_any):
            return WhenResult(False, f"none of repo_has_any present: {pred.repo_has_any}")
    for rel in pred.repo_lacks:
        if (repo_root / rel).exists():
            return WhenResult(False, f"repo_lacks violated: {rel} exists")
    if pred.custom_check:
        try:
            r = subprocess.run(
                pred.custom_check, shell=True, cwd=str(repo_root),
                capture_output=True, timeout=timeout_s, check=False,
            )
        except subprocess.TimeoutExpired:
            return WhenResult(False, f"custom_check timeout after {timeout_s}s")
        if r.returncode != 0:
            return WhenResult(False, f"custom_check exit {r.returncode}")
    return WhenResult(True, "")
```

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/predicates.py tests/test_hooks_predicates.py
git commit -m "feat(hooks): evaluate when predicates for conditional install"
```

---

### Task 5: `aec hooks validate` CLI

**Files:** `aec/commands/hooks_cmd.py` (new sub-app with only `validate`), `aec/cli.py` (register sub-app), `tests/test_hooks_cli.py`

**Critical:** `aec/cli.py` exports a module-level `app` object inside `if HAS_TYPER:` — there is no `build_app()` function. Tests import the module-level `app` directly:

```python
from aec.cli import app
```

Sub-app registration goes into the `if HAS_TYPER:` block **after `test_app`'s commands and before `repo_app`** (approximately line 335). This places `hooks_app` among first-class sub-apps, not next to the deprecated `rules_app`.

- [ ] **Step 1: Write failing tests.**

```python
# tests/test_hooks_cli.py
import json
import pytest
from typer.testing import CliRunner


class TestHooksValidateCLI:
    def setup_method(self):
        from aec.cli import app
        self.app = app
        self.runner = CliRunner(mix_stderr=False)

    def test_validate_passes_minimal_file(self, tmp_path):
        p = tmp_path / "hooks.json"
        p.write_text(json.dumps({"$schema": "x", "version": "1.0.0", "hooks": []}))
        result = self.runner.invoke(
            self.app, ["hooks", "validate", str(p), "--item-version", "1.0.0"],
        )
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_fails_on_version_mismatch(self, tmp_path):
        p = tmp_path / "hooks.json"
        p.write_text(json.dumps({"$schema": "x", "version": "1.0.0", "hooks": []}))
        result = self.runner.invoke(
            self.app, ["hooks", "validate", str(p), "--item-version", "2.0.0"],
        )
        assert result.exit_code != 0

    def test_validate_warns_but_succeeds_on_mirror_override(self, tmp_path):
        data = {
            "$schema": "x", "version": "1.0.0", "hooks": [],
            "claude": [{
                "id": "mirror", "matcher": "Edit|Write",
                "hooks": [{"type": "command", "command": "x"}],
            }],
        }
        p = tmp_path / "hooks.json"
        p.write_text(json.dumps(data))
        result = self.runner.invoke(
            self.app, ["hooks", "validate", str(p), "--item-version", "1.0.0"],
        )
        assert result.exit_code == 0
        # Combine stdout+stderr for the warning check; rich may go either way.
        text = (result.stdout + result.stderr).lower()
        assert "warn" in text or "mirror" in text
```

- [ ] **Step 2: Verify fail** — ImportError: `aec.commands.hooks_cmd`.

- [ ] **Step 3: Create `aec/commands/hooks_cmd.py` with ONLY `validate`** (other commands land in Task 12).

```python
# aec/commands/hooks_cmd.py
"""`aec hooks ...` CLI sub-app."""

from pathlib import Path
import typer
from rich.console import Console

hooks_app = typer.Typer(help="Manage item hooks (Claude/Gemini/Cursor/git)")
_console = Console()


@hooks_app.command("validate")
def validate(
    path: Path = typer.Argument(..., help="Path to hooks.json"),
    item_version: str = typer.Option(..., "--item-version", help="Expected item frontmatter version"),
) -> None:
    """Validate a hooks.json file against the schema and spec rules."""
    from ..lib.hooks.schema import load_hooks_file, HooksSchemaError
    from ..lib.hooks.validator import validate_hooks_file

    try:
        hf = load_hooks_file(path)
    except (FileNotFoundError, HooksSchemaError) as e:
        _console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(2)

    errors, warnings = validate_hooks_file(hf, expected_version=item_version)
    for w in warnings:
        _console.print(f"[yellow]warning[/yellow] {w.path}: {w.message}")
    for e in errors:
        _console.print(f"[red]error[/red] {e.path}: {e.message}")

    if errors:
        raise typer.Exit(1)
    _console.print(f"[green]ok[/green] {path} is valid")
```

- [ ] **Step 4: Register `hooks_app` in `aec/cli.py`.**

Locate the first-class sub-app region — right after `test_app`'s last command and before `repo_app = typer.Typer(...)` (approximately line 335). Insert:

```python
    # --- hooks ---
    from .commands.hooks_cmd import hooks_app
    app.add_typer(hooks_app, name="hooks")
```

- [ ] **Step 5: Verify pass.**
- [ ] **Step 6: Commit.**

```bash
git add aec/commands/hooks_cmd.py aec/cli.py tests/test_hooks_cli.py
git commit -m "feat(hooks): add aec hooks validate CLI command"
```

**Phase 1 exit criteria:**
- `aec hooks validate <path>` works end-to-end.
- `aec/lib/hooks/` package co-exists with legacy language-hook generator.
- All legacy tests still pass.

---

## Phase 2 — Install Lifecycle

### Task 6: Content fingerprint

**Files:** `aec/lib/hooks/fingerprint.py`, `tests/test_hooks_fingerprint.py`

SHA-256 of canonical JSON (sorted keys, no whitespace, UTF-8). Must be stable across dict ordering and Python versions.

- [ ] **Step 1: Write tests.**

```python
# tests/test_hooks_fingerprint.py

class TestFingerprintHook:
    def test_sha256_prefix(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        assert fingerprint_hook({}).startswith("sha256:")

    def test_same_content_same_fingerprint(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        a = {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "c"}]}
        b = {"hooks": [{"command": "c", "type": "command"}], "matcher": "Edit|Write"}
        assert fingerprint_hook(a) == fingerprint_hook(b)

    def test_different_content_different_fingerprint(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        assert fingerprint_hook({"a": 1}) != fingerprint_hook({"a": 2})

    def test_deterministic_across_calls(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        p = {"nested": {"b": 2, "a": 1}, "list": [3, 1, 2]}
        assert fingerprint_hook(p) == fingerprint_hook(p)

    def test_unicode_preserved(self):
        from aec.lib.hooks.fingerprint import fingerprint_hook
        assert fingerprint_hook({"x": "café"}) == fingerprint_hook({"x": "café"})
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement** `fingerprint_hook(payload: dict) -> str` returning `"sha256:<hex>"`:

```python
# aec/lib/hooks/fingerprint.py
import hashlib
import json


def fingerprint_hook(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/fingerprint.py tests/test_hooks_fingerprint.py
git commit -m "feat(hooks): add deterministic content fingerprint for drift detection"
```

---

### Task 7: Per-item state files `.aec/installed-hooks/<type>.<key>.json`

**Files:** `aec/lib/hooks/state.py`, `tests/test_hooks_state.py`

**Concurrency rationale (P1-D9):** Two parallel `aec install skill:foo` and `aec install skill:bar` calls must not race on a shared file. The per-item split ensures each writer touches an independent file and atomic_write_json eliminates torn reads. Concurrent writes to the SAME item are serialized by the atomic rename at the filesystem level — last-write-wins within a single item is acceptable (same item, same source content, same outcome).

State file shape (`.aec/installed-hooks/skill.foo.json`):
```json
{
  "schema_version": 1,
  "item_type": "skill",
  "item_key": "foo",
  "item_version": "1.2.3",
  "hooks_file_hash": "sha256:…",
  "hooks_installed": [
    {"hook_id": "check", "agent": "claude", "target_json_pointer": "/hooks/PostToolUse/0", "content_fingerprint": "sha256:…", "version": "1.2.3"}
  ],
  "hooks_skipped": [
    {"hook_id": "lint", "reason": "missing required path: pyproject.toml"}
  ],
  "agents_targeted": ["claude", "cursor"],
  "skipped_versions": [],
  "allow_custom_check": false
}
```

**`allow_custom_check`** (per P1-D8): set to `true` after the user confirms execution of any hook whose `when.custom_check` is a real shell command during first install. Defaults to `false` on fresh state. When an upgrade changes the `custom_check` command string from what state last saw, re-confirmation is required and the flag is reset until re-approved. `ItemHookState` exposes `allow_custom_check: bool = False`.

- [ ] **Step 1: Write tests.**

```python
# tests/test_hooks_state.py
import json
from pathlib import Path
import pytest


class TestItemHookState:
    def test_fresh_load_returns_empty(self, tmp_path):
        from aec.lib.hooks.state import load_state
        state = load_state(tmp_path, item_type="skill", item_key="foo")
        assert state.hooks_installed == []
        assert state.hooks_skipped == []
        assert state.skipped_versions == []

    def test_round_trip(self, tmp_path):
        from aec.lib.hooks.state import load_state, save_state
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        s.item_version = "1.0.0"
        s.hooks_file_hash = "sha256:abc"
        s.hooks_installed = [{
            "hook_id": "h1", "agent": "claude",
            "target_json_pointer": "/hooks/PostToolUse/0",
            "content_fingerprint": "sha256:def", "version": "1.0.0",
        }]
        save_state(tmp_path, s)
        loaded = load_state(tmp_path, item_type="skill", item_key="foo")
        assert loaded.item_version == "1.0.0"
        assert loaded.hooks_installed[0]["hook_id"] == "h1"

    def test_parallel_writes_to_different_items_both_persist(self, tmp_path):
        # Writers for skill.foo and skill.bar touch separate files; both must persist.
        from aec.lib.hooks.state import load_state, save_state
        for key in ("foo", "bar"):
            s = load_state(tmp_path, item_type="skill", item_key=key)
            s.item_version = "1.0.0"
            save_state(tmp_path, s)
        assert (tmp_path / ".aec/installed-hooks/skill.foo.json").exists()
        assert (tmp_path / ".aec/installed-hooks/skill.bar.json").exists()

    def test_skipped_version_is_recorded(self, tmp_path):
        from aec.lib.hooks.state import load_state, save_state, mark_version_skipped, is_version_skipped
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        mark_version_skipped(s, "2.0.0")
        save_state(tmp_path, s)
        reloaded = load_state(tmp_path, item_type="skill", item_key="foo")
        assert is_version_skipped(reloaded, "2.0.0") is True
        assert is_version_skipped(reloaded, "1.0.0") is False

    def test_remove_state_file(self, tmp_path):
        from aec.lib.hooks.state import load_state, save_state, remove_state
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        s.item_version = "1.0.0"
        save_state(tmp_path, s)
        assert (tmp_path / ".aec/installed-hooks/skill.foo.json").exists()
        remove_state(tmp_path, item_type="skill", item_key="foo")
        assert not (tmp_path / ".aec/installed-hooks/skill.foo.json").exists()

    def test_list_all_installed_items(self, tmp_path):
        from aec.lib.hooks.state import load_state, save_state, list_installed_items
        for key in ("a", "b", "c"):
            s = load_state(tmp_path, item_type="skill", item_key=key)
            s.item_version = "1.0.0"
            save_state(tmp_path, s)
        items = list_installed_items(tmp_path)
        assert {(t, k) for t, k in items} == {("skill", "a"), ("skill", "b"), ("skill", "c")}
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement `state.py`** using `aec.lib.atomic_write.atomic_write_json`. Key functions: `load_state`, `save_state`, `remove_state`, `mark_version_skipped`, `is_version_skipped`, `list_installed_items`. Filename pattern: `<type>.<key>.json` with character-safety (if `<key>` contains path separators, reject — validate in loader).

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/state.py tests/test_hooks_state.py
git commit -m "feat(hooks): add per-item .aec/installed-hooks/<type>.<key>.json state"
```

---

### Task 8: Git delimited-block read/write

**Files:** `aec/lib/hooks/git_blocks.py`, `tests/test_hooks_git_blocks.py`

Per spec §1.7 — write `# >>> AEC:BEGIN item=<key> hook_id=<id> version=<v>` … `# <<< AEC:END` blocks into `.git/hooks/{pre-commit,pre-push,…}` files. Idempotent: replace existing matching block or append; preserve non-AEC content.

**Cross-platform note:** `chmod 0o755` is best-effort. On Windows (including WSL-on-Windows-FS), executable bits are not preserved; git respects `core.filemode=false`. Wrap the chmod call so it doesn't fail on platforms without POSIX permissions.

- [ ] **Step 1: Write tests.**

```python
# tests/test_hooks_git_blocks.py
from pathlib import Path
import pytest


class TestGitBlocks:
    def test_write_to_empty_file_creates_shebang_and_block(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="lint", version="1.0.0",
                    command="echo lint")
        text = hook_file.read_text()
        assert text.startswith("#!/usr/bin/env bash") or text.startswith("#!/bin/sh")
        assert "# >>> AEC:BEGIN item=skill:foo hook_id=lint" in text
        assert "# <<< AEC:END" in text
        assert "echo lint" in text

    def test_write_preserves_existing_user_content(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        hook_file.write_text("#!/bin/sh\necho 'user content'\n")
        write_block(hook_file, item_key="skill:foo", hook_id="lint", version="1.0.0",
                    command="echo lint")
        text = hook_file.read_text()
        assert "echo 'user content'" in text
        assert "echo lint" in text

    def test_two_items_coexist(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        write_block(hook_file, item_key="skill:bar", hook_id="b", version="1", command="echo b")
        text = hook_file.read_text()
        assert text.count("AEC:BEGIN") == 2
        assert "echo a" in text and "echo b" in text

    def test_reinstall_same_block_is_byte_identical(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        first = hook_file.read_text()
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        assert hook_file.read_text() == first

    def test_remove_block_preserves_user_content(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block, remove_block
        hook_file = tmp_path / "pre-commit"
        hook_file.write_text("#!/bin/sh\necho 'user content'\n")
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        remove_block(hook_file, item_key="skill:foo", hook_id="a")
        text = hook_file.read_text()
        assert "echo 'user content'" in text
        assert "AEC:BEGIN" not in text

    def test_executable_bit_set_on_posix(self, tmp_path):
        import os, sys
        if sys.platform.startswith("win"):
            pytest.skip("POSIX-only permission semantics")
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        assert os.access(hook_file, os.X_OK)
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.** Regex-based block extraction with `DOTALL|MULTILINE`. Wrap chmod in `try/except (AttributeError, NotImplementedError, PermissionError)`.

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/git_blocks.py tests/test_hooks_git_blocks.py
git commit -m "feat(hooks): idempotent git hook delimited blocks"
```

---

### Task 9: Installer (split into 9a–9g)

Each sub-task delivers a bite-sized, individually-committable slice. Start the installer with helpers + one target, grow outward.

#### Task 9a: Merge helpers — unit-tested in isolation

**Files:** `aec/lib/hooks/installer.py` (partial), `tests/test_hooks_installer_merge.py`

Extract the config-merge logic into pure helpers before the installer grows real orchestration. This is where the `_merge_claude` early-return bug must be avoided.

- [ ] **Step 1: Write failing tests** for `_merge_hook_entries(config: dict, entries: list[dict]) -> dict`:

```python
# tests/test_hooks_installer_merge.py
from aec.lib.hooks.fingerprint import fingerprint_hook


class TestMergeClaudeEntries:
    def test_empty_config_adds_entry(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        entry = {"event_key": "PostToolUse",
                 "payload": {"matcher": "Edit|Write", "hooks": [{"command": "c"}]}}
        result = _merge_claude_entries({}, [entry])
        assert result["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"

    def test_idempotent_same_fingerprint(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        entry = {"event_key": "PostToolUse",
                 "payload": {"matcher": "Edit|Write", "hooks": [{"command": "c"}]}}
        once = _merge_claude_entries({}, [entry])
        twice = _merge_claude_entries(once, [entry])
        assert len(twice["hooks"]["PostToolUse"]) == 1

    def test_multiple_entries_all_added_when_first_matches(self):
        # REGRESSION TEST: early-return bug would drop entry2.
        from aec.lib.hooks.installer import _merge_claude_entries
        entry1 = {"event_key": "PostToolUse", "payload": {"matcher": "A", "hooks": []}}
        entry2 = {"event_key": "PostToolUse", "payload": {"matcher": "B", "hooks": []}}
        first = _merge_claude_entries({}, [entry1])
        combined = _merge_claude_entries(first, [entry1, entry2])  # entry1 dup, entry2 new
        assert len(combined["hooks"]["PostToolUse"]) == 2
        matchers = [h["matcher"] for h in combined["hooks"]["PostToolUse"]]
        assert "A" in matchers and "B" in matchers

    def test_different_event_keys_independent_arrays(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        e1 = {"event_key": "PostToolUse", "payload": {"matcher": "A"}}
        e2 = {"event_key": "PreToolUse", "payload": {"matcher": "B"}}
        result = _merge_claude_entries({}, [e1, e2])
        assert "PostToolUse" in result["hooks"]
        assert "PreToolUse" in result["hooks"]


class TestMergeGeminiEntries:
    def test_adds_to_gemini_hooks(self):
        from aec.lib.hooks.installer import _merge_gemini_entries
        entry = {"event_key": "AfterTool",
                 "payload": {"matcher": "write_file", "hooks": [{"command": "c"}]}}
        result = _merge_gemini_entries({}, [entry])
        assert result["hooks"]["AfterTool"][0]["matcher"] == "write_file"


class TestMergeCursorEntries:
    def test_cursor_shape(self):
        from aec.lib.hooks.installer import _merge_cursor_entries
        entry = {"event_key": "afterFileEdit", "payload": {"command": "c"}}
        result = _merge_cursor_entries({}, [entry])
        assert result["hooks"]["afterFileEdit"][0]["command"] == "c"


class TestRemoveFromConfig:
    def test_remove_by_fingerprint_leaves_others(self):
        from aec.lib.hooks.installer import _remove_from_claude
        existing = {"hooks": {"PostToolUse": [
            {"matcher": "A"}, {"matcher": "B"},
        ]}}
        fp_a = fingerprint_hook({"matcher": "A"})
        result = _remove_from_claude(existing, "PostToolUse", fp_a)
        assert result["hooks"]["PostToolUse"] == [{"matcher": "B"}]

    def test_remove_empty_array_cleans_up_key(self):
        from aec.lib.hooks.installer import _remove_from_claude
        existing = {"hooks": {"PostToolUse": [{"matcher": "A"}]}}
        fp_a = fingerprint_hook({"matcher": "A"})
        result = _remove_from_claude(existing, "PostToolUse", fp_a)
        assert "PostToolUse" not in result.get("hooks", {})
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement helpers** — pure functions operating on `dict` in/out. **No early `return`** inside the entry loop; use `continue` for duplicates:

```python
# aec/lib/hooks/installer.py (partial; full file grows across 9a-9g)
from .fingerprint import fingerprint_hook


def _merge_claude_entries(config: dict, entries: list[dict]) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        new_payload = entry["payload"]
        fp_new = fingerprint_hook(new_payload)
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue  # already present, skip this entry only
        arr.append(new_payload)
    return settings


def _merge_gemini_entries(config: dict, entries: list[dict]) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        new_payload = entry["payload"]
        fp_new = fingerprint_hook(new_payload)
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(new_payload)
    return settings


def _merge_cursor_entries(config: dict, entries: list[dict]) -> dict:
    cfg = dict(config) if config else {}
    hooks = cfg.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        fp_new = fingerprint_hook(entry["payload"])
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(entry["payload"])
    return cfg


def _remove_from_claude(config: dict, event_key: str, fingerprint: str) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.get("hooks", {})
    if event_key not in hooks:
        return settings
    hooks[event_key] = [e for e in hooks[event_key] if fingerprint_hook(e) != fingerprint]
    if not hooks[event_key]:
        del hooks[event_key]
    if not hooks:
        settings.pop("hooks", None)
    return settings
```

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/installer.py tests/test_hooks_installer_merge.py
git commit -m "feat(hooks): add pure merge helpers for claude/gemini/cursor configs"
```

---

#### Task 9b: Installer entrypoint — Claude target only, happy path

**Files:** extend `aec/lib/hooks/installer.py`, `tests/test_hooks_installer.py`

Target-minimal slice. End-to-end: load `hooks.json` → validate → translate for Claude → merge into `.claude/settings.json` → record state. No other agents yet, no `when`, no scripts.

- [ ] **Step 1: Write failing test.**

```python
# tests/test_hooks_installer.py
import json
import pytest


class TestInstallItemHooksClaude:
    def test_installs_generic_claude_hook_end_to_end(self, tmp_path):
        from aec.lib.hooks.installer import install_item_hooks

        # Fake item dir shipping a hooks.json
        item_dir = tmp_path / "item"
        item_dir.mkdir()
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0",
            "hooks": [{
                "id": "lint", "event": "on_file_edit",
                "command": "echo hi", "description": "lint",
            }],
        }))

        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["claude"],
        )

        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert settings["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write|MultiEdit"
        assert settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == "echo hi"

        state_path = repo_root / ".aec/installed-hooks/skill.demo.json"
        state = json.loads(state_path.read_text())
        assert state["item_version"] == "1.0.0"
        assert state["agents_targeted"] == ["claude"]
        assert len(state["hooks_installed"]) == 1
        assert state["hooks_installed"][0]["hook_id"] == "lint"
        assert state["hooks_installed"][0]["agent"] == "claude"
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement `install_item_hooks`.** Only handles `agents=["claude"]` in this slice; later slices add gemini/cursor/git.

```python
# aec/lib/hooks/installer.py (additions)
import json
from pathlib import Path
from typing import Sequence

from ..atomic_write import atomic_write_json
from .schema import load_hooks_file
from .validator import validate_hooks_file
from .translator import translate_to_agent
from .fingerprint import fingerprint_hook
from . import state as hook_state


def install_item_hooks(
    *, item_type: str, item_key: str, item_version: str,
    item_dir: Path, repo_root: Path,
    agents: Sequence[str],
) -> None:
    hooks_json = item_dir / "hooks.json"
    if not hooks_json.exists():
        return
    hf = load_hooks_file(hooks_json)
    errs, _warns = validate_hooks_file(hf, expected_version=item_version)
    if errs:
        messages = "; ".join(f"{e.path}: {e.message}" for e in errs)
        raise ValueError(f"hooks.json validation failed: {messages}")

    resolved = {h.id: h.command for h in hf.hooks}  # script resolution in 9e

    st = hook_state.load_state(repo_root, item_type=item_type, item_key=item_key)
    st.item_version = item_version
    st.hooks_file_hash = fingerprint_hook(json.loads(hooks_json.read_text()))
    st.agents_targeted = list(agents)
    st.hooks_installed = []

    for agent in agents:
        entries = translate_to_agent(hf, agent, resolved_commands=resolved)
        if agent == "claude":
            _install_claude(repo_root, entries, st, item_version)
        # gemini/cursor/git added in 9c/9d
        else:
            raise NotImplementedError(f"agent {agent!r} handled in later task")

    hook_state.save_state(repo_root, st)


def _install_claude(repo_root: Path, entries: list[dict], st, item_version: str) -> None:
    settings_path = repo_root / ".claude/settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    updated = _merge_claude_entries(existing, entries)
    atomic_write_json(settings_path, updated)
    for entry in entries:
        fp = fingerprint_hook(entry["payload"])
        idx = next(
            (i for i, e in enumerate(updated["hooks"][entry["event_key"]])
             if fingerprint_hook(e) == fp),
            -1,
        )
        st.hooks_installed.append({
            "hook_id": entry["source_hook_id"],
            "agent": "claude",
            "target_json_pointer": f"/hooks/{entry['event_key']}/{idx}",
            "content_fingerprint": fp,
            "version": item_version,
        })
```

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): install Claude-target hooks with state recording"
```

---

#### Task 9c: Idempotent re-install + remove_item_hooks

**Files:** extend `aec/lib/hooks/installer.py`, `tests/test_hooks_installer.py`

- [ ] **Step 1: Write failing tests.**

```python
class TestInstallIdempotent:
    def test_install_twice_no_duplicates(self, tmp_path):
        import json
        from aec.lib.hooks.installer import install_item_hooks
        # Setup (reused from 9b fixture helper):
        repo_root = tmp_path / "repo"
        (repo_root / ".claude").mkdir(parents=True)
        item_dir = tmp_path / "sources/skills/demo"
        item_dir.mkdir(parents=True)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0",
            "hooks": [{
                "id": "h1", "event": "on_file_edit",
                "command": "echo hi", "description": "d",
            }],
        }))
        kwargs = dict(
            item_dir=item_dir, item_type="skill", item_key="demo",
            item_version="1.0.0", repo_root=repo_root,
            agents=["claude"], allow_custom_check=False,
        )
        install_item_hooks(**kwargs)
        install_item_hooks(**kwargs)  # second call should be a no-op
        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert len(settings["hooks"]["PostToolUse"]) == 1


class TestRemoveItemHooks:
    def test_remove_cleans_settings_and_state(self, tmp_path):
        import json
        from aec.lib.hooks.installer import install_item_hooks, remove_item_hooks
        # Setup identical to idempotent test above.
        repo_root = tmp_path / "repo"
        (repo_root / ".claude").mkdir(parents=True)
        item_dir = tmp_path / "sources/skills/demo"
        item_dir.mkdir(parents=True)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0",
            "hooks": [{
                "id": "h1", "event": "on_file_edit",
                "command": "echo hi", "description": "d",
            }],
        }))
        install_item_hooks(
            item_dir=item_dir, item_type="skill", item_key="demo",
            item_version="1.0.0", repo_root=repo_root,
            agents=["claude"], allow_custom_check=False,
        )
        remove_item_hooks(item_type="skill", item_key="demo", repo_root=repo_root)
        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert settings.get("hooks", {}).get("PostToolUse", []) == []
        assert not (repo_root / ".aec/installed-hooks/skill.demo.json").exists()
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement `remove_item_hooks`** — loads state, iterates `hooks_installed`, removes each by `(agent, event_key, content_fingerprint)`, then `hook_state.remove_state(...)`.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): idempotent install and clean removal"
```

---

#### Task 9d: Gemini + Cursor targets

**Files:** extend `aec/lib/hooks/installer.py`, `tests/test_hooks_installer.py`

- [ ] **Step 1: Write failing tests.**

```python
class TestInstallGeminiAndCursor:
    def test_install_all_three_targets(self, tmp_path):
        import json
        from aec.lib.hooks.installer import install_item_hooks
        repo_root = tmp_path / "repo"
        (repo_root / ".claude").mkdir(parents=True)
        (repo_root / ".gemini").mkdir()
        (repo_root / ".cursor").mkdir()
        item_dir = tmp_path / "sources/skills/demo"
        item_dir.mkdir(parents=True)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0",
            "hooks": [{
                "id": "h1", "event": "on_file_edit",
                "command": "echo hi", "description": "d",
            }],
        }))
        install_item_hooks(
            item_dir=item_dir, item_type="skill", item_key="demo",
            item_version="1.0.0", repo_root=repo_root,
            agents=["claude", "gemini", "cursor"], allow_custom_check=False,
        )
        assert (repo_root / ".claude/settings.json").exists()
        assert (repo_root / ".gemini/settings.json").exists()
        assert (repo_root / ".cursor/hooks.json").exists()
        # Shape sanity — each file parses and has entries for the item.
        gemini = json.loads((repo_root / ".gemini/settings.json").read_text())
        assert "hooks" in gemini
        cursor = json.loads((repo_root / ".cursor/hooks.json").read_text())
        assert cursor.get("hooks") or cursor.get("afterFileEdit")
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement `_install_gemini` and `_install_cursor`.** Writing to `.gemini/settings.json` and `.cursor/hooks.json` respectively. Use `_merge_gemini_entries` / `_merge_cursor_entries` from Task 9a. Each follows the same "load-or-default → merge → atomic_write_json" shape as `_install_claude` in 9b.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): install Gemini and Cursor targets"
```

---

#### Task 9e: Git target via `git_blocks.py`

**Files:** extend `aec/lib/hooks/installer.py`, `tests/test_hooks_installer.py`

- [ ] **Step 1: Write failing test.**

```python
class TestInstallGitTarget:
    def test_install_pre_commit_writes_delimited_block(self, tmp_path):
        import json
        from aec.lib.hooks.installer import install_item_hooks
        repo_root = tmp_path / "repo"
        (repo_root / ".git/hooks").mkdir(parents=True)
        item_dir = tmp_path / "sources/skills/demo"
        item_dir.mkdir(parents=True)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0",
            "hooks": [{
                "id": "lint", "event": "pre_commit",
                "command": "echo linting", "description": "d",
            }],
        }))
        install_item_hooks(
            item_dir=item_dir, item_type="skill", item_key="demo",
            item_version="1.0.0", repo_root=repo_root,
            agents=["git"], allow_custom_check=False,
        )
        content = (repo_root / ".git/hooks/pre-commit").read_text()
        assert "# >>> AEC:BEGIN skill:demo lint" in content
        assert "# <<< AEC:END skill:demo lint" in content
        assert "echo linting" in content

    def test_reinstall_produces_byte_identical_block(self, tmp_path):
        # (same setup) — install twice and assert the file hash is stable.
        ...
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement `_install_git`.** Calls `git_blocks.write_block(hook_file, item_key=f"{type}:{key}", hook_id=id, version=v, command=cmd)`. Fingerprint the block's content (not a JSON payload) — for state, use `fingerprint_hook({"command": cmd, "hook_name": "pre-commit"})`. Ensure `.git/hooks/` exists; create if missing. `chmod +x` the file on non-Windows (wrap chmod in try/except — see Task 8 Windows-compat note).
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): install git hooks via delimited AEC:BEGIN/END blocks"
```

---

#### Task 9f: Script resolution — `aec run-script` command rewriting

**Files:** extend `aec/lib/hooks/installer.py`, `tests/test_hooks_installer.py`

When a hook `command` starts with `aec run-script <item> <script>`, the installer resolves `<script>` to an absolute path (project-first, global fallback per `aec.lib.scope`) and embeds the resolved path. If the script does not exist in either scope, installation fails loudly per spec §2.2.

- [ ] **Step 1: Write failing tests** — (a) script exists in item_dir: resolves correctly; (b) script missing: install fails with clear error.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement `_resolve_script_commands(hf, item_dir, scope)`.** Parses commands of the form `aec run-script <item> <script>`; rewrites to the actual absolute path to the script (keeping it runnable via the installed binary).
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): resolve aec run-script commands to absolute script paths"
```

---

#### Task 9g: `when` predicate partitioning — hooks_skipped population

**Files:** extend `aec/lib/hooks/installer.py`, `tests/test_hooks_installer.py`

Before translation, evaluate `when` for each generic hook; skipped hooks go to `state.hooks_skipped` (not installed).

**Security policy (P1-D8):** The first time an item is installed whose hooks contain a `when.custom_check`, the installer prompts the user: `This item's hooks.json executes custom shell: <excerpt>. Allow? [y/N]`. Persist "allowed" flag in the item's state; subsequent installs of the same `(item_type, item_key, item_version)` skip the prompt. **No prompting during tests** — tests pass `allow_custom_check=True` explicitly.

- [ ] **Step 1: Write failing tests.**
  - `when.repo_has_any=["pyproject.toml"]` in repo without it → hook ends up in `hooks_skipped`, NOT in `.claude/settings.json`, reason captured.
  - First install with `custom_check` and `allow_custom_check=False` → `PermissionError`-style typed exception.
  - First install with `custom_check` and `allow_custom_check=True` → succeeds; state records allowance.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement.** Call `evaluate_when(h.when, repo_root)` per generic hook; partition accordingly. Surface `allow_custom_check: bool = False` parameter on `install_item_hooks`.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): partition hooks via when predicates and gate custom_check"
```

**Partial-failure rollback (Task 9 closing note):** The installer writes to up to four target files then the state file. If any intermediate write fails (permission error, disk full, corrupt existing JSON), the previously-written files remain modified. For P1 the policy is: surface the exception, leave partial state, require `aec hooks repair` (Task 12f) to reconcile. A true transactional installer with rollback staging is out of scope; a TODO comment in `install_item_hooks` documents this and a future task will harden.

---

### Task 10: Drift detection

**Files:** `aec/lib/hooks/drift.py`, `tests/test_hooks_drift.py`

Per spec §3.2: fast path — if `hooks_file_hash` in state equals `fingerprint_hook(json.load(source hooks.json))`, skip drift evaluation entirely. Slow path: iterate `state.hooks_installed`, resolve `target_json_pointer` in the live config, compare `content_fingerprint`.

Drift kinds:
- `missing` — entry in state, not in config.
- `mutated` — entry present but fingerprint differs.
- `upgrade_available` — installed version differs from source version (hash differs at top level).

- [ ] **Step 1: Write failing tests.**

```python
class TestDetectDrift:
    def test_fresh_install_has_no_drift(self, tmp_path):
        # install, then immediately detect_drift → []
        ...

    def test_manual_deletion_reports_missing(self, tmp_path):
        # install, then manually empty .claude/settings.json, then detect_drift
        ...

    def test_manual_mutation_reports_mutated(self, tmp_path):
        # install, then modify command in .claude/settings.json, then detect_drift
        ...

    def test_source_hash_change_reports_upgrade_available(self, tmp_path):
        # install, then overwrite hooks.json with new content, detect_drift
        ...

    def test_unchanged_source_hash_skips_evaluation(self, tmp_path, monkeypatch):
        # if state.hooks_file_hash == fingerprint(source), return [] fast-path
        ...
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** `detect_drift(repo_root, item_type, item_key) -> list[DriftReport]` and `detect_all_drift(repo_root) -> dict[(type, key), list[DriftReport]]`.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git add aec/lib/hooks/drift.py tests/test_hooks_drift.py
git commit -m "feat(hooks): detect drift (missing/mutated/upgrade_available)"
```

---

### Task 11: Tiered upgrade prompts (split into 11a–11d)

**Files:** `aec/lib/hooks/prompts.py`, `tests/test_hooks_prompts.py`

Per spec §3.3: top-level `Y/n/d/s/v` prompt; `v` enters per-hook `y/n/d/q` loop.

#### Task 11a: Top-level prompt and decision dataclass

- [ ] **Step 1: Write failing tests.**

```python
# tests/test_hooks_prompts.py
import pytest

SCRIPTED = lambda answers: iter(answers)


class TestTopLevelPrompt:
    def test_Y_accepts_all(self, monkeypatch):
        from aec.lib.hooks.prompts import prompt_upgrade, UpgradeDecision
        answers = SCRIPTED(["Y"])
        monkeypatch.setattr("builtins.input", lambda *a, **kw: next(answers))
        decision = prompt_upgrade(item_key="demo", diff_summary="x", hooks_changed=[
            {"hook_id": "a", "from_fp": "sha256:1", "to_fp": "sha256:2"},
        ])
        assert decision.accept_all is True

    def test_n_rejects_all(self, monkeypatch):
        from aec.lib.hooks.prompts import prompt_upgrade
        answers = SCRIPTED(["n"])
        monkeypatch.setattr("builtins.input", lambda *a, **kw: next(answers))
        decision = prompt_upgrade("demo", "x", [{"hook_id": "a"}])
        assert decision.accept_all is False
        assert decision.per_hook == {}

    def test_s_records_skip_version(self, monkeypatch):
        from aec.lib.hooks.prompts import prompt_upgrade
        answers = SCRIPTED(["s"])
        monkeypatch.setattr("builtins.input", lambda *a, **kw: next(answers))
        decision = prompt_upgrade("demo", "x", [{"hook_id": "a"}])
        assert decision.skip_version is True
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement `UpgradeDecision` dataclass + top-level prompt.**
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): top-level upgrade prompt (Y/n/s/d loop)"
```

#### Task 11b: Diff rendering (`d` branch)

- [ ] **Step 1: Write failing test.**

```python
def test_d_renders_diff_then_reprompts(monkeypatch, capsys):
    from aec.lib.hooks.prompts import prompt_upgrade
    answers = SCRIPTED(["d", "Y"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(answers))
    decision = prompt_upgrade("demo", "rendered-diff-here", [{"hook_id": "a"}])
    captured = capsys.readouterr()
    assert "rendered-diff-here" in captured.out
    assert decision.accept_all is True
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement `d` branch** — prints diff, re-enters prompt loop.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): render diff in upgrade prompt (d branch)"
```

#### Task 11c: Per-hook loop (`v` branch with y/n/d/q)

- [ ] **Step 1: Write failing tests** for each per-hook branch including `q` mid-loop.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** per-hook loop; on `q`, `decision.per_hook` contains only pre-`q` answers and `decision.quit_mid_loop = True`.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): per-hook v-loop with y/n/d/q in upgrade prompt"
```

#### Task 11d: State-commit policy on `q`

- [ ] **Step 1: Write failing test** — `q` mid-loop preserves already-accepted decisions in state; rejected/unanswered remain pending.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** `apply_decision(decision, repo_root, item_type, item_key)` helper.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): persist partial decisions on mid-loop quit"
```

---

### Task 12: Remaining `aec hooks` CLI commands + top-level `aec run-script`

Each command gets its own test scaffold + implementation + commit. All CLI implementations in `hooks_cmd.py` EXCEPT `run-script`, which lives in `run_script_cmd.py` to avoid circular import (hooks_cmd.py cannot reference `app` from `aec/cli.py` since `aec/cli.py` imports `hooks_cmd`).

#### Task 12a: `aec hooks list`

- [ ] **Step 1: Write failing test.**

```python
class TestHooksListCLI:
    def test_list_shows_installed_items(self, tmp_path, monkeypatch):
        # Install two items, then invoke `aec hooks list`
        # Assert both appear in output
        ...
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** `@hooks_app.command("list")` — iterates `state.list_installed_items(repo_root)`, prints table.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): aec hooks list command"
```

#### Task 12b: `aec hooks install`

- [ ] **Step 1: Write failing test.**

```python
class TestHooksInstallCLI:
    def test_install_single_item(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app
        # Point scope resolver at tmp_path repo with the fixture skill already on disk.
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, ["hooks", "install", "skill:hooks-fixture-skill"])
        assert result.exit_code == 0
        state_file = tmp_path / ".aec/installed-hooks/skill.hooks-fixture-skill.json"
        assert state_file.exists()
        # Hook also wired into Claude settings
        claude_settings = (tmp_path / ".claude/settings.json").read_text()
        assert "aec run-script" in claude_settings
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** — thin wrapper around `installer.install_item_hooks` with scope resolution. Resolves `<type>:<key>` → source dir → calls installer.
- [ ] **Step 4-5: Verify pass + commit.**

```bash
git commit -am "feat(hooks): aec hooks install command"
```

#### Task 12c: `aec hooks upgrade`

**Behavior wiring (addresses I3):** Before prompting, the implementation MUST call `state.is_version_skipped(st, source_version)` — if True, skip the item silently. The `skipped_versions` persistence in Task 12g is only load-bearing if this command honors it. Also: if `drift.detect_drift` surfaces a `custom_check` command that has changed since the last install, reset `state.allow_custom_check = False` and re-prompt (per P1-D8).

- [ ] **Step 1: Write failing test.**

```python
class TestHooksUpgradeCLI:
    def test_upgrade_respects_skipped_versions(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app
        from aec.lib.hooks.state import load_state, save_state, mark_version_skipped
        # Pre-seed state: skill.demo installed at 1.0.0, user skipped 2.0.0
        st = load_state(tmp_path, "skill", "demo")
        st.item_version = "1.0.0"
        mark_version_skipped(st, "2.0.0")
        save_state(tmp_path, st)
        # Source on disk is at 2.0.0 (fixture)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, ["hooks", "upgrade", "skill:demo"], input="")
        assert result.exit_code == 0
        assert "skipped" in result.stdout.lower() or "nothing to upgrade" in result.stdout.lower()
        # Prompt did NOT appear — assert by checking no "[Y/n/d/s/v]" in output
        assert "[Y/n/d/s/v]" not in result.stdout
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** — `drift.detect_drift` + skip-version check + `prompts.prompt_upgrade` + `installer.install_item_hooks` with fresh entries. State update persists new item_version + content fingerprints on accept.
- [ ] **Step 4-5: Verify pass + commit.**

```bash
git commit -am "feat(hooks): aec hooks upgrade command"
```

#### Task 12d: `aec hooks remove`

- [ ] **Step 1: Write failing test.**

```python
class TestHooksRemoveCLI:
    def test_remove_deletes_state_and_unwires_entries(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app
        # Pre-install skill:demo (use installer directly to set up scenario)
        # ... setup ...
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, ["hooks", "remove", "skill:demo", "--yes"])
        assert result.exit_code == 0
        assert not (tmp_path / ".aec/installed-hooks/skill.demo.json").exists()
        # Claude settings no longer contain the item's hook entry
        claude = (tmp_path / ".claude/settings.json").read_text()
        assert "skill:demo" not in claude
```

- [ ] **Step 2-3: Verify fail + implement** — wraps `installer.remove_item_hooks` + deletes per-item state.
- [ ] **Step 4-5: Verify pass + commit.**

```bash
git commit -am "feat(hooks): aec hooks remove command"
```

#### Task 12e: `aec hooks diff`

- [ ] **Step 1: Write failing test.**

```python
class TestHooksDiffCLI:
    def test_diff_shows_unified_diff(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app
        # Install skill:demo, then mutate .claude/settings.json by hand
        # ... setup that creates drift ...
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, ["hooks", "diff", "skill:demo"])
        assert result.exit_code == 0
        # Unified-diff markers present
        assert "---" in result.stdout
        assert "+++" in result.stdout
        assert result.stdout.count("\n") > 3  # real multi-line diff, not empty
```

- [ ] **Step 2-3: Verify fail + implement** — for each installed agent target, render a unified diff between the state-recorded content_fingerprint payload and the current on-disk payload at `target_json_pointer`. Useful for debugging drift.
- [ ] **Step 4-5: Verify pass + commit.**

```bash
git commit -am "feat(hooks): aec hooks diff command"
```

#### Task 12f: `aec hooks repair`

- [ ] **Step 1: Write failing test.**

```python
class TestHooksRepairCLI:
    def test_repair_restores_missing_hook(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app
        # Install skill:demo, then manually delete its entry from .claude/settings.json
        # ... setup ...
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, ["hooks", "repair", "skill:demo"])
        assert result.exit_code == 0
        claude = (tmp_path / ".claude/settings.json").read_text()
        assert "skill:demo" in claude  # entry restored

    def test_repair_does_not_auto_upgrade(self, tmp_path, monkeypatch):
        # Drift type is upgrade_available → repair must leave alone
        # ... setup with newer source than state ...
        result = runner.invoke(app, ["hooks", "repair", "skill:demo"])
        assert result.exit_code == 0
        assert "upgrade" in result.stdout.lower()
        assert "run `aec hooks upgrade`" in result.stdout.lower()
```

- [ ] **Step 2-3: Verify fail + implement** — for each state entry with `missing`/`mutated` drift, reinstall from source. For `upgrade_available` drift, do NOT auto-upgrade (user must run `aec hooks upgrade`) — print a directive message.
- [ ] **Step 4-5: Verify pass + commit.**

```bash
git commit -am "feat(hooks): aec hooks repair command"
```

#### Task 12g: `aec hooks skip-version`

- [ ] **Step 1: Write failing test.**

```python
class TestHooksSkipVersionCLI:
    def test_skip_version_persists_to_state(self, tmp_path, monkeypatch):
        from typer.testing import CliRunner
        from aec.cli import app
        from aec.lib.hooks.state import load_state, save_state
        # Pre-seed state with skill:demo installed
        st = load_state(tmp_path, "skill", "demo")
        st.item_version = "1.0.0"
        save_state(tmp_path, st)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(app, ["hooks", "skip-version", "skill:demo", "2.0.0"])
        assert result.exit_code == 0
        reloaded = load_state(tmp_path, "skill", "demo")
        assert "2.0.0" in reloaded.skipped_versions
```

- [ ] **Step 2-3: Verify fail + implement** — records a version in `state.skipped_versions` via `mark_version_skipped`, persists via `save_state`. Consumed by Task 12c's upgrade command.
- [ ] **Step 4-5: Verify pass + commit.**

```bash
git commit -am "feat(hooks): aec hooks skip-version command"
```

#### Task 12h: Top-level `aec run-script`

Separate module to avoid circular import. `aec/commands/run_script_cmd.py` defines a plain function; `aec/cli.py` registers it via decorator.

- [ ] **Step 1: Write failing test.**

```python
class TestRunScriptCLI:
    def test_run_script_invokes_resolved_script(self, tmp_path):
        # Create fake script, invoke `aec run-script skill:demo demo.sh arg1`
        # Assert subprocess ran, exit code propagated.
        ...
```

- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement.**

```python
# aec/commands/run_script_cmd.py
"""`aec run-script <item> <script>` — scope-aware script runner."""
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer

from ..lib.scope import resolve_scope, find_tracked_repo


def run_script(
    item: str = typer.Argument(..., help="Item in form <type>:<key>, e.g. skill:my-skill"),
    script: str = typer.Argument(..., help="Script filename relative to the item's scripts/ dir"),
    extra: Optional[List[str]] = typer.Argument(None),
) -> None:
    """Resolve <script> from the item's install directory and exec it."""
    # ... scope resolution; subprocess.run(); sys.exit(rc)
    raise NotImplementedError  # filled in during Step 3


# aec/cli.py addition (inside `if HAS_TYPER:` block, near the other top-level commands):
#     from .commands.run_script_cmd import run_script
#     app.command("run-script")(run_script)
```

- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(hooks): aec run-script top-level command"
```

---

### Task 13: Integrate `installer.install_item_hooks` into `aec install`

**Files modified:** `aec/commands/install_cmd.py`, possibly `aec/commands/install.py`
**Fixture created:** `tests/fixtures/skills/hooks-fixture-skill/`

- [ ] **Step 1: Investigate legacy integration points.**

```bash
grep -rn "get_verification_playwright_hook\|_post_install_playwright_pipeline" aec/ | tee /tmp/legacy-hook-callsites.txt
grep -rn "def install\|install_cmd\|install_item" aec/commands/install*.py | tee /tmp/install-entrypoints.txt
```

Report whether `aec/commands/install.py` is active for any install path. If yes, the hooks integration lands in BOTH files. If it's dead (superseded by `install_cmd.py`), note so in the commit body and leave untouched.

- [ ] **Step 2: Create fixture skill.**

```bash
mkdir -p tests/fixtures/skills/hooks-fixture-skill/scripts
```

```markdown
<!-- tests/fixtures/skills/hooks-fixture-skill/SKILL.md -->
---
name: hooks-fixture-skill
version: 1.0.0
description: Fixture skill used by installer integration tests.
---

Test fixture only.
```

```json
// tests/fixtures/skills/hooks-fixture-skill/hooks.json
{
  "$schema": "https://bernierllc.io/schemas/aec-hooks-v1.json",
  "version": "1.0.0",
  "hooks": [
    {
      "id": "demo",
      "event": "on_file_edit",
      "command": "aec run-script hooks-fixture-skill demo.sh",
      "description": "Fixture hook"
    }
  ]
}
```

```bash
# tests/fixtures/skills/hooks-fixture-skill/scripts/demo.sh
#!/usr/bin/env bash
echo "demo ran"
```
(Make executable: `chmod +x tests/fixtures/skills/hooks-fixture-skill/scripts/demo.sh`.)

- [ ] **Step 3: Write failing integration test.**

```python
# tests/test_hooks_cli.py — add
class TestInstallWiresHooks:
    def test_aec_install_calls_install_item_hooks_for_fixture_skill(
        self, tmp_path, monkeypatch,
    ):
        # Install `hooks-fixture-skill` into tmp_path; verify:
        #  - .claude/settings.json has PostToolUse entry
        #  - .aec/installed-hooks/skill.hooks-fixture-skill.json recorded
        ...
```

- [ ] **Step 4: Verify fail.**

- [ ] **Step 5: Implement `_install_item_hooks_if_present`** in `install_cmd.py`:

```python
def _install_item_hooks_if_present(
    item_dir: Path, item_type: str, item_key: str, item_version: str,
    repo_root: Path, agents: Sequence[str] = ("claude", "gemini", "cursor", "git"),
) -> None:
    if not (item_dir / "hooks.json").exists():
        return
    from ..lib.hooks.installer import install_item_hooks
    install_item_hooks(
        item_type=item_type, item_key=item_key, item_version=item_version,
        item_dir=item_dir, repo_root=repo_root, agents=list(agents),
    )
```

Wire into the skill/rule/agent install flow. `_post_install_playwright_pipeline` becomes a guarded no-op:

```python
def _post_install_playwright_pipeline(*args, **kwargs):
    # Superseded by install_item_hooks when the skill ships hooks.json.
    # Retained as a no-op shim for backward compatibility; deletion in Phase 3.
    return
```

If Step 1 showed `aec/commands/install.py` is still active, add the same `_install_item_hooks_if_present` call there.

- [ ] **Step 6: Verify pass.** All existing hook tests still green: `pytest tests/test_hooks.py tests/test_catalog_hashes_hook.py tests/test_repo_hooks.py -v`.

- [ ] **Step 7: Commit.**

```bash
git add tests/fixtures/skills/hooks-fixture-skill/ aec/commands/install_cmd.py \
        aec/commands/install.py tests/test_hooks_cli.py
git commit -m "feat(hooks): wire hooks.json into aec install via installer.install_item_hooks"
```

---

### Task 14: Integrate upgrade flow

**Files modified:** `aec/commands/upgrade.py` (specifically `run_upgrade`)

- [ ] **Step 1: Identify callsite.** `aec/commands/upgrade.py::run_upgrade` handles per-item upgrades; the per-item loop is in `_upgrade_scope`.
- [ ] **Step 2: Write integration test** — after upgrading an item with changed hooks.json, `prompts.prompt_upgrade` is called and state reflects the new version if the user accepts.
- [ ] **Step 3: Verify fail.**
- [ ] **Step 4: Implement** — in the per-item upgrade branch, call `installer.upgrade_item_hooks(item_type, item_key, new_version, item_dir, repo_root, agents)` which internally uses `detect_drift` + `prompt_upgrade`.
- [ ] **Step 5: Verify pass.**
- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(hooks): integrate hooks upgrade flow into aec upgrade"
```

---

### Task 15: AEC pre-push validator guard (spec §2.3)

**Files:**
- Create: `scripts/hooks-pre-push-validate.sh`
- Modify: existing AEC pre-push wiring (see `project_hook_worktree_quirks.md` for the current pre-push file location)

Runs `aec hooks validate` against every `hooks.json` in the repo and rejects the push on errors.

- [ ] **Step 1: Write test** — simulate pre-push with a bad `hooks.json` in a fixture; verify non-zero exit.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** shell script that `find`s `**/hooks.json`, pairs with sibling item version (from `SKILL.md` / `agent.md` / `rule.md` frontmatter), invokes `aec hooks validate --item-version <v>`.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Wire into AEC's existing pre-push.** Use the `# >>> AEC:BEGIN ... # <<< AEC:END` block pattern from Task 8 so removal is clean.
- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(hooks): pre-push guard validates every hooks.json before accepting"
```

---

### Task 16: Wire `remove_item_hooks` into `aec uninstall` (added 2026-05-19)

**Why added:** The original 2026-04-21 plan covered install (Task 13) and upgrade (Task 14) wiring but not the uninstall path. Without this task, removing a hooks-shipping item via `aec uninstall <type> <name>` leaves three forms of orphaned state behind: (a) entries in `.claude/settings.json` / `.gemini/settings.json` / `.cursor/settings.json` whose `fingerprint`/`installed_by` reference a deleted item, (b) `aec run-script` commands in those entries pointing at a deleted item directory, and (c) the `.aec/installed-hooks/<type>.<key>.json` state file. User explicitly required this coverage during the 2026-05-19 wrap-up.

**Files modified:** `aec/commands/uninstall.py` (specifically `run_uninstall`)

**Files referenced (must stay green):** `aec/lib/hooks/installer.py` (`remove_item_hooks`), `aec/lib/hooks/state.py` (`load_state`, `remove_state`).

- [ ] **Step 1: Investigate the existing `run_uninstall` surface.**
  - Confirm the function signature `run_uninstall(item_type, name, global_flag=False, yes=False)` and that scope resolution via `resolve_scope(global_flag)` yields `scope.repo_path` for the local case.
  - Confirm `item_type` arrives as one of `skill|rule|agent` (uninstall already returns early for `mcp`, which does not ship `hooks.json`).
  - Note: `remove_item_install` is called *after* the file/directory is deleted; hook removal must happen *before* directory deletion so that the installer can read `hooks.json` to know what to remove (or alternatively, must rely solely on the state file, see Step 3).

- [ ] **Step 2: Write failing test in `tests/test_hooks_installer.py` (or a new `tests/test_uninstall_hooks_wiring.py` if cleaner).**

```python
def test_aec_uninstall_removes_hooks_via_state(tmp_path, monkeypatch):
    """Given a skill with installed hooks recorded in state, run_uninstall must
    remove the corresponding Claude/Gemini/Cursor/git entries and delete the
    .aec/installed-hooks/skill.<name>.json state file."""
    # 1. Set up a fake repo under tmp_path with a skill installed via
    #    install_item_hooks (use the Task 13 fixture skill).
    # 2. Confirm .claude/settings.json has the expected PostToolUse entry
    #    and .aec/installed-hooks/skill.hooks-fixture-skill.json exists.
    # 3. Call run_uninstall("skill", "hooks-fixture-skill", global_flag=False, yes=True).
    # 4. Assert: the PostToolUse entry is gone, the state file is gone, no
    #    AEC:BEGIN/END blocks remain in any git hook file.
    ...
```

- [ ] **Step 3: Verify fail** (no caller of `remove_item_hooks` yet).

- [ ] **Step 4: Implement.** Add a helper and wire it in. The helper drives off **state**, not `hooks.json`, because (a) the item directory may already have been deleted by the time we want to remove hooks if we ever reorder operations, (b) the state file is authoritative for what was installed — `hooks.json` could have changed shape since install and is no longer trustworthy for cleanup.

```python
# aec/commands/uninstall.py
def _remove_item_hooks_if_present(
    item_type: str, item_key: str, repo_root: Path,
) -> None:
    """Best-effort: remove any installed hook entries + state for this item.

    Drives off state.load_state, not hooks.json on disk, so this works even
    when the item directory has already been or is about to be deleted.
    """
    from ..lib.hooks.state import load_state
    from ..lib.hooks.installer import remove_item_hooks

    try:
        state = load_state(repo_root, item_type, item_key)
    except FileNotFoundError:
        return  # nothing to remove; item never installed hooks
    if not state.installed_entries:
        # State exists but no entries (e.g., all hooks were `when`-skipped at
        # install time). Just delete the state file.
        from ..lib.hooks.state import remove_state
        remove_state(repo_root, item_type, item_key)
        return
    remove_item_hooks(
        item_type=item_type, item_key=item_key, repo_root=repo_root,
    )
```

Then wire into `run_uninstall`. Place the call **before** the `shutil.rmtree(item_path)` / `item_path.unlink()` block so the item directory is still intact if any future helper needs to read it, and **before** the `remove_item_install` manifest mutation so failures in hook removal surface before the manifest is updated:

```python
# inside run_uninstall, after the y/N prompt resolves to yes, before deletion:
if item_type != "mcp":
    _remove_item_hooks_if_present(item_type, name, scope.repo_path if not scope.is_global else Path.home())
```

For the global scope case (`scope.is_global == True`), the repo_root is ambiguous — hooks were installed into per-repo `.aec/installed-hooks/` directories across every repo that used this item. **Out of scope for this task:** sweeping every tracked repo. Document this in a code comment and a CHANGELOG note: *"Uninstalling a global item does not currently remove hook installations from per-repo `.aec/installed-hooks/` directories. Use `aec hooks remove <type>:<name>` per-repo (Task 12d) to clean those up. Tracked separately."* This is acceptable because global items shipping hooks is rare and `aec hooks list` (Task 12a) will surface the orphans.

- [ ] **Step 5: Verify pass.** Re-run the test from Step 2 plus the full hook test suite to make sure no regression in the install path:

```bash
pytest tests/test_hooks_installer.py tests/test_hooks_state.py tests/test_uninstall*.py -v
```

- [ ] **Step 6: Add a documentation line** to `docs/contributors/architecture.md` (or the equivalent section that describes the install/uninstall lifecycle) noting that `aec uninstall <type> <name>` cleans up hooks for the local-scope case, and that global-scope cleanup is per-repo and tracked separately.

- [ ] **Step 7: Commit.**

```bash
git add aec/commands/uninstall.py tests/test_uninstall_hooks_wiring.py docs/contributors/architecture.md
git commit -m "feat(hooks): wire remove_item_hooks into aec uninstall"
```

**Decision P1-D11 (added 2026-05-19):** Uninstall removal is driven off state (`.aec/installed-hooks/<type>.<key>.json`), not the item's `hooks.json` on disk. Rationale: state is the authoritative record of what was actually installed (after `when`-predicate filtering); `hooks.json` may have drifted since install. Reversibility: trivial — switch to reading `hooks.json` later if state ever proves insufficient, no data migration needed.

**Decision P1-D12 (added 2026-05-19):** Global-scope uninstall does NOT sweep per-repo state. Rationale: doing so requires enumerating every tracked repo (via `scope.get_all_tracked_repos()`), opening each `.aec/installed-hooks/`, and removing matching entries — a non-trivial cross-repo mutation that warrants its own design and its own y/N prompt per repo. Tracked as a follow-up: see "Open Questions for Review" #4 below. Reversibility: additive — implementing the sweep later is a pure capability add.

---

## CI expectations

- New tests run under the existing `pytest tests/` invocation (no new config).
- If CI runs `mypy aec/` or similar, the new package must type-check cleanly; dataclasses use lowercase generics (`list[str]`, `dict[str, str]`) which require Python 3.9+ at runtime — project is pinned 3.11+ in `pyproject.toml` so this is safe.
- If CI enforces the pre-push guard from Task 15, ensure a CI-equivalent job exists (`bash scripts/hooks-pre-push-validate.sh`).

---

## Final Verification (end of Phase 2)

- [ ] **Full test suite green.**

```bash
pytest tests/ -q
```

- [ ] **Manual end-to-end smoke test using the Task-13 fixture skill:**

```bash
cd /tmp && rm -rf scratch-hooks-smoke && mkdir scratch-hooks-smoke && cd scratch-hooks-smoke
git init

# Install the fixture skill from the AEC repo directly (requires pip install -e . in the repo).
aec install --from-path ~/projects/agents-environment-config/tests/fixtures/skills/hooks-fixture-skill

cat .claude/settings.json   # verify PostToolUse entry with Edit|Write|MultiEdit
cat .aec/installed-hooks/skill.hooks-fixture-skill.json   # verify state recorded
aec hooks list
aec hooks remove skill:hooks-fixture-skill
test ! -f .aec/installed-hooks/skill.hooks-fixture-skill.json || exit 1
```

If `aec install --from-path` is not supported, run the installer in Python directly via `python -c "from aec.lib.hooks.installer import install_item_hooks; …"`.

- [ ] **Confirm legacy tests still pass:** `pytest tests/test_hooks.py tests/test_repair_hook_keys.py tests/test_repo_hooks.py tests/test_discovery_hooks.py tests/test_catalog_hashes_hook.py -v`

- [ ] **Update CHANGELOG.md:**

```markdown
### Added
- `hooks.json` specification for skills/rules/agents with Claude/Gemini/Cursor/git hook translation (spec 2026-04-21).
- `aec hooks` CLI (`validate`, `list`, `install`, `upgrade`, `remove`, `diff`, `repair`, `skip-version`).
- `aec run-script <item> <script>` for scope-aware script invocation.
- Per-item `.aec/installed-hooks/<type>.<key>.json` state files (concurrency-safe).

### Changed
- `aec/lib/hooks.py` relocated to `aec/lib/hooks/__init__.py`; all existing symbols re-exported — no consumer changes required.
- `aec install` now installs item-ships hooks automatically via the new system; legacy `_post_install_playwright_pipeline` is superseded (no-op shim until Phase 3 removes it).

### Known divergence from spec
- Spec §2.1 Phase-2 exit criteria (delete `aec/lib/hooks.py`, migrate 8 internal importers) intentionally deferred to Phase 3 to keep this PR's blast radius bounded.
```

- [ ] **Final commit.**

```bash
git add CHANGELOG.md
git commit -m "docs(hooks): document Phase 1+2 in CHANGELOG"
```

---

## Decisions Embedded in This Plan

| ID | Decision | Alternative | Rationale | Reversibility |
|---|---|---|---|---|
| P1-D1 | Convert `aec/lib/hooks.py` → `aec/lib/hooks/__init__.py` as Task 0 | Rename legacy to `lint_hooks.py` and update all importers | Zero import-site churn; all existing tests stay untouched | `git mv aec/lib/hooks/__init__.py aec/lib/hooks.py` restores original layout; submodules must be removed first |
| P1-D2 | Script-path resolution lives in `installer.py` (Task 9f), not `scope.py` | Add script resolution to `scope.py` | Keeps `scope.py` focused on repo discovery; hook-specific concerns stay in `lib/hooks/` | Low cost — can move `_resolve_script_commands` into `scope.py` later if needed; pure function with no persisted state |
| P1-D3 | `aec hooks validate` accepts `--item-version` explicitly, doesn't sniff frontmatter | Auto-detect version from sibling SKILL.md | Validator is reusable from any caller (CI, pre-push, tests) without coupling to item discovery | Additive — sniffing can be layered on top later without breaking the explicit flag |
| P1-D4 | Legacy `_post_install_playwright_pipeline` becomes a no-op shim in Task 13, NOT deleted | Delete in Task 13 | Deferred to Phase 3 so this PR has a clean blast radius | Trivial — delete the shim in Phase 3 once callers migrate |
| P1-D5 | `predicates.py` evaluates `custom_check` via real `subprocess.run(shell=True)` | `shlex.split` + no-shell exec | Matches spec §1.4 (any single-line shell); timeout hard-capped | Medium — tightening to no-shell would be a breaking change for any hook author relying on shell features; announce with deprecation window |
| P1-D6 | **This plan diverges from spec §2.1 Phase-2 exit.** Legacy `aec/lib/hooks.py` surface stays re-exported through the new `__init__.py`; 8 internal importers stay on the legacy path. A Phase-3 plan is required to reach the spec-defined Phase-2 exit. Flagged loudly in Scope, CHANGELOG, and this decision | Delete legacy module + migrate all importers in this PR | Blast radius for migrating `cli.py`/`repo.py`/`install.py`/`doctor.py` is too large for a single PR; keeping them stable lets the new hooks surface ship fast | Explicit — Phase 3 plan is the reversal; no data migration required (re-exports are pure Python) |
| P1-D7 | `aec run-script` lives in `aec/commands/run_script_cmd.py` as a top-level command, NOT inside `hooks_cmd.py` | Place under `@hooks_app.command` | Avoids circular import (`cli.py` imports `hooks_cmd`; `hooks_cmd` would have to import `cli.app`); also matches user ergonomics (called from hooks, not a hook subcommand) | Easy — if the circular-import constraint ever relaxes, move the function into `hooks_cmd.py` and re-register via `@hooks_app.command`. Hook `command` strings (`aec run-script …`) are user-invocation style, don't change |
| P1-D8 | `when.custom_check` requires explicit user confirmation on first install; persisted in state | Allow freely / ban entirely | Balances spec §8.11 "out of scope for sandboxing" against not shipping an arbitrary-code-execution vector that runs silently | Medium — removing the flag means all existing state files need a migration step (add default `allow_custom_check: false`); load path handles missing key defensively |
| P1-D9 | **State is per-item** — one file per installed item at `.aec/installed-hooks/<type>.<key>.json`, not the single `.aec/installed-hooks.json` shown in spec §3.1 | Single state file with locking | Matches existing per-type `installed_store.py` pattern and user feedback `feedback_multi_agent_concurrency.md`; parallel installs of different items never touch the same file | Medium — consolidating back to a single file needs a one-shot migration script that reads `.aec/installed-hooks/*.json` and emits a single aggregated file. Straightforward but not zero-cost |
| P1-D10 | `match` field is parsed by schema (Task 1) but **silently dropped** by translator (Task 3) in P1 | (a) Translate to per-agent conditional, (b) remove from schema | Authoring surface is stable now; translation semantics deferred until we have real consumers. Schema accepts the field today so v1-format hooks.json don't need to be rewritten when translation arrives. Documented in `GenericHook.match` docstring | Easy — adding translation later is additive; existing hooks.json files with or without `match` both stay valid |

---

## Open Questions for Review

1. **Should `.aec/installed-hooks/` be git-ignored by default?** Plan assumes **committed** (it's per-repo install state, same rationale as `.aec.json`). Counter-argument: content includes `allow_custom_check` user decisions that might be personal to a dev machine.
2. **Global-scope state location:** for items installed globally (`~/.claude/skills/...`), plan records state only in per-repo `.aec/installed-hooks/`. If an item's hooks apply across every repo, should there be a parallel global state at `~/.agents-environment-config/installed-hooks/<type>.<key>.json`? Plan defers to "per-repo only" (matches spec §3.1) but flag if this creates drift-detection blind spots.
3. **`aec run-script` behavior when the referenced item is uninstalled between install and hook fire:** plan assumes `run-script` fails with a clear "not installed in this scope" error and the invoking agent sees the non-zero exit. Confirm this is acceptable UX.
4. **(added 2026-05-19) Global-item uninstall cross-repo sweep.** When a globally-installed item is uninstalled, should `aec uninstall --global <type> <name>` walk every tracked repo and remove that item's hook entries + state files from each? Plan defers this (decision P1-D12) and exposes the orphans via `aec hooks list`. Counter-argument: leaving orphans on disk means hooks may keep firing in repos where the item no longer exists, producing confusing "command not found" errors. If we want strict cleanup, the sweep is a separate task with its own per-repo y/N prompt; flag if this needs to land before any global hook-shipping item exists.
