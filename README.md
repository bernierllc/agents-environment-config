# Agents Environment Configuration

Every new project means setting up AI agent configs from scratch -- `CLAUDE.md`, Cursor rules, Gemini instructions, and more. Then keeping them consistent across projects. Then remembering which agents need frontmatter and which don't.

This repo eliminates that. Define your development standards once, and `aec` distributes them to every project, formatted correctly for each agent.

> **Note:** This is a template repository. It provides shared configurations that get copied to your projects. Do not add project-specific content here -- that goes in each project's `AGENTINFO.md`.

## What's Inside

- **Shared Cursor rules** (`.cursor/rules/`) - Development standards in Cursor format (with YAML frontmatter)
- **Agent-agnostic rules** (`.agent-rules/`) - The same rules without Cursor frontmatter, so other agents don't waste tokens on it
- **Agent instruction files** (`templates/CLAUDE.md`, `templates/AGENTS.md`, etc.) - Templates that tell each agent where to find your rules
- **The `aec` CLI** - Sets up new projects, keeps rules in sync, validates parity across formats
- **Submodules** for agents and skills (`bernierllc/agency-agents`, `bernierllc/skills`)

## Supported Agents

AEC handles the format differences between agents automatically. You write rules once; each agent gets them in the format it expects.

| Agent | Instruction File | Detection | Hooks | Description |
|-------|------------------|-----------|-------|-------------|
| Claude Code | `CLAUDE.md` | `claude` command or `~/.claude` | Yes | Anthropic's CLI coding agent |
| Cursor | `.cursor/rules/*.mdc` | `cursor` command or `/Applications/Cursor.app` | Yes | AI-first IDE with Cursor rules |
| Codex | `AGENTS.md` | `codex` command | No | OpenAI's coding agent |
| Gemini CLI | `GEMINI.md` | `gemini` command | Yes | Google's CLI coding agent |
| Qwen Code | `QWEN.md` | `qwen` command | No | Alibaba's coding agent |

