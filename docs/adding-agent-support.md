# Adding Agent Support

Guide for contributors who want to add support for a new AI coding agent in agents-environment-config.

## Prerequisites

- Familiarity with the [README](../README.md) and the overall repo structure
- The agent you are adding must have a documented instruction file format (e.g., a markdown file the agent reads at startup)
- A working installation of the agent on your machine for testing

## Overview

Adding a new agent requires changes across seven areas. Each section below maps to a specific file or set of files.

| # | Area | Key Files |
|---|------|-----------|
| 1 | Agent instruction file | `AGENTNAME.md` (repo root) |
| 2 | Agent detection logic | `aec/lib/config.py` |
| 3 | Setup script (shell) | `scripts/setup-repo.sh` |
| 4 | Python CLI | `aec/commands/repo.py` |
| 5 | Agent file generation | `scripts/generate-agent-files.py` |
| 6 | Migration support | `scripts/setup-repo.sh`, `aec/commands/repo.py` |
| 7 | Tests | `tests/` |

## 1. Agent Instruction File

Create a new `AGENTNAME.md` template at the repo root. This file gets copied into target projects during `aec repo setup`.

### Requirements

- Reference `.agent-rules/` (NOT `.cursor/rules/`). Non-Cursor agents do not need Cursor frontmatter.
- Follow the slim/reference-only pattern used by existing files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md`).
- Point to `AGENTINFO.md` as the canonical source for project-specific information.

### Example structure

```markdown
# AgentName Agent Instructions

> **Canonical Source**: Project-specific standards live in `AGENTINFO.md`.
> Read that file first. This file provides rule references.

## Quick Start

1. Read `AGENTINFO.md` for project-specific info
2. Read relevant `.agent-rules/*.md` files on demand
3. Do NOT memorize all rules - reference them when needed

## Rules Reference
...
```

You do not need to write this file by hand. Step 5 (agent file generation) will auto-generate it. But you do need to register the filename in the generation script.

### Registration

Add the new filename to two locations:

**`scripts/setup-repo.sh`** -- the `AGENT_FILES` array inside `copy_fresh_agent_files()`:

```bash
AGENT_FILES=("AGENTINFO.md" "AGENTS.md" "CLAUDE.md" "GEMINI.md" "QWEN.md" "AGENTNAME.md")
```

**`aec/commands/repo.py`** -- the `AGENT_FILES` list:

```python
AGENT_FILES = ["AGENTINFO.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "QWEN.md", "AGENTNAME.md"]
```

Also add the filename to `GITIGNORE_PATTERNS` in `aec/commands/repo.py` so target projects ignore it by default:

```python
GITIGNORE_PATTERNS = [
    "AGENTINFO.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "QWEN.md",
    "AGENTNAME.md",  # <-- add here
    ".cursor/rules",
    "/plans/",
]
```

And add the same pattern to the `PATTERNS` array in `scripts/setup-repo.sh`:

```bash
PATTERNS=("AGENTINFO.md" "AGENTS.md" "CLAUDE.md" "GEMINI.md" "QWEN.md" "AGENTNAME.md" ".cursor/rules" "/plans/")
```

## 2. Agent Detection Logic

Agent detection determines which agents are installed on the user's machine. This drives Raycast script generation and future features.

### Where to modify

**`aec/lib/config.py`** -- Add an entry to the `SUPPORTED_AGENTS` dictionary. The `detect_agents()` function iterates over this dict automatically.

```python
SUPPORTED_AGENTS = {
    # ... existing agents ...
    "agentname": {
        "commands": ["agentname"],           # CLI commands to check via shutil.which()
        "alt_paths": [],                     # Fallback filesystem paths (e.g., Path("/Applications/AgentName.app"))
        "terminal_launch": True,             # True = open in Terminal, False = direct command (like cursor)
        "launch_args": "",                   # Arguments appended to the agent command
        "has_resume": False,                 # Whether the agent supports a --resume flag
    },
}
```

For agents with alternative detection (like Cursor via `/Applications/Cursor.app`), add paths to `alt_paths`:

```python
"alt_paths": [Path("/Applications/AgentName.app"), Path.home() / ".agentname"],
```

For agents with resume support (like Claude), add:

```python
"has_resume": True,
"resume_args": "--resume",
```

For non-terminal agents (like Cursor), set:

```python
"terminal_launch": False,
"launch_template": "agentname {path}/",  # {path} is replaced with project path
```

### Shell script detection

Also add detection to `detect_installed_agents()` in `scripts/setup-repo.sh`:

```bash
# agentname: check command
if command -v agentname &>/dev/null; then
    DETECTED_AGENTS="$DETECTED_AGENTS agentname"
fi
```

And add a case to `generate_raycast_script()` in the same file:

```bash
case "$agent" in
    # ... existing cases ...
    agentname)
        echo "osascript -e 'tell application \"Terminal\" to do script \"cd ${proj_path}/; agentname\"'" >> "$script_path"
        ;;
