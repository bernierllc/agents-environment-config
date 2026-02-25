# Generation Pipeline

Three scripts generate derived files from the source-of-truth inputs. They must be run in the correct order.

## Scripts

| Script | Input | Output | When to Run |
|--------|-------|--------|-------------|
| `scripts/generate-agent-rules.py` | `.cursor/rules/*.mdc` | `.agent-rules/*.md` | After editing any rule |
| `scripts/generate-agent-files.py` | `.cursor/rules/*.mdc` + `agents.json` | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md` | After editing rules or `agents.json` |
| `scripts/generate-agent-config.py` | `agents.json` | `scripts/_agent-config.sh` | After editing `agents.json` |

## What Each Script Does

**`generate-agent-rules.py`** -- Strips Cursor YAML frontmatter from `.cursor/rules/*.mdc` files and writes plain markdown to `.agent-rules/*.md`. This lets non-Cursor agents use the rules without Cursor-specific metadata.

**`generate-agent-files.py`** -- Reads `.cursor/rules/` to find essential rules, then generates per-agent instruction files (CLAUDE.md, AGENTS.md, etc.) that embed those rules. Uses `agents.json` to determine which agents need files and what format to use.

**`generate-agent-config.py`** -- Reads `agents.json` and produces `scripts/_agent-config.sh`, a bash 3-compatible shell config with agent detection functions, file lists, and Raycast command definitions.

## Workflow Order

```
Edit rules in .cursor/rules/
        │
        ▼
python3 scripts/generate-agent-rules.py     # Step 1: regenerate .agent-rules/
        │
        ▼
python3 scripts/generate-agent-files.py     # Step 2: regenerate agent instruction files
        │
        ▼
aec rules validate                          # Step 3: verify parity
```

If you also changed `agents.json`:

```
python3 scripts/generate-agent-config.py    # Additionally: regenerate shell config
```

## Pre-Commit Validation

The `aec rules validate` command checks that `.agent-rules/` and `.cursor/rules/` are in sync (same count, matching structure). Run it before committing to catch missed regeneration.

## Common Recipes

### Added or edited a rule

```bash
python3 scripts/generate-agent-rules.py
python3 scripts/generate-agent-files.py
aec rules validate
```

### Added a new agent to agents.json

```bash
python3 scripts/generate-agent-config.py
python3 scripts/generate-agent-files.py
```

### Changed agents.json fields (non-new-agent)

```bash
python3 scripts/generate-agent-config.py
```

### Full regeneration (nuclear option)

```bash
python3 scripts/generate-agent-rules.py
python3 scripts/generate-agent-config.py
python3 scripts/generate-agent-files.py
aec rules validate
```
