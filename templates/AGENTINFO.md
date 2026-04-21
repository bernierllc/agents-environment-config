# Project-Specific Agent Information

> **REPLACE THIS CONTENT** with your project's specific information.
> This file is the single source of truth for project-specific standards.

## Stack Information

<!-- AGENT TASK: If the section below still contains the placeholder, detect this
     project's stack and replace the placeholder with real information. Analyze
     package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod, Gemfile,
     or other manifest files to determine:
     - Language(s) and version(s)
     - Framework(s) (e.g. Next.js, FastAPI, Rails, etc.)
     - Package manager (npm, pnpm, yarn, pip, poetry, cargo, etc.)
     - Database(s) if detectable (Postgres, MongoDB, Redis, etc.)
     - Key dependencies and their roles
     Then replace everything between the STACK-START and STACK-END markers with
     the detected information. Remove this comment block when done. -->

<!-- STACK-START -->
**[PLACEHOLDER — an agent will auto-detect and fill this section on first read]**
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

## Commits and PRs

- Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`
- Feature branches from `main`
- Add project-specific branching rules

## Security and Configuration

- Environment variables needed
- Secrets management approach
- Configuration files location

## Port Registry

This project's ports are registered with AEC. Before assigning new ports,
check `aec ports list` to see all registered ports and avoid conflicts.

To register new ports:
1. Add them to `.aec.json` in the `ports` section
2. Run `aec ports register` to register them centrally

Port assignments use first-come-first-served. See `.aec.json` for this
project's current port assignments.

## Documentation

- Where docs live
- How to update docs
- Documentation standards
