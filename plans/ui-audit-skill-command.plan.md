# UI Audit Skill and Command Implementation Plan

## Overview

Create a reusable UI audit system as both a Claude skill (`.claude/skills/ui-audit/`) and Cursor command (`.cursor/commands/skills/ui-audit.md`) that automates the UI testing workflow from SCF-Neue. The system will discover routes, detect auth methods, create helpers, and manage tasks in Vibe-Kanban with a clear action-then-pass workflow.

## Key Design Decisions

1. **CONTEXT_CACHE Location**: Placed at git repository root (`<repo-root>/CONTEXT_CACHE/`) to be accessible from all worktrees, automatically added to `.gitignore`
2. **Task Workflow**: Discovery creates EXPLORE tasks only. Agents create TEST tasks during exploration (not upfront)
3. **Task Naming**: `{user-level}-route-explore-{number}` (e.g., `super-admin-route-explore-001`)
4. **Rate Limiting**: sleep(1) between task creations, handle 429 errors by increasing delay by 0.5s
5. **Auth Detection**: Discover auth method during audit, create HELPER tickets first (blocks TEST tickets)
6. **Project Detection**: Auto-detect Vibe-Kanban project ID from current working directory via `git_repo_path` match

## Critical Workflow Understanding

### Discovery Phase
- Discover routes from code constants + Playwright traversal
- Normalize routes and store in SQLite
- **MANDATORY**: Create EXPLORE tasks for each route using Vibe-Kanban MCP
- Task naming: `{user-level}-route-explore-{number}`
- Rate limiting: sleep(1) between creations, exponential backoff on 429
- Mark discovery complete ONLY after all EXPLORE tasks created

### Exploration Phase (Agents pick up EXPLORE tasks)
- Start browser session, authenticate, navigate
- Use Playwright MCP to manually explore route
- Document all UI elements, interactions, states
- Record all Playwright MCP calls made
- Check for new routes, create new EXPLORE tasks if found
- **Create TEST task during exploration** with Playwright code
- Mark EXPLORE task complete

### Test Phase (Agents pick up TEST tasks)
- Read Playwright code from TEST task description
- Refine into proper test structure
- Run and verify tests pass
- Mark TEST task complete

## File Structure

```
agents-environment-config/
├── .claude/skills/ui-audit/
│   ├── SKILL.md                    # Main skill definition
│   ├── templates/                  # Task templates
│   │   ├── discover-routes.md     # Discovery task template
│   │   ├── explore-route.md       # Route exploration task template
│   │   ├── test-route.md          # Test writing task template
│   │   ├── helper-*.md            # Helper task templates
│   │   └── bug-report.md         # Bug task template
│   └── scripts/                   # Utility scripts
│       ├── detect-auth.mjs        # Auth method detection
│       └── create-explore-tasks.mjs # Task creation with rate limiting
├── .cursor/commands/skills/
│   └── ui-audit.md                # Cursor command wrapper
└── docs/                          # Documentation
    └── ui-audit/
        ├── README.md              # Usage guide
        └── workflow.md            # Workflow documentation
```

## Implementation Tasks

### Phase 1: Core Infrastructure

1. **Create skill directory structure**
   - Create `.claude/skills/ui-audit/` directory
   - Set up `templates/` and `scripts/` subdirectories

2. **Copy and adapt files from SCF-Neue**
   - Copy `CONTEXT_CACHE/ui-audit-bootstrap.mjs` → adapt for generic use
   - Copy `CONTEXT_CACHE/schema.sql` → keep as-is (SQLite schema)
   - Copy `tests/AUDIT-TASKS-GUIDANCE.md` → adapt as reference documentation
   - Copy `docs/testing/generalized-ui-testing-plan.md` → adapt as workflow guide

3. **Create CONTEXT_CACHE management**
   - Script to detect git repo root (handles worktrees)
   - Ensure `CONTEXT_CACHE/` at repo root
   - Auto-add to `.gitignore` if missing
   - Cleanup script for end-of-process

### Phase 2: Skill Definition

4. **Create main SKILL.md**
   - Skill metadata (name, description, license)
   - Input parameters: user types list, base URL (optional), project ID (auto-detect)
   - MCP requirements: Playwright, Vibe-Kanban
   - Workflow overview emphasizing EXPLORE task creation

5. **Implement auth detection logic**
   - Analyze codebase for auth patterns (magic link, OAuth, session, etc.)
   - Create `scripts/detect-auth.mjs` utility
   - Output auth method and required helpers

