# Project-Specific Agent Information

> **REPLACE THIS CONTENT** with your project's specific information.
> This file is the single source of truth for project-specific standards.

## Stack Information

<!-- STACK-START -->
- **Language:** Python 3.9+
- **Framework:** CLI tool (`aec` command) built with setuptools
- **Package manager:** pip with `pyproject.toml`
- **CLI framework:** Typer (optional dev dependency, argparse fallback)
- **Test runner:** pytest (dev dependency)
- **Key dependencies:** None at runtime (zero-dependency); `typer>=0.9.0` and `pytest>=7.0.0` as dev deps
- **Database:** None
<!-- STACK-END -->

## Project Structure

```
# Describe your project structure here
src/
tests/
docs/
```

## Build/Test Commands

```bash
# Example commands - replace with your own
npm run build
npm run test
npm run lint
```

## Coding Style

- Document your project-specific coding style expectations here
- Example: "We use 2-space indentation"
- Example: "All functions must have JSDoc comments"

## Testing Guidance

Testing policy is defined in `~/.claude/CLAUDE.md` (global).
Add project-specific testing notes here:
- Test database setup
- Test fixtures location
- CI/CD test configuration

## Seed Data Awareness

Database work MUST classify data correctly before it ships. Misclassification leaks test fixtures into production migrations and corrupts shared environments.

- **Three-tier data model at a glance:**
  - `reference` — canonical lookup data required in every environment (statuses, enums, roles, country codes). Owned by migrations.
  - `seed` — baseline rows needed for the app to function or demo (default org, admin user, starter plans). Owned by seed scripts, environment-aware.
  - `fixture` — disposable data for tests and local experiments. Never shipped; lives under `tests/` or local-only scripts.
- **Invoke the `seed-data` skill** (`.claude/skills/seed-data/SKILL.md`) whenever you are adding, modifying, or migrating database rows. The skill walks the classification and picks the right home for each row.
- **Read the rule before writing migrations or seed scripts:** `.agent-rules/frameworks/database/seed-data.md` (installed path: `~/.agent-tools/rules/agents-environment-config/frameworks/database/seed-data.md`).
- **When this applies:**
  - Adding a new table or column with default/lookup rows
  - Writing a migration that inserts or updates data
  - Authoring or editing seed scripts
  - Creating test fixtures that touch the database
- **Anti-pattern:** Do not commit test fixtures to migrations — migrations run in production.

## AEC Item Types and Commands

AEC manages five item types: **skills**, **rules**, **agents**, **packages**, and **plugins**.

### Plugin commands

```bash
aec install plugin <name|url>   # install a plugin (prompts for confirmation before running any command)
aec uninstall plugin <name>     # remove a plugin
aec info plugin <name>          # details about an installed plugin
```

Plugins also appear in `aec list`, `aec search`, `aec outdated`, `aec export`, and `aec apply`.

### Install types (declared in `plugin.json`)

- `marketplace` — Claude-only; runs the marketplace install command after confirmation.
- `per-tool` — runs per-agent `run` command after confirmation, or prints `steps` if no command is provided.
- `external` — AEC **never executes anything**; prints instructions only.

### Preferences

| Key | Values | Effect |
|-----|--------|--------|
| `plugins.execution` | `default` / `instructions-only` | `instructions-only` downgrades all plugins (including marketplace/per-tool) to print-only; no commands are ever executed. |

```bash
aec config set plugins.execution instructions-only
aec config set plugins.execution default
```

Loadout schema: `docs/loadout/` — plugin publishers ship a `plugin.json` at the item root.

## Commits and PRs

- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`
- Feature branches from `main`
- Add project-specific branching rules

## Security and Configuration

- Environment variables needed
- Secrets management approach
- Configuration files location

## Documentation

- Where docs live
- How to update docs
- Documentation standards
