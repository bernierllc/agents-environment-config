# Architecture

How the pieces of agents-environment-config fit together.

## High-Level Overview

```
agents.json                          # Single source of truth for agent definitions
    │
    ├── aec/lib/registry.py          # Python: loads agents.json at runtime
    ├── scripts/generate-agent-config.py   # Shell: generates _agent-config.sh
    └── scripts/generate-agent-files.py    # Generates CLAUDE.md, AGENTS.md, etc.

.cursor/rules/*.mdc                  # Rules with Cursor frontmatter (source of truth)
    │
    ├── scripts/generate-agent-rules.py    # Strips frontmatter → .agent-rules/*.md
    └── scripts/generate-agent-files.py    # Embeds essential rules into agent files

~/.agent-tools/                      # Shared directory for all agents
    ├── rules/agents-environment-config -> repo/.agent-rules/
    ├── agents/agents-environment-config -> repo/.claude/agents/
    ├── skills/agents-environment-config -> repo/.claude/skills/
    └── commands/agents-environment-config -> repo/.cursor/commands/
```

## Library Modules (`aec/lib/`)

| Module | Purpose |
|--------|---------|
| `config.py` | Platform detection, path constants (`AEC_HOME`, `AGENT_TOOLS_DIR`, etc.), agent detection, Raycast script generation |
| `registry.py` | Loads `agents.json`, provides `get_supported_agents()`, `get_agent_files()`, `get_gitignore_patterns()` with caching |
| `console.py` | Colored terminal output (headers, success/error/warning, dim text) with `NO_COLOR` support |
| `filesystem.py` | Cross-platform symlink operations (create, remove, check), directory creation, file copy |
| `tracking.py` | Manages `~/.agents-environment-config/` state: setup log, repo tracking, version info |
| `preferences.py` | Optional feature preferences: load/save/prompt from `preferences.json` |

## CLI Structure

The CLI uses [Typer](https://typer.tiangolo.com/) with sub-apps mounted on the main app:

```
aec (main app)
├── install          # Full installation
├── doctor           # Health check
├── repo setup       # Set up a project
├── rules generate   # Regenerate .agent-rules/
├── rules validate   # Check parity
├── preferences list/set/reset
└── agent-tools setup
```

Entry point: `aec/cli.py`. A pre-command callback in the main app calls `check_pending_preferences()` to prompt for unanswered optional features before any command runs.

## Agent & Skill Sync System

The sync system keeps agent and skill files synchronized between submodule repositories and Cursor commands. It runs automatically via git hooks.

### How It Works

1. **Pre-push hook**: Checks submodule state (pushes unpushed commits, blocks on uncommitted changes), then syncs agents/skills to `.cursor/commands/`
2. **Post-merge hook**: Re-syncs after pulling changes
3. **Content replacement**: `{{file:...}}` references in Cursor command files are replaced with actual source content
4. **Frontmatter preservation**: Existing Cursor command frontmatter is kept intact

### Path Mapping

- **Agents** (1:1): `.claude/agents/engineering/ai-engineer.md` -> `.cursor/commands/agents/engineering/ai-engineer.md`
- **Skills** (parent dir becomes filename): `.claude/skills/algorithmic-art/SKILL.md` -> `.cursor/commands/skills/algorithmic-art.md`

### Configuration

Sync behavior is configured in `scripts/sync-config.json`, which defines submodule paths, target directories, and PR settings.

### Manual Sync

```bash
python3 scripts/sync-agents-skills.py
```

### Skip Sync

```bash
SKIP_SYNC=1 git push
```

## File Flow: Rules to Projects

```
.cursor/rules/*.mdc          # Author rules here (with Cursor frontmatter)
        │
        ▼
.agent-rules/*.md            # generate-agent-rules.py strips frontmatter
        │
        ▼
CLAUDE.md, AGENTS.md, etc.   # generate-agent-files.py embeds essential rules
        │
        ▼
Target projects              # aec repo setup copies agent files + links rules
```

When `aec repo setup` runs on a target project, it copies the agent instruction files and creates symlinks from `~/.agent-tools/rules/` so agents can reference the full rule set.
