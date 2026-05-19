> Status: shipped — Phase 1 via PR #47 (2026-05-04..18), test coverage via PR #48. Phase 2 tracked separately in 2026-05-19-org-config-overlay-phase-2.md.

# Org Config Overlay — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the schema, parser, on-disk loader, and `aec org` command surface for unsigned, single-org configs — the foundation that every subsequent phase builds on.

**Architecture:** A new `aec/lib/org_config/` package owns parsing, validation, hashing, state, and the discovery loop. A new `aec/commands/org.py` exposes the `aec org` subcommand group. The on-disk layout (`~/.aec/orgs/<id>.yaml` + `<id>.state.json`, plus reserved paths for conflict-resolutions and trusted-orgs) is multi-org-shaped from day one so Phase 3 needs no migration. Trust mode is restricted to `unsigned` only; signing plumbing waits for Phase 2.

**Tech Stack:** Python 3.9+, Typer (already a dev/optional dep), stdlib `hashlib`/`json`/`pathlib`, PyYAML (new — gated behind `pip install aec[org-configs-preview]` extras). Zero new runtime deps for users without org configs.

**Spec reference:** `docs/superpowers/specs/2026-05-04-org-config-overlay-design.md`

**Phase 1 scope (from spec, Rollout Plan):**
- Schema definition, validator, loader for `~/.aec/orgs/`
- `items` + `sources` + `preferences` blocks (core 60% of value)
- Single-org only (multi-org parsing rejected with clear error)
- Trust mode: `unsigned` only, with loud warning
- Commands: `aec org enroll`, `list`, `status`, `show`, `remove`
- Docs: `docs/users/org-configs.md`, `docs/orgs/authoring-org-configs.md`
- Allow-list resolution for `install.preferences` keys and `install.prompts` IDs
- Multi-org-shaped on-disk layout (yaml + state.json + reserved paths)
- Ships behind `pip install aec[org-configs-preview]`

**Out of Phase 1 (explicit):**
- Any signature verification (`pinned_key`, `dns_anchor`) → Phase 2
- `aec org sync` → Phase 2
- Multi-org discovery + conflict detection → Phase 3
- `projects[]`, `install.mode`, `enrollment_script` execution → Phase 4
- Refresh TTL, branding block, `aec daemon-check` → Phase 5

---

## File Structure

### New files

```
aec/lib/org_config/
├── __init__.py                 # Public surface: load_org_config, OrgConfig dataclass
├── schema.py                   # Dataclasses for parsed config; CLOSED stance/source enums
├── parser.py                   # YAML+frontmatter parser (text → raw dict)
├── validator.py                # Schema validation (raw dict → OrgConfig | ValidationError)
├── allow_lists.py              # PREFERENCES_ALLOW_LIST + PROMPTS_ALLOW_LIST (resolved in Task 1)
├── hashing.py                  # sha256(file_bytes), canonical state file shape
├── state.py                    # read/write ~/.aec/orgs/<id>.state.json with file lock
├── paths.py                    # ~/.aec/orgs/, conflict-resolutions.json, trusted-orgs.json paths
├── trust.py                    # Phase 1: only unsigned mode + warning prompt
├── discovery.py                # Scan ~/.aec/orgs/*.yaml, single-org enforcement
└── errors.py                   # OrgConfigError hierarchy (parse, validate, trust, multi-org)

aec/commands/
└── org.py                      # `aec org` subcommand group (enroll, list, status, show, remove)

tests/lib/org_config/
├── __init__.py
├── test_parser.py
├── test_validator.py
├── test_allow_lists.py
├── test_hashing.py
├── test_state.py
├── test_trust_unsigned.py
├── test_discovery.py
└── fixtures/
    ├── valid-minimal.yaml
    ├── valid-full.yaml
    ├── invalid-no-source.yaml
    ├── invalid-unknown-source.yaml
    ├── invalid-bad-stance.yaml
    ├── invalid-future-schema.yaml
    └── invalid-multi-org-rejected.yaml      # Phase 1 rejects 2+ orgs in one dir

tests/commands/
└── test_org.py                              # CLI integration tests for `aec org *`

docs/users/
└── org-configs.md                           # End-user guide

docs/orgs/                                   # NEW directory
├── authoring-org-configs.md                 # Schema reference (Phase 1 subset)
└── examples/
    └── minimal-phase1.yaml                  # Single-org, unsigned, items+sources+preferences

docs/superpowers/specs/
└── 2026-05-04-org-config-overlay-allow-lists.md   # Output of Task 1 audit
```

### Modified files

- `pyproject.toml` — add `[org-configs-preview]` extras with `PyYAML>=6.0`
- `aec/cli.py` — register the `org` subcommand group from `aec/commands/org.py`
- `aec/commands/doctor.py` — add an "Org configurations" section (read-only)
- `README.md` — add "AEC for Individuals, Teams, and Organizations" section near the top with link to `docs/users/org-configs.md`
- `aec/lib/__init__.py` — no exported additions in Phase 1; `org_config` lives under `aec.lib.org_config`

### Why this decomposition

Each module in `aec/lib/org_config/` has one responsibility and a small interface. `parser.py` only turns bytes into a raw dict. `validator.py` only turns a raw dict into a typed `OrgConfig`. `state.py` only handles state files. This means each test file is small, each task in the plan touches few files, and Phase 2's signing work slots into `trust.py` without disturbing parsing or storage.

`commands/org.py` is one file because the `aec org` subcommands share a small pool of helpers (resolve org-id, format status); splitting them per-command would push that helper layer into another file with no real isolation benefit.

---

## Conventions used in every task

- **Test framework:** `pytest`. Run from repo root.
- **Test naming:** `test_<module>.py` for the module, one test function per behavior.
- **No mocking the filesystem.** Use `tmp_path` fixture (pytest builtin) for any test that touches `~/.aec/`. Inject a `home_dir: Path` arg into helpers rather than reading `$HOME` directly so tests can pass `tmp_path`.
- **Commit message style:** Lowercase conventional commits (`feat(org-config): ...`, `test(org-config): ...`, `docs(org-config): ...`, `chore(org-config): ...`). Required by repo's commitlint config.
- **TDD:** Test first, watch it fail, implement the minimum, watch it pass, commit.
- **Don't run with `--watch`.** All tests must terminate (per CLAUDE.md).

Run tests for this feature with:
```bash
pytest tests/lib/org_config/ tests/commands/test_org.py -v
```

Run the full suite (required before each commit that changes lib code):
```bash
pytest -v
```

---

## Task 1: Resolve `install.preferences` and `install.prompts` allow-lists

**Why first:** Open Questions #1 and #2 in the spec — the allow-lists must be locked before the validator references them, otherwise tasks downstream get rewritten.

**Files:**
- Read: `aec/lib/preferences.py`, `aec/commands/preferences.py`, `aec/commands/install.py`, `aec/commands/setup.py`, `aec/lib/global_install_prompt.py`
- Create: `docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md`

This is a research-and-propose task. No code is written. Output is a design addendum the user reviews before Task 2 starts.

