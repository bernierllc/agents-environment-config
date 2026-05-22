# `aec` CLI reference

All operations are available through the `aec` command, which works on macOS, Linux, and Windows.

## Installation

```bash
# From the repo directory
pip install -e .

# Or without cloning (coming soon)
# pip install aec
```

On Windows, the CLI uses NTFS junctions (no admin required) instead of symlinks for directories.

## Commands

### Setup & lifecycle

| Command | Description |
|---------|-------------|
| `aec install` | Full setup (submodules, rules, agent-tools, settings, quality infra prompts, project walk) |
| `aec install <type> <name>` | Install a skill, rule, or agent (see [Catalog](catalog.md)) |
| `aec update` | Fetch latest sources |
| `aec upgrade` | Apply available upgrades |
| `aec uninstall <type> <name>` | Remove an installed item |
| `aec doctor` | Health check for installation |
| `aec version` | Show version |
| `aec prune` | Remove stale tracking entries |
| `aec export` | Write the current setup to a portable manifest file |
| `aec apply <file>` | Reproduce a setup from a portable manifest file |

### Catalog

| Command | Description |
|---------|-------------|
| `aec list` | Show installed items |
| `aec search <term>` | Search available items |
| `aec outdated` | Show what has upgrades available |
| `aec info <type> <name>` | Show detailed metadata for an item |

### Projects

| Command | Description |
|---------|-------------|
| `aec setup [path]` | Track a project (agent files, `.aec.json`, port registration, test detection) |
| `aec setup --all` | Track all projects in configured projects directory |
| `aec untrack <path>` | Stop tracking a project |
| `aec discover-repos` | Find repos from Raycast scripts |

### Configuration

| Command | Description |
|---------|-------------|
| `aec config list` | Show current preferences and settings |
| `aec config set <key> <value>` | Set a preference |
| `aec config reset <key>` | Reset a preference (re-prompts on next run) |

### Generation & validation

| Command | Description |
|---------|-------------|
| `aec generate rules` | Generate `.agent-rules/` from `.cursor/rules/` |
| `aec generate files` | Regenerate agent instruction files from templates |
| `aec validate` | Validate rule parity |

### Discovery

| Command | Description |
|---------|-------------|
| `aec discover` | Scan for local items matching AEC catalog |
| `aec discover -g` | Scan global `~/.claude/` for items matching AEC catalog |
| `aec discover --depth 1\|2\|3` | Set scan depth (Quick/Normal/Deep) |
| `aec discover --rediscover` | Re-surface previously dismissed items |

See [Discovery](discovery.md) for details.

### Ports

| Command | Description |
|---------|-------------|
| `aec ports list` | Show all registered ports across all projects |
| `aec ports check [path]` | Check for port conflicts without registering |
| `aec ports register [path]` | Register ports from `.aec.json` |
| `aec ports unregister [path]` | Remove port registrations for a project |
| `aec ports validate` | Find stale port registry entries |

See [Port registry](ports.md) for details.

### Tests

| Command | Description |
|---------|-------------|
| `aec test run` | Run test suites for the current project |
| `aec test run -g` | Run scheduled suites across all tracked projects |
| `aec test schedule` | Interactive setup for automated daily test runs |
| `aec test status [-g]` | Show test config (local) or schedule status (global) |
| `aec test enable` | Enable scheduled test runs |
| `aec test disable` | Disable scheduled test runs |
| `aec test report [-g]` | View latest test results (local) or full summary (global) |
| `aec test detect` | Re-run test framework detection, update `.aec.json` |

See [Test runner & scheduler](test-runner.md) for details.

## Examples

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

## Portable setup across machines

`aec export` captures everything you have installed — skills, rules, agents, and
MCP servers, in both global and per-repo scope — into a single, hand-editable
manifest file. `aec apply` reads that file on another machine and installs the
same set, so your setup is reproducible everywhere.

The manifest is machine-independent: absolute paths, content hashes, and
timestamps are stripped, and project paths are stored as portable tokens (e.g.
`${PROJECTS}/my-app`) that resolve to the right location on each machine.

```bash
# On machine 1 — capture your current setup
aec export --out my-setup.aec.json

# Move the file to machine 2 (commit it, scp it, etc.), then:
aec apply my-setup.aec.json --dry-run   # preview the plan, change nothing
aec apply my-setup.aec.json             # install everything in the manifest
```

| Flag | Applies to | Description |
|------|------------|-------------|
| `--out`, `-o <file>` | `export` | Write to a file instead of stdout |
| `--latest` | `export`, `apply` | Track/install the latest catalog version instead of the pinned one |
| `--no-repos` | `export` | Export global-scope items only |
| `--dry-run` | `apply` | Print the install plan without making changes |

`apply` is idempotent — items already installed at the requested version are
left untouched, so it is safe to re-run.

## Scripts vs CLI

Most operations are available through both the Python CLI and shell scripts:

| Operation | Python CLI | Shell script |
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
| Generate `.agent-rules/` | `aec generate rules` | `scripts/generate-agent-rules.py` |
| Validate rule parity | `aec validate` | `scripts/validate-rule-parity.py` |
| Run project tests | `aec test run` | — |
| Run all scheduled tests | `aec test run -g` | — |
| Schedule test runs | `aec test schedule` | — |
| View test reports | `aec test report [-g]` | — |
| Discover matching items | `aec discover` | — |
| Discover repos from scripts | `aec discover-repos` | — |
| Health check | `aec doctor` | — |
| Install git hooks | — | `scripts/install-git-hooks.sh` |
| Cleanup hung processes | — | `scripts/cleanup-hung-processes.sh` (macOS/Linux) or `scripts/cleanup-hung-processes.ps1` (Windows) |
