---
name: "verification-writer"
description: "Use when generating, updating, or auditing manual verification docs (docs/verification/*.md) for browser-based QA. Analyzes codebase routes, components, forms, error handling, and user types to produce tiered verification checklists and a findings report of gaps. Also invoked by browser-verification when docs are stale or missing."
tags: "["skill"]"
---

# Verification Writer

## Overview

Analyze a codebase to generate and maintain manual verification docs for use by the browser-verification skill. Audit every route, component, and interaction point across all user types. Check whether graceful error handling exists. Produce verification checklists AND a findings report of gaps.

**Core principle:** Every user-facing interaction has a happy path and failure paths. Both must be verifiable. If code doesn't handle failure gracefully, that's a finding — flag it, fix it if small, or report it.

**Relationship to browser-verification:** This skill creates and maintains the docs. Browser-verification executes against them. The two form a feedback loop.

## Entry Points

Determine which applies from context:

| Trigger | Scope |
|---|---|
| **New project** | Full scan: all routes, all user types, complete `docs/verification/` scaffold |
| **New feature** | Git diff to find changed/added files, trace to routes and components, generate items for affected sections |
| **After code changes** | Same as new feature + check existing docs for staleness against current code |
| **On demand** | User specifies route, feature, or role — scan just that scope |
| **Called by browser-verification** | Specific items are stale/missing — update those sections, re-validate |

## Checklist

You MUST complete these in order:

1. **Determine scope and entry point**
2. **Determine doc location and organization** (first run only)
3. **Run Phase 1: Codebase Analysis**
4. **Run Phase 2: Generate outputs**
5. **Apply fixes within thresholds**
6. **Run test suite to verify fixes**
7. **Produce findings report**
8. **Suggest verification run**

## Doc Location and Organization

**On first run in a project (no existing verification docs):** Ask the user before generating anything:

### Where to put the docs

Default: `docs/verification/`. But ask:

> "I'll generate verification docs for this project. Where would you like them? Default is `docs/verification/` — or specify a different path."

Accept whatever path they give. If they have an existing `docs/` structure, suggest something that fits (e.g., `docs/qa/verification/`, `docs/testing/verification/`). Store the chosen path and use it consistently.

### How to organize the files

Analyze what was found in Phase 1 (user types, route count, feature count) and propose an organization that fits the project:

**Multi-role apps (2+ user types, role-based routing):**
One file per role + shared. This is the default for projects with role-based access.

```
verification/
├── index.md
├── admin.md
├── educator.md
├── student.md
├── shared.md          # Public pages, cross-role components
├── findings/
└── logs/
```

**Single-role or no-role apps (one user type, or no auth):**
Organize by feature area instead of role.

```
verification/
├── index.md
├── authentication.md
├── dashboard.md
├── settings.md
├── billing.md
├── shared.md          # Common components, navigation
├── findings/
└── logs/
```

**Large apps (50+ routes):**
Split further — one file per major feature area within each role, or by product section.

```
verification/
├── index.md
├── admin/
│   ├── user-management.md
│   ├── settings.md
│   └── analytics.md
├── educator/
│   ├── classes.md
│   ├── assignments.md
│   └── gradebook.md
├── shared.md
├── findings/
└── logs/
```

**API-only projects (no UI routes):**
Organize by API domain. Items verify API responses, error codes, and auth boundaries via `curl` or API testing tools rather than browser interaction.

```
verification/
├── index.md
├── auth-endpoints.md
├── user-endpoints.md
├── data-endpoints.md
├── webhook-endpoints.md
├── findings/
└── logs/
```

**Present your recommendation to the user based on what Phase 1 found:**

> "This project has [X] user types and [Y] routes. I'd recommend organizing verification docs as [describe structure]. Does that work, or would you prefer a different breakdown?"

### When to split a file

A verification file should be split when:
- It exceeds 300 checklist items (too large to navigate)
- It covers 10+ unrelated feature sections (too broad)
- A single section has 50+ items (that section deserves its own file)

When splitting, update the index and any cross-references. Tell the user what you split and why.

### On subsequent runs

Check the existing structure and follow it. Don't reorganize without asking. If the project has grown enough that the current organization is strained (files getting too large), suggest a restructure but don't do it automatically.

