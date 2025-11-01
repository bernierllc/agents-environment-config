# UI Audit - Quick Start Guide

## Overview

The UI Audit skill automates the process of discovering routes, creating exploration tasks, and generating Playwright tests. It uses a ticket-driven workflow with Vibe-Kanban integration.

## Prerequisites

- Git repository initialized
- Node.js installed
- SQLite available (optional, but recommended)
- Vibe-Kanban MCP running (`npx vibe-kanban` in separate terminal)
- Playwright MCP available

## Quick Start

### 1. Bootstrap CONTEXT_CACHE

```bash
node .claude/skills/ui-audit/scripts/ui-audit-bootstrap.mjs --user-level regular
```

This will:
- Detect git repo root (handles worktrees)
- Create CONTEXT_CACHE directory
- Copy schema.sql to CONTEXT_CACHE
- Ensure .gitignore contains CONTEXT_CACHE/
- Initialize SQLite database

### 2. Run Discovery

Invoke the skill with user types:

**From Claude Desktop:**
```
I want to audit the UI for regular and admin users. Base URL is http://localhost:8081.
```

**From Cursor:**
Use the `ui-audit` command from the command palette.

### 3. Discovery Creates EXPLORE Tasks

The discovery task will:
- Discover routes from code constants + Playwright traversal
- Normalize routes (lowercase, strip trailing slash, replace IDs with `:id`)
- Store routes in SQLite database
- **Create EXPLORE tasks for each route** via Vibe-Kanban MCP
- Task naming: `{user-level}-route-explore-{number}`

### 4. Agents Pick Up EXPLORE Tasks

Each EXPLORE task:
- Uses Playwright MCP to manually explore the route
- Documents all UI elements, interactions, states
- Records all Playwright MCP calls
- Creates TEST task during exploration with Playwright code

### 5. Agents Pick Up TEST Tasks

Each TEST task:
- Reads Playwright code from exploration task
- Refines code into proper test structure
- Runs tests and verifies they pass

### 6. Cleanup (After Audit Complete)

```bash
node .claude/skills/ui-audit/scripts/cleanup.mjs
```

This removes `CONTEXT_CACHE/UI_AUDIT/*` while preserving bootstrap files.

## Workflow Diagram

```
Discovery Task
    ↓
Creates EXPLORE Tasks (one per route)
    ↓
Agents Explore Routes
    ↓
Creates TEST Tasks (during exploration)
    ↓
Agents Write Tests
    ↓
Tests Pass
```

## Important Notes

- **Discovery MUST create EXPLORE tasks**: Not optional - discovery is incomplete until all EXPLORE tasks are created
- **No "next steps" sections**: Tasks create the next tasks, don't just list them
- **Task naming**: `{user-level}-route-explore-{number}` format
- **Rate limiting**: Built-in (1s delay, 429 handling)

## Troubleshooting

### Vibe-Kanban MCP Not Available

Error: "Vibe-Kanban MCP tools not available"

Solution: Run `npx vibe-kanban` in a separate terminal

### CONTEXT_CACHE Not Created

Error: "Not in a git repository"

Solution: Ensure you're in a git repository, or initialize one with `git init`

### Rate Limiting Errors

If you see 429 errors, the script will automatically increase delay. Wait for it to complete.

## See Also

- [Detailed Workflow Guide](./workflow.md)
- [SKILL.md](../.claude/skills/ui-audit/SKILL.md)

