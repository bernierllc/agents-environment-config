# AEC Quality Infrastructure: `.aec.json`, Port Registry & Test Detection

> Design spec for adding per-project `.aec.json` configuration, a central port registry
> with conflict detection, test framework auto-detection, and report viewer preferences.
> This is Phase 1 of a three-phase initiative to bring automated quality infrastructure
> to AEC-managed projects.

## Problem

Developers managing multiple projects on a single machine face three recurring problems
that AEC is well-positioned to solve:

1. **Port collisions** — Projects silently claim the same ports. Developers discover conflicts
   at runtime when a dev server or database fails to bind. The current workaround is a
   manually maintained `~/projects/ports.json` file that agents are told to check, but it
   has no enforcement and already contains conflicts (port 3000 is claimed by 5 projects).

2. **No per-project AEC metadata** — AEC tracks installed skills/rules/agents in a central
   manifest (`installed-manifest.json`) but has no in-repo counterpart. Projects can't
   declare their own configuration, and agents have no structured way to learn about a
   project's test setup, ports, or installed tooling.

3. **Test discovery is manual** — When setting up a project, AEC detects languages and
   installs lint hooks, but has no awareness of test frameworks, test commands, or test
   infrastructure. This blocks the Phase 2/3 goal of scheduled automated test runs.

## Phasing Overview

This spec covers **Phase 1** only. The full initiative is:

- **Phase 1** (this spec): `.aec.json` schema, port registry, test framework detection,
  report viewer preferences, CLI commands, integration with existing flows
- **Phase 2**: Generic runner script, OS-specific scheduler wrappers (launchd/cron/Task
  Scheduler), report generation, retention policies
- **Phase 3**: Multi-project orchestration, preflight checks, cleanup verification,
  `aec reports` command suite

---

## Core Principles

1. **First-come-first-served.** Port assignments are resolved by registration timestamp.
   The first project to register a port owns it. Conflicts are surfaced as warnings, never
   silently resolved.

2. **Explicit unregister only.** Ports are freed only when `aec prune` detects a project
   directory no longer exists. No automatic reassignment.

3. **Committed by default.** `.aec.json` is checked into git by default. It contains useful
   project metadata (ports, test suites, installed tooling) that benefits any contributor,
   not just AEC users. Gitignore is toggleable via `aec config set aec_json_gitignored true`.

4. **Full schema from day one.** `.aec.json` ships with all sections (ports, test, installed)
   even though test scheduling is wired in Phase 2/3. Sections can be empty. This avoids
   schema migrations later.

5. **Extensible detection.** Test framework detection follows the same dict-based pattern as
   `LANGUAGE_HOOKS` — adding a new framework means adding a dict entry.

6. **Never auto-install.** Consistent with AEC's core principle: all features are opt-in.
   Port registry, scheduled tests, and report viewers are all prompted during install/setup.

---

## `.aec.json` Schema

Located at the project root. Created/updated during `aec setup`.

```json
{
  "$schema": "https://aec.bernier.dev/schema/aec.json",
  "version": "1.0.0",
  "project": {
    "name": "earnlearn",
    "description": "EarnLearn platform - Next.js application"
  },
  "ports": {
    "dev-server": {
      "port": 3333,
      "protocol": "http",
      "description": "Next.js dev server"
    },
    "test-database": {
      "port": 5433,
      "protocol": "postgresql",
      "description": "Docker test DB"
    },
    "supabase-api": {
      "port": 54421,
      "protocol": "http",
      "description": "Local Supabase API Gateway"
    }
  },
  "test": {
    "suites": {
      "unit": {
        "command": "npm run test:unit",
        "cleanup": null
      },
      "integration": {
        "command": "npm run test:integration",
        "cleanup": "docker compose -f docker-compose.test.yml down"
      },
      "e2e": {
        "command": "npm run test:e2e",
        "cleanup": "npx playwright cleanup"
      }
    },
    "prerequisites": ["docker"],
    "scheduled": ["unit", "integration"]
  },
  "installed": {
    "skills": {},
    "rules": {},
    "agents": {}
  }
}
```

### Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `$schema` | string | No | JSON Schema URL (forward-looking, not hosted yet) |
| `version` | string | Yes | Schema version (`"1.0.0"`) |
| `project.name` | string | Yes | Project identifier, defaults to directory name |
| `project.description` | string | No | Human-readable description |
| `ports` | object | No | Flat key-value map. Keys are user-defined names. |
| `ports.<key>.port` | integer | Yes | Port number |
| `ports.<key>.protocol` | string | No | Protocol hint (http, postgresql, redis, etc.) |
| `ports.<key>.description` | string | No | Human-readable description |
| `test` | object | No | Test configuration (populated by detection, editable by user) |
| `test.suites` | object | No | Named test suites |
| `test.suites.<key>.command` | string | Yes | Shell command to run this suite |
| `test.suites.<key>.cleanup` | string/null | No | Shell command to run after suite completes |
| `test.prerequisites` | array[string] | No | Required tools (checked before scheduled runs) |
| `test.scheduled` | array[string] | No | Suite names to include in automated runs |
| `installed` | object | No | Mirror of central manifest data for this repo |
| `installed.skills` | object | No | `{name: {version, contentHash, installedAt}}` |
| `installed.rules` | object | No | Same structure |
| `installed.agents` | object | No | Same structure |

### Design Decisions

- **`ports` keys are free-form.** No enforced `environment` field. Users name keys however
  they want (`dev-server`, `test-db`, `supabase-studio`, etc.). This matches the existing
  `ports.json` convention and avoids imposing structure that doesn't fit all projects.

- **`test.scheduled` is a whitelist.** Only suites listed here run in automated scheduled
  runs. E2E suites that spin up browsers or heavy infrastructure can exist in `.aec.json`
  for documentation without being included in unattended runs.

- **`installed` mirrors central manifest.** This gives the repo a local copy of what AEC
  has installed. Updated during `aec setup`, `aec install`, `aec upgrade`. The central
  `installed-manifest.json` remains the source of truth; `.aec.json` is a convenience copy
  for agents and developers reading the repo.

- **`$schema` is forward-looking.** Not hosted in Phase 1, but reserving the field means
  IDEs will pick up validation automatically when we do host it.

---

## Central Port Registry

Located at `~/.agents-environment-config/ports-registry.json`.

```json
{
  "version": "1.0.0",
  "ports": {
    "3333": {
      "project": "earnlearn",
      "project_path": "/Users/mattbernier/projects/earnlearn",
      "key": "dev-server",
      "protocol": "http",
      "description": "Next.js dev server",
      "registered_at": "2026-04-07T14:00:00Z"
    },
    "5433": {
      "project": "earnlearn",
      "project_path": "/Users/mattbernier/projects/earnlearn",
      "key": "test-database",
      "protocol": "postgresql",
      "description": "Docker test DB",
      "registered_at": "2026-04-07T14:00:00Z"
    }
  }
}
```

### Design Decisions

- **Keyed by port number (as string).** Conflict detection is O(1) lookup.

- **`registered_at` timestamp.** Enforces first-come-first-served. When a conflict is
  detected, AEC shows which project registered first and when.

- **`project_path` enables pruning.** `aec prune` checks if the directory still exists
  and frees ports when it doesn't.

- **Built from `.aec.json` files.** During `aec setup`, AEC reads the project's `.aec.json`
  ports section and attempts to register each one. Conflicts are surfaced immediately.

- **Non-blocking conflicts.** Port conflicts warn but do not block `aec setup`. The project
  is tracked, but conflicting ports are not registered. The user fixes `.aec.json` and
  re-runs `aec setup` or `aec ports register`.

### Conflict UX

```
$ aec setup ~/projects/new-project
  ⚠ Port conflict: port 3000 is already registered to "mbernier.com"
    (registered 2026-03-15T10:00:00Z)
    Your .aec.json assigns 3000 to "dev-server"
    → Update your .aec.json to use a different port, or run
      aec ports list to see all registered ports
```