## Phase 1: Codebase Analysis

Read `references/codebase-analysis.md` for detailed heuristics. Summary:

### Layer 1: User Types and Access

- Scan auth config, middleware, role definitions, database schema for user/role tables
- Build a matrix of every user type in the system
- For each route: determine which user types can access it and which should be denied

### Layer 2: Route Discovery

- Walk `app/` directory structure for all page routes (dynamic, catch-all, parallel, layouts, error boundaries, loading/not-found)
- Map `app/api/` endpoints to the UI routes that call them
- Run `scripts/route-scanner.py` for deterministic directory walk if available; otherwise walk manually

### Layer 3: Component Analysis

- For each route, read the page file and trace imports
- Categorize: forms (fields, validation), tables (sort/filter/pagination), CRUD operations, modals, navigation, state-dependent UI
- Flag shared components (used across multiple routes)

### Layer 4: Error Path Analysis

For every interaction point from Layer 3, determine error handling status:

| Interaction | What constitutes graceful handling |
|---|---|
| Form submission | Client-side AND server-side validation, user-facing error messages, no exposed stack traces |
| API calls | try/catch or error boundary, meaningful error UI, loading/error states |
| Auth boundaries | Middleware redirects unauthorized users, no flash of protected content |
| Data loading | Loading state, empty state, handles null/undefined without crash |
| Destructive actions | Confirmation dialog, failure of the action itself handled |
| External dependencies | Service-down fallback, degraded state rather than crash |

Record each as:
- **Handled** — graceful error handling exists. Document expected behavior.
- **Partial** — some handling exists, incomplete. Document what exists, flag what's missing.
- **Missing** — no error handling. Goes in findings report.

**Code is the source of truth.** Tests are a hint for discovering intended error paths, but the code determines what actually exists.

## Phase 2: Generate Outputs

Read `references/verification-item-format.md` for item syntax details.

### Output 1: Verification Docs

Written to the location and structure determined in "Doc Location and Organization" above. Each file covers the scope assigned to it (by role, by feature, or by API domain).

**Item format:** `- [ ] [depth] **Action** --- Expected result. *Expected: type*`

**Depth tags:** `smoke`, `standard`, `deep` — must match browser-verification tiers.

**Expectation types:**
- `success` — happy path works
- `warning dialog` — warned before destructive action
- `client-side validation error` — bad input caught before server
- `graceful server error` — server rejects, UI handles gracefully
- `auth boundary enforcement` — access control works
- `success with side effects` — works AND downstream effects happen
- `graceful empty state` — no-data scenario handled appropriately

**Generation rules:**
- Every route gets at minimum a `[smoke]` item (page loads without error)
- Every form gets `[standard]` items for valid submission AND `[deep]` items for empty/invalid/boundary submissions
- Every CRUD operation gets `[standard]` items for each operation AND `[deep]` items for conflict/failure states
- Every auth boundary gets `[standard]` items for wrong-role access
- Every destructive action gets `[standard]` items verifying the confirmation flow
- Every error path that has graceful handling gets a `[deep]` item to verify the graceful behavior

**Items for Partial/Missing handling:** If error handling is Partial, write the item documenting what SHOULD happen (so browser-verification will find the gap). If Missing, write the item only after the fix is applied or note it in the findings report.

### Output 2: Findings Report (`<verification-path>/findings/YYYY-MM-DD-analysis.md`)

Read `references/findings-report-format.md` for full template.

Always generated, even if zero gaps found. Includes:
- Summary stats (routes analyzed, interaction points, handled/partial/missing counts)
- Auto-fixes applied (with file/line details)
- Gaps requiring manual fix (with severity, current vs. expected behavior, suggested approach)
- Systemic issues (patterns affecting multiple routes/user types)

### Output 3: Index (`<verification-path>/index.md`)

Master index: all verification files, prerequisites, login credentials, date each file was last generated/updated.

## Fix Behavior

Thresholds identical to browser-verification — ALL must be true:
- < 75 lines of changes
- Isolated to <= 3 components
- Isolated to <= 2 routes
- Does NOT touch shared code (shared components, utilities, middleware, hooks used across features)

