# Agent & Skill Sync System

Automated bidirectional sync system for agents and skills between submodule repositories and Cursor commands.

## Overview

This system automatically syncs agent and skill files from `.claude/agents` and `.claude/skills` (git submodules) to `.cursor/commands/` directories, replacing `{{file:...}}` references with actual file content.

## Features

- **Submodule push enforcement**: Before every push, submodules (`.claude/agents`, `.claude/skills`) are checked. If any have unpushed commits, they are pushed first; if any have uncommitted changes, the push is blocked until you commit and push in the submodule. Updated submodule refs are auto-committed so the parent repo always points at the latest submodule commits.
- **Bidirectional Sync**: Syncs from submodules to cursor commands
- **Deterministic Path Mapping**: Simple 1:1 mapping for agents, parent-dir-to-filename for skills
- **Content Replacement**: Replaces `{{file:...}}` references with actual content
- **Frontmatter Preservation**: Preserves existing cursor command frontmatter
- **Validation**: Checks submodule state and GitHub CLI authentication
- **Error Handling**: Graceful failures with clear error messages
- **Skip Mechanism**: Easy way to bypass sync when needed

## Installation

Run the installation script to set up git hooks:

```bash
./scripts/install-git-hooks.sh
```

This will:
- Install pre-push and post-merge git hooks
- Validate Python 3 and GitHub CLI installation
- Check submodule initialization and branch state
- Verify GitHub CLI authentication

## Usage

### Automatic Sync

Sync happens automatically:
- **Pre-push**: (1) Submodule push check: unpushed submodule commits are pushed; uncommitted submodule changes block the push. (2) Submodule refs are staged and committed if they changed. (3) Agents/skills are synced to cursor commands.
- **Post-merge**: After pulling/merging changes

To run only the submodule push check (no sync): `./scripts/push-submodules.sh`

### Manual Sync

Run the sync script directly:

```bash
python3 scripts/sync-agents-skills.py
```

### Skip Sync

To skip sync operations:

```bash
# Skip sync on push
SKIP_SYNC=1 git push

# Skip all hooks (standard git)
git push --no-verify

# Skip sync on pull
SKIP_SYNC=1 git pull
```

## How It Works

### Path Mapping

**Agents** (1:1 mapping):
```
.claude/agents/engineering/engineering-ai-engineer.md
→ .cursor/commands/agents/engineering/engineering-ai-engineer.md
```

**Skills** (parent directory becomes filename):
```
.claude/skills/algorithmic-art/SKILL.md
→ .cursor/commands/skills/algorithmic-art.md
```

### Content Replacement

1. Reads source file from `.claude/agents` or `.claude/skills`
2. Extracts content (removes source frontmatter if present)
3. Preserves existing cursor command frontmatter (or creates default)
4. Combines frontmatter with source content
5. Writes to `.cursor/commands/`

**Before:**
```markdown
---
name: "AI Engineer"
tags: ["engineering"]
---

{{file:~/.claude/agents/engineering/engineering-ai-engineer.md}}
```

**After:**
```markdown
---
name: "AI Engineer"
tags: ["engineering"]
---

# AI Engineer Agent

You are an **AI Engineer**...
[Full content from source file]
```

## File Structure

```
scripts/
├── sync-agents-skills.py          # Core sync logic
├── sync-config.json               # Configuration
├── git-hooks/
│   ├── pre-push                  # Pre-push hook
│   └── post-merge                # Post-merge hook
└── install-git-hooks.sh          # Hook installer
```

## Configuration

Edit `scripts/sync-config.json` to customize:

```json
{
  "submodules": {
    "agents": {
      "path": ".claude/agents",
      "repo": "bernierllc/agency-agents",
      "cursor_target": ".cursor/commands/agents"
    },
    "skills": {
      "path": ".claude/skills",
      "repo": "bernierllc/skills",
      "cursor_target": ".cursor/commands/skills",
      "skill_file_pattern": ["Skill.md", "SKILL.md"]
    }
  },
  "pr_settings": {
    "base_branch": "main",
    "title_template": "Sync {type}: {filename}",
    "body_template": "Automated sync from agents-environment-config"
  }
}
```

## Validation

The system validates:

- **Submodules**: Checks if `.claude/agents` and `.claude/skills` are initialized
- **Branch State**: Ensures submodules are not on detached HEAD
- **GitHub CLI**: Verifies `gh` is installed and authenticated (for PR creation)
- **Python**: Checks Python 3 is available

## Error Handling

The system handles errors gracefully:

- **Missing dependencies**: Warns but continues with available operations
- **Submodule issues**: Clear error messages with resolution steps
- **GitHub CLI not authenticated**: Skips PR creation but continues sync
- **File errors**: Logs errors but doesn't block git operations

## Troubleshooting

### Submodules not initialized

```bash
git submodule update --init --recursive
```

### Submodule on detached HEAD

```bash
cd .claude/agents
git checkout main
```

### GitHub CLI not authenticated

```bash
gh auth login
```

### Sync not working

1. Check Python 3 is installed: `python3 --version`
2. Run sync manually: `python3 scripts/sync-agents-skills.py`
3. Check for errors in output
4. Verify submodules are initialized

### Force sync (ignore timestamps)

```bash
# Touch files to update timestamps
touch .claude/agents/**/*.md
python3 scripts/sync-agents-skills.py
```

## Development

### Testing

Test the sync system:

```bash
# Run installation
./scripts/install-git-hooks.sh

# Run manual sync
python3 scripts/sync-agents-skills.py

# Test skip mechanism
SKIP_SYNC=1 python3 scripts/sync-agents-skills.py
```

### Adding New Features

The sync script is modular with clear functions:

- `map_agent_path()` - Path mapping for agents
- `map_skill_path()` - Path mapping for skills
- `validate_submodules()` - Submodule validation
- `validate_github_cli()` - GitHub CLI validation
- `sync_to_cursor_commands()` - Main sync logic
- `generate_cursor_command()` - Content replacement

## Future Enhancements

- GitHub Actions workflow as alternative to hooks
- Enhanced error recovery mechanisms
- Sync status reporting
- Conflict resolution for manual edits

## References

- [Plan Document](../plans/automated_agent_and_skill_sync_system_d7a93e74.plan.md)
- [README](../README.md)