- [ ] **Step 1: Audit all preference keys currently writeable to `~/.aec/prefs.json`**

  Read `aec/lib/preferences.py` and any callers that write into `prefs.json`. Produce a complete table:

  | Key | Type | Where set | Safe for org to set? | Notes |
  |---|---|---|---|---|

  "Safe" criteria: setting the value cannot exfiltrate user data, cannot redirect AEC fetches to attacker-controlled hosts, and cannot install code without user consent. A key like `projects_dir` is safe (filesystem path under user's home). A key like `update_url` (hypothetical) would NOT be safe.

- [ ] **Step 2: Audit all prompt sites in install/setup flows**

  Grep for prompt sites in `aec/commands/install.py`, `aec/commands/setup.py`, `aec/lib/global_install_prompt.py`. List every yes/no or multi-choice prompt and identify whether it has a stable ID today. For prompts without a stable ID, propose one.

- [ ] **Step 3: Write allow-list addendum**

  Write `docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md` with three sections:
  1. **`install.preferences` allow-list** — the final list of keys with types and validation rules.
  2. **`install.prompts` allow-list** — the final list of prompt IDs with stable definitions.
  3. **Refactors required to enable allow-listing** — if any prompts need stable IDs introduced, list them as code changes that must happen in Task 2.

- [ ] **Step 4: User review checkpoint**

  Stop. Ask the user to review the addendum before proceeding. Quote: *"Allow-list addendum written to `docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md`. Please review — Tasks 2+ depend on this list. Approve to continue, or request changes."*

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md
git commit -m "docs(specs): resolve org-config phase-1 allow-lists for preferences and prompts"
```

---

## Task 2: Add `[org-configs-preview]` extras to packaging

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the optional dependency group**

  In `pyproject.toml` under `[project.optional-dependencies]`, add (alongside the existing `dev` group):

  ```toml
  org-configs-preview = [
      "PyYAML>=6.0",
  ]
  ```

  Do NOT modify the top-level `dependencies = []` list. Core AEC stays zero-runtime-dep.

- [ ] **Step 2: Verify install works**

  ```bash
  pip install -e ".[org-configs-preview]"
  python -c "import yaml; print(yaml.__version__)"
  ```

  Expected: a 6.x version string. If pip fails, the most likely cause is an existing broken local install — investigate before continuing.

- [ ] **Step 3: Verify core install still works without the extras**

  ```bash
  pip install -e .
  python -c "import yaml" 2>&1 | head -1
  ```

  Expected: `ModuleNotFoundError: No module named 'yaml'` (proves yaml is NOT a hard dep).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(packaging): add org-configs-preview extras with PyYAML"
```

---

## Task 3: Define `aec/lib/org_config/paths.py` — canonical filesystem paths

**Why:** Every other module needs to ask "where is this org's config / state / conflict file?" — centralizing avoids drift.

**Files:**
- Create: `aec/lib/org_config/__init__.py` (empty for now)
- Create: `aec/lib/org_config/paths.py`
- Create: `tests/lib/org_config/__init__.py` (empty)
- Create: `tests/lib/org_config/test_paths.py`

- [ ] **Step 1: Write the failing test**

  In `tests/lib/org_config/test_paths.py`:

  ```python
  from pathlib import Path
  from aec.lib.org_config.paths import OrgPaths


  def test_org_paths_exposes_canonical_locations(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)

      assert paths.aec_dir == tmp_path / ".aec"
      assert paths.orgs_dir == tmp_path / ".aec" / "orgs"
      assert paths.conflict_resolutions == tmp_path / ".aec" / "conflict-resolutions.json"
      assert paths.conflict_resolutions_history == tmp_path / ".aec" / "conflict-resolutions.history.json"
      assert paths.trusted_orgs == tmp_path / ".aec" / "trusted-orgs.json"


  def test_org_paths_per_org_helpers(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)

      assert paths.config_for("acme") == tmp_path / ".aec" / "orgs" / "acme.yaml"
      assert paths.state_for("acme") == tmp_path / ".aec" / "orgs" / "acme.state.json"
      assert paths.state_lock_for("acme") == tmp_path / ".aec" / "orgs" / "acme.state.json.lock"


  def test_org_paths_default_uses_real_home():
      paths = OrgPaths.default()
      assert paths.home_dir == Path.home()
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/lib/org_config/test_paths.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'aec.lib.org_config.paths'`.

- [ ] **Step 3: Implement `paths.py`**

  ```python
  """Canonical filesystem locations for org-config state.

  All other org_config modules must go through OrgPaths rather than
  hardcoding strings, so tests can inject tmp_path as home_dir.
  """
  from __future__ import annotations

  from dataclasses import dataclass
  from pathlib import Path


  @dataclass(frozen=True)
  class OrgPaths:
      home_dir: Path

      @classmethod
      def default(cls) -> "OrgPaths":
          return cls(home_dir=Path.home())

      @property
      def aec_dir(self) -> Path:
          return self.home_dir / ".aec"

      @property
      def orgs_dir(self) -> Path:
          return self.aec_dir / "orgs"

      @property
      def conflict_resolutions(self) -> Path:
          return self.aec_dir / "conflict-resolutions.json"

      @property
      def conflict_resolutions_history(self) -> Path:
          return self.aec_dir / "conflict-resolutions.history.json"

      @property
      def trusted_orgs(self) -> Path:
          return self.aec_dir / "trusted-orgs.json"

      def config_for(self, org_id: str) -> Path:
          return self.orgs_dir / f"{org_id}.yaml"

      def state_for(self, org_id: str) -> Path:
          return self.orgs_dir / f"{org_id}.state.json"

      def state_lock_for(self, org_id: str) -> Path:
          return self.orgs_dir / f"{org_id}.state.json.lock"
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  pytest tests/lib/org_config/test_paths.py -v
  ```

  Expected: 3 passed.

- [ ] **Step 5: Commit**

  ```bash
  git add aec/lib/org_config/__init__.py aec/lib/org_config/paths.py tests/lib/org_config/
  git commit -m "feat(org-config): add OrgPaths for canonical filesystem locations"
  ```

---

## Task 4: Define `aec/lib/org_config/errors.py` — error hierarchy

**Files:**
- Create: `aec/lib/org_config/errors.py`
- Create: `tests/lib/org_config/test_errors.py`

- [ ] **Step 1: Write the failing test**

  ```python
  from aec.lib.org_config.errors import (
      OrgConfigError,
      OrgConfigParseError,
      OrgConfigValidationError,
      OrgConfigTrustError,
      OrgConfigMultiOrgRejectedError,
      OrgConfigUnknownSchemaError,
  )


  def test_all_errors_subclass_org_config_error():
      for cls in (
          OrgConfigParseError,
          OrgConfigValidationError,
          OrgConfigTrustError,
          OrgConfigMultiOrgRejectedError,
          OrgConfigUnknownSchemaError,
      ):
          assert issubclass(cls, OrgConfigError)


  def test_validation_error_carries_field_path():
      err = OrgConfigValidationError("bad stance", field_path="items.skills.foo.stance")
      assert err.field_path == "items.skills.foo.stance"
      assert "items.skills.foo.stance" in str(err)
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/lib/org_config/test_errors.py -v
  ```

  Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `errors.py`**

  ```python
  """Error hierarchy for org-config loading.

  Distinct subclasses so the CLI can map each to a specific exit code
  (10=trust, 12=multi-org-rejected, 13=schema/validation).
  """
  from __future__ import annotations

  from typing import Optional


  class OrgConfigError(Exception):
      """Base for all org-config errors."""


  class OrgConfigParseError(OrgConfigError):
      """YAML or frontmatter could not be parsed."""


  class OrgConfigValidationError(OrgConfigError):
      """Parsed dict failed schema validation."""

      def __init__(self, message: str, field_path: Optional[str] = None) -> None:
          self.field_path = field_path
          if field_path:
              super().__init__(f"{field_path}: {message}")
          else:
              super().__init__(message)


  class OrgConfigUnknownSchemaError(OrgConfigError):
      """schema_version is unknown to this build of aec."""


  class OrgConfigTrustError(OrgConfigError):
      """Trust verification refused the config (or user declined unsigned warning)."""


  class OrgConfigMultiOrgRejectedError(OrgConfigError):
      """Phase 1: more than one org config present in ~/.aec/orgs/."""
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  pytest tests/lib/org_config/test_errors.py -v
  ```

  Expected: 2 passed.

- [ ] **Step 5: Commit**

  ```bash
  git add aec/lib/org_config/errors.py tests/lib/org_config/test_errors.py
  git commit -m "feat(org-config): add OrgConfigError hierarchy"
  ```

---

## Task 5: Define `aec/lib/org_config/schema.py` — typed dataclasses

**Why:** A typed in-memory representation lets the validator output a single object the rest of the system uses, instead of dict-typing everywhere.

**Files:**
- Create: `aec/lib/org_config/schema.py`
- Create: `tests/lib/org_config/test_schema.py`

- [ ] **Step 1: Write the failing test**

  ```python
  import pytest

  from aec.lib.org_config.schema import (
      Stance,
      RESERVED_SOURCE_IDS,
      ItemPolicy,
      CustomSource,
      OrgConfig,
      SCHEMA_VERSION_SUPPORTED,
  )


  def test_stance_is_closed_set():
      assert {s.value for s in Stance} == {"required", "recommended", "blocked", "pinned", "silent"}


  def test_reserved_source_ids():
      assert RESERVED_SOURCE_IDS == frozenset({
          "aec.default.skills",
          "aec.default.rules",
          "aec.default.agents",
          "aec.default.mcps",
      })


  def test_supported_schema_version_is_1_0():
      assert "1.0" in SCHEMA_VERSION_SUPPORTED


  def test_item_policy_requires_source():
      pol = ItemPolicy(source="aec.default.skills", stance=Stance.REQUIRED, version=">=2.0.0")
      assert pol.source == "aec.default.skills"


  def test_org_config_construct():
      cfg = OrgConfig(
          schema_version="1.0",
          org_id="acme",
          org_name="Acme",
          config_version="1.0.0",
          description=None,
          trust_mode="unsigned",
          default_sources={"skills": "keep", "rules": "keep", "agents": "keep", "mcps": "keep"},
          custom_sources=[],
          items={"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
          install_preferences={},
          install_prompts={},
          install_agents_enabled=[],
          install_agents_disabled=[],
      )
      assert cfg.org_id == "acme"
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/lib/org_config/test_schema.py -v
  ```

  Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `schema.py`**

  ```python
  """Typed in-memory representation of a parsed, validated org config.

  All fields are normalized: missing-but-optional becomes None or empty
  collection; closed enums (Stance) replace strings.
  """
  from __future__ import annotations

  from dataclasses import dataclass, field
  from enum import Enum
  from typing import Any, Optional


  SCHEMA_VERSION_SUPPORTED = frozenset({"1.0"})


  RESERVED_SOURCE_IDS = frozenset({
      "aec.default.skills",
      "aec.default.rules",
      "aec.default.agents",
      "aec.default.mcps",
  })


  ITEM_TYPES = ("skills", "rules", "agents", "mcps")


  DEFAULT_SOURCE_STANCES = ("keep", "replace", "deny")


  class Stance(str, Enum):
      REQUIRED = "required"
      RECOMMENDED = "recommended"
      BLOCKED = "blocked"
      PINNED = "pinned"
      SILENT = "silent"


  @dataclass(frozen=True)
  class ItemPolicy:
      source: str
      stance: Stance
      version: Optional[str] = None


  @dataclass(frozen=True)
  class CustomSource:
      id: str
      url: str
      ref: str
      contributes: tuple[str, ...]


  @dataclass(frozen=True)
  class OrgConfig:
      schema_version: str
      org_id: str
      org_name: str
      config_version: str
      description: Optional[str]
      trust_mode: str  # Phase 1: only "unsigned"

      # sources block
      default_sources: dict[str, str]            # {"skills": "keep", ...}
      custom_sources: list[CustomSource]

      # items block
      items: dict[str, dict[str, ItemPolicy]]    # {"skills": {"name": ItemPolicy, ...}, ...}

      # install block (subset for Phase 1)
      install_preferences: dict[str, Any]
      install_prompts: dict[str, Any]
      install_agents_enabled: list[str]
      install_agents_disabled: list[str]
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  pytest tests/lib/org_config/test_schema.py -v
  ```

  Expected: 5 passed.

- [ ] **Step 5: Commit**

  ```bash
  git add aec/lib/org_config/schema.py tests/lib/org_config/test_schema.py
  git commit -m "feat(org-config): add typed schema dataclasses and closed enums"
  ```

---

## Task 6: Implement `aec/lib/org_config/allow_lists.py`

**Why:** Materializes the Task 1 audit into Python constants the validator can reference.

**Files:**
- Create: `aec/lib/org_config/allow_lists.py`
- Create: `tests/lib/org_config/test_allow_lists.py`

- [ ] **Step 1: Translate Task 1 addendum into constants**

  Read `docs/superpowers/specs/2026-05-04-org-config-overlay-allow-lists.md`. Convert the resolved allow-lists into Python:

  ```python
  PREFERENCES_ALLOW_LIST: dict[str, type] = { ... }   # key -> expected type
  PROMPTS_ALLOW_LIST: frozenset[str] = frozenset({ ... })
  ```

  If the addendum required code refactors (e.g., adding stable IDs to existing prompts), do those refactors as part of this task — they're prerequisites for any prompt being allow-listable. Add unit tests for any refactored prompt sites covering the new ID surface.

- [ ] **Step 2: Write the failing test**

  ```python
  from aec.lib.org_config.allow_lists import PREFERENCES_ALLOW_LIST, PROMPTS_ALLOW_LIST


  def test_preferences_allow_list_is_non_empty():
      assert len(PREFERENCES_ALLOW_LIST) > 0


  def test_prompts_allow_list_is_non_empty():
      assert len(PROMPTS_ALLOW_LIST) > 0


  def test_preferences_allow_list_keys_match_known_prefs():
      # Every key in the allow-list must exist in the real preferences module —
      # otherwise we're advertising a key that doesn't actually do anything.
      from aec.lib.preferences import KNOWN_PREFERENCE_KEYS  # may need to expose this

      for key in PREFERENCES_ALLOW_LIST:
          assert key in KNOWN_PREFERENCE_KEYS, f"Allow-listed pref {key!r} is not a real preference"
  ```

  Note: `KNOWN_PREFERENCE_KEYS` may need to be added to `aec/lib/preferences.py` if it doesn't exist. Per CLAUDE.md "Contract Change Coverage" — this is a contract change to the preferences module; sweep all writers.

- [ ] **Step 3: Run test to verify it fails**

  ```bash
  pytest tests/lib/org_config/test_allow_lists.py -v
  ```

  Expected: failures across all three tests.

- [ ] **Step 4: Implement allow-lists per Task 1 addendum**

  Write `aec/lib/org_config/allow_lists.py` with the resolved values. If `KNOWN_PREFERENCE_KEYS` doesn't yet exist, add it to `aec/lib/preferences.py` and ensure all preference writers reference it.

- [ ] **Step 5: Run test + full suite**

  ```bash
  pytest tests/lib/org_config/test_allow_lists.py -v
  pytest -v
  ```

  Expected: all green. The full suite gates against regressions in any `preferences.py` refactor.

- [ ] **Step 6: Commit**

  ```bash
  git add aec/lib/org_config/allow_lists.py aec/lib/preferences.py tests/
  git commit -m "feat(org-config): add allow-lists for install.preferences and install.prompts"
  ```

---

## Task 7: Implement `aec/lib/org_config/parser.py` — YAML + frontmatter parsing

**Files:**
- Create: `aec/lib/org_config/parser.py`
- Create: `tests/lib/org_config/test_parser.py`
- Create: `tests/lib/org_config/fixtures/valid-minimal.yaml`
- Create: `tests/lib/org_config/fixtures/valid-full.yaml`

- [ ] **Step 1: Write the fixtures**

  `tests/lib/org_config/fixtures/valid-minimal.yaml`:

  ```yaml
  ---
  schema_version: "1.0"
  org_id: "minimal"
  org_name: "Minimal Org"
  config_version: "1.0.0"
  trust:
    mode: "unsigned"
  ---

  sources:
    default: { skills: keep, rules: keep, agents: keep, mcps: keep }
    custom: []

  items:
    skills: {}
    rules: {}
    agents: {}
    mcps: {}
  ```

  `tests/lib/org_config/fixtures/valid-full.yaml` — the annotated example from the spec (lines 95–192), trimmed to Phase 1 fields (drop `projects[]` and `enrollment_script` for now; those are Phase 4).

- [ ] **Step 2: Write the failing tests**

  In `tests/lib/org_config/test_parser.py`:

  ```python
  from pathlib import Path
  import pytest

  from aec.lib.org_config.parser import parse_org_config_text
  from aec.lib.org_config.errors import OrgConfigParseError


  FIXTURES = Path(__file__).parent / "fixtures"


  def test_parses_minimal_valid_config():
      text = (FIXTURES / "valid-minimal.yaml").read_text()
      frontmatter, body = parse_org_config_text(text)

      assert frontmatter["schema_version"] == "1.0"
      assert frontmatter["org_id"] == "minimal"
      assert frontmatter["trust"]["mode"] == "unsigned"
      assert "sources" in body
      assert "items" in body


  def test_parses_full_valid_config():
      text = (FIXTURES / "valid-full.yaml").read_text()
      frontmatter, body = parse_org_config_text(text)
      assert frontmatter["org_id"]
      assert "items" in body


  def test_rejects_missing_frontmatter():
      with pytest.raises(OrgConfigParseError, match="frontmatter"):
          parse_org_config_text("sources: {}\nitems: {}\n")


  def test_rejects_unterminated_frontmatter():
      with pytest.raises(OrgConfigParseError, match="frontmatter"):
          parse_org_config_text("---\nschema_version: 1.0\n\nbody-without-closing-marker\n")


  def test_rejects_invalid_yaml_in_frontmatter():
      with pytest.raises(OrgConfigParseError):
          parse_org_config_text("---\nschema_version: [unclosed\n---\nitems: {}\n")
  ```

- [ ] **Step 3: Run tests to verify they fail**

  ```bash
  pytest tests/lib/org_config/test_parser.py -v
  ```

  Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `parser.py`**

  ```python
  """Parse org-config YAML files into raw (frontmatter, body) dict pairs.

  Frontmatter is a YAML block delimited by `---` lines at the start of the file.
  Body is the rest. Both are loaded with safe_load.
  """
  from __future__ import annotations

  from typing import Any

  import yaml

  from .errors import OrgConfigParseError

  FRONTMATTER_DELIMITER = "---"


  def parse_org_config_text(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
      lines = text.splitlines()
      if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
          raise OrgConfigParseError(
              "config must begin with a YAML frontmatter block delimited by '---'"
          )

      try:
          end_idx = next(
              i for i, line in enumerate(lines[1:], start=1)
              if line.strip() == FRONTMATTER_DELIMITER
          )
      except StopIteration:
          raise OrgConfigParseError(
              "frontmatter block is not terminated with a closing '---' line"
          ) from None

      frontmatter_text = "\n".join(lines[1:end_idx])
      body_text = "\n".join(lines[end_idx + 1:])

      try:
          frontmatter = yaml.safe_load(frontmatter_text) or {}
          body = yaml.safe_load(body_text) or {}
      except yaml.YAMLError as exc:
          raise OrgConfigParseError(f"YAML parse error: {exc}") from exc

      if not isinstance(frontmatter, dict):
          raise OrgConfigParseError("frontmatter must be a YAML mapping")
      if not isinstance(body, dict):
          raise OrgConfigParseError("body must be a YAML mapping")

      return frontmatter, body
  ```

- [ ] **Step 5: Run tests to verify they pass**

  ```bash
  pytest tests/lib/org_config/test_parser.py -v
  ```

  Expected: 5 passed.

- [ ] **Step 6: Commit**

  ```bash
  git add aec/lib/org_config/parser.py tests/lib/org_config/test_parser.py tests/lib/org_config/fixtures/
  git commit -m "feat(org-config): add yaml frontmatter parser"
  ```

---

## Task 8: Implement `aec/lib/org_config/validator.py` — schema validation

**Files:**
- Create: `aec/lib/org_config/validator.py`
- Create: `tests/lib/org_config/test_validator.py`
- Create: fixtures `invalid-no-source.yaml`, `invalid-unknown-source.yaml`, `invalid-bad-stance.yaml`, `invalid-future-schema.yaml`

- [ ] **Step 1: Write invalid fixtures**

  Each fixture is a complete YAML file that's valid YAML but invalid per our schema:
  - `invalid-no-source.yaml` — an item missing the `source` field.
  - `invalid-unknown-source.yaml` — an item with `source: "not-declared"`.
  - `invalid-bad-stance.yaml` — `stance: "kinda-required"`.
  - `invalid-future-schema.yaml` — `schema_version: "9.9"`.

- [ ] **Step 2: Write the failing tests**

  ```python
  from pathlib import Path
  import pytest

  from aec.lib.org_config.parser import parse_org_config_text
  from aec.lib.org_config.validator import validate_org_config
  from aec.lib.org_config.errors import (
      OrgConfigValidationError,
      OrgConfigUnknownSchemaError,
  )
  from aec.lib.org_config.schema import OrgConfig, Stance


  FIXTURES = Path(__file__).parent / "fixtures"


  def _load(name: str):
      return parse_org_config_text((FIXTURES / name).read_text())


  def test_validates_minimal_config():
      fm, body = _load("valid-minimal.yaml")
      cfg = validate_org_config(fm, body)
      assert isinstance(cfg, OrgConfig)
      assert cfg.org_id == "minimal"
      assert cfg.trust_mode == "unsigned"


  def test_validates_full_config_into_typed_items():
      fm, body = _load("valid-full.yaml")
      cfg = validate_org_config(fm, body)
      # Every item must have a Stance enum value
      for type_name, items in cfg.items.items():
          for item_name, policy in items.items():
              assert isinstance(policy.stance, Stance), \
                  f"{type_name}.{item_name} stance is not Stance enum"


  def test_rejects_item_missing_source():
      fm, body = _load("invalid-no-source.yaml")
      with pytest.raises(OrgConfigValidationError, match="source"):
          validate_org_config(fm, body)


  def test_rejects_item_with_unknown_source():
      fm, body = _load("invalid-unknown-source.yaml")
      with pytest.raises(OrgConfigValidationError, match="source"):
          validate_org_config(fm, body)


  def test_rejects_unknown_stance():
      fm, body = _load("invalid-bad-stance.yaml")
      with pytest.raises(OrgConfigValidationError, match="stance"):
          validate_org_config(fm, body)


  def test_rejects_unknown_future_schema():
      fm, body = _load("invalid-future-schema.yaml")
      with pytest.raises(OrgConfigUnknownSchemaError):
          validate_org_config(fm, body)


  def test_rejects_non_unsigned_trust_in_phase_1():
      fm, body = _load("valid-minimal.yaml")
      fm["trust"]["mode"] = "dns_anchor"
      with pytest.raises(OrgConfigValidationError, match="trust"):
          validate_org_config(fm, body)


  def test_rejects_install_preference_outside_allow_list():
      fm, body = _load("valid-minimal.yaml")
      body["install"] = {"preferences": {"definitely_not_allowed_key": "x"}}
      with pytest.raises(OrgConfigValidationError, match="install.preferences"):
          validate_org_config(fm, body)


  def test_rejects_install_prompt_outside_allow_list():
      fm, body = _load("valid-minimal.yaml")
      body["install"] = {"prompts": {"definitely_not_a_real_prompt_id": True}}
      with pytest.raises(OrgConfigValidationError, match="install.prompts"):
          validate_org_config(fm, body)


  def test_rejects_enrollment_script_in_phase_1():
      # Phase 4 introduces enrollment_script execution. Phase 1 must reject it
      # rather than parse-and-ignore, so authors don't ship configs that silently
      # do less than they think.
      fm, body = _load("valid-minimal.yaml")
      body["install"] = {"enrollment_script": [{"action": "run_doctor"}]}
      with pytest.raises(OrgConfigValidationError, match="enrollment_script"):
          validate_org_config(fm, body)


  def test_rejects_projects_block_in_phase_1():
      fm, body = _load("valid-minimal.yaml")
      body["projects"] = [{"match": {"git_remote": "*"}, "profile": {}}]
      with pytest.raises(OrgConfigValidationError, match="projects"):
          validate_org_config(fm, body)
  ```

- [ ] **Step 3: Run tests to verify they fail**

  ```bash
  pytest tests/lib/org_config/test_validator.py -v
  ```

  Expected: all fail with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `validator.py`**

  Validator must:
  1. Check `schema_version` is in `SCHEMA_VERSION_SUPPORTED` → else `OrgConfigUnknownSchemaError`.
  2. Check required top-level frontmatter fields: `org_id`, `org_name`, `config_version`, `trust.mode`.
  3. Phase 1: refuse `trust.mode != "unsigned"` (signed comes in Phase 2).
  4. Build the set of valid source IDs = `RESERVED_SOURCE_IDS | {s["id"] for s in sources.custom}`.
  5. For every item: require `source` field; require `source` is in valid set; require `stance` is in `Stance` enum values.
  6. For `install.preferences`: every key must be in `PREFERENCES_ALLOW_LIST`.
  7. For `install.prompts`: every key must be in `PROMPTS_ALLOW_LIST`.
  8. Phase 1: refuse top-level `projects` block and `install.enrollment_script` with a clear "this is a Phase N feature, not supported in this version" message.
  9. Return a populated `OrgConfig` dataclass.

  Validator surfaces `field_path` on errors (e.g., `items.skills.experimental-foo.source`).

- [ ] **Step 5: Run tests to verify they pass**

  ```bash
  pytest tests/lib/org_config/test_validator.py -v
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```bash
  git add aec/lib/org_config/validator.py tests/lib/org_config/test_validator.py tests/lib/org_config/fixtures/
  git commit -m "feat(org-config): add schema validator with allow-list enforcement"
  ```

---

## Task 9: Implement `aec/lib/org_config/hashing.py`

**Files:**
- Create: `aec/lib/org_config/hashing.py`
- Create: `tests/lib/org_config/test_hashing.py`

- [ ] **Step 1: Write the failing test**

  ```python
  from pathlib import Path

  from aec.lib.org_config.hashing import hash_config_bytes, hash_config_file


  def test_hash_config_bytes_is_sha256_hex():
      h = hash_config_bytes(b"hello world")
      assert h == "sha256:b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


  def test_hash_config_file_matches_bytes(tmp_path: Path):
      p = tmp_path / "x.yaml"
      p.write_bytes(b"hello world")
      assert hash_config_file(p) == hash_config_bytes(b"hello world")


  def test_hash_includes_prefix():
      h = hash_config_bytes(b"x")
      assert h.startswith("sha256:")
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  pytest tests/lib/org_config/test_hashing.py -v
  ```

- [ ] **Step 3: Implement `hashing.py`**

  ```python
  """Content hashing for org-config files. sha256 with explicit prefix
  so the algorithm is recoverable from the hash string alone (forward-compat
  if we ever migrate)."""
  from __future__ import annotations

  import hashlib
  from pathlib import Path


  HASH_PREFIX = "sha256:"


  def hash_config_bytes(data: bytes) -> str:
      return HASH_PREFIX + hashlib.sha256(data).hexdigest()


  def hash_config_file(path: Path) -> str:
      return hash_config_bytes(path.read_bytes())
  ```

- [ ] **Step 4: Run + commit**

  ```bash
  pytest tests/lib/org_config/test_hashing.py -v
  git add aec/lib/org_config/hashing.py tests/lib/org_config/test_hashing.py
  git commit -m "feat(org-config): add sha256 content hashing"
  ```

---

## Task 10: Implement `aec/lib/org_config/state.py` — state file IO with locking

**Files:**
- Create: `aec/lib/org_config/state.py`
- Create: `tests/lib/org_config/test_state.py`

- [ ] **Step 1: Write the failing tests**

  ```python
  from pathlib import Path

  from aec.lib.org_config.paths import OrgPaths
  from aec.lib.org_config.state import OrgState, read_state, write_state


  def test_write_and_read_state_roundtrip(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)
      paths.orgs_dir.mkdir(parents=True)

      state = OrgState(
          org_id="acme",
          config_version="1.0.0",
          config_hash="sha256:abc",
          trust_mode="unsigned",
          pubkey_fingerprint=None,
          pubkey_source=None,
          last_verified_at="2026-05-04T12:00:00Z",
          last_applied_at="2026-05-04T12:00:01Z",
          source_of_record="local",
          unsigned_warning_acknowledged_at="2026-05-04T12:00:00Z",
          key_rotation_pending=None,
      )
      write_state(paths, state)
      loaded = read_state(paths, "acme")
      assert loaded == state


  def test_read_state_returns_none_for_unknown_org(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)
      paths.orgs_dir.mkdir(parents=True)
      assert read_state(paths, "ghost") is None


  def test_write_state_is_atomic(tmp_path: Path):
      """Half-written state files would corrupt the org. write_state writes
      to a temp file and atomically renames. This test simulates a crash
      mid-write by inspecting that no partial file appears."""
      paths = OrgPaths(home_dir=tmp_path)
      paths.orgs_dir.mkdir(parents=True)

      state = OrgState(
          org_id="acme", config_version="1.0.0", config_hash="sha256:x",
          trust_mode="unsigned", pubkey_fingerprint=None, pubkey_source=None,
          last_verified_at="t", last_applied_at="t", source_of_record="local",
          unsigned_warning_acknowledged_at=None, key_rotation_pending=None,
      )
      write_state(paths, state)

      # The tmp file used for atomic rename must not exist after a successful write
      tmp_files = list(paths.orgs_dir.glob("acme.state.json.tmp*"))
      assert tmp_files == []
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/lib/org_config/test_state.py -v
  ```

- [ ] **Step 3: Implement `state.py`**

  Key requirements:
  - `OrgState` dataclass mirrors the JSON shape from spec section "State file shape".
  - `write_state` writes to `<state>.tmp.<pid>` and uses `os.replace` for atomic rename.
  - Acquire `<state>.lock` with `fcntl.flock` (LOCK_EX) for the duration of write. Release on exit.
  - `read_state` returns `None` if file missing; raises `OrgConfigError` subclass on corrupt JSON.
  - All datetime fields are stored as ISO-8601 UTC strings (no Python datetime serialization).

- [ ] **Step 4: Run tests + commit**

  ```bash
  pytest tests/lib/org_config/test_state.py -v
  git add aec/lib/org_config/state.py tests/lib/org_config/test_state.py
  git commit -m "feat(org-config): add atomic state file IO with flock"
  ```

---

## Task 11: Implement `aec/lib/org_config/trust.py` — unsigned-only Phase 1 trust

**Files:**
- Create: `aec/lib/org_config/trust.py`
- Create: `tests/lib/org_config/test_trust_unsigned.py`

- [ ] **Step 1: Write the failing tests**

  ```python
  import pytest

  from aec.lib.org_config.trust import (
      verify_trust,
      UnsignedConsent,
      UnsignedConsentDeclined,
  )
  from aec.lib.org_config.errors import OrgConfigTrustError


  def test_unsigned_with_consent_passes():
      result = verify_trust(
          trust_mode="unsigned",
          config_bytes=b"x",
          consent=UnsignedConsent(acknowledged=True),
      )
      assert result.acknowledged is True


  def test_unsigned_without_consent_raises():
      with pytest.raises(UnsignedConsentDeclined):
          verify_trust(
              trust_mode="unsigned",
              config_bytes=b"x",
              consent=UnsignedConsent(acknowledged=False),
          )


  def test_signed_modes_rejected_in_phase_1():
      with pytest.raises(OrgConfigTrustError, match="phase 2"):
          verify_trust(
              trust_mode="dns_anchor",
              config_bytes=b"x",
              consent=UnsignedConsent(acknowledged=True),
          )

      with pytest.raises(OrgConfigTrustError, match="phase 2"):
          verify_trust(
              trust_mode="pinned_key",
              config_bytes=b"x",
              consent=UnsignedConsent(acknowledged=True),
          )
  ```

- [ ] **Step 2: Run + implement + run + commit**

  Implement `trust.py` exposing `UnsignedConsent`, `UnsignedConsentDeclined`, and `verify_trust`. Phase 2 will extend this module with signed verification — keep the signature shaped for that (`verify_trust` returning a result object that can later carry pubkey fingerprint, etc.).

  ```bash
  pytest tests/lib/org_config/test_trust_unsigned.py -v
  git add aec/lib/org_config/trust.py tests/lib/org_config/test_trust_unsigned.py
  git commit -m "feat(org-config): add phase-1 unsigned trust verification"
  ```

---

## Task 12: Implement `aec/lib/org_config/discovery.py` — single-org loader

**Files:**
- Create: `aec/lib/org_config/discovery.py`
- Create: `tests/lib/org_config/test_discovery.py`

- [ ] **Step 1: Write the failing tests**

  ```python
  import shutil
  from pathlib import Path

  import pytest

  from aec.lib.org_config.paths import OrgPaths
  from aec.lib.org_config.discovery import discover_enrolled_orgs
  from aec.lib.org_config.errors import OrgConfigMultiOrgRejectedError


  FIXTURES = Path(__file__).parent / "fixtures"


  def test_discovery_finds_no_orgs_when_dir_empty(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)
      paths.orgs_dir.mkdir(parents=True)
      assert discover_enrolled_orgs(paths) == []


  def test_discovery_finds_no_orgs_when_dir_missing(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)
      assert discover_enrolled_orgs(paths) == []


  def test_discovery_loads_single_org(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)
      paths.orgs_dir.mkdir(parents=True)
      shutil.copy(FIXTURES / "valid-minimal.yaml", paths.orgs_dir / "minimal.yaml")

      orgs = discover_enrolled_orgs(paths)
      assert len(orgs) == 1
      assert orgs[0].config.org_id == "minimal"


  def test_discovery_rejects_multiple_orgs_in_phase_1(tmp_path: Path):
      paths = OrgPaths(home_dir=tmp_path)
      paths.orgs_dir.mkdir(parents=True)
      shutil.copy(FIXTURES / "valid-minimal.yaml", paths.orgs_dir / "minimal.yaml")
      shutil.copy(FIXTURES / "valid-full.yaml", paths.orgs_dir / "full.yaml")

      with pytest.raises(OrgConfigMultiOrgRejectedError, match="phase 3"):
          discover_enrolled_orgs(paths)
  ```

- [ ] **Step 2: Run + implement**

  `discover_enrolled_orgs(paths)` returns a list of `EnrolledOrg(config: OrgConfig, content_hash: str, source_path: Path)`. Steps:
  1. List `*.yaml` in `paths.orgs_dir` (return `[]` if dir missing).
  2. If more than one → raise `OrgConfigMultiOrgRejectedError` with message: *"Phase 1 supports a single enrolled org. Multi-org support arrives in Phase 3."*
  3. For the one file: read bytes, parse, validate, hash, return.

- [ ] **Step 3: Commit**

  ```bash
  pytest tests/lib/org_config/test_discovery.py -v
  git add aec/lib/org_config/discovery.py tests/lib/org_config/test_discovery.py
  git commit -m "feat(org-config): add single-org discovery for phase 1"
  ```

---

## Task 13: Wire public surface in `aec/lib/org_config/__init__.py`

**Files:**
- Modify: `aec/lib/org_config/__init__.py`

- [ ] **Step 1: Export the public API**

  ```python
  """Org-config overlay engine.

  Phase 1: schema, validation, single-org discovery, unsigned trust.
  """
  from .discovery import EnrolledOrg, discover_enrolled_orgs
  from .errors import (
      OrgConfigError,
      OrgConfigParseError,
      OrgConfigValidationError,
      OrgConfigTrustError,
      OrgConfigMultiOrgRejectedError,
      OrgConfigUnknownSchemaError,
  )
  from .paths import OrgPaths
  from .schema import OrgConfig, ItemPolicy, CustomSource, Stance

  __all__ = [
      "EnrolledOrg",
      "discover_enrolled_orgs",
      "OrgConfig",
      "OrgConfigError",
      "OrgConfigParseError",
      "OrgConfigValidationError",
      "OrgConfigTrustError",
      "OrgConfigMultiOrgRejectedError",
      "OrgConfigUnknownSchemaError",
      "OrgPaths",
      "ItemPolicy",
      "CustomSource",
      "Stance",
  ]
  ```

- [ ] **Step 2: Smoke test**

  ```bash
  python -c "from aec.lib.org_config import discover_enrolled_orgs, OrgConfig; print('ok')"
  ```

  Expected: `ok`. (Requires `pip install -e ".[org-configs-preview]"` for PyYAML.)

- [ ] **Step 3: Commit**

  ```bash
  git add aec/lib/org_config/__init__.py
  git commit -m "feat(org-config): export phase-1 public api"
  ```

---

## Task 14: Implement `aec/commands/org.py` — `aec org` command group

**Files:**
- Create: `aec/commands/org.py`
- Create: `tests/commands/test_org.py`
- Modify: `aec/cli.py` (register new subcommand group)

Phase 1 commands: `enroll`, `list`, `status`, `show`, `remove`. Each is a thin shell over `aec.lib.org_config`. Refer to `aec/commands/preferences.py` and `aec/commands/discover.py` for the existing typer-based command-file conventions in this codebase.

- [ ] **Step 1: Write the failing tests**

  ```python
  from pathlib import Path

  from typer.testing import CliRunner

  from aec.cli import app


  runner = CliRunner()
  FIXTURES = Path(__file__).parent.parent / "lib" / "org_config" / "fixtures"


  def _run(args, env_home: Path):
      return runner.invoke(app, args, env={"HOME": str(env_home)})


  def test_org_help_lists_phase_1_commands(tmp_path: Path):
      result = _run(["org", "--help"], tmp_path)
      assert result.exit_code == 0
      for cmd in ("enroll", "list", "status", "show", "remove"):
          assert cmd in result.stdout


  def test_org_list_empty(tmp_path: Path):
      result = _run(["org", "list"], tmp_path)
      assert result.exit_code == 0
      assert "no orgs enrolled" in result.stdout.lower()


  def test_org_enroll_local_path_with_consent(tmp_path: Path):
      cfg = FIXTURES / "valid-minimal.yaml"
      result = _run(
          ["org", "enroll", str(cfg), "--allow-unsigned", "--yes"],
          tmp_path,
      )
      assert result.exit_code == 0
      assert (tmp_path / ".aec" / "orgs" / "minimal.yaml").exists()
      assert (tmp_path / ".aec" / "orgs" / "minimal.state.json").exists()


  def test_org_enroll_unsigned_without_consent_refuses(tmp_path: Path):
      cfg = FIXTURES / "valid-minimal.yaml"
      result = _run(["org", "enroll", str(cfg)], tmp_path)
      # Without --allow-unsigned and without an interactive yes, refuses.
      assert result.exit_code != 0


  def test_org_status_shows_enrolled_org(tmp_path: Path):
      cfg = FIXTURES / "valid-minimal.yaml"
      _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
      result = _run(["org", "status"], tmp_path)
      assert result.exit_code == 0
      assert "minimal" in result.stdout
      assert "unsigned" in result.stdout.lower()


  def test_org_show_prints_config(tmp_path: Path):
      cfg = FIXTURES / "valid-minimal.yaml"
      _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
      result = _run(["org", "show", "minimal"], tmp_path)
      assert result.exit_code == 0
      assert "schema_version" in result.stdout


  def test_org_remove_deletes_state_and_config(tmp_path: Path):
      cfg = FIXTURES / "valid-minimal.yaml"
      _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
      result = _run(["org", "remove", "minimal", "--yes"], tmp_path)
      assert result.exit_code == 0
      assert not (tmp_path / ".aec" / "orgs" / "minimal.yaml").exists()
      assert not (tmp_path / ".aec" / "orgs" / "minimal.state.json").exists()


  def test_org_enroll_url_not_supported_in_phase_1(tmp_path: Path):
      result = _run(
          ["org", "enroll", "https://example.com/config.yaml", "--allow-unsigned", "--yes"],
          tmp_path,
      )
      # Phase 2 adds URL fetch + signing. Phase 1 supports local-path only.
      assert result.exit_code != 0
      assert "phase 2" in result.stdout.lower() or "phase 2" in result.stderr.lower()
  ```

  These tests use `--yes` to bypass interactive prompts so they're deterministic. Implementation must support `--yes` and `--allow-unsigned`.

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  pytest tests/commands/test_org.py -v
  ```

- [ ] **Step 3: Implement `aec/commands/org.py`**

  Required commands and behaviors:

  | Command | Phase 1 behavior |
  |---|---|
  | `aec org enroll <path>` | Local-path only. Read file, parse, validate, run trust check (unsigned consent prompt unless `--allow-unsigned` or `--yes`), copy to `~/.aec/orgs/<org-id>.yaml`, write state. URL paths exit with "URL fetch added in Phase 2". |
  | `aec org list` | List enrolled orgs (Phase 1: ≤ 1) with `org_id`, `config_version`, `trust_mode`, `last_applied_at`. Empty case: "no orgs enrolled". |
  | `aec org status [<org-id>]` | Detailed status: org metadata, hash, trust state, source-of-record, any `unsigned` warnings. If no `<org-id>`, show all (Phase 1: 0 or 1). |
  | `aec org show <org-id>` | Print the resolved/effective config. `--raw` flag prints the file as-is. |
  | `aec org remove <org-id>` | Remove `<org-id>.yaml` + `<org-id>.state.json`. Prompt for confirmation unless `--yes`. |

  Helpers used by all subcommands:
  - `_resolve_paths()` — returns `OrgPaths.default()`. Tests inject `$HOME` so this just works.
  - `_print_unsigned_warning(console)` — formatted multi-line warning per spec.

  Exit codes (per spec):
  - `10` — trust failure
  - `12` — multi-org rejected (Phase 1) or P6 violation (Phase 3+)
  - `13` — schema/validation failure

- [ ] **Step 4: Wire into `aec/cli.py`**

  Find where existing subcommand groups are registered (search for `app.add_typer` or the typer group registrations). Register the org group:

  ```python
  from .commands.org import org_app
  app.add_typer(org_app, name="org", help="Manage organization configurations")
  ```

- [ ] **Step 5: Run all tests + smoke `aec org --help`**

  ```bash
  pytest -v
  pip install -e ".[org-configs-preview,dev]"
  aec org --help
  ```

  Expected: pytest all green, `aec org --help` lists the five commands.

- [ ] **Step 6: Commit**

  ```bash
  git add aec/commands/org.py aec/cli.py tests/commands/test_org.py
  git commit -m "feat(org-config): add aec org command group for phase 1"
  ```

---

## Task 15: Add "Org configurations" section to `aec doctor`

**Files:**
- Modify: `aec/commands/doctor.py`
- Modify: `tests/commands/test_org.py` (add doctor-section test) OR new `tests/commands/test_doctor_org_section.py`

- [ ] **Step 1: Write the failing test**

  ```python
  def test_doctor_shows_org_section_when_org_enrolled(tmp_path: Path):
      cfg = FIXTURES / "valid-minimal.yaml"
      _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
      result = _run(["doctor"], tmp_path)
      assert result.exit_code == 0
      assert "org configuration" in result.stdout.lower()
      assert "minimal" in result.stdout
      # Unsigned configs must always be flagged in doctor output.
      assert "unsigned" in result.stdout.lower()


  def test_doctor_omits_org_section_when_no_orgs(tmp_path: Path):
      result = _run(["doctor"], tmp_path)
      assert result.exit_code == 0
      # Section should be absent OR clearly say no orgs enrolled.
      out_low = result.stdout.lower()
      assert "no orgs enrolled" in out_low or "org configurations" not in out_low
  ```

- [ ] **Step 2: Run failing test, then add the doctor section**

  In `aec/commands/doctor.py`, find where existing sections render. Add a new section that:
  - Calls `discover_enrolled_orgs(OrgPaths.default())` inside a try/except.
  - On no orgs: omit the section entirely (don't pad output with empty noise).
  - On 1 org: print `org_id`, `config_version`, `trust_mode` (red if `unsigned`), `last_verified_at`.
  - On `OrgConfigError`: print the error in red; doctor exit code stays 0 (doctor reports, doesn't gate).

- [ ] **Step 3: Run + commit**

  ```bash
  pytest -v
  git add aec/commands/doctor.py tests/commands/
  git commit -m "feat(doctor): surface enrolled org configuration in doctor output"
  ```

---

## Task 16: User-facing documentation

**Files:**
- Create: `docs/users/org-configs.md`
- Create: `docs/orgs/authoring-org-configs.md`
- Create: `docs/orgs/examples/minimal-phase1.yaml`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/users/org-configs.md`**

  Audience: end-user receiving an org config. Must answer:
  - What is an org config?
  - How do I enroll? (`aec org enroll <path>` — Phase 1 local-path only)
  - What does `unsigned` mean and why does it matter?
  - How do I see what an org has configured? (`aec org show`, `aec org status`)
  - How do I leave? (`aec org remove`)
  - What's NOT supported yet (Phase 2+ features)

- [ ] **Step 2: Write `docs/orgs/authoring-org-configs.md`**

  Audience: IT/admin authoring an org config. Must include:
  - Schema reference for Phase 1 fields only (frontmatter, `sources`, `items`, `install.preferences`, `install.prompts`, `install.agents`).
  - The closed allow-lists for `install.preferences` keys and `install.prompts` IDs (link out to `allow_lists.py` for the source of truth).
  - The reserved source IDs.
  - The closed Stance vocabulary.
  - "Phase 2+" callout sections explaining what's coming so authors don't ship configs depending on signing/projects/enrollment_script before they're real.
  - Reference the example file.

- [ ] **Step 3: Write `docs/orgs/examples/minimal-phase1.yaml`**

  A complete, working Phase 1 config that an org can copy and adapt. Should cover the unsigned trust mode, both reserved and (commented-out) custom sources, and at least one item per type.

- [ ] **Step 4: Update README**

  Add a new section (location: just after the project tagline, before installation instructions) titled "AEC for Individuals, Teams, and Organizations" with:
  - Three short paragraphs (one per scale).
  - Note that AEC never hosts org configurations; each organization publishes their own.
  - Link to `docs/users/org-configs.md` for end users.
  - Link to `docs/orgs/authoring-org-configs.md` for admins.

  Per CLAUDE.md "README Guidelines": do NOT use real local project names; use placeholders.

- [ ] **Step 5: Verify links resolve**

  ```bash
  # quick sanity: every relative link in README and the new docs points at a real file
  python3 - <<'PY'
  import re, pathlib
  for md in ["README.md", "docs/users/org-configs.md", "docs/orgs/authoring-org-configs.md"]:
      text = pathlib.Path(md).read_text()
      for m in re.finditer(r'\]\(([^)]+\.(?:md|yaml))\)', text):
          target = pathlib.Path(md).parent / m.group(1)
          assert target.resolve().exists(), f"{md} references missing file: {m.group(1)}"
  print("ok")
  PY
  ```

- [ ] **Step 6: Commit**

  ```bash
  git add docs/users/org-configs.md docs/orgs/ README.md
  git commit -m "docs(org-config): add phase-1 user, author, and example docs"
  ```

---

## Task 17: Update `docs/qa-verification.md`

Per CLAUDE.md: any plan file requires updates to the QA verification doc.

**Files:**
- Modify: `docs/qa-verification.md` (if it exists in this repo) OR create new section in repo's existing QA doc

- [ ] **Step 1: Check whether the file exists**

  ```bash
  test -f docs/qa-verification.md && echo "exists" || echo "missing — confirm with user before creating"
  ```

  If missing: stop and ask the user whether to create it or whether QA verification lives elsewhere in this repo. Don't unilaterally create.

- [ ] **Step 2: Add Phase 1 verification steps**

  Add a section "Org Config — Phase 1" with manual verification steps mirroring the test suite but stated for a human:

  1. With `pip install -e .` (no extras), `aec org --help` exits cleanly with a "requires `pip install aec[org-configs-preview]`" message.
  2. With `pip install -e ".[org-configs-preview]"`, `aec org enroll <path-to-minimal-fixture> --allow-unsigned --yes` creates `~/.aec/orgs/minimal.yaml` and `~/.aec/orgs/minimal.state.json`.
  3. `aec org list` shows the enrolled org.
  4. `aec org status` shows trust mode `unsigned` in red/highlighted.
  5. `aec org show minimal` prints the validated config.
  6. `aec doctor` includes an "Org configurations" section flagging the unsigned config.
  7. Dropping a second YAML into `~/.aec/orgs/` causes `aec org list` to exit 12 with a "Phase 1: single-org only" message.
  8. `aec org remove minimal --yes` cleans up both files.

- [ ] **Step 3: Commit**

  ```bash
  git add docs/qa-verification.md
  git commit -m "docs(qa): add phase-1 org-config verification steps"
  ```

---

## Task 18: Roadmap entry

Per CLAUDE.md: every new plan must be discussed for placement in `plans/ROADMAP.md`.

**Files:**
- Modify: `plans/ROADMAP.md`

- [ ] **Step 1: Read `plans/ROADMAP.md` and `AGENTINFO.md`**

  Identify tier definitions and current entries.

- [ ] **Step 2: Propose a tier placement to the user**

  Org-config Phase 1 is a foundation feature with no current users blocked on it but high strategic value. Suggest a tier and explain reasoning (likely mid-tier). User must confirm before commit.

- [ ] **Step 3: Add the entry and commit**

  Once approved:

  ```bash
  git add plans/ROADMAP.md
  git commit -m "docs(roadmap): add org-config phase 1 plan"
  ```

---

## Task 19: Final verification

- [ ] **Step 1: Full test suite green**

  ```bash
  pytest -v
  ```

  Coverage must stay above the configured `--cov-fail-under=65`.

- [ ] **Step 2: Linter / type-checker (if configured)**

  ```bash
  test -f .pre-commit-config.yaml && pre-commit run --all-files || true
  test -d .mypy_cache && python -m mypy aec/ || true
  ```

  Resolve any new errors. Linting errors must never be ignored or bypassed (CLAUDE.md).

- [ ] **Step 3: Manual smoke per `docs/qa-verification.md` Phase 1 section**

  Execute steps 1–8 from Task 17 against a clean `$HOME` (use `HOME=$(mktemp -d)` in a subshell).

- [ ] **Step 4: Final commit (if anything above produced changes)**

  ```bash
  git status
  # if clean, nothing to commit
  ```

- [ ] **Step 5: Open PR**

  ```bash
  git push -u origin <branch>
  gh pr create --title "feat: org-config overlay phase 1 (schema, parser, unsigned trust, aec org commands)" --body "$(cat <<'EOF'
  ## Summary
  - Adds `aec/lib/org_config/` package: parser, validator, hashing, state, unsigned trust, single-org discovery
  - Adds `aec org` command group: `enroll`, `list`, `status`, `show`, `remove`
  - Adds `Org configurations` section to `aec doctor`
  - Ships behind `pip install aec[org-configs-preview]`; core remains zero runtime deps
  - Phase 1 only — signed trust modes, multi-org, projects[], enrollment_script land in later phases

  Spec: `docs/superpowers/specs/2026-05-04-org-config-overlay-design.md`
  Plan: `docs/superpowers/plans/2026-05-04-org-config-overlay-phase-1.md`

  ## Test plan
  - [ ] `pytest -v` green
  - [ ] Manual smoke per `docs/qa-verification.md` "Org Config — Phase 1" section
  - [ ] `aec org enroll` against `docs/orgs/examples/minimal-phase1.yaml` works end-to-end
  - [ ] Multi-org scenario produces exit code 12 with clear "Phase 3" message

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

---

## Out-of-scope reminders (for the next plan, not this one)

When Phase 2 is planned:
- Add `pynacl` to a new `[org-configs]` extras group (extras-preview becomes the precursor).
- Implement `dns_anchor` and `pinned_key` modes inside `aec/lib/org_config/trust.py`.
- Add `aec org sync`, `aec org trust-rotate`, `aec org pubkey verify` commands.
- Update `validator.py` to accept `dns_anchor`/`pinned_key` trust modes.
- Update `OrgState` to populate `pubkey_fingerprint` and `pubkey_source`.
- Add `docs/orgs/signing-keys.md` and `docs/orgs/hosting-and-distribution.md`.

When Phase 3 is planned:
- Remove the `discover_enrolled_orgs` single-org guard.
- Implement `aec/lib/org_config/conflicts.py`.
- Add `aec org resolve`, `aec org reorder`, `aec org resolutions` commands.
- Conflict-resolutions JSON file shape (already reserved on disk).
