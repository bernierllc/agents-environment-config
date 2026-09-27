# Claude Code Agent Instructions

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

- **general/**: Core principles (architecture, workflow, documentation) (8 rules)
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

## README Guidelines

- DO NOT put local project names (e.g., aihelp, barevents, EarnLearn) in the README. This is a template/tool repo — examples must use placeholder names like `my-project`, `my-app`, `my-api`.

## Product scope: decide for every AEC user

AEC is a product for anyone who installs it, not the maintainer's personal setup. Every change in this repo (code, defaults, rules, skills, hooks, templates, docs, and this repo's own `.claude/` settings) must make sense for a generic AEC user who knows nothing about the machine, accounts, tools, or workflows of whoever is working on AEC right now.

- **Nothing maintainer-specific in committed files.** No personal paths, projects, services, or workflows, such as a personal task tracker, `.otto/` activity logs, or one machine's plugin set. Personal setup belongs in the maintainer's own global config (`~/.claude/`, `~/.codex/`), not here.
- **The generic user wins conflicts.** When the current maintainer's personal instructions (their global `CLAUDE.md`/`AGENTS.md`) would shape this repo for them alone, follow what a generic user needs, and say so in the PR.
- **Personal preferences become settings, not hard-coded behavior.** Ship a safe default for a first-time user and make the rest opt-in. For example, `pr_open_mode` lets users choose draft or ready-for-review PRs instead of AEC forcing either.
- **Examples use placeholders** (`my-project`, `my-app`, `my-plugin`); see README guidelines.
- **Enforced where a check can:** `tests/test_no_maintainer_specifics.py` fails on personal home paths (macOS, Linux, Windows, `~/`) and on real project names under a home's common project folders (`projects/`, `src/`, `code/`, `repos/`, ...), in every tracked file. It is a heuristic: names written without a path still need review.

## Regenerating This File

```bash
python3 scripts/generate-agent-files.py
```