---

## CLI Commands

### New: `aec ports` Command Group

| Command | Description |
|---|---|
| `aec ports list` | Show all registered ports across all projects. Grouped by project, sorted by port number. |
| `aec ports check [path]` | Check a project's `.aec.json` ports against the registry without registering. Reports conflicts. Defaults to current directory. |
| `aec ports register [path]` | Register a project's ports from its `.aec.json`. Skips conflicts with warnings. Defaults to current directory. |
| `aec ports unregister [path]` | Remove all port registrations for a project. Defaults to current directory. |
| `aec ports validate` | Scan the full registry for stale entries (dead project paths) and report. Does not remove — `aec prune` does. |

### Changes to Existing Commands

**`aec install` (first-time setup)**

After existing steps (submodules, agent detection, settings prompts), add:

1. "Enable port registry?" (Y/n) — stores `port_registry_enabled` preference
2. "Enable scheduled test runs?" (Y/n) — stores `scheduled_tests_enabled` preference
   (wiring comes Phase 3, but ask now so the preference exists)
3. If scheduled tests enabled: report viewer selection prompt (see Report Viewers section)
4. If scheduled tests enabled: retention preference — "Automatically prune reports older
   than N days, or manage manually?" → stores `report_retention_mode` (`auto`/`manual`)
   and `report_retention_days` (default 30)

**`aec setup [path]`**

After existing steps (agent files, gitignore, raycast scripts, lint hooks), add:

1. Check for existing `.aec.json` — if present, read it; if not, create skeleton
2. Populate `project.name` from directory name
3. Run language detection (existing) → run test framework detection (new) → suggest test
   suites via interactive selection
4. Prompt for port assignments if `ports` section is empty — or validate existing ports
5. Register ports against central registry, warn on conflicts
6. Populate `installed` section from current manifest data for this repo
7. Prompt for `.aec.json` gitignore preference (respects `aec_json_gitignored` setting if
   already configured globally, otherwise asks)

**`aec prune`**

After existing stale-path removal:

1. Load port registry
2. Remove all port entries whose `project_path` no longer exists
3. Report freed ports (count and port numbers)

**`aec setup --all`**

Batch mode already exists. Port registration runs per-project. Conflicts accumulate and
are reported as a summary at the end rather than interactive prompts per-project.

**`aec update` / `aec upgrade`**

When upgrading a repo's skills/rules/agents, also update the `installed` section of that
repo's `.aec.json` to stay in sync with the central manifest.

**`aec list`**

When run inside a project with `.aec.json`, show local installed items alongside global.

### New Config Settings

| Setting | Default | Description |
|---|---|---|
| `aec_json_gitignored` | `false` | Whether `.aec.json` should be added to `.gitignore` during setup |
| `port_registry_enabled` | prompted | Whether port registry is active |
| `scheduled_tests_enabled` | prompted | Whether scheduled test runs are enabled (wired in Phase 3) |
| `report_viewer` | prompted | Command key for opening reports, or `null` for no auto-open |
| `report_retention_mode` | prompted | `auto` or `manual` |
| `report_retention_days` | `30` | Days to keep reports (only used when mode is `auto`) |

All settings manageable via `aec config set <key> <value>` and documented in `--help`.

---

## Test Framework Detection

New `TEST_FRAMEWORK_HOOKS` dict in `hooks.py`, parallel to `LANGUAGE_HOOKS`.

