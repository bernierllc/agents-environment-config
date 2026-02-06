# Agents Environment Configuration

> **This is a TEMPLATE repository.** It provides shared AI agent configurations that get copied to other projects. Do not add project-specific content here.

## What This Repo Is

This repository contains:
- **Shared cursor rules** (`.cursor/rules/`) - Development standards for all projects (Cursor format with frontmatter)
- **Agent-agnostic rules** (`.agent-rules/`) - Same rules without Cursor frontmatter for non-Cursor agents
- **Agent instruction files** (`CLAUDE.md`, `AGENTS.md`, etc.) - Templates for AI assistants
- **Setup scripts** - Tools to configure new projects with these standards
- **Submodules** for agents and skills (`bernierllc/agency-agents`, `bernierllc/skills`)

## Quick Start

### Setting Up This Repo (One Time)

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config

# Option 1: Python CLI (recommended, cross-platform)
python -m aec install

# Option 2: Shell script (macOS/Linux only)
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
python -m aec repo setup my-new-project
python -m aec repo setup /path/to/existing/project

# Or using shell script
./scripts/setup-repo.sh my-new-project
```

This copies agent files and creates directories in the target project.

**Raycast users:** The same script exists at `raycast_scripts/setup-repo.sh` with Raycast metadata.

## Python CLI

The `python -m aec` CLI provides cross-platform support (macOS, Linux, Windows).

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
| `aec rules generate` | Generate .agent-rules/ from .cursor/rules/ |
| `aec rules validate` | Validate rule parity |

### Examples

```bash
# Check installation health
python -m aec doctor

# Setup a new project
python -m aec repo setup my-app

# List all tracked projects
python -m aec repo list

# Update all tracked projects
python -m aec repo update --all

# Validate rules are in sync
python -m aec rules validate
```

### Windows Support

On Windows, the CLI uses NTFS junctions (no admin required) instead of symlinks for directories.

## Repository Structure

```
agents-environment-config/          # THIS IS A TEMPLATE - don't add project-specific content!
├── aec/                            # Python CLI package (python -m aec)
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
│   ├── generate-agent-files.py     # Regenerate CLAUDE.md etc from rules
│   ├── generate-agent-rules.py     # Generate .agent-rules/ from .cursor/rules/
│   ├── validate-rule-parity.py     # Pre-commit validation for rule parity
│   └── git-hooks/                  # Git hooks for this repo
├── raycast_scripts/
│   ├── setup-repo.sh               # Raycast version of setup-repo
│   └── *.sh                        # Project launcher scripts
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
| Full setup | `python -m aec install` | `scripts/setup.sh` |
| Create ~/.agent-tools/ | `python -m aec agent-tools setup` | `scripts/setup-agent-tools.sh` |
| Migrate existing setup | `python -m aec agent-tools migrate` | `scripts/migrate-to-agent-tools.sh` |
| Rollback migration | `python -m aec agent-tools rollback <dir>` | `scripts/rollback-agent-tools.sh` |
| Setup a project | `python -m aec repo setup <path>` | `scripts/setup-repo.sh` |
| List tracked projects | `python -m aec repo list` | `scripts/setup-repo.sh --list` |
| Generate .agent-rules/ | `python -m aec rules generate` | `scripts/generate-agent-rules.py` |
| Validate rule parity | `python -m aec rules validate` | `scripts/validate-rule-parity.py` |
| Health check | `python -m aec doctor` | — |
| Install git hooks | — | `scripts/install-git-hooks.sh` |

### Script Parity

Scripts in `scripts/` and `raycast_scripts/` must stay in sync. A pre-commit hook validates:
- `setup-repo.sh` exists in both directories
- AGENTINFO.md remains a template (not project-specific)
- `.agent-rules/` parity with `.cursor/rules/`

To install the git hooks:

```bash
./scripts/install-git-hooks.sh
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
python -m aec repo list

# Update all tracked projects
python -m aec repo update --all

# Preview updates without making changes
python -m aec repo update --all --dry-run
```

## Migration for Existing Users

If you already have symlinks from a previous setup:

```bash
# Preview changes (dry run)
python -m aec agent-tools migrate --dry-run

# Run migration (creates backup automatically)
python -m aec agent-tools migrate

# Rollback if needed
python -m aec agent-tools rollback ~/.agent-tools-backup-TIMESTAMP
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
python -m aec rules generate

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
