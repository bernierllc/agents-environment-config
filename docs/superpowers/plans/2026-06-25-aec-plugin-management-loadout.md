# AEC Plugin Management & `loadout` Schema — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class plugin management to AEC (install/uninstall/list/export/apply/outdated) driven by an optional, open item-manifest schema called `loadout`, shipped as docs + JSON Schema in this repo.

**Architecture:** A new `loadout.py` library locates/parses (`.json` stdlib, `.yaml` optional) and validates a `plugin.json` manifest with a lightweight stdlib checker. A new `plugin_install.py` module resolves install targets (`supports ∩ detect_agents()`) and dispatches on `install_type` (`marketplace` / `per-tool` / `external`) under a per-type confirm-then-run vs instructions-only policy. Plugins follow the `mcp` precedent: a special-cased install handler, not a file copy. The manifest (`manifest_v2`) gains a `plugins` bucket so `list`/`export`/`apply`/`outdated` flow through. The `loadout` schema is documented + vendored as JSON Schema in `docs/loadout/` for external publishers.

**Tech Stack:** Python 3.10+, `typer` CLI, stdlib `json`/`subprocess`/`pathlib`. **Zero new runtime dependencies** — AEC's `pyproject.toml` declares `dependencies = []`. PyYAML and `jsonschema` are dev/optional only: YAML loadout files are parsed via an optional `import yaml` (graceful degrade to "JSON only" when absent), and `jsonschema` is used **only in tests** to prove the published JSON Schema and example files agree. AEC's own runtime validation is a small hand-rolled checker.

---

## Spec reference

Design spec: `docs/superpowers/specs/2026-06-25-aec-plugin-management-and-loadout-schema-design.md`

Read it before starting. Key invariants the plan enforces:
- **AEC never auto-installs.** Executable install types are confirm-then-run; `external` is never executed. (`feedback_no_auto_install`)
- **Additive, non-breaking.** Loadout is optional; items without it keep working.
- **Parallel-agent-safe.** One file per plugin (`plugins/<name>/plugin.json`); no shared manifest.
- **Zero runtime deps.** Do not add anything to `pyproject.toml` `dependencies`.

## Conventions for every task

- TDD: write the failing test, run it, see it fail for the *expected* reason, implement minimally, run it, see it pass, commit.
- Run a single test: `python -m pytest tests/<file>::<Class>::<test> -v`
- Run a file: `python -m pytest tests/<file> -v`
- Full suite before any "done" claim: `python -m pytest -q`
- Conventional commits, **lowercase** subject and scope: `feat(plugins): ...`, `feat(loadout): ...`, `test(plugins): ...`, `docs(loadout): ...`.
- Reference @superpowers:test-driven-development for the discipline; @superpowers:verification-before-completion before claiming any task complete.

## File structure (created / modified)

**New:**
- `aec/lib/loadout.py` — locate + parse (json|yaml) + validate a loadout manifest.
- `aec/lib/plugin_install.py` — target resolution, execution policy, three handlers, orchestrator.
- `plugins/ponytail/plugin.json` — vendored `per-tool` registry entry.
- `plugins/<external-example>/plugin.json` — vendored `external` registry entry.
- `docs/loadout/README.md`, `docs/loadout/schema/{plugin,skill,agent,rule}.schema.json`, `docs/loadout/examples/*`.
- `tests/test_loadout.py`, `tests/test_plugin_install.py`, `tests/test_loadout_schema.py`.

**Modified:**
- `aec/lib/manifest_v2.py` — `ITEM_TYPES`, `_empty_scope`, `record_plugin_install`.
- `aec/lib/sources.py` — `_discover_available_plugins`, hook into `discover_available`.
- `aec/commands/install_cmd.py` — `VALID_TYPES`, `TYPE_TO_PLURAL`, `plugin` branch.
- `aec/commands/uninstall.py` — `VALID_TYPES`, `TYPE_TO_PLURAL`, plugin uninstall path.
- `aec/commands/list_cmd.py`, `outdated.py`, `search.py` — add `"plugins"` to each command's **local** `ITEM_TYPES` tuple (they don't import the manifest one).
- `aec/commands/apply_cmd.py`, `export_cmd.py` — already iterate `manifest_v2.ITEM_TYPES`; `apply` adds the plugin handler call.
- `aec/commands/info.py` — `info plugin <name>` shows loadout fields.
- `aec/commands/preferences.py` — add string-setting routing for `plugins.execution` (stored via `lib/preferences.set_setting`). **Not** `config_cmd.py` (that only forwards).
- `aec/cli.py` — help strings (`skill, rule, agent, mcp, or plugin`).
- `README.md`, `AGENTINFO.md`, `docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md` (reconcile `aec add plugin` → `aec install plugin`), `plans/ROADMAP.md`.

---

## Task 1: Loadout JSON Schemas + README (docs)

**Files:**
- Create: `docs/loadout/schema/plugin.schema.json`
- Create: `docs/loadout/schema/skill.schema.json`, `agent.schema.json`, `rule.schema.json`
- Create: `docs/loadout/README.md`
- Test: `tests/test_loadout_schema.py`

- [ ] **Step 1: Write the failing test** — every schema file is well-formed JSON and a valid Draft 2020-12 JSON Schema.

```python
# tests/test_loadout_schema.py
import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "docs" / "loadout" / "schema"
SCHEMA_FILES = ["plugin", "skill", "agent", "rule"]


@pytest.mark.parametrize("name", SCHEMA_FILES)
def test_schema_is_valid_json_schema(name: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())
    # Raises jsonschema.SchemaError if the schema itself is malformed.
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"].startswith("https://json-schema.org/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_loadout_schema.py -v`
Expected: FAIL (files do not exist → `FileNotFoundError`).

