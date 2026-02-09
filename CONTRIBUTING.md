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

Never edit `.agent-rules/` directly -- it will be overwritten.

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

When adding new features, add corresponding tests in `tests/`.

## Adding Agent Support

If you want to add support for a new AI coding agent, see [docs/adding-agent-support.md](docs/adding-agent-support.md) or open an issue using the **New Agent Support** template.

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