**Can fix:**
- Missing client-side validation on a form
- Missing error boundary wrapper on a route
- Missing confirmation dialog on destructive action (if ConfirmDialog component already exists in codebase)
- Missing loading/empty states

**Must log as gap:**
- No consistent error handling pattern across the app
- Shared component needs error handling but used by 5+ routes
- Auth middleware needs restructuring
- Database constraints missing
- Third-party integration has no fallback

**After every fix:**
1. Update the verification doc to reflect the fix
2. Add to findings report under "Auto-Fixes Applied"
3. Run the project's test suite — if tests fail, revert and log as gap instead

## Cross-Skill Integration

### When invoked by browser-verification

Browser-verification sends a payload describing what's stale:
- Section and route affected
- Stale items (UI changed, behavior changed)
- Missing items (uncovered elements found)
- Fixed items (verification updated behavior during a run)

Re-analyze that specific section against current code. Update the doc. Return control to browser-verification.

### After generating/updating docs

Suggest (do not auto-invoke) a verification run:

> "Verification docs updated for [scope]. Run `/browser-verification` at smoke depth to confirm these items are accurate?"

## Memory Integration

After determining the doc location, organization, and log preferences for a project, **save this to memory** so that both verification-writer and browser-verification can find it in future sessions without re-asking.

**What to save (project memory):**

```markdown
---
name: verification-docs-config
description: Verification doc location, organization, and preferences for [project name]
type: project
---

Verification docs for [project name] are at `<verification-path>/`.

Organization: [by role | by feature | by API domain | nested by role]
Files: [list the files that exist]
Git tracking: [logs gitignored, findings tracked | both tracked | both gitignored]
Log cleanup: [keep 5 most recent | keep all]

**Why:** Configured on [date] during initial verification-writer run.
**How to apply:** browser-verification reads this to find docs. verification-writer reads this to know where to write and how to organize.
```

**When to save:** After the user confirms the location, organization, and preferences in the first run. Update the memory whenever files are added, split, or reorganized.

**When to read:** At the start of every verification-writer AND browser-verification run. If this memory doesn't exist, verification-writer should ask the user and create it. If browser-verification reads it and the docs don't exist at the specified path, it should tell the user to run verification-writer first.

## Log and Report Management

**On first run in a project:** After determining the doc location, ask:

1. **Git tracking:** "Should verification logs and findings reports be tracked in git, or should I add `<verification-path>/logs/` and `<verification-path>/findings/` to `.gitignore`?"
   - If gitignored: add both paths to `.gitignore`
   - If tracked: leave `.gitignore` unchanged — logs become part of project history
   - Default suggestion: track findings reports (they document code quality over time), gitignore run logs (they're ephemeral)

2. **Old report cleanup:** "Should I clean up old findings reports, or keep them all for history?"
   - If cleanup: keep only the most recent 5 findings reports, delete older ones
   - If keep all: leave everything
   - This question applies to findings only — verification docs themselves are never auto-deleted

**On subsequent runs:** Check the established pattern (is `.gitignore` already configured?) and follow it. Don't re-ask unless the user brings it up.

## Common Mistakes

| Mistake | Prevention |
|---|---|
| Generating items for code that doesn't exist yet | Code is source of truth — only document what's actually in the codebase |
| Skipping error path analysis | Every interaction point gets Layer 4 analysis, no exceptions |
| Writing items without expectation types | Every item must have `*Expected: type*` — browser-verification needs this |
| Fixing shared code without asking | Check import graph — if used across features, log as gap |
| Generating docs without checking for existing ones | Always read existing `docs/verification/` first — update, don't overwrite |
| Trusting tests over code | Tests are hints. Code is truth. Tests may be stale. |
| Ignoring partial handling | Partial is not handled — flag what's missing |
| Not running test suite after fixes | Every fix must be verified by tests before committing |

## Red Flags — STOP

- About to overwrite manually-curated verification docs without checking diff
- Fix touches shared code or exceeds thresholds
- Analysis shows systemic absence of error handling (> 50% of interaction points missing) — this needs architecture discussion, not item-by-item fixes
- User type discovery finds no roles — auth system may not be conventional, ask the user