```python
TEST_FRAMEWORK_HOOKS: Dict[str, Dict[str, Any]] = {
    "jest": {
        "display_name": "Jest",
        "languages": ["typescript", "javascript"],
        "detect_files": [
            "jest.config.js", "jest.config.ts",
            "jest.config.mjs", "jest.config.cjs",
        ],
        "detect_package_json": {
            "devDependencies": ["jest"],
            "scripts": ["test"],
        },
        "default_command": "npx jest",
        "default_cleanup": None,
    },
    "vitest": {
        "display_name": "Vitest",
        "languages": ["typescript", "javascript"],
        "detect_files": [
            "vitest.config.ts", "vitest.config.js",
            "vitest.config.mts",
        ],
        "detect_package_json": {"devDependencies": ["vitest"]},
        "default_command": "npx vitest run",
        "default_cleanup": None,
    },
    "pytest": {
        "display_name": "pytest",
        "languages": ["python"],
        "detect_files": ["pytest.ini", "conftest.py"],
        "detect_pyproject": {
            "tool.pytest": True,
            "project.optional-dependencies": ["pytest"],
        },
        "default_command": "python -m pytest",
        "default_cleanup": None,
    },
    "playwright": {
        "display_name": "Playwright",
        "languages": ["typescript", "javascript", "python"],
        "detect_files": [
            "playwright.config.ts", "playwright.config.js",
        ],
        "detect_package_json": {
            "devDependencies": ["@playwright/test"],
        },
        "default_command": "npx playwright test",
        "default_cleanup": None,
    },
    "cargo_test": {
        "display_name": "Cargo Test",
        "languages": ["rust"],
        "detect_files": ["Cargo.toml"],
        "default_command": "cargo test",
        "default_cleanup": None,
    },
    "go_test": {
        "display_name": "Go Test",
        "languages": ["go"],
        "detect_files": ["go.mod"],
        "default_command": "go test ./...",
        "default_cleanup": None,
    },
    "rspec": {
        "display_name": "RSpec",
        "languages": ["ruby"],
        "detect_files": [".rspec", "spec/spec_helper.rb"],
        "default_command": "bundle exec rspec",
        "default_cleanup": None,
    },
}
```

### Detection Flow During `aec setup`

1. Run `detect_languages()` (existing)
2. Run `detect_test_frameworks(project_dir)` — checks `detect_files`, then parses
   `package.json`/`pyproject.toml` for deeper signals (`detect_package_json`,
   `detect_pyproject` keys)
3. Scan `package.json` `scripts` object for keys matching `test*` — collect as candidate
   commands with their values
4. Present findings to user interactively:

```
  Detected test frameworks:
    ✓ Jest (jest.config.ts)
    ✓ Playwright (playwright.config.ts)

  Found test scripts in package.json:
    • test:unit → jest --config jest.config.unit.ts
    • test:integration → jest --config jest.config.integration.ts
    • test:e2e → playwright test

  Which should be included in .aec.json test suites?
  [x] test:unit
  [x] test:integration
  [ ] test:e2e
```

5. For selected commands, ask about cleanup commands (or accept `null`)
6. Write to `.aec.json` `test.suites` section with user's selections
7. In batch mode (`aec setup --all`), use detected defaults without interactive prompts

### New Detection Functions

```python
def detect_test_frameworks(project_dir: Path) -> List[Dict[str, Any]]:
    """Detect test frameworks in a project directory.

    Returns list of dicts with keys: key, display_name, detected_by.
    """

def scan_test_scripts(project_dir: Path) -> List[Dict[str, str]]:
    """Scan package.json/pyproject.toml for test-related scripts.

    Returns list of dicts with keys: name, command, source.
    """
```

### Extensibility

Adding a new test framework requires only adding a dict entry to `TEST_FRAMEWORK_HOOKS`.
No code changes needed. Same pattern developers already understand from `LANGUAGE_HOOKS`.

---

## Report Viewers

New `REPORT_VIEWERS` dict in a new `viewers.py` module (or added to `hooks.py`),
keyed by OS platform. Same extensible pattern as `LANGUAGE_HOOKS`.

