# Agents Environment Configuration

> **This is a TEMPLATE repository.** It provides shared AI agent configurations that get copied to other projects. Do not add project-specific content here.

## What This Repo Is

This repository contains:
- **Shared cursor rules** (`.cursor/rules/`) - Development standards for all projects (Cursor format with frontmatter)
- **Agent-agnostic rules** (`.agent-rules/`) - Same rules without Cursor frontmatter for non-Cursor agents
- **Agent instruction files** (`CLAUDE.md`, `AGENTS.md`, etc.) - Templates for AI assistants
- **Setup scripts** - Tools to configure new projects with these standards
- **Submodules** for agents and skills (`bernierllc/agency-agents`, `bernierllc/skills`)

## Supported Agents

| Agent | Instruction File | Detection | Description |
|-------|------------------|-----------|-------------|
| Claude Code | `CLAUDE.md` | `claude` command or `~/.claude` | Anthropic's CLI coding agent |
| Cursor | `.cursor/rules/*.mdc` | `cursor` command or `/Applications/Cursor.app` | AI-first IDE with Cursor rules |
| Codex | `AGENTS.md` | `codex` command | OpenAI's coding agent |
| Gemini CLI | `GEMINI.md` | `gemini` command | Google's CLI coding agent |
| Qwen Code | `QWEN.md` | `qwen` command | Alibaba's coding agent |

All non-Cursor agents use `.agent-rules/*.md` (standard markdown, no frontmatter). Cursor uses `.cursor/rules/*.mdc` (with YAML frontmatter). See [Rules Architecture](#rules-architecture) for details.

All agent definitions live in [`agents.json`](agents.json) at the repo root. This is the single source of truth -- Python config, shell config, file lists, and detection logic are all derived from it.

Want to add support for another agent? See the [Adding Agent Support](docs/adding-agent-support.md) guide -- it's just one JSON entry + two commands.

## Quick Start

### Setting Up This Repo (One Time)

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config

# Install the CLI (one time)
pip install -e .

# Run setup
aec install
```

Or using shell scripts (macOS/Linux only):
```bash
./scripts/setup.sh
```

This creates:
1. `~/.agent-tools/` - Centralized directory for rules, agents, skills, and commands
2. Agent-specific symlinks for Claude and Cursor
3. Optional Claude Code statusline

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

```bash
# Using Python CLI (recommended)
aec repo setup my-new-project
aec repo setup /path/to/existing/project

# Or using shell script
./scripts/setup-repo.sh my-new-project
```

This copies agent files and creates directories in the target project.

**Raycast users:** The same script exists at `raycast_scripts/setup-repo.sh` with Raycast metadata.

## Python CLI

The `aec` CLI provides cross-platform support (macOS, Linux, Windows).

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
| `aec install` | Full setup (submodules, rules, agent-tools) |
| `aec doctor` | Health check for installation |
| `aec version` | Show version |
| `aec repo setup <path>` | Setup a project with agent files |
| `aec repo list` | List tracked repositories |
| `aec repo update [--all]` | Update repositories |
| `aec agent-tools setup` | Create ~/.agent-tools/ structure |
| `aec agent-tools migrate` | Migrate from old symlink structure |
| `aec agent-tools rollback <backup>` | Rollback migration |
| `aec discover` | Discover repos from existing Raycast scripts |
| `aec rules generate` | Generate .agent-rules/ from .cursor/rules/ |
| `aec rules validate` | Validate rule parity |

### Examples

```bash
# Check installation health
aec doctor

# Setup a new project
aec repo setup my-app

# List all tracked projects
aec repo list

# Update all tracked projects
aec repo update --all

# Validate rules are in sync
aec rules validate
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
├── agents.json                     # Single source of truth for agent definitions
├── AGENTINFO.md                    # TEMPLATE - gets filled in per-project
├── CLAUDE.md                       # TEMPLATE - references .agent-rules/
├── AGENTS.md                       # TEMPLATE - for Codex (references .agent-rules/)
├── GEMINI.md                       # TEMPLATE - for Gemini (references .agent-rules/)
├── QWEN.md                         # TEMPLATE - for Qwen (references .agent-rules/)
└── README.md                       # This file
```

## Rules Architecture

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
| Create ~/.agent-tools/ | `aec agent-tools setup` | `scripts/setup-agent-tools.sh` |
| Migrate existing setup | `aec agent-tools migrate` | `scripts/migrate-to-agent-tools.sh` |
| Rollback migration | `aec agent-tools rollback <dir>` | `scripts/rollback-agent-tools.sh` |
| Setup a project | `aec repo setup <path>` | `scripts/setup-repo.sh` |
| List tracked projects | `aec repo list` | `scripts/setup-repo.sh --list` |
| Generate .agent-rules/ | `aec rules generate` | `scripts/generate-agent-rules.py` |
| Validate rule parity | `aec rules validate` | `scripts/validate-rule-parity.py` |
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

During project setup (`aec repo setup` or `scripts/setup-repo.sh`), users are prompted to generate [Raycast](https://raycast.com/) launcher scripts. These scripts provide one-keystroke access to open a project in any detected agent.

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

The scripts create a `~/.agents-environment-config/` directory to store local state:

```
~/.agents-environment-config/
├── README.md                    # Explains why this directory exists
└── setup-repo-locations.txt     # Tracks projects set up with agent files
```

This directory enables:
- **Cascading updates**: Update all tracked projects at once
- **Re-run detection**: Detects if a project was already set up
- **Inventory**: List all configured projects

```bash
# List all tracked projects
aec repo list

# Update all tracked projects
aec repo update --all

# Preview updates without making changes
aec repo update --all --dry-run
```

## Migration for Existing Users

If you already have symlinks from a previous setup:

```bash
# Preview changes (dry run)
aec agent-tools migrate --dry-run

# Run migration (creates backup automatically)
aec agent-tools migrate

# Rollback if needed
aec agent-tools rollback ~/.agent-tools-backup-TIMESTAMP
```

## How Projects Use This

When you run `setup-repo.sh` on a project, it:

1. Creates directories: `.cursor/rules/`, `docs/`, `plans/`
2. Copies template files: `AGENTINFO.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md`
3. Copies `CURSOR.mdc` to `.cursor/rules/`
4. Updates `.gitignore` to ignore agent files
5. Optionally creates Raycast launcher scripts

**After setup, edit `AGENTINFO.md`** in the target project with project-specific info.

## Updating Rules

When cursor rules in `.cursor/rules/` change:

```bash
# Regenerate the agent-agnostic rules
aec rules generate

# Regenerate the agent instruction files
python3 scripts/generate-agent-files.py

# Commit the changes
git add .agent-rules/ CLAUDE.md AGENTS.md GEMINI.md QWEN.md
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
