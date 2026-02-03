# Gemini CLI Agent Instructions

> **Canonical Source**: Project-specific standards live in `AGENTINFO.md`.
> Read that file first. This file provides rule references.

## Quick Start

1. Read `AGENTINFO.md` for project-specific info
2. Read relevant `.cursor/rules/*.mdc` files on demand
3. Do NOT memorize all rules - reference them when needed

## Rules Reference

Rules are organized in `.cursor/rules/` and should be read on demand when relevant.
Do NOT memorize all rules - read the specific rule file when working in that area.

### Essential Rules (read when relevant)

- **Testing**: `.cursor/rules/frameworks/testing/standards.mdc`
- **Typescript**: `.cursor/rules/languages/typescript/typing-standards.mdc`
- **Architecture**: `.cursor/rules/general/architecture.mdc`
- **Git**: `.cursor/rules/topics/git/workflow.mdc`
- **Quality**: `.cursor/rules/topics/quality/gates.mdc`

### All Rules by Category

- **general/**: Core principles (architecture, workflow, documentation) (8 rules)
- **languages/**: Language conventions (Python, TypeScript) (2 rules)
- **stacks/**: Stack patterns (Next.js, FastAPI, React Native) (3 rules)
- **frameworks/**: Framework guides (databases, testing, UI) (9 rules)
- **topics/**: Cross-cutting (API, git, security, quality) (12 rules)
- **packages/**: Package management (2 rules)

### How to Use Rules

1. When working on TypeScript, read `languages/typescript/typing-standards.mdc`
2. When writing tests, read `frameworks/testing/standards.mdc`
3. When setting up a project, read `general/architecture.mdc`
4. For project-specific info, see `AGENTINFO.md`

## Regenerating This File

```bash
python3 scripts/generate-agent-files.py
```