esac
```

### What to check

| Check | Example |
|-------|---------|
| CLI command exists | `shutil.which("agentname")` or `command -v agentname` |
| Application path exists | `/Applications/AgentName.app` (macOS) |
| Config directory exists | `~/.agentname/` |

Provide at least one detection method. Two is better for reliability.

## 3. Setup Script Updates

Modify `scripts/setup-repo.sh` to support the new agent in three places.

### a. Agent files array

Already covered in Step 1 above -- add to the `AGENT_FILES` array and `PATTERNS` array.

### b. Agent detection (for Raycast scripts)

The Raycast section of `setup-repo.sh` currently generates scripts for Claude and Cursor. Add a detection block and script template for the new agent.

Example pattern (add after the existing claude/cursor blocks inside the Raycast section):

```bash
# Create agentname script (if installed)
if command -v agentname &> /dev/null; then
    cat > "$RAYCAST_DIR/agentname-$SAFE_NAME.sh" << EOF
#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title agentname $PROJECT_NAME
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description open agentname $PROJECT_NAME project
# @raycast.author matt_bernier
# @raycast.authorURL https://raycast.com/matt_bernier

agentname $ABS_PROJECT_DIR/

EOF
    chmod +x "$RAYCAST_DIR/agentname-$SAFE_NAME.sh"
