# Verification Writer Skill — Design Spec

**Date:** 2026-03-25
**Status:** Approved
**Related:** browser-verification skill

## Overview

A skill that analyzes a codebase to generate and maintain manual verification docs (`docs/verification/*.md`) for use by the browser-verification skill. It audits every route, component, and interaction point across all user types, checks whether graceful error handling exists, and produces both verification checklists and a findings report of gaps.

This is the authoring counterpart to browser-verification. Verification-writer creates and maintains the docs; browser-verification executes against them. The two skills form a feedback loop — browser-verification can invoke verification-writer when docs are stale, and verification-writer can suggest verification runs after updates.

## Skill Structure

```
verification-writer/
├── SKILL.md                          # Orchestration: phases, entry points, fix thresholds, output formats
├── references/
│   ├── codebase-analysis.md          # How to scan routes, trace components, detect error handling patterns
│   ├── verification-item-format.md   # Item syntax, depth tags, expectation types, user type annotations
│   └── findings-report-format.md     # Gap report structure, severity levels, fix-vs-log criteria
└── scripts/
    └── route-scanner.py              # Deterministic route discovery from app/ directory structure
```

## Entry Points

| Trigger | What happens |
|---|---|
| **New project** | Full scan of all routes, all user types. Generate complete `docs/verification/` structure. |
| **New feature** | Scan changed/added files (git diff), trace their routes and components, generate items for affected sections. |
| **After code changes** | Same as new feature but also checks existing verification docs for staleness against current code. |
| **On demand** | User specifies a route, feature, or role. Skill scans just that scope. |
| **Called by browser-verification** | Receives specific items that are stale or missing. Updates those sections and re-validates. |

The skill determines which entry point applies from context — git status, user's request, or whether it was invoked by browser-verification with a specific update payload.

## Phase 1: Codebase Analysis

The analysis phase builds a complete map of what's verifiable. It works in layers, each feeding the next.

### Layer 1: User Types and Access

- Scan auth configuration, middleware, role definitions, database schema for user/role tables
- Build a matrix of every user type in the system
- For each route discovered later, determine which user types can access it and which should be denied

### Layer 2: Route Discovery

- Walk `app/` directory structure for all page routes (including dynamic routes like `[id]`, catch-alls, parallel routes)
- Identify layouts, error boundaries, loading states, not-found pages
- Map `app/api/` endpoints to the UI routes that call them
- `route-scanner.py` handles the deterministic directory walk; the skill handles the semantic analysis of what's on each route

### Layer 3: Component Analysis

- For each route, read the page file and trace imports
- Categorize what's on the page: forms (with their fields and validation), tables (with sorting/filtering/pagination), CRUD operations, modals, navigation elements, state-dependent UI
- Note which components are shared (used across multiple routes) — these get extra scrutiny

### Layer 4: Error Path Analysis

For every interaction point found in Layer 3:

| What it looks for | How it determines graceful handling exists |
|---|---|
| Form submission | Has validation (client-side and/or server-side), shows user-facing error messages, doesn't expose stack traces |
| API calls | Has try/catch or error boundary, UI shows meaningful error state, loading/error states exist |
| Auth boundaries | Middleware redirects unauthorized users, no flash of protected content, appropriate error page |
| Data loading | Has loading state, has empty state, handles null/undefined without crashing |
| Destructive actions | Has confirmation dialog, has undo or clear warning, handles failure of the destructive operation itself |
| External dependencies | Handles third-party service being down, shows degraded state rather than crash |

For each interaction point, the skill records one of:
- **Handled** — graceful error handling exists in the code. Document what the expected behavior is.
- **Partial** — some handling exists but it's incomplete (e.g., client validation but no server validation). Document what exists, flag what's missing.
- **Missing** — no error handling. This goes in the findings report.

**Code is the source of truth.** Tests are a useful hint for discovering what error paths were intended, but the code determines what actually exists. Tests may be stale.

**Output of Phase 1:** A structured map of `route -> user types -> components -> interaction points -> error handling status`.

## Phase 2: Output Generation

### Output 1: Verification Docs (`docs/verification/*.md`)

Organized by role/user type. Each file covers all routes that user type can access. Items use a single-doc, tiered-annotation format:

```markdown
# Verification: Admin

## Prerequisites
- Admin account: admin@example.com
- Requires: running Supabase, seeded test data

## Dashboard (/admin/dashboard)

- [ ] [smoke] **Navigate to /admin/dashboard** --- Page loads, main layout renders, no console errors. *Expected: success*
- [ ] [standard] **Verify stats cards populate** --- Cards show numeric values, not loading spinners or "undefined". *Expected: success*
- [ ] [deep] **Load dashboard with no users in database** --- Empty state message displays, no broken layout. *Expected: graceful empty state*
- [ ] [deep] **Load dashboard with Supabase connection dropped** --- Error boundary renders, message suggests retry. Console shows connection error, no unhandled exception. *Expected: graceful server error*

## Auth Boundaries

- [ ] [standard] **Access /admin/users as student role** --- Redirect to student dashboard. No flash of admin content. *Expected: auth boundary enforcement*
- [ ] [deep] **Access /admin/users with expired session** --- Redirect to login. Session-expired message shown. *Expected: auth boundary enforcement*
```