```python
REPORT_VIEWERS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "darwin": {
        "cursor": {
            "display_name": "Cursor",
            "command": "cursor {file}",
            "detect": ["cursor"],
        },
        "vscode": {
            "display_name": "VS Code",
            "command": "code {file}",
            "detect": ["code"],
        },
        "open": {
            "display_name": "Default App (open)",
            "command": "open {file}",
            "detect": None,
        },
        "nano": {
            "display_name": "nano",
            "command": "nano {file}",
            "detect": ["nano"],
        },
        "vim": {
            "display_name": "vim",
            "command": "vim {file}",
            "detect": ["vim"],
        },
    },
    "linux": {
        "vscode": {
            "display_name": "VS Code",
            "command": "code {file}",
            "detect": ["code"],
        },
        "xdg": {
            "display_name": "Default App (xdg-open)",
            "command": "xdg-open {file}",
            "detect": ["xdg-open"],
        },
        "nano": {
            "display_name": "nano",
            "command": "nano {file}",
            "detect": ["nano"],
        },
        "vim": {
            "display_name": "vim",
            "command": "vim {file}",
            "detect": ["vim"],
        },
    },
    "windows": {
        "vscode": {
            "display_name": "VS Code",
            "command": "code {file}",
            "detect": ["code"],
        },
        "notepad": {
            "display_name": "Notepad",
            "command": "notepad {file}",
            "detect": None,
        },
        "start": {
            "display_name": "Default App",
            "command": "start {file}",
            "detect": None,
        },
    },
}
```

### Viewer Selection During Install/Setup

When scheduled tests are opted into:

```
  How would you like test reports opened?
  Detected on this machine:
    1. Cursor
    2. VS Code
    3. Default App (open)
    4. nano
    5. vim
    6. Other (enter command with {file} placeholder)
    7. Don't open reports automatically
```

- Option 6 accepts a custom command string containing `{file}` placeholder
- Option 7 stores `"report_viewer": null`
- Detection uses `shutil.which()` — same pattern as `detect_agents()` in `config.py`
- `detect: None` means always available on that OS (e.g., `open` on macOS, `notepad` on Windows)
- Stored in preferences as `report_viewer` setting
- Changeable later via `aec config set report_viewer cursor`

---

## Report Retention

User chooses during install/setup when scheduled tests are enabled:

```
  How should test reports be managed?
    1. Automatically prune reports older than N days (default: 30)
    2. Manage manually
```

### Automatic Mode

- Runner script (Phase 2) prunes reports older than `report_retention_days` after each run
- Stored as `report_retention_mode: "auto"` and `report_retention_days: 30` in preferences

### Manual Mode

- Reports accumulate indefinitely
- Each report summary file includes a header note:
  ```
  Note: 47 days of reports exist in ~/.agents-environment-config/tests/
  ```
- Count is computed at report generation time by counting existing date directories
- User can run `aec reports prune` (Phase 3) to clean up manually

---

## Integration with Existing AEC Flows

### Agent Instruction Injection

During `aec setup`, if port registry is enabled, append a section to the project's
`AGENTINFO.md`:

```markdown
## Port Registry

This project's ports are registered with AEC. Before assigning new ports,
check `aec ports list` to see all registered ports and avoid conflicts.

To register new ports:
1. Add them to `.aec.json` in the `ports` section
2. Run `aec ports register` to register them centrally

Port assignments use first-come-first-served. See `.aec.json` for this
project's current port assignments.
```

This replaces manual "go check ports.json" instructions currently given to agents.

### `.aec.json` Gitignore Management

- Default: `.aec.json` is **not** gitignored (committed to repo)
- Toggle: `aec config set aec_json_gitignored true`
- When set to `true`, `aec setup` adds `.aec.json` to `.gitignore`
- When set to `false`, `aec setup` removes `.aec.json` from `.gitignore` if present
- Per-project override is possible by manually editing `.gitignore`
- Documented in `aec config --help`

### Manifest Sync

When `aec install`, `aec uninstall`, or `aec upgrade` modifies a repo's installed items:

1. Update central `installed-manifest.json` (existing behavior)
2. If the repo has `.aec.json`, also update its `installed` section to match

This keeps the local copy in sync without requiring a separate command.

---

## Migration: Existing `ports.json`

The existing `~/projects/ports.json` on this machine contains ~15 projects with ~80+
port assignments. This is a one-time manual migration task during implementation, not
a CLI feature.

### Migration Strategy

