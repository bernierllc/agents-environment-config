# Agents Environment Configuration

> **This is a TEMPLATE repository.** It provides shared AI agent configurations that get copied to other projects. Do not add project-specific content here.

## What This Repo Is

This repository contains:
- **Shared cursor rules** (`.cursor/rules/`) - Development standards for all projects
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

This creates symlinks from your home directory to this repo's configs.

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
├── .claude/
│   ├── agents/                     # Agent definitions (git submodule)
│   └── skills/                     # Skill definitions (git submodule)
├── .cursor/
│   ├── commands/                   # Cursor command wrappers
│   └── rules/                      # Cursor rules (global development standards)
├── scripts/
│   ├── setup.sh                    # Install this repo to your system
│   ├── setup-repo.sh               # Set up a NEW project with agent files
│   ├── generate-agent-files.py     # Regenerate CLAUDE.md etc from rules
│   └── git-hooks/                  # Git hooks for this repo
├── raycast_scripts/
│   ├── setup-repo.sh               # Raycast version of setup-repo
│   └── *.sh                        # Project launcher scripts
├── AGENTINFO.md                    # TEMPLATE - gets filled in per-project
├── CLAUDE.md                       # TEMPLATE - reference-only agent instructions
├── AGENTS.md                       # TEMPLATE - for Codex
├── GEMINI.md                       # TEMPLATE - for Gemini
├── QWEN.md                         # TEMPLATE - for Qwen
└── README.md                       # This file
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup.sh` | Install this repo's configs to your home directory (symlinks) |
| `scripts/setup-repo.sh` | Set up a new/existing project with agent files |
| `scripts/generate-agent-files.py` | Regenerate CLAUDE.md etc from `.cursor/rules/` |
| `scripts/install-git-hooks.sh` | Install git hooks for this repo |
| `raycast_scripts/setup-repo.sh` | Raycast version of setup-repo |

### Script Parity

Scripts in `scripts/` and `raycast_scripts/` must stay in sync. A pre-commit hook validates:
- `setup-repo.sh` exists in both directories
- AGENTINFO.md remains a template (not project-specific)

To install the git hooks:

```bash
./scripts/install-git-hooks.sh
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
# Regenerate the agent instruction files
python3 scripts/generate-agent-files.py

# Commit the changes
git add CLAUDE.md AGENTS.md GEMINI.md QWEN.md
git commit -m "chore: regenerate agent files from rules"
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
| `.cursor/rules/*.mdc` | Development standards | No - shared across projects |

## Security Notes

- Never commit `.env` files
- API keys go in `.env` (copy from `.env.template`)
- Review API key permissions - use least-privilege access

## Related Repositories

- [agency-agents](https://github.com/bernierllc/agency-agents) - Agent definitions
- [skills](https://github.com/bernierllc/skills) - Skill definitions
