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
**Language:** Python 3.9+
**Framework:** CLI tool (`aec` command) built with setuptools
**Test Runner:** pytest (dev dependency, tests in `tests/`)
**Type Check:** Not configured (no mypy or pyright)
**Lint:** Not explicitly configured
**Package Manager:** pip with pyproject.toml
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
