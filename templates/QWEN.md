# Qwen Code Agent Instructions

> **Canonical Source**: Project-specific standards live in `AGENTINFO.md`.
> Read that file first. This file provides rule references.

## Quick Start

1. Read `AGENTINFO.md` for project-specific info
2. Read relevant `~/.agent-tools/rules/agents-environment-config/*.md` files on demand
3. Do NOT memorize all rules - reference them when needed

## Rules Reference

Rules live in `~/.agent-tools/rules/agents-environment-config/` (installed by `aec install`) and should be read on demand.
Do NOT memorize all rules - read the specific rule file when working in that area.

### Essential Rules (read when relevant)

- **Testing**: `~/.agent-tools/rules/agents-environment-config/frameworks/testing/standards.md`
- **Typescript**: `~/.agent-tools/rules/agents-environment-config/languages/typescript/typing-standards.md`
- **Architecture**: `~/.agent-tools/rules/agents-environment-config/general/architecture.md`
- **Git**: `~/.agent-tools/rules/agents-environment-config/topics/git/workflow.md`
- **Quality**: `~/.agent-tools/rules/agents-environment-config/topics/quality/gates.md`

### All Rules by Category

- **general/**: Core principles (architecture, workflow, documentation) (9 rules)
- **languages/**: Language conventions (Python, TypeScript) (2 rules)
- **stacks/**: Stack patterns (Next.js, FastAPI, React Native) (3 rules)
- **frameworks/**: Framework guides (databases, testing, UI) (10 rules)
- **topics/**: Cross-cutting (API, git, security, quality) (12 rules)
- **packages/**: Package management (2 rules)

### How to Use Rules

1. When working on TypeScript, read `~/.agent-tools/rules/agents-environment-config/languages/typescript/typing-standards.md`
2. When writing tests, read `~/.agent-tools/rules/agents-environment-config/frameworks/testing/standards.md`
3. When working with databases, read `~/.agent-tools/rules/agents-environment-config/frameworks/database/connection-management.md`
4. When setting up a project, read `~/.agent-tools/rules/agents-environment-config/general/architecture.md`
5. For project-specific info, see `AGENTINFO.md`

## Regenerating This File

```bash
python3 -m aec files generate
```