6. **Create task templates**
   - `discover-routes.md`: Discovery task with MANDATORY EXPLORE task creation
     - Must include Vibe-Kanban MCP code example with rate limiting
     - Explicit checklist that task creation is completion requirement
     - Task naming convention: `{user-level}-route-explore-{number}`
   - `explore-route.md`: Route exploration using Playwright MCP
     - Clear instructions: "Start browser session, authenticate, navigate"
     - Document all UI elements, record all Playwright MCP calls
     - Check for new routes, create new EXPLORE tasks if found
     - Create TEST task during exploration with Playwright code
   - `test-route.md`: Test writing (created by agent during exploration)
     - Task description contains Playwright code from exploration
     - Refine code into proper test structure
   - `helper-login.md`: Login helper (blocks TEST tasks until complete)
   - `helper-profile.md`: Profile completion helper
   - `bug-report.md`: Bug reporting template

### Phase 3: Task Creation Logic

7. **Discovery task logic (CRITICAL: Must create EXPLORE tasks programmatically)**
   - Discover routes from code constants + Playwright traversal
   - Normalize routes (lowercase, strip trailing slash, `:id`/`:slug` replacement)
   - UPSERT to SQLite (status='discovered')
   - **MANDATORY COMPLETION STEP**: For EACH discovered route:
     - Check if `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{normalized-route}/route.txt` exists
     - If NOT exists:
       - Create EXPLORE task via Vibe-Kanban MCP `create_task`
       - Task name: `{user-level}-route-explore-{number}`
       - Sleep(1) between creations
       - Handle 429 errors: increase delay by 0.5s, retry
       - Write `route.txt` file with task ID
       - Track tasks in parent discovery task checklist
   - Update parent discovery task with checklist of all created tasks
   - Mark discovery task complete ONLY after all EXPLORE tasks created

8. **Explore task logic (Agents execute)**
   - Start browser session, authenticate as specified user type
   - Navigate to route using Playwright MCP (manual exploration)
   - Document all UI elements, forms, interactions, states
   - Record all Playwright MCP calls made
   - Exercise all sub-navigation, modals, links
   - Check for new routes (create new EXPLORE tasks if found)
   - **Create TEST task during exploration** with Playwright code
   - Update this task with findings summary
   - Mark complete

9. **Test task logic (Agents execute)**
   - Read Playwright code from task description
   - Check HELPER dependencies (block if incomplete)
   - Refine code into proper test structure
   - Run tests and verify they pass
   - Mark complete

10. **Helper task logic**
    - Implement auth/profile completion helpers
    - Test helper works with Playwright
    - Document helper usage in guidance
    - Mark complete

### Phase 4: Rate Limiting Implementation

11. **Create task creation script with rate limiting**
    - `scripts/create-explore-tasks.mjs`
    - Initial delay: 1000ms (1 second)
    - On 429 error: increase delay by 500ms (0.5 seconds)
    - Maximum retries: 3 per task
    - Log progress and errors
    - Continue on errors, report summary at end

### Phase 5: Cursor Command Wrapper

12. **Create Cursor command**
    - `.cursor/commands/skills/ui-audit.md`
    - Reference skill: `{{file:~/.claude/skills/ui-audit/SKILL.md}}`
    - Command metadata (name, description, tags)
    - Usage instructions
    - Emphasize: "Discovery phase creates EXPLORE tasks automatically - do not skip this step"

### Phase 6: Project Integration

13. **Vibe-Kanban project detection**
    - Get current working directory
    - Query Vibe-Kanban MCP `list_projects`
    - Match `git_repo_path` to current directory
    - Fail with clear error if multiple matches or no match

14. **CONTEXT_CACHE cleanup**
    - Script to safely remove `CONTEXT_CACHE/UI_AUDIT/*` after audit cycle
    - Preserve bootstrap files (bootstrap.mjs, schema.sql)
    - Document when to run cleanup

### Phase 7: Documentation

15. **Create usage documentation**
    - `docs/ui-audit/README.md`: Quick start guide
    - `docs/ui-audit/workflow.md`: Detailed workflow explanation
       - Emphasize: Discovery → EXPLORE Task Creation → Manual Exploration → TEST Task Creation → Test Writing
       - Make it clear: Discovery is NOT done until EXPLORE tasks created
       - Show example of proper task creation code with rate limiting
       - Explain task naming convention: `{user-level}-route-explore-{number}`
       - Explain that agents create TEST tasks during exploration (not upfront)
    - Task lifecycle diagrams showing mandatory task creation step
    - Examples for different auth methods
    - Common mistakes section: "Don't skip task creation", "Agents create TEST tasks during exploration"

