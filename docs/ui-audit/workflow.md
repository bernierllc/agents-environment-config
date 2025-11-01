# UI Audit - Detailed Workflow Guide

## Overview

This document provides a detailed explanation of the UI audit workflow, including task lifecycle, ticket creation patterns, and best practices.

## Workflow Phases

### Phase 1: Discovery

**Purpose**: Discover all navigable routes for a user type and create EXPLORE tasks.

**Steps**:

1. **Bootstrap** (if not already done):
   ```bash
   node CONTEXT_CACHE/ui-audit-bootstrap.mjs --user-level {user-type}
   ```

2. **Discover Routes**:
   - Seed from route constants or sitemap
   - Authenticate as user type
   - Traverse UI using Playwright MCP
   - Normalize routes (lowercase, strip trailing slash, `:id` replacement)

3. **Store Routes**:
   - UPSERT to SQLite database (`CONTEXT_CACHE/ui_audit.db`)
   - Table: `routes`
   - Status: `discovered`

4. **Create EXPLORE Tasks** (MANDATORY):
   - For EACH discovered route:
     - Check `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{route}/route.txt`
     - If NOT exists:
       - Create task via Vibe-Kanban MCP: `{user-type}-route-explore-{number}`
       - Rate limiting: sleep(1) between creations
       - Handle 429 errors: increase delay by 0.5s
       - Write `route.txt` with task ID
   - Update parent task with checklist

**Completion Criteria**:
- ✅ All routes discovered and stored in SQLite
- ✅ EXPLORE tasks created for every route
- ✅ No duplicate tasks (de-duplication files exist)
- ✅ Rate limiting handled correctly

**CRITICAL**: Discovery is NOT complete until all EXPLORE tasks are created!

### Phase 2: Exploration

**Purpose**: Manually explore each route and document findings.

**Steps** (for each EXPLORE task):

1. **Start Browser Session**:
   ```javascript
   const browser = await playwright.launch({ headless: false });
   const page = await browser.newPage();
   ```

2. **Authenticate**:
   - Use HELPER-002 (login helper)
   - Use HELPER-004 (profile completion) if needed

3. **Navigate**:
   ```javascript
   await page.goto('{base_url}{route}');
   await page.waitForLoadState('networkidle');
   ```

4. **Explore and Document**:
   - All UI elements (buttons, links, forms, inputs)
   - All interactions (clicks, submissions, navigation)
   - All states (empty, loading, populated, error)
   - **Record ALL Playwright MCP calls**

5. **Check for New Routes**:
   - Extract URLs from links/navigation
   - Normalize and check SQLite database
   - If new route: create EXPLORE task, add to database

6. **Create TEST Task**:
   - Task name: `{user-type}-route-test-{number}`
   - Paste ALL Playwright code from exploration
   - Add coverage checklist
   - Add edge cases
   - Add data requirements

7. **Update and Complete**:
   - Update EXPLORE task with findings summary
   - Mark complete

**Completion Criteria**:
- ✅ Route explored and documented
- ✅ TEST task created with Playwright code
- ✅ New routes discovered (if any) handled
- ✅ EXPLORE task updated with summary

### Phase 3: Test Writing

**Purpose**: Implement and verify Playwright tests.

**Steps** (for each TEST task):

1. **Read Playwright Code**:
   - Extract code from TEST task description (created during exploration)

2. **Refine into Test Structure**:
   ```typescript
   import { test, expect } from '@playwright/test';
   import { signInAsRegular } from '../helpers/auth';
   import { ensureProfileComplete } from '../helpers/profile';

   test.describe('{route} - {user-type}', () => {
     test.beforeEach(async ({ page }) => {
       await signInAsRegular(page);
       await ensureProfileComplete(page);
     });

     test('should load route successfully', async ({ page }) => {
       // Refined code from exploration
     });
   });
   ```

3. **Implement Coverage Checklist**:
   - All items from exploration checklist
   - Proper assertions
   - Error handling

4. **Run Tests**:
   ```bash
   npx playwright test tests/{user-type}/{normalized-route}.spec.ts
   ```

5. **Handle Failures**:
   - UI mismatch: Adjust selectors
   - Timing issues: Add robust waits
   - Product bug: Create BUG task, mark blocked
   - Missing data: Document requirements

6. **Complete**:
   - Tests pass
   - Test file path documented
   - Task marked complete

**Completion Criteria**:
- ✅ Test file created
- ✅ All coverage items implemented
- ✅ Tests pass locally
- ✅ Tests are deterministic

## Task Lifecycle

```
Discovery Task
    ↓
    Creates EXPLORE Tasks (one per route)
    ↓
    [Discovery Complete]
    
EXPLORE Task
    ↓
    Explores Route
    ↓
    Creates TEST Task (with Playwright code)
    ↓
    [EXPLORE Complete]
    
TEST Task
    ↓
    Writes Tests
    ↓
    Tests Pass
    ↓
    [TEST Complete]
```

## Rate Limiting Strategy

**Initial Configuration**:
- Delay: 1000ms (1 second)
- Max retries: 3 per task

**On Success**:
- Continue with same delay
- Reset consecutive error count

**On 429 Error**:
- Increase delay by 500ms (0.5 seconds)
- Wait double the delay before retry
- Retry up to 3 times

**On Other Errors**:
- Log error
- Continue with same delay
- Don't increase delay for non-429 errors

## De-duplication Strategy

**File-based Cache**:
- Location: `CONTEXT_CACHE/UI_AUDIT/{USER_TYPE}/{normalized-route}/route.txt`
- Content: Task ID (string)
- Purpose: Prevent duplicate task creation

**Check Before Create**:
```javascript
const routePath = `CONTEXT_CACHE/UI_AUDIT/${userType}/${normalizedRoute}/route.txt`;
if (fs.existsSync(routePath)) {
  // Task already exists, skip
  continue;
}
// Create task and write route.txt
```

## Common Mistakes

### ❌ Discovery Lists "Next Steps" Instead of Creating Tasks

**Wrong**:
```markdown
## Next Steps
- Create EXPLORE tasks for each route
- ...
```

**Right**:
- Actually create EXPLORE tasks using Vibe-Kanban MCP
- Update parent task with checklist of created tasks

### ❌ Agents Skip Task Creation

**Prevention**:
- Discovery template includes explicit checklist
- Checklist requires task creation as completion step
- No "next steps" section allowed

### ❌ TEST Tasks Created Upfront

**Wrong**: Discovery creates both EXPLORE and TEST tasks

**Right**: EXPLORE tasks create TEST tasks during exploration

### ❌ No Rate Limiting

**Wrong**: Create all tasks at once

**Right**: Sleep(1) between creations, handle 429 errors

## Best Practices

1. **Always check de-duplication** before creating tasks
2. **Always implement rate limiting** for Vibe-Kanban API calls
3. **Record all Playwright calls** during exploration
4. **Create TEST tasks during exploration**, not after
5. **Handle 429 errors gracefully** with exponential backoff
6. **Update parent tasks** with checklists of created tasks

## References

- Task Templates: `.claude/skills/ui-audit/templates/`
- Scripts: `.claude/skills/ui-audit/scripts/`
- SKILL.md: `.claude/skills/ui-audit/SKILL.md`