- [ ] **Step 3: Write the schemas.** Create `docs/loadout/schema/plugin.schema.json`. Common base fields (`schema`, `item_type`, `name`, `version`, `description`, `source` required; `homepage`, `author`, `license`, `supports`, `usage` optional) plus the plugin extension (`install_type` enum `["marketplace","per-tool","external"]`, and `install`/`uninstall` objects). Mirror the spec's field table (lines 100–198).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/mbernier/loadout/schema/plugin.schema.json",
  "title": "loadout plugin manifest",
  "type": "object",
  "required": ["schema", "item_type", "name", "version", "description", "source", "install_type", "install"],
  "additionalProperties": false,
  "properties": {
    "schema": { "type": "string", "const": "loadout/v1" },
    "item_type": { "type": "string", "const": "plugin" },
    "name": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
    "version": { "type": "string" },
    "description": { "type": "string" },
    "source": { "type": "string" },
    "homepage": { "type": "string" },
    "author": {
      "type": "object",
      "properties": { "name": { "type": "string" }, "url": { "type": "string" } },
      "additionalProperties": false
    },
    "license": { "type": "string" },
    "supports": {
      "type": "array",
      "items": { "type": "string", "enum": ["claude", "cursor", "gemini", "qwen", "codex"] }
    },
    "usage": { "type": "string" },
    "install_type": { "type": "string", "enum": ["marketplace", "per-tool", "external"] },
    "install": { "type": "object" },
    "uninstall": { "type": "object" }
  },
  "allOf": [
    {
      "if": { "properties": { "install_type": { "const": "marketplace" } } },
      "then": { "properties": { "install": { "required": ["marketplace", "plugin"] } } }
    },
    {
      "if": { "properties": { "install_type": { "const": "per-tool" } } },
      "then": { "properties": { "install": { "required": ["tools"] } } }
    },
    {
      "if": { "properties": { "install_type": { "const": "external" } } },
      "then": { "properties": { "install": { "required": ["external"] } } }
    }
  ]
}
```

Then create `skill.schema.json`, `agent.schema.json`, `rule.schema.json` — common base only (no `install_type`/`install` required), with `item_type` const matching the file, `additionalProperties: false`, and the same optional base fields. These are the additive enrichment schemas referenced by the spec (lines 116–119).

- [ ] **Step 4: Write `docs/loadout/README.md`.** Cover: what loadout is (a portable `{item}.json`/`{item}.yaml` that travels with an item and tells any AI tool how to install/use it); the file-naming rule (follows the `hook.json` precedent); the `.json`-wins-over-`.yaml` rule; the common base field table; the three plugin install types with one example each; a "why publishers should ship it" section; and a note that the schema version lives in the `schema` field (`loadout/v1`), never resolved over the network. Keep it tight and publisher-facing.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_loadout_schema.py -v`
Expected: PASS (or SKIP if `jsonschema` unavailable — install dev extras: `pip install -e ".[dev]"` plus `pip install jsonschema`).

- [ ] **Step 6: Commit**

```bash
git add docs/loadout/schema docs/loadout/README.md tests/test_loadout_schema.py
git commit -m "docs(loadout): add json schemas and publisher readme"
```

---

## Task 2: Loadout example files + conformance test

**Files:**
- Create: `docs/loadout/examples/plugin.json`, `docs/loadout/examples/plugin.yaml`
- Create: `docs/loadout/examples/{skill,agent,rule}.json` (+ `.yaml` for at least one)
- Modify: `tests/test_loadout_schema.py`

- [ ] **Step 1: Write the failing test** — every example validates against its schema, and `plugin.json`/`plugin.yaml` parse to equal data.

```python
# append to tests/test_loadout_schema.py
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "loadout" / "examples"


def test_examples_validate_against_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        schema = json.loads((SCHEMA_DIR / f"{data['item_type']}.schema.json").read_text())
        jsonschema.validate(data, schema)  # raises on invalid


def test_plugin_json_and_yaml_are_equivalent() -> None:
    yaml = pytest.importorskip("yaml")
    j = json.loads((EXAMPLES_DIR / "plugin.json").read_text())
    y = yaml.safe_load((EXAMPLES_DIR / "plugin.yaml").read_text())
    assert j == y
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_loadout_schema.py -k examples -v`
Expected: FAIL (no examples dir).

- [ ] **Step 3: Write the examples.** `plugin.json` = the annotated ponytail `per-tool` example from the spec (lines 126–172). `plugin.yaml` = the byte-for-byte semantic equivalent in YAML. Add a minimal `skill.json`, `agent.json`, `rule.json` (common base only) and a `skill.yaml`. Keep them realistic and valid.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_loadout_schema.py -k examples -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/loadout/examples tests/test_loadout_schema.py
git commit -m "docs(loadout): add annotated example manifests"
```

---

## Task 3: `loadout.py` — locate, parse, validate

**Files:**
- Create: `aec/lib/loadout.py`
- Test: `tests/test_loadout.py`

`load_loadout(directory)` finds `plugin.json` (preferred), then `plugin.yaml`, at the dir root or under `.loadout/`; parses it; validates with a stdlib checker; returns the dict. Raises `LoadoutError` with a clear message on missing file, parse error, missing yaml support, or validation failure. **Do not use `jsonschema` here** — hand-roll the checks (required fields present, `item_type`/`install_type` enums, `schema == "loadout/v1"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_loadout.py
import json
from pathlib import Path

