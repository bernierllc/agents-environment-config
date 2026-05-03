# Contributing to Agents Environment Config

Thanks for your interest in contributing! This repo manages shared AI agent configurations for Claude, Cursor, Codex, Gemini, and Qwen.

## Getting Started

```bash
git clone https://github.com/bernierllc/agents-environment-config.git
cd agents-environment-config

# Install the CLI in editable mode
pip install -e .

# Run setup
aec install

# Verify everything works
aec doctor
```

## Development Setup

**Requirements:** Python 3.9+

```bash
# Install in editable mode (picks up code changes immediately)
pip install -e .

# Run the test suite
python -m pytest tests/

# Validate rule parity
aec rules validate
```

## Project Structure

```
aec/                    # Python CLI package
.cursor/rules/          # Cursor rules WITH frontmatter (source of truth)
.agent-rules/           # Rules WITHOUT frontmatter (generated)
scripts/                # Shell scripts and generation scripts
tests/                  # Test suite
docs/                   # Documentation
```

See [README.md](README.md) for the full structure breakdown.

## Making Changes

### Rules (`.cursor/rules/`)

Rules are authored in `.cursor/rules/` with Cursor YAML frontmatter. The `.agent-rules/` directory is auto-generated from these.

1. Edit the rule in `.cursor/rules/`
2. Run `aec rules generate` to regenerate `.agent-rules/`
3. Run `python3 scripts/generate-agent-files.py` to update agent instruction files
4. Run `aec rules validate` to verify parity

Never edit `.agent-rules/` directly -- it will be overwritten. See [docs/contributors/generation-pipeline.md](docs/contributors/generation-pipeline.md) for the full generation workflow.

### Agent Instruction Files (`CLAUDE.md`, `AGENTS.md`, etc.)

These are auto-generated from the rules. To change them, edit `scripts/generate-agent-files.py` and regenerate:

```bash
python3 scripts/generate-agent-files.py
```

### CLI (`aec/`)

The Python CLI lives in `aec/`. When adding or changing CLI commands:

- Add commands in `aec/commands/`
- Shared utilities go in `aec/lib/`
- Keep feature parity with the shell scripts in `scripts/`

#### Skill dependencies

Skills can declare `min_version` constraints on other skills via a `dependencies` block in `SKILL.md` frontmatter. AEC resolves the full dependency graph at install and upgrade time.

**Key files:**

| File | Purpose |
|------|---------|
| `aec/lib/skills_manifest.py` | `parse_dependencies_block()` — reads `dependencies.skills` from frontmatter |
| `aec/lib/skill_dependencies.py` | `resolve_install_graph()` — DFS topological sort, returns `ResolvedGraph` |
| `aec/lib/dep_approval_prompt.py` | `prompt_dep_install()`, `prompt_dep_upgrade_conflict()` — user-facing prompts |
| `aec/commands/install_cmd.py` | `_resolve_and_prompt_deps()` — wires resolver into install flow |
| `aec/commands/upgrade.py` | `_check_and_upgrade_dep_conflicts()` — wires resolver into upgrade flow |

**`ResolvedGraph` fields:**

- `to_install` — deps that need to be installed (topologically ordered, leaves first)
- `already_satisfied` — deps already installed at a sufficient version
- `version_conflicts` — deps installed below the required `min_version` (each is a `VersionConflict` with `name`, `required_min`, `installed_ver`)
- `missing` — deps not found in the catalog
- `cycles` — any dependency cycles detected

**`installedAs` field:**

Every skill manifest record carries `installedAs: "explicit" | "dependency"`. Skills installed directly by the user get `"explicit"`; skills installed to satisfy a dep get `"dependency"`. Existing records without this field are backfilled with `"explicit"` on first load.

**Adding a new skill with dependencies:**

1. Add the `dependencies` block to the skill's `SKILL.md` (see README for the exact YAML shape).
2. Run `python -m pytest tests/test_skill_dependencies.py` to verify the resolver handles the new graph.
3. `parse_dependencies_block` raises `ValueError` on malformed frontmatter — treat this as a hard error; fix the SKILL.md rather than catching it in callers.

### Shell Scripts (`scripts/`)

Shell scripts provide macOS/Linux support and must stay in sync with the Python CLI. If you change behavior in one, update the other.

## Testing

```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v

# Validate rules
aec rules validate

# Health check
aec doctor
```

When adding new features, add corresponding tests in `tests/`. See [docs/contributors/testing.md](docs/contributors/testing.md) for fixtures, patterns, and the mocking strategy.

## Adding Agent Support

All agents are defined in [`agents.json`](agents.json) at the repo root. Adding a new agent is just one JSON entry + two generation commands. See [docs/contributors/adding-agent-support.md](docs/contributors/adding-agent-support.md) for the full guide, or open an issue using the **New Agent Support** template. For how the pieces fit together, see [docs/contributors/architecture.md](docs/contributors/architecture.md).

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` -- New feature or agent support
- `fix:` -- Bug fix
- `docs:` -- Documentation only
- `chore:` -- Maintenance, dependency updates, generation scripts
- `test:` -- Test additions or fixes
- `refactor:` -- Code restructuring without behavior change

Examples:

```
feat: add Windsurf agent support
fix: correct symlink detection on Windows
docs: update CLI command reference
chore: regenerate agent rules and files
test: add tests for aec rules validate
```

## PR Process

1. Fork the repo and create a branch (`feat/my-feature`, `fix/my-fix`)
2. Make your changes
3. Run tests: `python -m pytest tests/`
4. Validate rules: `aec rules validate`
5. Regenerate if needed: `aec rules generate && python3 scripts/generate-agent-files.py`
6. Submit a PR using the pull request template
7. Wait for review

## Code Style

- **Python**: Standard conventions, consistent with existing `aec/` code
- **Shell scripts**: Follow patterns in existing `scripts/` files
- **Markdown rules**: Match the structure and formatting of existing rules in `.cursor/rules/`

## Questions?

Open an [issue](https://github.com/bernierllc/agents-environment-config/issues) and we will get back to you.
