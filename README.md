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
- `~/.cursor/commands/agents-environment-config` → `~/.agent-tools/commands/agents-environment-config`

### Setting Up a New Project

```bash
# Interactive mode
./scripts/setup-repo.sh

# Or direct mode
./scripts/setup-repo.sh my-new-project
./scripts/setup-repo.sh /path/to/existing/project
```

This copies agent files and creates directories in the target project.

**Raycast users:** The same script exists at `raycast_scripts/setup-repo.sh` with Raycast metadata.

## Repository Structure

```
agents-environment-config/          # THIS IS A TEMPLATE - don't add project-specific content!
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

| Script | Purpose |
|--------|---------|
| `scripts/setup.sh` | Full setup: submodules, .agent-rules/, ~/.agent-tools/ |
| `scripts/setup-agent-tools.sh` | Create ~/.agent-tools/ structure and symlinks |
| `scripts/init-aec-home.sh` | Initialize ~/.agents-environment-config/ (sourced by other scripts) |
| `scripts/migrate-to-agent-tools.sh` | Migrate existing users (with backup) |
| `scripts/rollback-agent-tools.sh` | Rollback migration from backup |
| `scripts/setup-repo.sh` | Set up a new/existing project with agent files |
| `scripts/generate-agent-files.py` | Regenerate CLAUDE.md etc from rules |
| `scripts/generate-agent-rules.py` | Generate .agent-rules/ from .cursor/rules/ |
| `scripts/validate-rule-parity.py` | Validate .agent-rules/ matches .cursor/rules/ |
| `scripts/install-git-hooks.sh` | Install git hooks for this repo |

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
- **Cascading updates**: Run `setup-repo.sh --update-all` to update all tracked projects
- **Re-run detection**: Detects if a project was already set up
- **Inventory**: Run `setup-repo.sh --list` to see all configured projects

```bash
# List all tracked projects
./scripts/setup-repo.sh --list

# Update all tracked projects
./scripts/setup-repo.sh --update-all

# Preview updates without making changes
./scripts/setup-repo.sh --update-all-dry-run
```

## Migration for Existing Users

If you already have symlinks from a previous setup:

```bash
# Preview changes (dry run)
./scripts/migrate-to-agent-tools.sh --dry-run

# Run migration (creates backup automatically)
./scripts/migrate-to-agent-tools.sh

# Rollback if needed
./scripts/rollback-agent-tools.sh ~/.agent-tools-backup-TIMESTAMP
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
python3 scripts/generate-agent-rules.py

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
