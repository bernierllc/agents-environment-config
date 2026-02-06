# Qwen Code Agent Instructions

> **Canonical Source**: Project-specific standards live in `AGENTINFO.md`.
> Read that file first. This file provides rule references.

## Quick Start

1. Read `AGENTINFO.md` for project-specific info
2. Read relevant `.agent-rules/*.md` files on demand
3. Do NOT memorize all rules - reference them when needed

## Rules Reference

Rules are organized in `.agent-rules/` (no Cursor frontmatter) and should be read on demand.
Do NOT memorize all rules - read the specific rule file when working in that area.

### Essential Rules (read when relevant)

- **Testing**: `.agent-rules/frameworks/testing/standards.md`
- **Typescript**: `.agent-rules/languages/typescript/typing-standards.md`
- **Architecture**: `.agent-rules/general/architecture.md`
- **Git**: `.agent-rules/topics/git/workflow.md`
- **Quality**: `.agent-rules/topics/quality/gates.md`

### All Rules by Category

- **general/**: Core principles (architecture, workflow, documentation) (8 rules)
- **languages/**: Language conventions (Python, TypeScript) (2 rules)
- **stacks/**: Stack patterns (Next.js, FastAPI, React Native) (3 rules)
- **frameworks/**: Framework guides (databases, testing, UI) (10 rules)
- **topics/**: Cross-cutting (API, git, security, quality) (12 rules)
- **packages/**: Package management (2 rules)

### How to Use Rules

1. When working on TypeScript, read `.agent-rules/languages/typescript/typing-standards.md`
2. When writing tests, read `.agent-rules/frameworks/testing/standards.md`
3. When working with databases, read `.agent-rules/frameworks/database/connection-management.md`
4. When setting up a project, read `.agent-rules/general/architecture.md`
5. For project-specific info, see `AGENTINFO.md`

## Regenerating This File

```bash
python3 scripts/generate-agent-files.py
```