All non-Cursor agents use `.agent-rules/*.md` (standard markdown, no frontmatter). Cursor uses `.cursor/rules/*.mdc` (with YAML frontmatter). See [Rules Architecture](#rules-architecture) for details.

All agent definitions live in [`agents.json`](agents.json) at the repo root. This is the single source of truth -- Python config, shell config, file lists, and detection logic are all derived from it.

Want to add support for another agent? See the [Adding Agent Support](docs/adding-agent-support.md) guide -- it's just one JSON entry + two commands.

## Quick Start

### First-Time Setup

> **New to Python/pip?** The `pip` command below requires Python 3.10+. If you don't have it installed, see the [official pip installation guide](https://pip.pypa.io/en/stable/installation/) for macOS, Windows, and Linux instructions.

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config

# Install the CLI (one time)
pip install -e .

# Run setup
aec install
```

> **Not totally sure yet?** Run with `--dry-run` to see what would be changed, before you run it for real!
> ```bash
> aec install --dry-run
> ```

Or using shell scripts (macOS/Linux only):
```bash
./scripts/setup.sh
```

This creates:
1. `~/.agent-tools/` - Centralized directory for rules, agents, skills, and commands
2. Agent-specific symlinks for Claude and Cursor
3. User settings (projects directory, plans directory, completion behavior)
4. Quality infrastructure prompts (port registry, scheduled tests, report viewer, profiling preferences)
5. Optionally walks your projects directory to set up each project

### Directory Structure After Setup

```
~/.agent-tools/                     # Centralized agent tools
├── .aec-managed                    # Marker file (identifies managed dirs)
├── rules/
│   ├── agents-environment-config/  # → repo/.agent-rules/ (no frontmatter)
│   └── [your rules here]
├── agents/
│   ├── agents-environment-config/  # → repo/.claude/agents/
│   └── [your agents here]
├── skills/
│   ├── agents-environment-config/  # → repo/.claude/skills/
│   └── [your skills here]
└── commands/
    ├── agents-environment-config/  # → repo/.cursor/commands/
    └── [your commands here]
```

**Agent-specific symlinks:**
- `~/.claude/agents/agents-environment-config` → `~/.agent-tools/agents/agents-environment-config`
- `~/.claude/skills/agents-environment-config` → `~/.agent-tools/skills/agents-environment-config`
- `~/.cursor/rules/agents-environment-config` → `repo/.cursor/rules/` (with frontmatter)

> **Note:** Cursor global commands (`~/.cursor/commands/`) are [not currently working](https://forum.cursor.com/t/commands-are-not-detected-in-the-global-cursor-directory/150967) due to a Cursor bug.

### Setting Up a New Project

Point `aec` at any project directory -- new or existing -- and it handles the rest.

```bash
# Using Python CLI (recommended)
aec setup my-new-project
aec setup /path/to/existing/project

# Or using shell script
./scripts/setup-repo.sh my-new-project
```

**Raycast users:** The same script exists at `raycast_scripts/setup-repo.sh` with Raycast metadata.

## Lint Hooks

AI agents write code fast, but they don't always check their work. AEC can install lint and type-check hooks that run after every file edit, so errors get caught the moment they're introduced -- not three prompts later.

**Supported languages:** TypeScript, Rust, Python, Go, Ruby

**Supported agents:** Claude Code, Gemini CLI, Cursor

During `aec setup`, AEC auto-detects your project's language and offers to install the appropriate hooks. Multi-language projects are supported — a TypeScript + Python monorepo gets both `tsc` and `mypy` hooks composed into a single config.

You control how hooks are handled:
- **Per-repo** (default): prompted each time, choose which languages to hook
- **Auto**: always install for detected languages
- **Never**: skip hook setup entirely

See [docs/users/lint-hooks.md](docs/users/lint-hooks.md) for details. To add support for more languages or agents, see [docs/contributors/adding-hook-support.md](docs/contributors/adding-hook-support.md).

### Hook Key Repair

Earlier versions of AEC wrote `.claude/settings.json` with camelCase hook keys (e.g., `postToolUse`) instead of the PascalCase keys Claude Code requires (`PostToolUse`). This causes Claude Code to reject the settings file on startup with an "Invalid key in record" error.

AEC automatically detects and fixes this issue in all tracked repos when you run:

```bash
aec install          # fixes all tracked repos during install
aec update && aec upgrade  # fixes all tracked repos during update
aec doctor           # reports which repos have the issue
```

No manual editing is needed -- the repair preserves all existing hook content and other settings in the file.

## Per-Project Configuration (`.aec.json`)

Each project can have an `.aec.json` file at its root that stores project-specific AEC configuration: port assignments, test suites, and installed tooling metadata. This file is created automatically during `aec setup`.

### Schema Overview

```json
{
  "$schema": "https://aec.bernier.dev/schema/aec.json",
  "version": "1.0.0",
  "project": {
    "name": "my-project",
    "description": "My project description"
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
    }
  },
  "test": {
    "suites": {
      "unit": { "command": "npm run test:unit", "cleanup": null },
      "integration": {
        "command": "npm run test:integration",
        "cleanup": "docker compose -f docker-compose.test.yml down"
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

### How It's Created

`aec setup` creates `.aec.json` automatically. It detects test frameworks, prompts for port assignments, and populates the `installed` section from the central manifest. You can also edit it manually.

### Gitignore Behavior

`.aec.json` is committed to git by default so all contributors benefit from the metadata. To gitignore it instead:

```bash
aec config set aec_json_gitignored true
```

When `aec_json_gitignored` is `true`, `aec setup` adds `.aec.json` to `.gitignore`. When `false`, it removes that entry if present.

### Sections

| Section | Purpose |
|---------|---------|
| `project` | Name and description (name defaults to directory name) |
| `ports` | Port assignments with protocol and description |
| `test` | Test suites, prerequisites, and scheduled run whitelist |
| `installed` | Local copy of installed skills/rules/agents (synced from central manifest) |

---

## Port Registry

When you manage multiple projects on one machine, port collisions are inevitable. Project A claims port 3000, project B also claims 3000, and you discover the conflict at runtime when a dev server fails to bind.

The port registry solves this with a central registry at `~/.agents-environment-config/ports-registry.json`. Ports are assigned first-come-first-served based on registration timestamp.

### How It Works

1. Each project declares its ports in `.aec.json` (see above)
2. During `aec setup`, ports are registered against the central registry
3. Conflicts are surfaced as warnings -- they do not block setup
4. You fix the `.aec.json` and re-register

### Commands

| Command | Description |
|---------|-------------|
| `aec ports list` | Show all registered ports across all projects, grouped by project |
| `aec ports check [path]` | Check for conflicts without registering (defaults to current directory) |
| `aec ports register [path]` | Register ports from `.aec.json` into the central registry |
| `aec ports unregister [path]` | Remove all port registrations for a project |
| `aec ports validate` | Find stale entries (project directories that no longer exist) |

### Conflict Resolution

Port conflicts warn but do not block. When a conflict is detected, AEC shows which project registered the port first and when:

```
⚠ Port conflict: port 3000 is already registered to "my-portfolio"
  (registered 2026-03-15T10:00:00Z)
  Your .aec.json assigns 3000 to "dev-server"
  → Update your .aec.json to use a different port, or run
    aec ports list to see all registered ports
```

Stale entries (from deleted project directories) are cleaned up automatically by `aec prune`.

---

## Test Framework Detection

During `aec setup`, AEC scans your project for test frameworks by checking for config files and parsing `package.json` / `pyproject.toml`.

### Supported Frameworks

| Framework | Language | Detection |
|-----------|----------|-----------|
| Jest | TypeScript, JavaScript | `jest.config.*`, `package.json` devDependencies |
| Vitest | TypeScript, JavaScript | `vitest.config.*`, `package.json` devDependencies |
| pytest | Python | `pytest.ini`, `conftest.py`, `pyproject.toml` |
| Playwright | TypeScript, JavaScript, Python | `playwright.config.*`, `package.json` devDependencies |
| Cargo Test | Rust | `Cargo.toml` |
| Go Test | Go | `go.mod` |
| RSpec | Ruby | `.rspec`, `spec/spec_helper.rb` |

### Interactive Suite Selection

After detection, `aec setup` presents the detected frameworks and any test scripts found in `package.json`, then lets you choose which to include in `.aec.json`:

```
Detected test frameworks:
  ✓ Jest (jest.config.ts)
  ✓ Playwright (playwright.config.ts)

Found test scripts in package.json:
  • test:unit → npm run test:unit
  • test:integration → npm run test:integration
  • test:e2e → npm run test:e2e

Which should be included in .aec.json test suites?
[x] test:unit
[x] test:integration
[ ] test:e2e
```

### Scheduled Whitelist

The `test.scheduled` array in `.aec.json` controls which suites run in automated scheduled runs. E2E suites that require browsers or heavy infrastructure can exist in `.aec.json` for documentation without being included in unattended runs. See [Test Runner](#test-runner) below for how scheduled runs work.

### Extensibility

Adding a new framework requires only adding a dict entry to `TEST_FRAMEWORK_HOOKS` in `aec/lib/test_detection.py`. No other code changes needed -- same pattern as `LANGUAGE_HOOKS` for lint hooks.

---

## Test Runner

The test runner executes test suites across your tracked projects, profiles resource usage, detects port and process leaks, and generates structured reports. It builds on the `.aec.json` test configuration from [Test Framework Detection](#test-framework-detection) above.

### `aec test` Commands

| Command | Scope | Description |
|---------|-------|-------------|
| `aec test run` | local | Run all suites from the current project's `.aec.json` |
| `aec test run -g` | global | Run scheduled suites across all tracked projects |
| `aec test schedule` | global | Interactive setup: pick run time, configure retention, register with OS scheduler |
| `aec test status` | local | Show this project's test config and last results |
| `aec test status -g` | global | Show schedule config, last run, next run |
| `aec test enable` | global | Re-enable scheduled runs (re-registers with OS scheduler) |
| `aec test disable` | global | Disable scheduled runs (removes OS scheduler registration, keeps config) |
| `aec test report` | local | Show this project's latest test results |
| `aec test report -g` | global | Open the full cross-project summary |
| `aec test detect` | local | Re-run test framework detection for the current project, update `.aec.json` |

**Local vs global scope:** `aec test run` (no `-g`) runs ALL suites in the current project, not just the `scheduled` ones, since the user is explicitly requesting a run. `aec test run -g` runs only the suites listed in `test.scheduled` across every tracked project.

### Examples

```bash
# Run all test suites for the current project
aec test run

# Run scheduled suites across all tracked projects
aec test run -g

# Set up automated daily test runs
aec test schedule

# Check this project's test configuration
aec test status

# Check global schedule and last run results
aec test status -g

# View latest results for this project
aec test report

# View latest cross-project summary
aec test report -g

# Re-detect test frameworks after adding a new one
aec test detect
```

---

## Scheduled Test Runs

Set up automated daily test runs with `aec test schedule`. The interactive flow prompts for:

1. Run time (default 02:00, 24h format)
2. Report retention settings
3. Profile retention settings

AEC registers the schedule with your OS-native scheduler:

| OS | Scheduler | Notes |
|----|-----------|-------|
| macOS | launchd | Runs missed jobs on wake (handles laptop sleep) |
| Linux | cron (user crontab) | Missed runs while off are skipped |
| Windows | Task Scheduler | Supports "wake to run" option |

### What Runs

Only suites listed in `test.scheduled` in each project's `.aec.json`. Projects without scheduled suites are skipped. Project execution order is randomized each run to expose cross-project contamination that deterministic ordering would mask.

### Where Reports Go

Reports are written to `~/.agents-environment-config/tests/{datetime}/`:

```
~/.agents-environment-config/
  tests/
    2026-04-08T02:00:00Z/
      summary.txt
      my-webapp_test_output.txt
      my-api_test_output.txt
```

### How to View Reports

```bash
# View latest results for the current project
aec test report

# View latest cross-project summary
aec test report -g
```

If `report_viewer` is configured (see [Report Viewers](#report-viewers)), the summary opens automatically in your preferred viewer after each run.

### Managing the Schedule

```bash
# Check schedule status
aec test status -g

# Temporarily disable without losing config
aec test disable

# Re-enable
aec test enable
```

The schedule configuration lives in `~/.agents-environment-config/scheduler-config.json`. You can edit it directly or use `aec test schedule` to reconfigure interactively.

---

## Test Profiling

Every test suite execution is profiled automatically. The runner captures resource snapshots before and after each suite to track performance trends and detect leaks.

### What's Profiled

| Metric | Description |
|--------|-------------|
| Duration | Wall-clock time for each suite |
| Memory | Peak memory usage during execution |
| Ports | Listening ports before and after (compared against port registry) |
| Docker containers | Containers started and remaining after cleanup |
| Process counts | Zombies, stuck I/O, node/test processes before and after |

### Where Profiles Are Stored

Profile data lives at `~/.agents-environment-config/profiles/{project}/`:

```
~/.agents-environment-config/
  profiles/
    my-webapp/
      2026-04-08T02:00:00Z.json
      2026-04-07T02:00:00Z.json
    my-api/
      2026-04-08T02:00:00Z.json
```

Profile data has its own retention setting (`profile_retention_days`, default 90 days), separate from test report retention (default 30 days). Profiles stick around longer because they're used for parallelization analysis and trend detection.

### Port Discovery

Port observations happen during every suite execution, regardless of whether the port registry is enabled:

- **Port registry ON:** Unregistered ports that appear during tests are surfaced in the report with a suggestion to register them in `.aec.json`.
- **Port registry OFF:** Observed ports are cross-referenced across all projects. Overlapping ports are flagged as potential problems for parallel development.

### Process Leak Detection

The runner takes before/after process snapshots for each suite. Only increases are reported -- decreases are just cleanup working correctly. Leaked processes are logged with PID, command, and elapsed time for debugging.

The runner never kills anything. If leaks are detected, you can:
- Fix cleanup commands in `.aec.json`
- Run `scripts/cleanup-hung-processes.sh` manually
- Ignore harmless leaks

---

## Smart Parallelization

By default, projects run sequentially in randomized order. After enough profiling data accumulates, the runner suggests parallel lane groupings.

### How It Works

1. **Sequential first.** The runner profiles each project's resource usage over multiple runs.
2. **After 3 runs**, the runner analyzes profiles to compute lane groupings where no two projects in the same lane share ports, both use Docker heavily, or would exceed memory limits together.
3. **Suggestion in report.** The proposed lanes appear in the test summary:
   ```
   Suggested lanes based on port/resource analysis:
     Lane 1: my-api, my-portfolio (no shared ports, low memory)
     Lane 2: my-webapp, my-service (no shared ports, both use docker)
   Enable with: aec config set parallel_enabled true
   ```
4. **User opts in.** Parallelization is never automatic:
   ```bash
   aec config set parallel_enabled true
   ```
5. **Lanes run concurrently.** Projects within the same lane still run sequentially to avoid resource conflicts.

---

## Test Prerequisites

Prerequisites gate test execution. They exist at two levels in `.aec.json`:

### Project-Level Prerequisites

If any project-level prerequisite fails, ALL suites for that project are skipped.

```json
{
  "test": {
    "prerequisites": ["docker"],
    "suites": { ... }
  }
}
```

### Per-Suite Prerequisites

Suite-level prerequisites are checked individually. A failed prerequisite skips only that suite -- other suites still run.

```json
{
  "test": {
    "suites": {
      "unit": { "command": "npm run test:unit" },
      "integration": {
        "command": "npm run test:integration",
        "cleanup": "docker compose -f docker-compose.test.yml down",
        "prerequisites": ["docker"]
      }
    }
  }
}
```

In this example, `unit` runs regardless of Docker availability, while `integration` is skipped if Docker isn't present. Prerequisites are checked via `shutil.which()` or service-specific checks (e.g., `docker info`).

---

## Report Viewers

After scheduled test runs, AEC can automatically open the report in your preferred viewer. You configure this during `aec install` when opting into scheduled tests, or anytime with `aec config set report_viewer <key>`.

### Available Viewers by OS

**macOS:**

| Key | Viewer | Command |
|-----|--------|---------|
| `cursor` | Cursor | `cursor {file}` |
| `vscode` | VS Code | `code {file}` |
| `open` | Default App | `open {file}` |
| `nano` | nano | `nano {file}` |
| `vim` | vim | `vim {file}` |

**Linux:**

| Key | Viewer | Command |
|-----|--------|---------|
| `vscode` | VS Code | `code {file}` |
| `xdg` | Default App | `xdg-open {file}` |
| `nano` | nano | `nano {file}` |
| `vim` | vim | `vim {file}` |

**Windows:**

| Key | Viewer | Command |
|-----|--------|---------|
| `vscode` | VS Code | `code {file}` |
| `notepad` | Notepad | `notepad {file}` |
| `start` | Default App | `start {file}` |

### Custom Command

Select "Other" during the interactive prompt to enter a custom command. Include `{file}` as a placeholder for the report path:

```bash
aec config set report_viewer "my-editor {file}"
```

---

## Configuration Settings

### Quality Infrastructure Settings

These settings are prompted during `aec install` and manageable via `aec config set <key> <value>`:

| Setting | Default | Description |
|---------|---------|-------------|
| `aec_json_gitignored` | `false` | Whether `.aec.json` is added to `.gitignore` during setup |
| `port_registry_enabled` | prompted | Whether the port registry is active |
| `scheduled_tests_enabled` | prompted | Whether scheduled test runs are enabled (wired in Phase 2/3) |
| `report_viewer` | prompted | Key for the report viewer command, or `null` for no auto-open |
| `report_retention_mode` | prompted | `auto` (prune after N days) or `manual` |
| `report_retention_days` | `30` | Days to keep reports (only used when `report_retention_mode` is `auto`) |
| `profile_retention_days` | `90` | Days to keep profile data in `profiles/` (separate from report retention) |
| `parallel_enabled` | `false` | Enable parallel lane execution (opt in after reviewing suggested lanes) |

---

## The `aec` CLI

All operations are available through the `aec` command, which works on macOS, Linux, and Windows.

### Installation

```bash
# From the repo directory
pip install -e .

# Or without cloning (coming soon)
# pip install aec
```

### Commands

| Command | Description |
|---------|-------------|
| `aec install` | Full setup (submodules, rules, agent-tools, settings, quality infra prompts, project walk) |
| `aec update` | Fetch latest sources |
| `aec upgrade` | Apply available upgrades |
| `aec install <type> <name>` | Install a skill, rule, or agent |
| `aec uninstall <type> <name>` | Remove an installed item |
| `aec list` | Show installed items |
| `aec search <term>` | Search available items |
| `aec outdated` | Show what has upgrades available |
| `aec info <type> <name>` | Show detailed metadata for an item |
| `aec setup [path]` | Track a project (agent files, `.aec.json`, port registration, test detection) |
| `aec setup --all` | Track all projects in configured projects directory |
| `aec untrack <path>` | Stop tracking a project |
| `aec config list` | Show current preferences and settings |
| `aec config set <key> <value>` | Set a preference |
| `aec config reset <key>` | Reset a preference (re-prompts on next run) |
| `aec generate rules` | Generate .agent-rules/ from .cursor/rules/ |
| `aec generate files` | Regenerate agent instruction files from templates |
| `aec validate` | Validate rule parity |
| `aec prune` | Remove stale tracking entries |
| `aec discover` | Find repos from Raycast scripts |
| `aec doctor` | Health check for installation |
| `aec version` | Show version |
| `aec ports list` | Show all registered ports across all projects |
| `aec ports check [path]` | Check for port conflicts without registering |
| `aec ports register [path]` | Register ports from `.aec.json` |
| `aec ports unregister [path]` | Remove port registrations for a project |
| `aec ports validate` | Find stale port registry entries |
| `aec test run` | Run test suites for the current project |
| `aec test run -g` | Run scheduled suites across all tracked projects |
| `aec test schedule` | Interactive setup for automated daily test runs |
| `aec test status [-g]` | Show test config (local) or schedule status (global) |
| `aec test enable` | Enable scheduled test runs |
| `aec test disable` | Disable scheduled test runs |
| `aec test report [-g]` | View latest test results (local) or full summary (global) |
| `aec test detect` | Re-run test framework detection, update `.aec.json` |

### Examples

```bash
# Check installation health
aec doctor

# Setup a new project (creates .aec.json, detects tests, registers ports)
aec setup my-app

# List installed items
aec list

# Fetch latest and apply upgrades
aec update && aec upgrade

# Validate rules are in sync
aec validate

# View all registered ports
aec ports list

# Check for port conflicts before registering
aec ports check /path/to/project
```

### Windows Support

On Windows, the CLI uses NTFS junctions (no admin required) instead of symlinks for directories.

## Repository Structure

```
agents-environment-config/          # THIS IS A TEMPLATE - don't add project-specific content!
├── aec/                            # Python CLI package (aec)
│   ├── commands/                   # CLI command implementations
│   └── lib/                        # Shared utilities
├── .agent-rules/                   # Rules WITHOUT Cursor frontmatter (generated)
│   ├── frameworks/testing/standards.md
│   └── ...                         # Mirrors .cursor/rules/ structure
├── .claude/
│   ├── agents/                     # Agent definitions (git submodule)
│   └── skills/                     # Skill definitions (git submodule)
├── .cursor/
│   ├── commands/                   # Cursor command wrappers
│   └── rules/                      # Cursor rules WITH frontmatter (source of truth)
├── scripts/
│   ├── setup.sh                    # Install this repo to your system
│   ├── setup-agent-tools.sh        # Create ~/.agent-tools/ structure
│   ├── migrate-to-agent-tools.sh   # Migrate existing users to new structure
│   ├── rollback-agent-tools.sh     # Rollback migration if needed
│   ├── setup-repo.sh               # Set up a NEW project with agent files
│   ├── cleanup-hung-processes.sh   # Kill hung processes + Docker cleanup (macOS/Linux)
│   ├── cleanup-hung-processes.ps1  # Same, for Windows (PowerShell)
│   ├── generate-agent-files.py     # Regenerate CLAUDE.md etc from rules
│   ├── generate-agent-rules.py     # Generate .agent-rules/ from .cursor/rules/
│   ├── validate-rule-parity.py     # Pre-commit validation for rule parity
│   └── git-hooks/                  # Git hooks for this repo
├── raycast_scripts/
│   ├── setup-repo.sh               # Raycast version of setup-repo
│   ├── cleanup-hung-processes.sh   # Raycast version (calls scripts/)
│   └── *.sh                        # Project launcher scripts
├── templates/                      # Canonical templates (copied to projects)
│   ├── AGENTINFO.md                # TEMPLATE - gets filled in per-project
│   ├── CLAUDE.md                   # TEMPLATE - references .agent-rules/
│   ├── AGENTS.md                   # TEMPLATE - for Codex (references .agent-rules/)
│   ├── GEMINI.md                   # TEMPLATE - for Gemini (references .agent-rules/)
│   ├── QWEN.md                     # TEMPLATE - for Qwen (references .agent-rules/)
│   └── .cursor/rules/CURSOR.mdc   # TEMPLATE - for Cursor
├── agents.json                     # Single source of truth for agent definitions
└── README.md                       # This file
```

## Rules Architecture

The core problem: Cursor needs YAML frontmatter in its rule files, but every other agent treats that frontmatter as noise. AEC maintains both formats from a single source.

### Two Rule Formats

| Directory | Format | Used By |
|-----------|--------|---------|
| `.cursor/rules/*.mdc` | Cursor format (WITH YAML frontmatter) | Cursor IDE |
| `.agent-rules/*.md` | Standard markdown (NO frontmatter) | Claude, Codex, Gemini, Qwen |

### Why Two Formats?

- **Cursor** requires YAML frontmatter (`description`, `globs`, `alwaysApply`, `tags`) for rule discovery
- **Other agents** don't understand Cursor frontmatter and waste tokens parsing it
- `.agent-rules/` saves ~5% tokens per rule and avoids polluting non-Cursor agents

### Keeping Rules in Sync

A pre-commit hook validates parity between `.cursor/rules/` and `.agent-rules/`:

```bash
# Generate .agent-rules/ from .cursor/rules/ (strips frontmatter)
python3 scripts/generate-agent-rules.py

# Validate parity (runs in pre-commit hook)
python3 scripts/validate-rule-parity.py
```

## Scripts

Most operations are available via both the Python CLI and shell scripts:

| Operation | Python CLI | Shell Script |
|-----------|------------|--------------|
| Full setup | `aec install` | `scripts/setup.sh` |
| Fetch latest sources | `aec update` | — |
| Apply upgrades | `aec upgrade` | — |
| Setup a project | `aec setup <path>` | `scripts/setup-repo.sh` |
| Setup all projects | `aec setup --all` | — |
| List installed items | `aec list` | — |
| Manage preferences | `aec config list\|set\|reset` | — |
| Manage ports | `aec ports list\|check\|register\|unregister\|validate` | — |
| Generate agent files | `aec generate files` | `scripts/generate-agent-files.py` |
| Generate .agent-rules/ | `aec generate rules` | `scripts/generate-agent-rules.py` |
| Validate rule parity | `aec validate` | `scripts/validate-rule-parity.py` |
| Run project tests | `aec test run` | — |
| Run all scheduled tests | `aec test run -g` | — |
| Schedule test runs | `aec test schedule` | — |
| View test reports | `aec test report [-g]` | — |
| Health check | `aec doctor` | — |
| Install git hooks | — | `scripts/install-git-hooks.sh` |
| Cleanup hung processes | — | `scripts/cleanup-hung-processes.sh` (macOS/Linux) or `scripts/cleanup-hung-processes.ps1` (Windows) |

### Cleanup Hung Processes

Kills hung/unresponsive development processes (vitest, jest, stale build tools) and runs Docker cleanup. Only terminates processes that are actually hung (e.g., running >10 min for test runners, >30 min for build tools), not active ones.

| Platform | Script | Notes |
|----------|--------|-------|
| macOS / Linux | `scripts/cleanup-hung-processes.sh` | Also available via Raycast: `raycast_scripts/cleanup-hung-processes.sh` |
| Windows | `scripts/cleanup-hung-processes.ps1` | Run in PowerShell: `pwsh -File scripts/cleanup-hung-processes.ps1` |

Both scripts include timeouts on Docker commands to prevent hangs when the Docker daemon is slow or unresponsive.

### Script Parity

Scripts in `scripts/` and `raycast_scripts/` must stay in sync. A pre-commit hook validates:
- `setup-repo.sh` and `cleanup-hung-processes.sh` exist in both directories
- AGENTINFO.md remains a template (not project-specific)
- `.agent-rules/` parity with `.cursor/rules/`

To install the git hooks:

```bash
./scripts/install-git-hooks.sh
```

## Raycast Integration

During project setup (`aec setup` or `scripts/setup-repo.sh`), users are prompted to generate [Raycast](https://raycast.com/) launcher scripts. These scripts provide one-keystroke access to open a project in any detected agent.

Scripts are generated per-agent based on what is installed on the machine. The setup detects all [supported agents](#supported-agents) (Claude, Cursor, Gemini, Qwen, Codex) and generates scripts for each one found.

| Script Pattern | Example | Purpose |
|----------------|---------|---------|
| `{agent}-{project}.sh` | `cursor-my-app.sh` | Open project in the agent |
| `claude-{project}-resume.sh` | `claude-my-app-resume.sh` | Resume last Claude session |

The generated scripts include Raycast metadata (`@raycast.schemaVersion`, `@raycast.title`, etc.) so they appear in the Raycast command palette automatically.

To skip Raycast script generation during setup, pass `--skip-raycast` (Python CLI) or answer "N" at the prompt (shell script).

### Discovering Existing Repos from Scripts

If you have existing Raycast scripts from before tracking was added, use `aec discover` to retroactively populate the tracking log:

```bash
aec discover              # Interactive - shows what was found, asks to add
aec discover --dry-run    # Preview without making changes
aec discover --auto       # Auto-add all discovered paths
```

## Local Configuration Directory

AEC tracks which projects you've set up and your preferences in `~/.agents-environment-config/`:

```
~/.agents-environment-config/
├── README.md                    # Explains why this directory exists
├── preferences.json             # User settings and optional feature toggles
├── ports-registry.json          # Central port registry (all projects)
├── scheduler-config.json        # Test schedule, execution, and retention config
├── runner.py                    # Generic test runner script
├── setup-repo-locations.txt     # Tracks projects set up with agent files
├── tests/                       # Test reports (one directory per run)
│   └── {datetime}/
│       ├── summary.txt
│       └── {project}_test_output.txt
└── profiles/                    # Profile data (one directory per project)
    └── {project}/
        └── {datetime}.json
```

`preferences.json` stores:
- **Settings**: Projects root directory, plans directory name, git tracking preference, plan completion behavior (archive/delete)
- **Quality infrastructure**: Port registry toggle, scheduled test toggle, report viewer, retention settings, profile retention, parallelization
- **Optional rules**: Feature toggles like "Leave It Better"

This directory enables:
- **Cascading updates**: Update all tracked projects at once
- **Re-run detection**: Detects if a project was already set up
- **Inventory**: List all configured projects
- **Consistent settings**: Plans directory and completion behavior applied across all projects
- **Port conflict detection**: Central registry prevents port collisions across projects

```bash
# List installed items
aec list

# Fetch latest and apply upgrades
aec update && aec upgrade

# Preview updates without making changes
aec update --dry-run
```

## Migration for Existing Users

If you already have symlinks from a previous setup:

```bash
# Preview changes (dry run)
aec install --dry-run

# Run full setup (handles migration automatically)
aec install
```

## How Projects Use This

Each project gets its own copy of the agent instruction files, configured to pull rules from the shared `~/.agent-tools/` directory. This means your standards stay centralized while each project can still define its own specifics in `AGENTINFO.md`.

When you run `aec setup` (or `setup-repo.sh`) on a project, it:

1. Creates directories: `.cursor/rules/`, `docs/`, and your configured plans directory (default: `.plans/`)
2. Copies template files from `templates/`: `AGENTINFO.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md`
3. Copies `CURSOR.mdc` to `.cursor/rules/`
4. Migrates legacy plan files from `plans/` or `docs/plans/` to your configured plans directory
5. Detects project languages and installs lint hooks for supported agents
6. Creates or updates `.aec.json` with project metadata, detected test suites, and installed tooling
7. Registers the project's ports against the central port registry (warns on conflicts)
8. Updates `.gitignore` to ignore agent files (and plans directory if configured)
9. Optionally creates Raycast launcher scripts

**After setup, edit `AGENTINFO.md`** in the target project with project-specific info.

### Batch Project Setup

If you have a directory full of projects, you don't have to set them up one at a time. During `aec install` (or anytime with `aec setup --all`), AEC walks your projects directory and sets up each one:

```bash
# During install, you'll be prompted automatically
aec install

# Or run standalone
aec setup --all
```

## Updating Rules

When cursor rules in `.cursor/rules/` change:

```bash
# Regenerate the agent-agnostic rules
aec generate rules

# Regenerate the agent instruction files (from templates/)
aec generate files

# Commit the changes
git add .agent-rules/ templates/
git commit -m "chore: regenerate agent rules and files"
```

## Updating Submodules

```bash
git submodule update --remote --recursive
```

## File Purposes

| File | Purpose | Edit In Project? |
|------|---------|------------------|
| `AGENTINFO.md` | Project-specific info | **YES** - Fill this in! |
| `CLAUDE.md` | Rule references for Claude | No - regenerated |
| `AGENTS.md` | Rule references for Codex | No - regenerated |
| `.cursor/rules/*.mdc` | Development standards (Cursor) | No - shared across projects |
| `.agent-rules/*.md` | Development standards (other agents) | No - generated from .cursor/rules/ |

## Trade-offs

Nothing is free. Here's what you're signing up for:

| Benefit | Cost |
|---------|------|
| Consistent rules across all agents | Maintain two file versions (.mdc and .md) |
| ~5% token savings per rule | Pre-commit hook validation overhead |
| No Cursor pollution for non-Cursor users | Slightly more complex setup |
| User extension points in ~/.agent-tools/ | Directory structure learning curve |

## Security Notes

- Never commit `.env` files
- API keys go in `.env` (copy from `.env.template`)
- Review API key permissions - use least-privilege access

## Related Repositories

- [agency-agents](https://github.com/bernierllc/agency-agents) - Agent definitions
- [skills](https://github.com/bernierllc/skills) - Skill definitions