**Item format:** `- [ ] [depth] **Action** --- Expected result. *Expected: type*`

**Depth tags:** `smoke`, `standard`, `deep` — matching browser-verification's three tiers. Browser-verification filters at runtime; smoke items are a subset of standard, which is a subset of deep.

**Expectation types:**
- `success` — happy path works
- `warning dialog` — user gets warned before destructive action
- `client-side validation error` — bad input caught before hitting server
- `graceful server error` — server rejects, UI handles gracefully
- `auth boundary enforcement` — access control works correctly
- `success with side effects` — works AND downstream effects happen
- `graceful empty state` — no data scenario handled with appropriate UI

### Output 2: Findings Report (`docs/verification/findings/YYYY-MM-DD-analysis.md`)

```markdown
# Verification Analysis Findings - YYYY-MM-DD

## Summary
- Routes analyzed: X
- Interaction points found: X
- Fully handled: X | Partial: X | Missing: X
- Auto-fixed: X | Needs manual fix: X | Needs architecture discussion: X

## Auto-Fixes Applied
### Fix: [description]
- Files changed: ...
- Lines changed: X
- What was missing: ...

## Gaps Requiring Manual Fix
### Gap: [route] — [what's missing]
- Severity: high | medium | low
- Route: ...
- What happens now: ...
- What should happen: ...
- Affected user types: ...
- Suggested approach: ...

## Systemic Issues
### Issue: [description]
- Affected routes: X routes across Y user types
- What's happening: ...
- Recommended approach: ...
```

### Output 3: Updated Index (`docs/verification/index.md`)

Master index listing all verification files, prerequisites, login credentials, and the date each file was last generated/updated.

## Fix Behavior

Fix thresholds are identical to browser-verification — ALL must be true:
- < 75 lines of changes
- Isolated to <= 3 components
- Isolated to <= 2 routes
- Does NOT touch shared code

**What verification-writer can fix:**
- Missing client-side validation on a form
- Missing error boundary wrapper on a route
- Missing confirmation dialog on a destructive action (if a ConfirmDialog component already exists in the codebase)
- Missing loading/empty states

**What it logs as a gap instead:**
- No consistent error handling pattern exists across the app
- Shared component needs error handling but is used by 5+ routes
- Auth middleware needs restructuring
- Database constraints are missing
- Third-party integration has no fallback strategy

**After fixes:**
1. Update the verification doc to reflect the fix
2. Add the fix to the findings report under "Auto-Fixes Applied"
3. Run the project's test suite to confirm the fix didn't break anything
4. If tests fail, revert the fix and log it as a gap instead

**Report always generated** — even if there are zero gaps. The findings report is a point-in-time snapshot of verifiability health.

## Cross-Skill Integration

### Browser-verification -> verification-writer

During a verification run, browser-verification detects staleness when:
- A checklist item describes UI that no longer exists
- A checklist item's expected behavior doesn't match actual code behavior
- Interactive elements on a page have no checklist items at all
- A fix was applied during verification that changes expected behavior

Browser-verification invokes verification-writer with a specific payload describing what's stale, missing, or changed. Verification-writer re-analyzes that section against current code and updates the doc.

### Verification-writer -> browser-verification

After generating or updating verification docs, verification-writer suggests (but does not automatically invoke) a smoke or standard verification run to confirm accuracy.

### Shared Contracts

| Contract | Owned by | Consumed by |
|---|---|---|
| Item format: `- [ ] [depth] **Action** --- Result. *Expected: type*` | verification-writer | browser-verification |
| Depth tags: `smoke`, `standard`, `deep` | Both (must match) | Both |
| Expectation types | verification-writer | browser-verification |
| Fix thresholds | Both (identical rules) | Both |
| File locations: `docs/verification/*.md`, `docs/verification/findings/`, `docs/verification/logs/` | verification-writer (docs, findings), browser-verification (logs) | Both |

### Browser-verification update: graceful failure as implicit standard

Every PASS/FAIL determination gets this baseline rule:

> A feature is not PASS if it works on the happy path but fails ungracefully on any expected error path. "Works but crashes ugly" is FAIL. The expectation type on each item tells you what kind of outcome to verify. If an item has no explicit error path items nearby, test basic error scenarios anyway and flag missing coverage back to verification-writer.