16. **Update existing files**
    - Adapt guidance docs from SCF-Neue for generic use
    - Update references to project-specific paths
    - Make templates project-agnostic

## Task Template Requirements

Following project-manager-senior agent criteria, each task must include:

- **Clear Title**: Action-oriented (e.g., "AUDIT-001: Discover {USER_TYPE} routes")
- **Description** with:
  - Prerequisites checklist
  - Step-by-step instructions
  - Acceptance criteria (testable, specific)
  - Files to create/edit
  - References to related docs
- **Completion Criteria**: Explicit definition of "done"
- **CRITICAL**: Discovery tasks MUST create EXPLORE tasks programmatically using Vibe-Kanban MCP
- **Task Naming Convention**: `{user-level}-route-explore-{number}` (e.g., `super-admin-route-explore-001`)
- **Rate Limiting**: sleep(1) between task creations, handle 429 errors by increasing delay by 0.5s
- **MANDATORY**: No "next steps" sections - instead, create the actual tasks as completion step
- **Discovery task template** must include explicit checklist:
  ```
  ## Completion Checklist
  - [ ] All routes discovered and stored in SQLite
  - [ ] For EACH route: Created {user-level}-route-explore-### task via Vibe-Kanban MCP create_task
  - [ ] For EACH route: Wrote CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt
  - [ ] Updated parent task with checklist of all created tasks
  - [ ] Verified all tasks created successfully
  - [ ] Rate limiting handled (429 errors with exponential backoff)
  ```
- **Explore task template** must state: "Use Playwright MCP to manually explore this route, create TEST task during exploration"

## Files to Copy and Adapt

From `/Users/mattbernier/projects/SCF-Neue/`:
- `CONTEXT_CACHE/ui-audit-bootstrap.mjs` → Generic bootstrap script
- `CONTEXT_CACHE/schema.sql` → Keep as-is
- `tests/AUDIT-TASKS-GUIDANCE.md` → Reference documentation
- `docs/testing/generalized-ui-testing-plan.md` → Workflow guide

## Technical Requirements

- **Node.js**: Bootstrap script uses ES modules
- **SQLite**: Database for route tracking
- **MCP Servers**: Playwright MCP, Vibe-Kanban MCP (npx vibe-kanban)
- **Git**: Detect repo root (handles worktrees)
- **File System**: Create CONTEXT_CACHE at repo root, manage .gitignore
- **Vibe-Kanban MCP**: Must be used programmatically to create EXPLORE tasks (not manual)
- **Rate Limiting**: sleep(1) between task creations, exponential backoff on 429 errors (+0.5s increments)
- **Task Naming**: `{user-level}-route-explore-{number}` format (e.g., `super-admin-route-explore-001`)

## Testing Strategy

- Test in a sample project with different auth methods
- Verify CONTEXT_CACHE creation at repo root
- Verify .gitignore handling
- **CRITICAL**: Verify discovery task creates EXPLORE tasks programmatically via Vibe-Kanban MCP
- Verify rate limiting works (1s delay, 429 handling)
- Verify task naming convention (`{user-level}-route-explore-{number}`)
- Verify agents cannot skip task creation step
- Verify explore tasks instruct Playwright MCP usage
- Verify explore tasks create TEST tasks during exploration (not upfront)
- Verify new route discovery creates new EXPLORE tasks
- Verify cleanup process

## Success Criteria

- Skill can be invoked from Claude Desktop
- Command can be invoked from Cursor
- Auto-detects project from git repo path
- Creates CONTEXT_CACHE at repo root with .gitignore entry
- Creates discovery tasks (one per user type)
- **CRITICAL**: Discovery tasks MUST create EXPLORE tasks programmatically (not just list next steps)
- Task naming follows convention: `{user-level}-route-explore-{number}`
- Rate limiting implemented (1s delay, 429 handling with +0.5s increments)
- Discovery task template makes task creation impossible to skip
- Explore tasks clearly instruct agents to use Playwright MCP for manual exploration
- Explore tasks instruct agents to create TEST tasks during exploration (not upfront)
- Agents can discover new routes and create new EXPLORE tasks dynamically
- Helper tasks block test tasks appropriately
- Cleanup script removes audit artifacts
- Documentation is clear and complete
- Workflow prevents agents from declaring victory before task creation

