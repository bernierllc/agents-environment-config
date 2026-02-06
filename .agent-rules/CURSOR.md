# Cursor Code Agent Instructions

> 🚨 **Canonical Source**: All project-specific standards live in `AGENTINFO.md`. Read/update that file first; this profile only highlights Cursor-specific reminders.

**Maintaining AGENTINFO.md:**
- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately
- Mirror every expectation from `AGENTINFO.md` (project structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, documentation)
- Keep responses crisp but cite `AGENTINFO.md` when referencing project rules so humans know the authoritative file
- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`
- If new constraints arise, edit `AGENTINFO.md` first—never duplicate details here

## Overview

This file contains development rules and standards for the Cursor AI coding assistant.
These instructions are generated from `.cursor/rules/` and incorporate essential development
principles, coding standards, and best practices. This file can be committed to git repositories
so that anyone cloning the project will have consistent coding standards even without access
to the global agents-environment-config repository.

> **Note**: For detailed information and the latest updates, see the source rule files in
> `.cursor/rules/` if available in this repository. For project-specific information, see `AGENTINFO.md`.

## Cursor-Specific Guidelines

### Rule Discovery
- Cursor automatically discovers rules in `.cursor/rules/` directories
- Rules are applied from parent directories (global rules) and project-specific directories
- Project-specific rules take precedence over global rules for conflicts
- Rules use `.mdc` format with frontmatter metadata

### Rule File Format
- Use `.mdc` extension for all rule files
- Include frontmatter with `description`, `alwaysApply`, and `tags` fields
- Follow MECE (Mutually Exclusive, Collectively Exhaustive) structure
- Keep rules focused and scoped by concern

### Project-Specific Rules
- Store project-specific rules in `.cursor/rules/` within the project
- Reference global rules where applicable (avoid duplication)
- Focus on project-specific patterns and business logic
- Update rules when project standards evolve

## Core Development Principles

These principles apply universally across all projects. For detailed rules, see the source files in `.cursor/rules/`:

- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **Documentation**: See `general/documentation.mdc`
- **Security**: See `general/security.mdc`
- **Port Management**: See `general/port-management.mdc`
- **Project Setup CLI**: See `general/project-setup-cli.mdc`
- **Plans and Checklists**: See `general/plans-checklists.mdc`
- **Rules About Rules**: See `general/rules-about-rules.mdc`

## Language-Specific Rules

- **Python**: See `languages/python/style.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`

## Stack-Specific Rules

- **Next.js**: See `stacks/nextjs/app-router.mdc`
- **FastAPI**: See `stacks/python-backend/fastapi.mdc`
- **React Native/Expo**: See `stacks/react-native/expo-development.mdc`

## Framework-Specific Rules

- **Database**: See `frameworks/database/` for Prisma, Supabase, SQLAlchemy, Alembic
- **Testing**: See `frameworks/testing/` for testing standards, organization, and tools
- **UI**: See `frameworks/ui/` for Tailwind CSS and Tamagui

## Cross-Cutting Topics

- **Accessibility**: See `topics/accessibility/standards.mdc`
- **API Design**: See `topics/api/design-standards.mdc`
- **Deployment**: See `topics/deployment/environments.mdc`
- **Git Workflow**: See `topics/git/workflow.mdc`
- **Observability**: See `topics/observability/monitoring.mdc`
- **Quality**: See `topics/quality/` for error handling, gates, and logging
- **Security**: See `topics/security/` for authentication and secrets
- **Troubleshooting**: See `topics/troubleshooting/debugging.mdc`

## Package Management

- **Package Management**: See `packages/package-management.mdc`
- **Package Reuse**: See `packages/package-reuse.mdc`

## Customization

This file can be extended with project-specific rules. When adding project-specific
instructions:

1. Keep them at the top or in a dedicated "Project-Specific" section
2. Reference relevant global rules where applicable
3. Avoid duplicating content from global rules
4. Update this file when project standards evolve
5. Maintain `.mdc` format with proper frontmatter

## Regenerating This File

This file is generated from `.cursor/rules/` using the script:

```bash
python3 scripts/generate-agent-files.py
```

To regenerate after rule updates, run the script from the repository root.