import pytest

from aec.lib.loadout import load_loadout, validate_loadout, LoadoutError

VALID = {
    "schema": "loadout/v1", "item_type": "plugin", "name": "ponytail",
    "version": "1.0.0", "description": "x", "source": "https://example.com",
    "install_type": "external",
    "install": {"external": {"download": "https://x", "instructions": "do it"}},
}


def _write(d: Path, name: str, data: dict) -> Path:
    p = d / name
    p.write_text(json.dumps(data))
    return p


class TestValidate:
    def test_valid_passes(self) -> None:
        validate_loadout(VALID)  # no raise

    def test_missing_required_field_raises(self) -> None:
        bad = {k: v for k, v in VALID.items() if k != "source"}
        with pytest.raises(LoadoutError, match="source"):
            validate_loadout(bad)

    def test_bad_install_type_raises(self) -> None:
        with pytest.raises(LoadoutError, match="install_type"):
            validate_loadout({**VALID, "install_type": "nope"})

    def test_wrong_schema_version_raises(self) -> None:
        with pytest.raises(LoadoutError, match="schema"):
            validate_loadout({**VALID, "schema": "loadout/v2"})


class TestLoad:
    def test_loads_plugin_json(self, tmp_path: Path) -> None:
        _write(tmp_path, "plugin.json", VALID)
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_json_wins_over_yaml(self, tmp_path: Path) -> None:
        _write(tmp_path, "plugin.json", VALID)
        (tmp_path / "plugin.yaml").write_text("name: other\n")
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_loadout_subdir(self, tmp_path: Path) -> None:
        sub = tmp_path / ".loadout"
        sub.mkdir()
        _write(sub, "plugin.json", VALID)
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_missing_returns_error(self, tmp_path: Path) -> None:
        with pytest.raises(LoadoutError, match="no loadout"):
            load_loadout(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_loadout.py -v`
Expected: FAIL (`ModuleNotFoundError: aec.lib.loadout`).

- [ ] **Step 3: Write `aec/lib/loadout.py`**

```python
"""Locate, parse, and validate a loadout item-manifest (plugin.json / plugin.yaml)."""

import json
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SCHEMA_VERSION = "loadout/v1"
ITEM_TYPES = ("plugin", "skill", "agent", "rule")
INSTALL_TYPES = ("marketplace", "per-tool", "external")
_BASE_REQUIRED = ("schema", "item_type", "name", "version", "description", "source")
# filename stems searched, in priority order, at dir root then .loadout/
_STEMS = ("plugin", "skill", "agent", "rule")


class LoadoutError(Exception):
    """Raised when a loadout manifest is missing, unparseable, or invalid."""


def validate_loadout(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise LoadoutError("loadout manifest must be a mapping")
    for field in _BASE_REQUIRED:
        if field not in data:
            raise LoadoutError(f"loadout manifest missing required field: {field}")
    if data["schema"] != SCHEMA_VERSION:
        raise LoadoutError(
            f"unsupported loadout schema {data['schema']!r}; expected {SCHEMA_VERSION!r}"
        )
    if data["item_type"] not in ITEM_TYPES:
        raise LoadoutError(f"invalid item_type: {data['item_type']!r}")
    if data["item_type"] == "plugin":
        it = data.get("install_type")
        if it not in INSTALL_TYPES:
            raise LoadoutError(f"invalid install_type: {it!r}")
        if "install" not in data:
            raise LoadoutError("plugin loadout missing install block")


def _parse(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix == ".json":
            return json.loads(text)
        if not HAS_YAML:
            raise LoadoutError(
                f"{path.name} is YAML but PyYAML is not installed; "
                "install PyYAML or provide a .json manifest"
            )
        return yaml.safe_load(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise LoadoutError(f"failed to parse {path.name}: {e}") from e


def find_loadout_file(directory: Path) -> Path | None:
    for base in (directory, directory / ".loadout"):
        for stem in _STEMS:
            for ext in (".json", ".yaml", ".yml"):
                candidate = base / f"{stem}{ext}"
                if candidate.is_file():
                    return candidate
    return None


def load_loadout(directory: Path) -> Dict[str, Any]:
    path = find_loadout_file(directory)
    if path is None:
        raise LoadoutError(f"no loadout manifest found in {directory}")
    data = _parse(path)
    validate_loadout(data)
    return data
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_loadout.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/loadout.py tests/test_loadout.py
git commit -m "feat(loadout): add loadout manifest locate/parse/validate library"
```

---

## Task 4: `manifest_v2` plugins bucket + `record_plugin_install`

**Files:**
- Modify: `aec/lib/manifest_v2.py:11` (`ITEM_TYPES`), `:19` (`_empty_scope`), add `record_plugin_install`
- Test: `tests/test_manifest_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_manifest_v2.py
from aec.lib.manifest_v2 import _empty_manifest, record_plugin_install, get_installed


def test_record_plugin_install_stores_metadata() -> None:
    m = _empty_manifest()
    record_plugin_install(m, "global", "ponytail", "1.0.0",
                          install_type="per-tool", targets=["claude", "cursor"])
    entry = get_installed(m, "global", "plugins")["ponytail"]
    assert entry["version"] == "1.0.0"
    assert entry["install_type"] == "per-tool"
    assert entry["targets"] == ["claude", "cursor"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_manifest_v2.py::test_record_plugin_install_stores_metadata -v`
Expected: FAIL (`ImportError: cannot import name 'record_plugin_install'`).

- [ ] **Step 3: Implement.** Add `"plugins"` to `ITEM_TYPES` (line 11) and a `"plugins": {}` bucket to `_empty_scope()` (line 19). Add, modeled on `record_mcp_install` (line 107):

```python
def record_plugin_install(manifest, scope, name, version, *, install_type, targets,
                          installed_as="explicit"):
    """Record a plugin install with its install_type and resolved targets."""
    _ensure_scope(manifest, scope)  # use whatever the file's existing helper is
    manifest[scope]["plugins"][name] = {
        "version": version,
        "install_type": install_type,
        "targets": list(targets),
        "installedAs": installed_as,
    }
```

Match the `installedAt` shape `record_mcp_install` uses (read it first; mirror the timestamp key). Note: `record_mcp_install` has **no** `installedAs` key — that key comes from `record_install`; adding `installedAs="explicit"` here is correct and consistent, just don't expect to find it in the MCP function. The `_empty_scope` edit gives every newly-written scope a `plugins` bucket. `load_manifest`'s backfill loop (lines ~54-55) only backfills the **global** scope from `ITEM_TYPES`, so global gets `plugins` for free on load; older per-repo scopes get the bucket when next written through `_empty_scope`/`_get_scope_dict`. Don't claim full backfill across all scopes.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_manifest_v2.py -v`
Expected: PASS (all manifest tests, including backfill).

- [ ] **Step 5: Commit**

```bash
git add aec/lib/manifest_v2.py tests/test_manifest_v2.py
git commit -m "feat(plugins): add plugins bucket and record_plugin_install to manifest"
```

---

## Task 5: Discovery — `_discover_available_plugins` + vendored registry

**Files:**
- Modify: `aec/lib/sources.py` (`discover_available` dispatch + new `_discover_available_plugins`)
- Create: `plugins/ponytail/plugin.json`, `plugins/<external-example>/plugin.json`
- Test: `tests/test_sources.py`

`_discover_available_plugins(source_dir)` scans `source_dir/*/plugin.json` (and `.yaml`), loads each via `loadout.load_loadout(dir)`, and returns `name -> {version, description, path, install_type}`. A malformed manifest is reported (collected into the result with an `error` key or re-raised per the file's existing convention for malformed items) — **not silently skipped**. Check how `_discover_available_mcps` handles malformed entries and match it.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_sources.py
from aec.lib.sources import _discover_available_plugins, discover_available


def test_discover_plugins_finds_registry_entry(tmp_path):
    d = tmp_path / "ponytail"
    d.mkdir()
    (d / "plugin.json").write_text(json.dumps({
        "schema": "loadout/v1", "item_type": "plugin", "name": "ponytail",
        "version": "1.0.0", "description": "lazy dev", "source": "https://x",
        "install_type": "external",
        "install": {"external": {"download": "https://x", "instructions": "go"}},
    }))
    found = _discover_available_plugins(tmp_path)
    assert found["ponytail"]["version"] == "1.0.0"
    assert found["ponytail"]["install_type"] == "external"


def test_discover_available_dispatches_plugins(tmp_path):
    d = tmp_path / "ponytail"
    d.mkdir()
    (d / "plugin.json").write_text(json.dumps({
        "schema": "loadout/v1", "item_type": "plugin", "name": "ponytail",
        "version": "1.0.0", "description": "x", "source": "https://x",
        "install_type": "external",
        "install": {"external": {"download": "https://x", "instructions": "go"}},
    }))
    assert "ponytail" in discover_available(tmp_path, "plugins")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources.py -k plugins -v`
Expected: FAIL (`ImportError` / `discover_available` returns `{}` for `"plugins"`).

- [ ] **Step 3: Implement.** Add a `"plugins"` branch to `discover_available` (after the `mcps` branch) returning `_discover_available_plugins(source_dir)`. Implement `_discover_available_plugins` using `from .loadout import load_loadout, find_loadout_file, LoadoutError`. Iterate `sorted(source_dir.iterdir())` dirs, skip non-dirs and dotted names, load each, build the result dict.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sources.py -k plugins -v`
Expected: PASS.

- [ ] **Step 5: Create the vendored registry entries.**
  - `plugins/ponytail/plugin.json` — the full `per-tool` ponytail manifest (spec lines 126–172). Use real, documented ponytail install commands from `github.com/DietrichGebert/ponytail`; if a tool's exact `run` command can't be verified, use `steps` (instructions-only) for that tool rather than fabricating a command (per the project rule against fabricating external commands).
  - `plugins/<external-example>/plugin.json` — an `external` manifest modeled on `impeccable.style` (download URL + in-tool instructions). Name the directory after the plugin.

  Verify both load: `python -c "from aec.lib.loadout import load_loadout; from pathlib import Path; print(load_loadout(Path('plugins/ponytail'))['name'])"` → `ponytail`.

- [ ] **Step 6: Commit**

```bash
git add aec/lib/sources.py plugins/ tests/test_sources.py
git commit -m "feat(plugins): add plugin discovery and vendored registry entries"
```

---

## Task 6: Target resolution — `supports ∩ detect_agents()`

**Files:**
- Create: `aec/lib/plugin_install.py` (start it here)
- Test: `tests/test_plugin_install.py`

`resolve_targets(manifest, detected)` returns the ordered list of tool keys to act on. Rules (spec lines 174–176, 159–161): omitted `supports` ⇒ all detected; `marketplace` ⇒ implicitly `["claude"]`; intersect with `detected`; supported-but-not-detected ⇒ excluded (caller notes the skip).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_plugin_install.py
import pytest
from aec.lib.plugin_install import resolve_targets


def test_intersects_supports_with_detected():
    m = {"install_type": "per-tool", "supports": ["claude", "cursor", "gemini"]}
    assert resolve_targets(m, {"claude": {}, "cursor": {}}) == ["claude", "cursor"]


def test_omitted_supports_means_all_detected():
    m = {"install_type": "per-tool"}
    assert resolve_targets(m, {"claude": {}, "qwen": {}}) == ["claude", "qwen"]


def test_marketplace_is_claude_only():
    m = {"install_type": "marketplace", "supports": ["claude", "cursor"]}
    assert resolve_targets(m, {"claude": {}, "cursor": {}}) == ["claude"]


def test_marketplace_without_claude_is_empty():
    m = {"install_type": "marketplace"}
    assert resolve_targets(m, {"cursor": {}}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_install.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** (start `aec/lib/plugin_install.py`):

```python
"""Install/uninstall plugins from validated loadout manifests."""

from typing import Any, Dict, List

ALL_TOOLS = ("claude", "cursor", "gemini", "qwen", "codex")


def resolve_targets(manifest: Dict[str, Any], detected: Dict[str, Any]) -> List[str]:
    if manifest.get("install_type") == "marketplace":
        supports = ["claude"]
    else:
        supports = manifest.get("supports") or list(detected.keys())
    return [t for t in supports if t in detected]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plugin_install.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/plugin_install.py tests/test_plugin_install.py
git commit -m "feat(plugins): resolve install targets from supports and detected agents"
```

---

## Task 7: Execution policy + marketplace handler

**Files:**
- Modify: `aec/lib/plugin_install.py`
- Test: `tests/test_plugin_install.py`

Handlers take an injected `runner` (callable that executes a command list) and a `confirm` callable so tests assert commands without real execution and without monkeypatching `subprocess`. `effective_policy(install_type, has_run, pref)` returns `"run"` or `"instructions"`; the `plugins.execution == "instructions-only"` preference downgrades everything to `"instructions"`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_plugin_install.py
from aec.lib.plugin_install import effective_policy, install_marketplace


def test_policy_external_always_instructions():
    assert effective_policy("external", has_run=False, pref=None) == "instructions"


def test_policy_marketplace_runs_by_default():
    assert effective_policy("marketplace", has_run=True, pref=None) == "run"


def test_policy_pref_downgrades_to_instructions():
    assert effective_policy("marketplace", has_run=True, pref="instructions-only") == "instructions"


def test_marketplace_handler_runs_two_commands():
    calls = []
    m = {"install_type": "marketplace",
         "install": {"marketplace": "DietrichGebert/ponytail", "plugin": "ponytail"}}
    install_marketplace(m, runner=lambda cmd: calls.append(cmd), confirm=lambda _: True)
    assert calls == [
        ["claude", "plugin", "marketplace", "add", "DietrichGebert/ponytail"],
        ["claude", "plugin", "install", "ponytail"],
    ]


def test_marketplace_handler_respects_declined_confirm():
    calls = []
    m = {"install_type": "marketplace",
         "install": {"marketplace": "x", "plugin": "y"}}
    install_marketplace(m, runner=lambda cmd: calls.append(cmd), confirm=lambda _: False)
    assert calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_install.py -k "policy or marketplace" -v`
Expected: FAIL.

- [ ] **Step 3: Implement.**

```python
def effective_policy(install_type: str, *, has_run: bool, pref: str | None) -> str:
    if install_type == "external":
        return "instructions"
    if pref == "instructions-only":
        return "instructions"
    if install_type == "per-tool" and not has_run:
        return "instructions"
    return "run"


def install_marketplace(manifest, *, runner, confirm) -> List[str]:
    blk = manifest["install"]
    cmds = [
        ["claude", "plugin", "marketplace", "add", blk["marketplace"]],
        ["claude", "plugin", "install", blk["plugin"]],
    ]
    if not confirm(cmds):
        return []
    for cmd in cmds:
        runner(cmd)
    return cmds
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plugin_install.py -k "policy or marketplace" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/plugin_install.py tests/test_plugin_install.py
git commit -m "feat(plugins): add execution policy and marketplace install handler"
```

---

## Task 8: Per-tool handler

**Files:**
- Modify: `aec/lib/plugin_install.py`
- Test: `tests/test_plugin_install.py`

`install_per_tool(manifest, targets, *, runner, confirm, printer, pref)` iterates targets; a tool with a `run` array runs under policy (confirm-then-run), a tool with only `steps` prints instructions, the `instructions-only` pref forces printing. Returns a summary (`{tool: "run"|"instructions"|"declined"}`).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_plugin_install.py
from aec.lib.plugin_install import install_per_tool


def _manifest():
    return {"install_type": "per-tool", "install": {"tools": {
        "claude": {"run": ["bash", "-c", "echo hi"]},
        "gemini": {"steps": "copy X to ~/.gemini"},
    }}}


def test_per_tool_runs_run_tools_and_prints_steps_tools():
    ran, printed = [], []
    summary = install_per_tool(
        _manifest(), ["claude", "gemini"],
        runner=lambda c: ran.append(c), confirm=lambda *_: True,
        printer=lambda s: printed.append(s), pref=None)
    assert ran == [["bash", "-c", "echo hi"]]
    assert any("gemini" in p or "~/.gemini" in p for p in printed)
    assert summary["claude"] == "run"
    assert summary["gemini"] == "instructions"


def test_per_tool_pref_downgrades_run_to_instructions():
    ran, printed = [], []
    install_per_tool(
        _manifest(), ["claude"],
        runner=lambda c: ran.append(c), confirm=lambda *_: True,
        printer=lambda s: printed.append(s), pref="instructions-only")
    assert ran == []
    assert printed  # claude's command was printed, not executed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_install.py -k per_tool -v`
Expected: FAIL.

- [ ] **Step 3: Implement** `install_per_tool` per the contract above, using `effective_policy(... )` per tool (`has_run = "run" in spec`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_plugin_install.py -k per_tool -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/plugin_install.py tests/test_plugin_install.py
git commit -m "feat(plugins): add per-tool install handler"
```

---

## Task 9: External handler (never executes)

**Files:**
- Modify: `aec/lib/plugin_install.py`
- Test: `tests/test_plugin_install.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_plugin_install.py
from aec.lib.plugin_install import install_external


def test_external_prints_and_never_runs():
    ran, printed = [], []
    m = {"install_type": "external", "install": {"external": {
        "download": "https://impeccable.style/#downloads",
        "instructions": "1. download 2. run /impeccable setup"}}}
    install_external(m, runner=lambda c: ran.append(c), printer=lambda s: printed.append(s))
    assert ran == []
    assert any("impeccable.style" in p for p in printed)
    assert any("/impeccable setup" in p for p in printed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_plugin_install.py -k external -v`
Expected: FAIL.

- [ ] **Step 3: Implement** `install_external(manifest, *, runner=None, printer)` — print download + instructions, never call `runner`. (Keep the `runner` param only so the orchestrator can pass a uniform signature; assert in the body it is never invoked, or simply ignore it.)

- [ ] **Step 4: Run test to verify it passes** — Run: `python -m pytest tests/test_plugin_install.py -k external -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/lib/plugin_install.py tests/test_plugin_install.py
git commit -m "feat(plugins): add external install handler (instructions only)"
```

---

## Task 10: Orchestrator — `install_plugin` + `uninstall_plugin`

**Files:**
- Modify: `aec/lib/plugin_install.py`
- Test: `tests/test_plugin_install.py`

`install_plugin(manifest, detected, *, runner, confirm, printer, pref)` ties it together: resolve targets, note skipped-but-supported tools, dispatch on `install_type`, print `usage` if present, return a result dict (`{install_type, targets, executed: bool}`) the command layer records via `record_plugin_install`. `uninstall_plugin(manifest, ...)` runs the `uninstall` block under the same policy (omitted ⇒ message "manual cleanup may be required").

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_plugin_install.py
from aec.lib.plugin_install import install_plugin


def test_install_plugin_external_returns_result_and_prints_usage():
    printed = []
    m = {"schema": "loadout/v1", "item_type": "plugin", "name": "imp",
         "version": "1.0.0", "description": "x", "source": "https://x",
         "install_type": "external", "usage": "run /imp setup",
         "install": {"external": {"download": "https://x", "instructions": "go"}}}
    result = install_plugin(m, {"claude": {}}, runner=lambda c: None,
                            confirm=lambda *_: True, printer=lambda s: printed.append(s),
                            pref=None)
    assert result["install_type"] == "external"
    assert result["executed"] is False
    assert any("run /imp setup" in p for p in printed)


def test_install_plugin_marketplace_without_claude_is_skipped():
    m = {"schema": "loadout/v1", "item_type": "plugin", "name": "p",
         "version": "1.0.0", "description": "x", "source": "https://x",
         "install_type": "marketplace",
         "install": {"marketplace": "a/b", "plugin": "b"}}
    result = install_plugin(m, {"cursor": {}}, runner=lambda c: None,
                            confirm=lambda *_: True, printer=lambda s: None, pref=None)
    assert result["targets"] == []
    assert result["executed"] is False
```

- [ ] **Step 2: Run test to verify it fails** — Run: `python -m pytest tests/test_plugin_install.py -k install_plugin -v` → FAIL.

- [ ] **Step 3: Implement** `install_plugin` and `uninstall_plugin`, dispatching to the three handlers and setting `executed` based on whether any command ran. Print a note for each supported-but-undetected tool.

- [ ] **Step 4: Run test to verify it passes** — Run: `python -m pytest tests/test_plugin_install.py -v` → PASS (whole file).

- [ ] **Step 5: Commit**

```bash
git add aec/lib/plugin_install.py tests/test_plugin_install.py
git commit -m "feat(plugins): add install/uninstall orchestrators"
```

---

## Task 11: Wire `install_cmd` — `plugin` branch (registry + URL)

**Files:**
- Modify: `aec/commands/install_cmd.py:22` (`VALID_TYPES`), `:23` (`TYPE_TO_PLURAL`), `run_install` branch + new `_install_plugin`
- Test: `tests/test_install_cmd.py`

`_install_plugin(name_or_url, global_flag, yes)` mirrors `_install_mcp`: resolve scope, find the plugin source dir, discover the plugin (registry) **or** if `name_or_url` looks like a URL/path, load loadout from a fetched/local dir (Phase 1: local path or git clone into a temp dir — keep the URL fetch minimal; a local directory path is the MVP, git clone is the stretch). Build `runner`/`confirm`/`printer` from `Console` + `input()` + `subprocess.run`, honoring `yes` and the `plugins.execution` preference (`get_setting("plugins.execution")`). On success call `record_plugin_install`.

- [ ] **Step 1: Write the failing test** — registry install of the `external` example records the manifest entry and executes nothing.

```python
# add to tests/test_install_cmd.py — follow existing patterns in this file for
# how a source dir + scope are set up (reuse existing fixtures/helpers).
def test_install_plugin_external_records_manifest(...):
    # arrange: a plugins source dir containing plugins/imp/plugin.json (external)
    # act: run_install("plugin", "imp", yes=True)
    # assert: manifest scope["plugins"]["imp"]["install_type"] == "external"
    ...
```

(Write this concretely against the fixtures already used by the MCP install tests in `tests/test_install_cmd.py` / `tests/test_mcp_install.py` — match their scope/source setup exactly.)

- [ ] **Step 2: Run test to verify it fails** — FAIL (`run_install` rejects `"plugin"`).

- [ ] **Step 3: Implement.** Add `"plugin"` to `VALID_TYPES`, `"plugin": "plugins"` to `TYPE_TO_PLURAL`, an early `if item_type == "plugin": return _install_plugin(...)` branch in `run_install` (mirror the `mcp` branch at line ~), and write `_install_plugin`. Source dir key is `"plugins"` from `get_source_dirs()` — add a `plugins/` entry there if `get_source_dirs` hard-codes keys (check `aec/lib/sources.py:get_source_dirs`; the vendored `plugins/` dir is in-repo, so map it to `repo / "plugins"`).

- [ ] **Step 4: Run test to verify it passes** — Run: `python -m pytest tests/test_install_cmd.py -k plugin -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/commands/install_cmd.py aec/lib/sources.py tests/test_install_cmd.py
git commit -m "feat(plugins): wire plugin install into install command"
```

---

## Task 12: Wire `uninstall` — plugin path

**Files:**
- Modify: `aec/commands/uninstall.py:13` (`VALID_TYPES`), `:14` (`TYPE_TO_PLURAL`), add `_uninstall_plugin`
- Test: `tests/test_uninstall_cmd.py`

- [ ] **Step 1: Write the failing test** — uninstalling a recorded plugin runs its `uninstall` block under policy and removes the manifest record. (Model on the MCP uninstall test in the same file.)

- [ ] **Step 2: Run test to verify it fails** — FAIL.

- [ ] **Step 3: Implement.** Add `"plugin"`/`"plugins"` to the type tables; add an early `plugin` branch calling `_uninstall_plugin`, which reads the recorded entry (for `install_type`), re-loads the loadout manifest from the registry to get the `uninstall` block, runs `uninstall_plugin(...)`, then `remove_install(manifest, scope, "plugins", name)`. If the registry manifest is gone, remove the record and warn that manual cleanup may be required.

- [ ] **Step 4: Run test to verify it passes** — Run: `python -m pytest tests/test_uninstall_cmd.py -k plugin -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/commands/uninstall.py tests/test_uninstall_cmd.py
git commit -m "feat(plugins): wire plugin uninstall into uninstall command"
```

---

## Task 13: `list` / `export` / `apply` / `outdated` / `search` / `info` coverage

**Files:**
- Verify/modify: `aec/commands/list_cmd.py`, `export_cmd.py`, `apply_cmd.py`, `outdated.py`, `search.py`, `info.py`
- Test: `tests/test_export_apply_e2e.py`, `tests/test_portable_manifest.py`, `tests/test_outdated*` (find exact names)

> **Important — do not trust auto-flow-through.** Only `apply_cmd.py` and `export_cmd.py` import `manifest_v2.ITEM_TYPES`. `list_cmd.py`, `outdated.py`, and `search.py` each define their **own local** `ITEM_TYPES = ("skills", "rules", "agents")` (which already excludes even `"mcps"`). You **must** add `"plugins"` to each of those three local tuples explicitly — plugins will not appear in `list`/`outdated`/`search` otherwise. (Consider whether to add `"mcps"` too while there, or leave that out of scope — do not silently expand it without noting it.)

- [ ] **Step 1: Write the failing test — manifest round-trip.** Install the `external` plugin, `export`, then `apply` into a fresh scope, assert the plugin is reproduced. Add to `tests/test_export_apply_e2e.py` following its existing structure.

- [ ] **Step 2: Run test to verify it fails** — FAIL (or reveals where a command hard-codes item types instead of iterating `ITEM_TYPES`).

- [ ] **Step 3: Implement.**
  - `apply_cmd.py` / `export_cmd.py` already import `manifest_v2.ITEM_TYPES` → plugins flow through once Task 4 lands; verify, no edit likely needed beyond `apply`'s handler call.
  - `list_cmd.py`, `outdated.py`, `search.py` → add `"plugins"` to each local `ITEM_TYPES` tuple.
  - `apply` must re-run the plugin install handler per recorded plugin: prompt once up front ("apply N plugins?"), then assume-yes for confirm-then-run types (spec lines 286–294); `external` stays instructions-only; `--yes` skips the prompt.
  - `outdated` compares installed version to the registry `plugin.json` version; URL-only plugins report **"version unknown"** (spec line 298).
  - `info plugin <name>` shows the loadout fields.

- [ ] **Step 4: Run test to verify it passes** — Run the affected test files → PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/commands tests
git commit -m "feat(plugins): cover plugins in list/export/apply/outdated/info"
```

---

## Task 14: `plugins.execution` preference

**Files:**
- Modify: `aec/commands/preferences.py` (the real edit site — `set_pref`/`reset_pref`/`list_preferences`)
- Test: `tests/test_config_cmd.py`

The preference is a **string** (`"instructions-only"` to force-downgrade; unset/`"default"` = per-type policy). It is stored via `lib/preferences.set_setting`/`get_setting` (string-valued), **not** the boolean `set_preference`.

> **No string-setting path exists yet — you are adding one.** `aec config set` (`config_cmd.py`, a 17-line pass-through) delegates to `commands/preferences.py:set_pref`. Today `set_pref` only handles boolean `OPTIONAL_FEATURES`: it rejects any key not in `OPTIONAL_FEATURES` and only accepts `on`/`off`, else `SystemExit(1)`. So `aec config set plugins.execution instructions-only` (spec line 270) currently **fails**. You must add string-setting routing in `commands/preferences.py`. Do **not** edit `config_cmd.py` — it just forwards.

Add a small allow-list of string settings, e.g. `STRING_SETTINGS = {"plugins.execution": {"default", "instructions-only"}}`, and branch in `set_pref` **before** the `OPTIONAL_FEATURES` check: if `feature in STRING_SETTINGS`, validate `value` is in the allowed set (else error listing allowed values) and call `lib_preferences.set_setting(feature, value)`. Mirror the branch in `reset_pref` (call `reset_preference`/clear the setting) and surface current string settings in `list_preferences`.

- [ ] **Step 1: Write the failing test** — `set_pref("plugins.execution", "instructions-only")` persists and `lib/preferences.get_setting("plugins.execution")` returns `"instructions-only"`; an invalid value (`set_pref("plugins.execution", "bogus")`) exits non-zero. (Add to `tests/test_config_cmd.py`, matching how it currently drives `set_pref`.)

- [ ] **Step 2: Run test to verify it fails** — Run: `python -m pytest tests/test_config_cmd.py -k plugins -v` → FAIL (`set_pref` rejects the key as "Unknown feature").

- [ ] **Step 3: Implement** the `STRING_SETTINGS` routing in `commands/preferences.py` as described above.

- [ ] **Step 4: Run test to verify it passes** — Run: `python -m pytest tests/test_config_cmd.py -k plugins -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/commands/config_cmd.py tests/test_config_cmd.py
git commit -m "feat(plugins): add plugins.execution preference"
```

---

## Task 15: CLI help strings

**Files:**
- Modify: `aec/cli.py` (help for `install`, `uninstall`, `info` — `:90` area)
- Test: `tests/test_cli_v2.py` or `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** — `aec install --help` output mentions `plugin`.

```python
def test_install_help_mentions_plugin(...):
    # invoke the CLI help (match how existing cli tests capture output)
    assert "plugin" in help_text
```

- [ ] **Step 2: Run test to verify it fails** — FAIL.

- [ ] **Step 3: Implement.** Update every `Type: skill, rule, agent, mcp` help string to `Type: skill, rule, agent, mcp, or plugin`.

- [ ] **Step 4: Run test to verify it passes** — PASS.

- [ ] **Step 5: Commit**

```bash
git add aec/cli.py tests
git commit -m "feat(plugins): add plugin to cli help strings"
```

---

## Task 16: Docs — README, AGENTINFO, reconcile agent-blurb, ROADMAP

**Files:**
- Modify: `README.md`, `AGENTINFO.md`, `docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md`, `plans/ROADMAP.md`

No code; documentation only. (No project names in README — use `my-plugin` placeholders per `feedback_no_project_names_in_readme`.)

- [ ] **Step 1:** Add a "Plugins" section to `README.md`: `aec install plugin <name|url>`, `aec uninstall plugin <name>`, the three install types, the per-type execution policy / never-auto-install guarantee, and a link to `docs/loadout/` with the "publishers: ship a `plugin.json`" suggestion.

- [ ] **Step 2:** Update `AGENTINFO.md` with the plugin commands and the `plugins.execution` preference.

- [ ] **Step 3:** Reconcile `docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md`: change `aec add plugin` → `aec install plugin` (spec line 304).

- [ ] **Step 4:** Add Phase 2 (extract to `~/projects/loadout`) and Phase 3 (adoption PRs) entries to `plans/ROADMAP.md`. **Confirm tier/priority placement with the user before finalizing** (per global rule on roadmap placement).

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTINFO.md docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md plans/ROADMAP.md
git commit -m "docs(plugins): document plugin commands and loadout schema"
```

---

## Final verification

- [ ] Run the full suite: `python -m pytest -q` — **100% pass, no skips that hide failures.**
- [ ] Lint/type per repo hooks (`.claude/settings.json` postToolUse, if present).
- [ ] Manual smoke: `aec install plugin <external-example> --yes` records the manifest and prints instructions without executing; `aec list` shows it; `aec uninstall plugin <external-example>` removes it.
- [ ] Confirm `pyproject.toml` `dependencies` is still `[]` (no runtime dep crept in).
- [ ] @superpowers:verification-before-completion before declaring Phase 1 done.

---

## Notes / decisions baked into this plan

- **Zero runtime deps preserved:** runtime validation is hand-rolled in `loadout.py`; `jsonschema` appears only in `tests/test_loadout_schema.py` (guarded by `importorskip`). YAML support is optional (`try: import yaml`) — a `.yaml`-only manifest with PyYAML absent fails with a clear, actionable error rather than a crash.
- **Dependency-injected handlers** (`runner`/`confirm`/`printer`): lets handler tests assert exact commands with no `subprocess`/`input` monkeypatching, satisfying "test our own code directly, no mocks for internal code." The thin `subprocess.run` wrapper is the only third-party boundary and is exercised by the command-level tests.
- **URL install MVP:** local directory path first; git-clone-into-temp is the stretch within Task 11. Arbitrary HTTP-hosted non-git `plugin.json` is deferred (spec open question, lines 396–398).
- **One plugin per repo via URL** is a stated Phase 1 limitation (spec lines 236–239), not a gap.
