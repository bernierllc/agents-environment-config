# Adding Agent Support

Guide for contributors who want to add support for a new AI coding agent in agents-environment-config.

## Prerequisites

- Familiarity with the [README](../README.md) and the overall repo structure
- The agent you are adding must have a documented instruction file format (e.g., a markdown file the agent reads at startup)
- A working installation of the agent on your machine for testing

## Overview

All agent definitions live in a single registry file: **`agents.json`** at the repo root. Adding a new agent requires one JSON entry plus running two generation commands. Everything else (shell config, Python config, file lists, detection logic, Raycast scripts) is derived automatically.

| # | Step | What to do |
|---|------|------------|
| 1 | Add to registry | Add entry to `agents.json` |
| 2 | Regenerate configs | Run generation commands |
| 3 | Run tests | Verify everything works |
| 4 | Update README | Add to Supported Agents table |
| 5 | Commit | Commit all generated + modified files |

## 1. Add Entry to `agents.json`

Open `agents.json` at the repo root and add a new entry to the `"agents"` object:

```json
{
  "agents": {
    "agentname": {
      "display_name": "Agent Name",
      "description": "Brief description of the agent",
      "instruction_file": "AGENTNAME.md",
      "commands": ["agentname"],
      "alt_paths": [],
      "terminal_launch": true,
      "launch_args": "",
      "has_resume": false,
      "use_agent_rules": true
    }
  }
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | Human-readable name (used in generated files) |
| `description` | string | Brief description |
| `instruction_file` | string or null | Filename for the agent's instruction file (null for Cursor which uses `.mdc` files) |
| `commands` | string[] | CLI commands to check via `shutil.which()` / `command -v` |
| `alt_paths` | string[] | Fallback filesystem paths for detection (e.g., `"/Applications/AgentName.app"`, `"~/.agentname"`) |
| `terminal_launch` | bool | `true` = open in Terminal via osascript, `false` = direct command |
| `launch_args` | string | Arguments appended to agent command (terminal agents only) |
| `launch_template` | string | Launch command template with `{path}` placeholder (non-terminal agents only) |
| `has_resume` | bool | Whether the agent supports a `--resume` flag |
| `resume_args` | string | Arguments for resume mode (only if `has_resume: true`) |
| `use_agent_rules` | bool | `true` = references `.agent-rules/*.md`, `false` = uses Cursor `.mdc` files |

### Examples

**Terminal agent with resume support** (like Claude):
```json
"myagent": {
  "display_name": "My Agent",
  "description": "Description here",
  "instruction_file": "MYAGENT.md",
  "commands": ["myagent"],
  "alt_paths": ["~/.myagent"],
  "terminal_launch": true,
  "launch_args": "--auto",
  "has_resume": true,
  "resume_args": "--auto --resume",
  "use_agent_rules": true
}
```

**GUI agent** (like Cursor):
```json
"myide": {
  "display_name": "My IDE",
  "description": "Description here",
  "instruction_file": null,
  "commands": ["myide"],
  "alt_paths": ["/Applications/MyIDE.app"],
  "terminal_launch": false,
  "launch_template": "myide {path}/",
  "has_resume": false,
  "use_agent_rules": false
}
```

## 2. Regenerate Configs

After editing `agents.json`, run these commands:

```bash
# Generate shell config from agents.json
python3 scripts/generate-agent-config.py

# Regenerate agent instruction files (CLAUDE.md, AGENTS.md, etc.)
python3 scripts/generate-agent-files.py
```

This automatically updates:
- `scripts/_agent-config.sh` -- shell detection, file lists, Raycast commands
- Agent instruction files at the repo root
- Python config is derived at runtime from `agents.json` (no regeneration needed)

## 3. Run Tests

```bash
# Run full test suite
python -m pytest tests/ -v

# Validate rule parity
aec rules validate

# Health check
aec doctor
```

## 4. Update README

Add the new agent to the [Supported Agents](../README.md#supported-agents) table in README.md.

## 5. Commit

```bash
git add agents.json scripts/_agent-config.sh AGENTNAME.md
git commit -m "feat: add AgentName support"
```

## How It Works

The `agents.json` registry is the single source of truth. All other agent-related configuration is derived from it:

| Derived config | How it's generated |
|----------------|-------------------|
| Python `SUPPORTED_AGENTS` dict | `aec/lib/registry.py` reads `agents.json` at runtime |
| `AGENT_FILES` list | `aec/lib/registry.py` → `get_agent_files()` |
| `GITIGNORE_PATTERNS` | `aec/lib/registry.py` → `get_gitignore_patterns()` |
| Migration file lists | `aec/lib/registry.py` → `get_migration_files()` |
| Shell agent config | `scripts/generate-agent-config.py` → `scripts/_agent-config.sh` |
| Shell detection function | Generated in `scripts/_agent-config.sh` |
| Shell Raycast commands | Generated in `scripts/_agent-config.sh` |
| Agent instruction files | `scripts/generate-agent-files.py` reads `agents.json` |

## Checklist

- [ ] Added entry to `agents.json`
- [ ] Ran `python3 scripts/generate-agent-config.py`
- [ ] Ran `python3 scripts/generate-agent-files.py`
- [ ] Tests pass: `python -m pytest tests/ -v`
- [ ] Rule parity validated: `aec rules validate`
- [ ] [Supported Agents](../README.md#supported-agents) table updated in README

## References

- [README](../README.md) -- project overview and structure
- [`agents.json`](../agents.json) -- agent registry (single source of truth)
- [`aec/lib/registry.py`](../aec/lib/registry.py) -- Python registry loader
- [`scripts/generate-agent-config.py`](../scripts/generate-agent-config.py) -- shell config generator
- [`scripts/generate-agent-files.py`](../scripts/generate-agent-files.py) -- agent file generation script