fi
```

Key considerations:

- **Terminal-based agents** (like Claude Code) need `osascript` to open a Terminal window. Use the Claude script as a template.
- **GUI-based agents** (like Cursor) can launch directly. Use the Cursor script as a template.
- **Resume variants**: If the agent supports a `--resume` flag, create a second script with `-resume` suffix (see the Claude resume script for reference).

## 4. Python CLI Updates

Modify `aec/commands/repo.py`:

- Add the new file to `AGENT_FILES` (covered in Step 1).
- Add to `GITIGNORE_PATTERNS` (covered in Step 1).
- Ensure `_copy_agent_files()` will pick it up automatically (it iterates over `AGENT_FILES`, so no further changes needed).

The Python CLI uses the `SUPPORTED_AGENTS` dict and `detect_agents()` from `aec/lib/config.py` for Raycast script generation. As long as you added your agent to `SUPPORTED_AGENTS` (Step 2), Raycast generation will pick it up automatically.

## 5. Agent File Generation

Update `scripts/generate-agent-files.py` to auto-generate the new agent's instruction file.

### Where to modify

Add an entry to the `agents` dictionary in the `main()` function:

```python
agents = {
    'AGENTS.md': ('Codex', True),
    'GEMINI.md': ('Gemini CLI', True),
    'QWEN.md': ('Qwen Code', True),
    'CLAUDE.md': ('Claude Code', True),
    'AGENTNAME.md': ('AgentName', True),  # <-- add here
}
```

The tuple format is `(display_name, use_agent_rules)`. All non-Cursor agents should set `use_agent_rules=True` so the generated file references `.agent-rules/*.md` instead of `.cursor/rules/*.mdc`.

After adding the entry, regenerate all agent files:

```bash
python3 scripts/generate-agent-files.py
```

Verify the output file looks correct and follows the slim/reference-only pattern.

## 6. Migration Support

When users update existing projects, migration logic detects and fixes outdated references. Add the new agent file to the migration checks.

### Shell script (`scripts/setup-repo.sh`)

Add the filename to the loop in both `needs_agent_rules_migration()` and `migrate_to_agent_rules()`:

```bash
for file in CLAUDE.md AGENTS.md GEMINI.md QWEN.md AGENTNAME.md; do
```

### Python CLI (`aec/commands/repo.py`)

Add the filename to the loop in both `_needs_migration()` and `_migrate_agent_files()`:

```python
for filename in ["CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md", "AGENTNAME.md"]:
```

## 7. Tests

Add tests to verify the new agent integration. Tests live in the `tests/` directory.

### Detection tests

Add tests in `tests/test_agents.py` to verify your agent is in `SUPPORTED_AGENTS` and detected correctly:

```python
from aec.lib.config import SUPPORTED_AGENTS, detect_agents

class TestAgentNameSupport:
    def test_agentname_in_supported_agents(self):
        """Agent should be listed in SUPPORTED_AGENTS."""
        assert "agentname" in SUPPORTED_AGENTS

    def test_agentname_has_required_keys(self):
        """Agent config should have all required keys."""
        config = SUPPORTED_AGENTS["agentname"]
        assert "commands" in config
        assert "terminal_launch" in config
        assert "has_resume" in config

    def test_agentname_detected_via_command(self, monkeypatch):
        """Detection should find agentname when CLI is available."""
        monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/local/bin/agentname" if cmd == "agentname" else None)
        detected = detect_agents()
        assert "agentname" in detected

    def test_agentname_not_detected_when_missing(self, monkeypatch):
        """Detection should skip agentname when not installed."""
        monkeypatch.setattr(shutil, "which", lambda cmd: None)
        # Also ensure alt_paths don't exist
        detected = detect_agents()
        assert "agentname" not in detected
```

### File generation tests

Add a test verifying the new agent file is generated correctly:

```python
def test_agentname_file_in_agent_files():
    """AGENTNAME.md should be in the AGENT_FILES list."""
    from aec.commands.repo import AGENT_FILES
    assert "AGENTNAME.md" in AGENT_FILES

def test_agentname_in_gitignore_patterns():
    """AGENTNAME.md should be in GITIGNORE_PATTERNS."""
    from aec.commands.repo import GITIGNORE_PATTERNS
    assert "AGENTNAME.md" in GITIGNORE_PATTERNS
```

### Validation

Run the full test suite before submitting:

```bash
python -m pytest tests/
```

Also validate rule parity:

```bash
aec rules validate
```

## Contributing Workflow

1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature/add-agentname-support
   ```
3. Follow steps 1 through 7 above.
4. Run tests:
   ```bash
   python -m pytest tests/
   ```
5. Validate rules:
   ```bash
   aec rules validate
   ```
6. Update the [Supported Agents](../README.md#supported-agents) table in the README.
7. Submit a pull request with a clear description of the agent being added and links to its documentation.

## Checklist

Use this checklist to verify all changes are complete before submitting a PR:

- [ ] `AGENTNAME.md` generated at repo root (via `generate-agent-files.py`)
- [ ] Added to `AGENT_FILES` in `scripts/setup-repo.sh`
- [ ] Added to `AGENT_FILES` in `aec/commands/repo.py`
- [ ] Added to `GITIGNORE_PATTERNS` in `aec/commands/repo.py`
- [ ] Added to `PATTERNS` in `scripts/setup-repo.sh`
- [ ] Added to `agents` dict in `scripts/generate-agent-files.py`
- [ ] Added to migration loops in both shell and Python
- [ ] Detection logic added (shell and/or Python)
- [ ] Raycast script template added (if applicable)
- [ ] Tests written and passing
- [ ] [Supported Agents](../README.md#supported-agents) table updated in README
- [ ] All existing tests still pass: `python -m pytest tests/`
- [ ] Rule parity validated: `aec rules validate`

## References

- [README](../README.md) -- project overview and structure
- [Agent & Skill Sync System](./agent-skill-sync-system.md) -- sync between submodules and Cursor commands
- [`scripts/generate-agent-files.py`](../scripts/generate-agent-files.py) -- agent file generation script
- [`aec/commands/repo.py`](../aec/commands/repo.py) -- Python CLI repo commands
- [`scripts/setup-repo.sh`](../scripts/setup-repo.sh) -- shell-based repo setup
