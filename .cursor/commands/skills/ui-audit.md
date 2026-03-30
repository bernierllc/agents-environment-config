---
name: "UI Audit"
description: "Automated UI audit system for discovering routes, creating exploration tasks, and generating Playwright tests with Vibe-Kanban integration."
tags: "["skill", "ui-audit", "testing", "playwright"]"
---

# UI Audit Skill

Automated UI audit system that discovers routes, creates exploration tasks, and generates Playwright tests using a ticket-driven workflow with Vibe-Kanban integration.

## Requirements

- **MCP Servers**: 
  - Playwright MCP (for browser automation)
  - Vibe-Kanban MCP (for task management) - run `npx vibe-kanban` in a separate terminal
- **Node.js**: For bootstrap and utility scripts
- **SQLite**: For route tracking database
- **Git**: Repository must be initialized (detects repo root, handles worktrees)

## Input Parameters

- **user_types** (required): Array of user types to audit (e.g., `["regular", "admin", "super-admin"]`)
- **base_url** (optional): Base URL for the application (defaults to `http://localhost:3000`)
- **project_id** (optional): Vibe-Kanban project ID (auto-detected from git repo path if not provided)

## Workflow Overview

### Phase 1: Discovery
1. Bootstrap CONTEXT_CACHE directory at repo root
2. Discover routes from code constants + Playwright traversal
3. Normalize routes (lowercase, strip trailing slash, replace IDs with `:id`/`:slug`)
4. Store routes in SQLite database (status='discovered')
5. **MANDATORY**: Create EXPLORE tasks for each route using Vibe-Kanban MCP
   - Task naming: `{user-level}-route-explore-{number}` (e.g., `super-admin-route-explore-001`)
   - Rate limiting: sleep(1) between creations, handle 429 errors with exponential backoff
   - Write `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt` with task ID

### Phase 2: Exploration (Agents pick up EXPLORE tasks)
1. Start browser session, authenticate as specified user type
2. Navigate to route using Playwright MCP
3. Document all UI elements, forms, interactions, states
4. Record all Playwright MCP calls made
5. Check for new routes (create new EXPLORE tasks if found)
6. **Create TEST task during exploration** with Playwright code
7. Mark EXPLORE task complete

### Phase 3: Test Writing (Agents pick up TEST tasks)
1. Read Playwright code from TEST task description
2. Refine code into proper test structure
3. Run tests and verify they pass
4. Mark TEST task complete

## Key Features

- **Automatic Auth Detection**: Analyzes codebase to detect auth methods and required helpers
- **Worktree Support**: Detects git repo root even in worktree environments
- **Rate Limiting**: Built-in rate limiting for Vibe-Kanban API calls
- **De-duplication**: Uses CONTEXT_CACHE file system to prevent duplicate task creation
- **Auto-cleanup**: Script to safely remove audit artifacts after completion

## Usage

### From Claude Desktop

Invoke the skill with user types:

```
I want to audit the UI for regular and admin users. Base URL is http://localhost:8081.
```

### From Cursor

Use the `ui-audit` command from the command palette.

### Bootstrap Setup

Before running discovery, ensure CONTEXT_CACHE is set up:

```bash
node .claude/skills/ui-audit/scripts/ui-audit-bootstrap.mjs --user-level regular
```

This will:
- Detect git repo root (handles worktrees)
- Create CONTEXT_CACHE directory
- Copy schema.sql to CONTEXT_CACHE
- Ensure .gitignore contains CONTEXT_CACHE/
- Initialize SQLite database

### Cleanup

After audit cycle is complete:

```bash
node .claude/skills/ui-audit/scripts/cleanup.mjs
```

This removes `CONTEXT_CACHE/UI_AUDIT/*` while preserving bootstrap files.

## Task Templates

See `templates/` directory for:
- `discover-routes.md`: Discovery task template
- `explore-route.md`: Route exploration task template
- `test-route.md`: Test writing task template
- `helper-*.md`: Helper task templates
- `bug-report.md`: Bug reporting template

## Critical Rules

1. **Discovery MUST create EXPLORE tasks**: Not optional - discovery is incomplete until all EXPLORE tasks are created
2. **No "next steps" sections**: Tasks create the next tasks, don't just list them
3. **Task naming convention**: `{user-level}-route-explore-{number}` format
4. **Rate limiting**: Always sleep(1) between task creations, handle 429 errors
5. **Agents create TEST tasks**: During exploration, not upfront

## References

- Workflow guide: `docs/ui-audit/workflow.md`
- Task guidance: Reference `tests/AUDIT-TASKS-GUIDANCE.md` (project-specific)
- Testing plan: Reference `docs/testing/generalized-ui-testing-plan.md` (project-specific)