1. Select 2-3 projects that are tracked by AEC and create `.aec.json` files in their
   project directories with port data from `ports.json` (tests project-first registration)
2. Convert the remaining projects' port data into the central `ports-registry.json`
   (tests global-first registration)
3. Keep a backup copy of the original `ports.json` as `ports.json.bak`

### Test Coverage from Migration

This provides real-world test fixtures for both registration paths:
- **Project → global**: Projects with `.aec.json` register ports into central registry
  during `aec setup`
- **Global → project**: Projects in central registry without `.aec.json` get ports
  populated when `.aec.json` is created during `aec setup`

---

## README Updates

The project README must be updated to document:

1. **`.aec.json` file** — purpose, schema reference, how it's created, gitignore option
2. **Port registry** — `aec ports` commands, conflict resolution, first-come-first-served rule
3. **Test framework detection** — what's detected, how to add custom test suites, the
   `TEST_FRAMEWORK_HOOKS` extensibility pattern
4. **Report viewers** — available viewers by OS, how to set/change, custom command option
5. **New config settings** — all settings added by this phase, their defaults, how to change
6. **Updated `aec install` flow** — new prompts added during first-time setup
7. **Updated `aec setup` flow** — `.aec.json` creation, port registration, test detection
8. **Updated `aec prune` behavior** — port registry cleanup

---

## Phase 2/3 Preview (Not in Scope)

For context on what Phase 1 is building toward:

### Phase 2: Runner & Scheduler

- Generic Python runner script (`~/.agents-environment-config/runner.py`) that reads
  `scheduler-config.json`, iterates tracked projects, reads each `.aec.json`, runs
  preflight checks, executes scheduled suites, runs cleanup, writes reports
- OS-specific scheduler wrappers in `schedulers/` (macos.py for launchd, linux.py for
  cron, windows.py for Task Scheduler)
- `aec schedule` command to configure run times

### Phase 3: Reports & Orchestration

- Report generation to `~/.agents-environment-config/tests/{datetime}/` with per-project
  output files and a summary file
- `aec reports` / `aec reports latest` commands
- Report viewer integration (open summary in configured viewer)
- Retention enforcement (auto-prune or manual with header notes)
- Preflight checks for prerequisites before running suites
- Multi-project concurrency and resource management

---

## File Changes Summary

### New Files

| File | Purpose |
|---|---|
| `aec/lib/test_detection.py` | `TEST_FRAMEWORK_HOOKS`, `detect_test_frameworks()`, `scan_test_scripts()` |
| `aec/lib/viewers.py` | `REPORT_VIEWERS` dict, `detect_viewers()`, viewer selection logic |
| `aec/lib/ports.py` | Port registry CRUD, conflict detection, validation |
| `aec/lib/aec_json.py` | `.aec.json` read/write/create, schema validation, merge logic |
| `aec/commands/ports.py` | `aec ports` command group (list, check, register, unregister, validate) |
| `tests/test_ports.py` | Port registry unit tests |
| `tests/test_test_detection.py` | Test framework detection tests |
| `tests/test_viewers.py` | Report viewer detection tests |
| `tests/test_aec_json.py` | `.aec.json` read/write/validation tests |

### Modified Files

| File | Change |
|---|---|
| `aec/cli.py` | Register `ports` command group |
| `aec/commands/install.py` | Add port registry + scheduled test prompts to install flow |
| `aec/commands/repo.py` | Add `.aec.json` creation, port registration, test detection to setup flow |
| `aec/commands/setup.py` | Pass-through to repo.py changes for `aec setup` |
| `aec/lib/tracking.py` | `prune_stale()` also frees ports for pruned projects |
| `aec/lib/preferences.py` | New `OPTIONAL_FEATURES` entries for port registry + scheduled tests |
| `aec/lib/hooks.py` | May stay unchanged if test detection goes in separate module |
| `aec/lib/config.py` | New path constants (`AEC_PORTS_REGISTRY`, etc.) |
| `README.md` | Full documentation of new features |
| `AGENTINFO.md` | Updated with port registry section template |
