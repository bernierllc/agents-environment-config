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
