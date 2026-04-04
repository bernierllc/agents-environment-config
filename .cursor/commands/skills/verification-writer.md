---
name: "verification-writer"
description: "Use when generating, updating, or auditing manual verification docs (docs/verification/*.md) for browser-based QA. Analyzes codebase routes, components, forms, error handling, and user types to produce tiered verification checklists and a findings report of gaps. Also invoked by browser-verification when docs are stale or missing."
tags: "["skill"]"
---

# Verification Writer

## Overview

Analyze a codebase to generate and maintain manual verification docs for use by the browser-verification skill. Audit every route, component, and interaction point across all user types. Check whether graceful error handling exists. Produce verification checklists AND a findings report of gaps.

**Core principle:** Every user-facing interaction has a happy path and failure paths. Both must be verifiable. If code doesn't handle failure gracefully, that's a finding — flag it, fix it if small, or report it.

**Browser-first principle:** Verification items MUST be written for browser-based verification whenever possible. If a feature has a UI, the verification item tests through the UI — not by calling the API directly. API-only verification items are acceptable ONLY when there is no UI that exercises the functionality (e.g., webhook endpoints, cron handlers, internal service-to-service APIs). See "Browser-First Verification" below for details and flagging requirements.

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
6.5. **Generate/update flow visualizations**
7. **Produce findings report**
8. **Suggest verification run**

## Doc Location and Organization

**On first run in a project (no existing verification docs):** Ask the user before generating anything:

### Where to put the docs

Default: `docs/verification/`. But ask:

> "I'll generate verification docs for this project. Where would you like them? Default is `docs/verification/` — or specify a different path."

Accept whatever path they give. If they have an existing `docs/` structure, suggest something that fits (e.g., `docs/qa/verification/`, `docs/testing/verification/`). Store the chosen path and use it consistently.

**Visualizations:** The `visualizations/` directory is created automatically at step 6.5 alongside `pages/` and `flows/`. No user input needed for its location — it always sits under the verification root.

### How to organize the files

Verification docs are organized around three concepts: **pages**, **flows**, and **shared components**. This structure supports three access patterns that verification needs:

1. **"Verify this page"** — open the page file, run items for one or all user types
2. **"Verify this flow"** — open the flow file, run the ordered sequence across pages
3. **"Verify everything for this user type"** — the index maps user types to all pages and flows they touch

#### Directory structure

```
verification/
├── index.md              # Master index: pages, flows, user types, prerequisites
├── pages/                # One file per page or closely related page group
│   ├── event-create.md
│   ├── event-detail.md
│   ├── event-edit.md
│   ├── event-list.md
│   ├── magic-link-landing.md
│   ├── artist-profile.md
│   ├── public-event-page.md
│   ├── dashboard.md
│   ├── login.md
│   └── settings.md
├── flows/                # Ordered sequences across pages
│   ├── event-lifecycle.md
│   ├── artist-onboarding.md
│   ├── magic-link-flow.md
│   └── flyer-upload-flow.md
├── shared.md             # Cross-page components (nav, layout, toasts, modals)
├── findings/
├── logs/
└── visualizations/           # Flow diagrams and interactive map
    ├── event-lifecycle.md
    ├── artist-onboarding.md
    └── app-overview.html
```

#### Page files

Each page file covers a single page (or a tightly coupled group like create/edit for the same entity). Within the file, items are grouped by user type so the same page can be verified from each perspective.

```markdown
# Event Detail Page (`/events/{id}`)

## All User Types
<!-- Items that apply regardless of role: page loads, core content renders -->
- [ ] [smoke] **EVT-DTL-01** Navigate to `/events/{id}` --- Page loads without error. *Expected: success*

## As Admin
<!-- Admin-specific items: edit button, delete, workflow actions -->
- [ ] [standard] **EVT-DTL-ADM-01** Verify edit button is visible --- Edit button appears in header. *Expected: success*
- [ ] [standard] **EVT-DTL-ADM-02** Verify delete button with confirmation --- Clicking delete shows confirmation dialog. *Expected: warning dialog*

## As Promoter (via magic link)
<!-- Promoter-specific items: limited view, edit permissions for their fields -->
- [ ] [standard] **EVT-DTL-PRO-01** Verify promoter sees event details but not admin actions --- Event info displays, no edit/delete buttons. *Expected: success*

## As Public Visitor
<!-- Public-specific items: what should and shouldn't be visible -->
- [ ] [standard] **EVT-DTL-PUB-01** Verify public page shows event info without admin controls --- Event name, date, venue display. No edit, delete, or management buttons. *Expected: success*
```

**Naming convention for page files:** Use the entity or feature name, not the route path. `event-detail.md` not `events-id.md`. If a page has sub-pages (tabs, nested views), include them in the same file as sections unless they exceed 50 items, in which case split into `event-detail-overview.md`, `event-detail-artists.md`, etc.

**Item ID convention:** `{PAGE-ABBREV}-{SECTION}-{ROLE-ABBREV}-{NUMBER}`. The role abbreviation makes it easy to filter: `EVT-DTL-ADM-01` is an admin item on the event detail page, `EVT-DTL-PUB-01` is a public visitor item. Items in the "All User Types" section omit the role abbreviation: `EVT-DTL-01`.

#### Flow files

Flow files define ordered, cross-page verification sequences. They reference items from page files by ID and add flow-specific context (what state to set up, what to check between steps, what the end-to-end expectation is).

```markdown
# Flow: Event Lifecycle

## Purpose
Verify the complete event lifecycle from creation through artist/promoter interaction to final review.

## User types involved
Admin, Promoter, Artist

## Prerequisites
- Admin account with editor role
- At least one artist and one promoter in the system
- Mailpit running (for magic link delivery)

## Steps

### Step 1: Admin creates event
**Page:** event-create.md
**User type:** Admin
**Run items:** EVT-CRT-ADM-01 through EVT-CRT-ADM-05
**After this step:** Note the created event ID. Verify workflow engine fired (check event activities).

### Step 2: Promoter receives magic link
**Page:** magic-link-landing.md
**User type:** Promoter
**Setup:** Retrieve magic link from Mailpit for the promoter associated with the new event.
**Run items:** MLK-LND-PRO-01 through MLK-LND-PRO-04
**After this step:** Verify promoter can see event details.

### Step 3: Promoter fills in event details
**Page:** magic-link-landing.md (event details section)
**User type:** Promoter
**Run items:** MLK-EVT-PRO-01 through MLK-EVT-PRO-06
**After this step:** Verify changes are reflected in admin view (cross-user data integrity).

### Step 4: Admin reviews updated event
**Page:** event-detail.md
**User type:** Admin
**Run items:** EVT-DTL-ADM-01 through EVT-DTL-ADM-03
**Verify:** Promoter's changes are visible. Activity log shows the update. Deadline timers reflect correct state.

## End-to-end expectations
- Data created by admin is visible to promoter via magic link
- Data edited by promoter is reflected in admin view
- Activity log captures all changes across user types
- Workflow engine fired at each state transition
```

**Flow files are not independent item sets.** They reference page file items by ID. This means:
- Items are authored and maintained in page files (single source of truth)
- Flow files are lightweight orchestration — they define order, setup, and cross-step checks
- If a page file item is updated, every flow that references it automatically gets the update
- Flow-specific checks (cross-step state verification, data integrity between user types) live in the flow file as inline items or "After this step" notes

**When to create a flow file:** When a meaningful user journey spans 2+ pages or involves 2+ user types interacting with the same data. Not every multi-page interaction needs a flow file — only ones where the end-to-end behavior matters beyond individual page correctness.

#### Shared components file

`shared.md` covers components that appear across multiple pages: navigation, layout, toasts/notifications, modal patterns, error boundaries, loading states. Items here are not role-specific (they test the component itself), but they note which pages use the component.

```markdown
# Shared Components

## Navigation
- [ ] [smoke] **SHR-NAV-01** Verify main navigation renders on all authenticated pages --- Nav bar appears with correct links for the current user role. *Expected: success*
<!-- Used on: all pages in pages/ except login.md and public-*.md -->
```

#### How to decide what goes where

| Question | Answer |
|---|---|
| "I changed the event detail page" | Open `pages/event-detail.md`, run relevant sections |
| "I changed the event create form" | Open `pages/event-create.md`, run relevant sections |
| "Verify the countdown timer on event detail" | Open `pages/event-detail.md`, find the timer items (search by element name or item ID) |
| "Verify the full event lifecycle" | Open `flows/event-lifecycle.md`, run steps in order |
| "Verify everything the promoter sees" | Check `index.md` for all pages and flows that include the Promoter role |
| "I changed a shared component (nav, toast)" | Open `shared.md` + check which page files use the component |
| "I changed an API endpoint" | Trace which pages call that API, verify those page files |
| "Run everything" | Run all page files + all flow files |

#### Naming and grouping pages

**One page file per route** is the default. Group into a single file only when pages are tightly coupled:
- Create and edit forms for the same entity → `event-form.md` (with "Create Mode" and "Edit Mode" sections) if they share a component, or separate files if they're distinct pages
- Tabs/sub-views within a single route → sections within one file
- Distinct pages that happen to be related (list and detail) → separate files

**When to split a file:**
- Exceeds 200 checklist items (too large to navigate)
- Has 4+ user type sections each with 20+ items (split by user type: `event-detail-admin.md`, `event-detail-promoter.md`)
- Has sub-pages/tabs that each have 30+ items (split by sub-page: `event-detail-overview.md`, `event-detail-artists.md`)

When splitting, update the index, update any flow file references, and tell the user what you split and why.

#### The index file

`index.md` is the entry point. It must contain:

1. **Page inventory:** Every page file with its route, user types, and item count
2. **Flow inventory:** Every flow file with its user types and page files involved
3. **User type matrix:** For each user type, which pages and flows include items for them — this enables "verify everything for role X"
4. **Prerequisites:** Login credentials, environment setup, test data requirements
5. **Last updated:** Date each file was last generated/updated by verification-writer

```markdown
# Verification Index

## Prerequisites
- Admin: admin@example.com (editor role)
- Promoter: Accessed via magic link (generated per-event)
- Public: No auth required

## Pages
| File | Route(s) | User Types | Items | Last Updated |
|---|---|---|---|---|
| event-create.md | /events/new | Admin | 24 | 2026-03-28 |
| event-detail.md | /events/{id} | Admin, Promoter, Public | 38 | 2026-03-28 |
| event-edit.md | /events/{id}/edit | Admin | 19 | 2026-03-28 |
| magic-link-landing.md | /m/{token} | Promoter, Artist | 42 | 2026-03-28 |
| public-event-page.md | /{venue}/{event} | Public | 15 | 2026-03-28 |

## Flows
| File | User Types | Pages Involved | Steps |
|---|---|---|---|
| event-lifecycle.md | Admin, Promoter, Artist | event-create, event-detail, magic-link-landing | 4 |
| flyer-upload-flow.md | Admin, Promoter | event-detail, magic-link-landing | 3 |

## User Type → Pages/Flows
| User Type | Pages | Flows |
|---|---|---|
| Admin | event-create, event-detail, event-edit, event-list, dashboard, settings | event-lifecycle, flyer-upload-flow |
| Promoter | magic-link-landing, event-detail | event-lifecycle, flyer-upload-flow |
| Artist | magic-link-landing | event-lifecycle |
| Public | public-event-page, public-venue-page | — |

## Visualizations
| File | Source Flow | User Types | Last Updated |
|---|---|---|---|
| [Event Lifecycle](visualizations/event-lifecycle.md) | flows/event-lifecycle.md | Admin, Promoter, Artist | 2026-04-04 |
| [Interactive Map](visualizations/app-overview.html) | all flows | all | 2026-04-04 |
```

#### API-only projects

Projects with no UI routes organize by API domain instead of pages. Each file covers an API resource. Flow files chain API calls into sequences. The structure is the same, just `pages/` becomes `endpoints/`.

```
verification/
├── index.md
├── endpoints/
│   ├── auth.md
│   ├── events.md
│   ├── users.md
│   └── webhooks.md
├── flows/
│   ├── auth-flow.md
│   └── event-creation-flow.md
├── findings/
└── logs/
```

#### On subsequent runs

Check the existing structure and follow it. Don't reorganize without asking. If the project has grown enough that the current organization is strained (files getting too large, new pages not fitting existing files), suggest specific changes but don't restructure automatically.

**When adding a new page:** Create a new file in `pages/`, update `index.md`, check if any existing flow files should reference it.

**When a page is removed:** Delete the file, update `index.md`, update any flow files that referenced its items.

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

#### Layer 3a: Form Deep Analysis

Every form discovered in Layer 3 gets a dedicated deep analysis. This produces the data that Phase 2 uses to generate per-field verification items. Skim-level "it's a form with fields" is not sufficient — read the component code.

**Field inventory:** For each form, build a complete field list:

| Field | Type | Required? | Validation rules | Default/placeholder | Conditional? |
|---|---|---|---|---|---|
| (name) | text / select / date / multi-select / toggle / file / etc. | yes/no | min/max length, pattern, custom validator, etc. | default value or placeholder text | shown/hidden based on what? |

**What to look for in the code:**
- Schema definitions (Zod, Yup, native HTML attributes like `required`, `minLength`, `pattern`)
- Conditional rendering (`{showField && ...}`, ternaries controlling field visibility)
- Field dependencies (one field's value controls another's options, enabled/disabled state, or visibility)
- Default values and initial state (hardcoded defaults, values from props/context, `useEffect` population)
- Custom field components (date pickers, search-selects, rich text editors, file uploaders) — note the component type because it affects what edge cases to test

**Submission behavior — read the submit handler:**
- What happens on submit? (API call, form action, client-side processing)
- Is there a loading/submitting state? (disabled button, spinner, optimistic UI)
- Is there double-submit protection? (disabled during submit, debounce, flag check)
- What feedback is shown on success? (toast, redirect, inline message)
- What feedback is shown on error? (toast, inline errors, field-level errors)
- Is there no-op detection on edit forms? (skip API call if nothing changed)

**Edit form pre-population — if the form edits existing data:**
- How is data loaded? (server component props, `useEffect` fetch, loader)
- Which fields are pre-populated? (all of them? some of them?)
- Are there fields that should NOT be editable? (disabled, hidden, display-only)
- What happens if the data fails to load? (loading state, error state, fallback)

**Accessibility — read the form markup:**
- Are all fields associated with a `<label>` (via `htmlFor`/`id` or wrapping)?
- Do error messages use `aria-describedby` or `aria-live` for screen reader announcement?
- Is there a logical tab order (no `tabIndex` hacks, fields in DOM order)?
- Is focus managed after submission? (focus moves to success message, error summary, or first invalid field)
- Can the form be completed entirely by keyboard? (custom components like date pickers and search-selects are common blockers)

#### Layer 3b: Visual Affordance Analysis

Every interactive component discovered in Layer 3 gets checked for **affordance honesty** — does the UI's visual design promise interactions that the code actually supports?

**What is an affordance?** A visual signal that implies a specific interaction: a dashed border implies drag-and-drop, a cursor pointer implies clickability, a grip handle implies draggability, a resize handle implies resizability. If the visual signal exists but the code doesn't implement the interaction, the UI is lying to the user.

**For each interactive component, check:**

| Visual signal | Implied interaction | What to look for in code |
|---|---|---|
| Dashed/dotted border around a drop zone | Drag-and-drop file upload | `onDrop`, `onDragOver`, `onDragEnter` event handlers, or a library like `react-dropzone` |
| Drag handle / grip icon on list items | Drag to reorder | `onDragStart`/`onDrop` handlers, or a library like `dnd-kit`, `react-beautiful-dnd` |
| Cursor pointer on a card/row | Clickable / navigates | `onClick` handler or wrapping `<a>`/`<Link>` |
| Resize handle on a panel/element | Resizable | `onMouseDown` + resize logic, or CSS `resize` property |
| Contenteditable-looking text | Inline editing | `contentEditable`, `onDoubleClick` to edit, or inline edit component |
| Paste-target styling on an input area | Paste content (images, rich text) | `onPaste` handler that processes clipboard data |
| Hover effects / lift shadow on cards | Interactive (clickable, expandable) | Any interaction handler beyond just CSS hover state |

**Recording:**
- **Honest** — Visual signal matches implemented behavior. Generate a verification item to confirm the interaction works.
- **Dishonest** — Visual signal exists but code doesn't implement the interaction. Goes in findings report as a UX defect with severity "medium" (misleading UI). Also generate a `[deep]` verification item that tests the implied interaction so browser-verification will catch it.
- **Ambiguous** — Can't determine from code alone (e.g., CSS comes from a library, handler might be inherited). Generate a `[deep]` verification item to test it in the browser.

**Common high-value targets:**
- File upload components — almost always styled as drop zones, but drag-and-drop support is often missing or broken
- Card grids — often have hover effects that imply clickability but only a small "View" link is actually interactive
- Table rows — cursor pointer on hover but clicks do nothing (only action buttons in the row work)
- Sortable/reorderable lists — grip handles rendered by a UI library but drag handlers never wired up

#### Layer 3c: Page Context Coherence

For each page, determine its **purpose** and **audience**, then check whether every element on the page is coherent with both. This analysis produces findings-report items for human review, not automatic pass/fail checklist items — context is subjective and requires human judgment.

**Step 1: Determine page purpose.** Read the page component and its route. Assign a purpose from the page's content and structure:
- Information display (event detail, profile view, about page)
- Data entry (create/edit forms)
- Data management (list/table with CRUD actions)
- Workflow (multi-step process, wizard, onboarding)
- Dashboard (aggregated status, metrics, quick actions)
- Public marketing (landing page, public listing)

**Step 2: Determine page audience.** From Layer 1 (user types) and route analysis:
- Which user type(s) access this page?
- Is this page public (no auth required)?
- What is this user type's role scope? (viewer, editor, admin, public visitor)

**Step 3: Element coherence check.** For each significant element on the page (buttons, action links, data displays, sections, toolbars), ask two questions:

1. **Purpose fit:** "Does this element serve the page's purpose?" A download-all-headshots button on a public event information page fails this test — the page exists to inform the public about the event, not to manage assets.

2. **Audience fit:** "Should this page's audience have access to this action or data?" Admin actions on public pages, editor tools on viewer pages, internal/debug information on customer-facing pages all fail this test.

**What to look for in code:**
- Actions that call admin-only or elevated-permission API endpoints, rendered on pages accessible to lower-privilege users or the public
- Components imported from admin/internal sections into public/user-facing pages
- Conditional rendering that depends on a role check — but ask whether the element should appear on the page at all, not just whether the role check works
- Debug/dev components, logging displays, or internal identifiers (UUIDs, internal status codes) on user-facing pages
- Actions that don't relate to any of the page's primary content (e.g., managing entity B from entity A's detail page, when there's no meaningful relationship)

**Recording:** Every flagged element goes in the findings report under a dedicated "Contextual Coherence Review" section (see Output 2). Each flag includes:
- The element (what it is, where on the page)
- The page purpose and audience
- Which question it fails (purpose, audience, or both)
- Why it looks wrong (brief explanation)
- A disposition for the human: `confirm-intended` | `likely-misplaced` | `needs-discussion`

**This analysis is not about permissions enforcement** — Layer 1 and auth boundary items handle whether the user *can* perform the action. This is about whether the element *should be on the page at all* given what the page is for and who sees it. A button can be perfectly permission-gated and still be contextually wrong.

#### Layer 3d: Business Rule Extraction for Dynamic Values

Components that display computed, derived, or time-sensitive values are high-risk for showing technically correct but semantically wrong data. The verification-writer reads the code that produces these values — this is knowledge the browser-verification skill cannot derive from the DOM alone. **The writer must capture and pass through the business logic context so the verifier can sanity-check what it sees.**

**Identify components that display dynamic/computed values:**
- Countdown timers, progress bars, status indicators
- Calculated prices, totals, percentages, scores
- Derived dates, deadlines, durations
- Counts, aggregations, statistics
- Status text that depends on business state (e.g., "Pending approval" vs. "Confirmed")
- Conditional messaging (banners, warnings, notices whose content depends on data)

**For each, trace the business rule in the code:**
- What is the source value? (database field, API response, computed from other fields)
- What transformation is applied? (date math, arithmetic, status mapping, conditional logic)
- What are the valid ranges or expected values? (a 72-hour deadline means the timer should never exceed 72 hours; a percentage should be 0-100; a count should be non-negative)
- What other values on the same page should be consistent with this one? (a deadline date and a countdown timer should agree; a total should equal the sum of visible line items; a "3 of 5 complete" badge should match the list below it)

**Recording:** For each dynamic component, produce:
1. The business rule in plain language (e.g., "Confirmation deadline is 72 hours from event creation, defined in `getDeadlineConfig()` at `lib/deadlines.ts:42`")
2. The expected valid range or constraints (e.g., "Timer value must be <= 72 hours", "Percentage must be 0-100")
3. Related values on the same page that should be cross-referenced (e.g., "Deadline date display should match timer countdown target")

This data is embedded in verification items as `<!-- BUSINESS-CONTEXT -->` annotations (see item format in Phase 2).

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

**Business context annotations:** When an item verifies a dynamic or computed value (identified in Layer 3d), add a `<!-- BUSINESS-CONTEXT -->` comment block immediately after the item. This gives browser-verification the business logic context it needs to sanity-check displayed values — not just "does the timer render" but "is the timer showing a plausible value given the rules."

```markdown
- [ ] [standard] **Verify countdown timer displays correct remaining time** --- Timer shows hours/minutes remaining until confirmation deadline. *Expected: success*
<!-- BUSINESS-CONTEXT:
  rule: Confirmation deadline is 72 hours from event creation (getDeadlineConfig in lib/deadlines.ts:42)
  valid_range: Timer value must be <= 72 hours and >= 0
  cross_reference: [Deadline date badge on same page should show a date ~72 hours from created_at]
  red_flags: [Timer > 72h means wrong deadline source; Timer showing days instead of hours means format bug; Timer at 0 but status not "expired" means state mismatch]
-->
```

**Annotation fields:**
- `rule:` — The business rule in plain language with a code reference (file:line)
- `valid_range:` — Bounds, constraints, or expected values. Be specific: not "reasonable number" but "0-72 hours" or "$10-$500" or "0-100%"
- `cross_reference:` — Other values on the same page that should be consistent with this one
- `red_flags:` — Specific symptoms that indicate a data bug, derived from reading the code. What would a wrong value look like and what would it mean?

**When to annotate:** Not every item needs a business context annotation. Use them when:
- The item verifies a computed/derived value (timers, totals, percentages, derived status)
- The correct value depends on business rules that aren't obvious from the UI alone
- Multiple values on the page should be internally consistent
- The component has known edge cases in the computation logic

**When NOT to annotate:** Static labels, navigation items, simple CRUD confirmations ("item was created"). If the expected result is self-evident from the action, an annotation adds noise.

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
- Every CRUD operation gets `[standard]` items for each operation AND `[deep]` items for conflict/failure states
- Every auth boundary gets `[standard]` items for wrong-role access
- Every destructive action gets `[standard]` items verifying the confirmation flow
- Every error path that has graceful handling gets a `[deep]` item to verify the graceful behavior

**Form generation rules (using Layer 3a data):**

Forms are high-density interaction points. A single form can need 15-40 verification items. The following rules are not optional — every form gets items in every category. If a category doesn't apply (e.g., no conditional fields), note "N/A — no conditional fields found" in a comment so the reviewer knows it was considered, not skipped.

*1. Field-level validation (one item per field, per rule):*
- `[standard]` — Submit with each required field individually empty. Verify field-level error message appears (not just a generic "form invalid" toast).
- `[deep]` — For each field with validation rules: test the boundary. Text fields: min length, max length, special characters (`<script>`, emoji, unicode), extremely long input. Number fields: below min, above max, non-numeric input. Date fields: past dates (if restricted), invalid date formats, date range violations. Select/dropdown fields: verify all options load, verify a selection can be made and cleared. File fields: wrong file type, oversized file, no file.
- `[deep]` — For fields with patterns or custom validators: test one invalid input per rule (e.g., email format, URL format, phone format).

*2. Submission behavior:*
- `[standard]` — Submit with all valid data. Verify: success feedback (toast, redirect, or inline message), data persisted (navigate to detail/list and confirm).
- `[standard]` — Verify submit button shows loading/disabled state during submission (if the code implements this). If the code has no loading state, this becomes a finding.
- `[deep]` — Click submit rapidly 2-3 times. Verify only one submission occurs (if double-submit protection exists). If no protection exists, this becomes a finding.
- `[deep]` — Submit with valid data when the server is expected to reject (e.g., constraint violation, expired session). Verify the error is displayed gracefully — no raw error objects, no blank screen, no console-only errors.

*3. Field interactions and conditional logic:*
- `[standard]` — For each conditional field found in Layer 3a: trigger the condition and verify the field appears. Remove the condition and verify the field disappears.
- `[standard]` — For dependent fields (e.g., selecting a venue populates venue-specific options): change the parent value and verify the child updates. Clear the parent value and verify the child resets.
- `[deep]` — For search-select / autocomplete fields: type a partial match and verify results filter. Select a result and verify it populates. Clear the selection and verify it resets. Type a term with no matches and verify empty state.
- `[deep]` — For date pickers: select a date via the picker UI. Type a date manually if the field allows it. Verify the selected value displays in the expected format.

*4. Pre-populated data (edit forms only):*
- `[smoke]` — Navigate to the edit form. Verify the form loads without error.
- `[standard]` — Verify each field individually contains the correct current value. Generate one item per field (not one item for "all fields load"). For complex fields (multi-selects, search-selects, date pickers), verify the value displays correctly in the field's specific format.
- `[standard]` — Verify any non-editable fields are correctly displayed as read-only or disabled (if the code has non-editable fields).
- `[deep]` — Submit the edit form without making any changes. Verify the app handles the no-op correctly (either skips the API call, or succeeds without error). No-op detection is a finding if missing.
- `[deep]` — Change one field, save, navigate back to edit. Verify the changed value persists and other fields remain unchanged.

*5. Accessibility:*
- `[standard]` — Complete the entire form using only the keyboard (Tab to move between fields, Enter/Space to interact, no mouse). Verify every field is reachable and operable.
- `[standard]` — Verify every field has a visible label. Verify clicking the label focuses the field (label-input association).
- `[deep]` — Trigger a validation error and verify the error message is associated with the field (check for `aria-describedby` or equivalent). Verify a screen reader would announce the error (use DOM inspection if no screen reader is available — check `aria-live`, `role="alert"`, or `aria-describedby` linking).
- `[deep]` — After a failed submission, verify focus moves to the first invalid field or an error summary (not left at the submit button or lost).
- `[deep]` — For custom components (date pickers, search-selects, modals within forms): verify they are keyboard-navigable. These are the most common accessibility failures.

*6. Edge cases:*
- `[deep]` — Paste a very long string (500+ characters) into each text field. Verify it's either accepted or truncated/rejected gracefully.
- `[deep]` — Paste special characters (`<script>alert('xss')</script>`, `'; DROP TABLE events; --`) into text fields. Verify they are escaped or rejected — never executed or stored raw.
- `[deep]` — Use browser back button after successful submission. Verify the form doesn't re-submit or show stale data.
- `[deep]` — If the form has unsaved changes, navigate away. Verify there is a "discard changes?" prompt (if the code implements this). If no prompt exists and the form has significant data entry, this becomes a finding.

**Visual affordance generation rules (using Layer 3b data):**

For each component where Layer 3b found a visual affordance (honest, dishonest, or ambiguous):

- `[deep]` — For **honest** affordances: test the implied interaction works end-to-end. E.g., "Drag an image file onto the upload drop zone --- File is accepted, preview displayed, upload begins." Don't just test the button fallback — test the affordance itself.
- `[deep]` — For **dishonest** affordances: test the implied interaction anyway, so browser-verification will confirm the failure. Write the item as what the UI *promises*, and set the expected type based on whether a fix is planned. E.g., "Drag an image file onto the dashed upload area --- File is accepted via drag-and-drop. *Expected: success*". The mismatch between expectation and reality will surface as a FAIL, which is the point.
- `[deep]` — For **ambiguous** affordances: test the implied interaction to determine which it is. E.g., "Click anywhere on the event card (not just the View button) --- Card navigates to event detail. *Expected: success*".

**Why this matters:** Users attempt the interaction the visual design implies. If drag-and-drop styling exists, users will drag files before they look for a button. A working button with a broken drop zone is a UX failure even though the "happy path" technically works.

**Data plausibility generation rules (using Layer 3d data):**

For each component where Layer 3d extracted business rules for dynamic values:

- `[standard]` — Verify the displayed value falls within the valid range defined by the business rule. Attach a `<!-- BUSINESS-CONTEXT -->` annotation with the rule, valid range, and red flags. E.g., "Verify countdown timer shows remaining time until confirmation deadline --- Timer displays hours/minutes, value is between 0 and 72 hours. *Expected: success*" with annotation explaining the 72-hour rule and its code source.
- `[standard]` — For each cross-reference pair identified in Layer 3d: verify the values are consistent with each other. E.g., "Verify countdown timer and deadline date badge show consistent values --- Timer countdown target matches the date shown in the deadline badge. *Expected: success*"
- `[deep]` — For components with edge-case computation paths (identified from code branching): test the edge case. E.g., if the timer handles "deadline already passed" differently, create an item that verifies the expired state renders correctly.
- `[deep]` — For values derived from multiple data sources: verify the aggregation is correct. E.g., "Verify '3 of 5 artists confirmed' badge matches the count of confirmed artists in the list below --- Count in badge equals number of artists with 'Confirmed' status. *Expected: success*"

**Why this matters:** A component can render without errors, pass all functional tests, and still display a value that is wrong according to the business rules. The verification-writer has the code context to know what values *should* be — the browser-verification skill only sees what *is*. The `BUSINESS-CONTEXT` annotations bridge that gap.

**Browser-First Verification:**

Every verification item must be written so that browser-verification can execute it through the UI. The decision tree:

1. **Does a UI exist for this functionality?** (form, page, button, dashboard widget, etc.)
   - **Yes** → Write the item as a browser interaction. The action is "click", "fill", "navigate", "submit" — not "call API" or "POST to endpoint".
   - **No** → This is an API-only item. Mark it with `*API-only*` and include an `<!-- API-VERIFICATION-FLAG -->` comment (see format below).

2. **When writing an API-only item**, always include:
   ```markdown
   - [ ] [depth] **Action via API** --- Expected result. *Expected: type* *API-only*
   <!-- API-VERIFICATION-FLAG: reason=[no UI available | webhook endpoint | cron handler | internal service API], durability=[permanent | temporary | needs-review], note=[explanation for human reviewer] -->
   ```

   **Durability values:**
   - `permanent` — This endpoint has no UI by design (webhooks, cron handlers, service-to-service). No need to revisit.
   - `temporary` — UI is planned or in progress. Re-check on next verification-writer run.
   - `needs-review` — Unclear whether UI should exist. Flag for human decision.

3. **In the findings report**, add a dedicated section listing all API-only verification items with their durability flags. This gives the human a single place to review and confirm intent.

4. **On subsequent runs:** Check existing `API-VERIFICATION-FLAG` comments. If durability is `temporary`, check whether a UI now exists. If it does, rewrite the item as a browser interaction and remove the flag. If durability is `needs-review`, keep flagging it until the human resolves it.

**Common violation:** Writing "POST to /api/events with valid data" when there's a "Create Event" form in the UI. The correct item is "Fill and submit the Create Event form with valid data." The API call happens as a side effect that browser-verification observes in the network tab — it is not the primary action.

**Items for Partial/Missing handling:** If error handling is Partial, write the item documenting what SHOULD happen (so browser-verification will find the gap). If Missing, write the item only after the fix is applied or note it in the findings report.

### Output 2: Findings Report (`<verification-path>/findings/YYYY-MM-DD-analysis.md`)

Read `references/findings-report-format.md` for full template.

Always generated, even if zero gaps found. Includes:
- Summary stats (routes analyzed, interaction points, handled/partial/missing counts)
- Auto-fixes applied (with file/line details)
- Gaps requiring manual fix (with severity, current vs. expected behavior, suggested approach)
- Systemic issues (patterns affecting multiple routes/user types)
- **Contextual coherence flags** (from Layer 3c — elements that may be misplaced given the page's purpose or audience, grouped by disposition: `confirm-intended`, `likely-misplaced`, `needs-discussion`. Each flag includes: the element, the page purpose/audience, which question it fails, and why it looks wrong. This section exists for human review — the skill does not auto-fix or auto-fail these items.)
- **API-only verification items** (list all items with `API-VERIFICATION-FLAG`, grouped by durability: permanent, temporary, needs-review — this gives the human a single place to confirm intent)

### Output 3: Index (`<verification-path>/index.md`)

Master index: all verification files, prerequisites, login credentials, date each file was last generated/updated.

## Phase 2.5: Flow Visualizations

Read `references/flow-visualization.md` for visualization generation rules, templates, and change detection mechanics. Summary:

Visualizations are comprehension aids for humans — they show what happens in a flow, who's involved, and where handoffs occur. They are NOT data dashboards. Deeper verification detail stays in the verification docs.

**Outputs:**

1. **Mermaid flow diagrams** — One per flow file, placed in `visualizations/` with the same base name as the source flow. Each diagram shows the flow's steps as nodes (with page names), transitions as edges, and color-codes by user type.

2. **Interactive HTML artifact** (optional) — Format chosen by user on first run (upgraded flow views, sitemap, both, or skip). Self-contained single HTML file with no external dependencies.

**When this step runs:**

| Entry point | Visualization scope |
|---|---|
| **New project** | Generate all Mermaid diagrams for all flow files. Ask about HTML preference. |
| **New feature** | Generate/update only visualizations for flows that reference changed pages or were themselves modified |
| **After code changes** | Same as new feature + check all existing visualizations for orphaned source flows |
| **On demand** | Generate/update only visualizations for flows within the user-specified scope |
| **Called by browser-verification** | Skip visualization step |

**Change detection:** Each visualization includes a staleness marker with a content hash of the source flow file. Only regenerate when the hash differs. See `references/flow-visualization.md` for full mechanics.

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

Organization: pages + flows (Option B)
Page files: [list files in pages/]
Flow files: [list files in flows/]
User types: [list user types and how they're accessed — e.g., Admin: email login, Promoter: magic link]
Git tracking: [logs gitignored, findings tracked | both tracked | both gitignored]
Log cleanup: [keep 5 most recent | keep all]
HTML visualization: [flow-views | sitemap | both | none]

**Why:** Configured on [date] during initial verification-writer run.
**How to apply:** browser-verification reads this to find docs and determine scope. verification-writer reads this to know where to write. Use index.md for user-type-to-page mapping.
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
| One validation item for the whole form | Generate one item per field per validation rule — "submit with empty fields" is one item, not the only validation item |
| Skipping edit form pre-population checks | Every field on an edit form gets its own item verifying the correct value loads — not just "form loads with data" |
| No accessibility items on forms | Every form gets keyboard navigation, label association, and error announcement items — no exceptions |
| Treating field interactions as optional | If code has conditional fields or dependent dropdowns, those get explicit items — they are high-bug-rate areas |
| Lumping submission behavior into happy path | Loading state, double-submit protection, and error feedback are separate items — not implied by "submit and it works" |
| Testing only the button when a drop zone exists | If the UI has drop-zone styling (dashed border, "drag files here" text), test drag-and-drop — not just the fallback button click |
| Ignoring visual affordances | Hover effects, drag handles, cursor pointers all promise interactions — verify the code delivers on what the UI promises |
| Not questioning elements on the page | Every element should serve the page's purpose and be appropriate for its audience — flag anything that looks misplaced for human review |
| Writing "verify timer works" without business context | If code says the deadline is 72 hours, the item must say the timer should be <= 72 hours — and include a `BUSINESS-CONTEXT` annotation with the rule, range, and red flags |
| Skipping Layer 3d for computed values | Every timer, counter, percentage, and derived status needs its business rule traced and annotated — browser-verification can't know the rules from the DOM alone |
| Not identifying cross-reference pairs | If two elements on the same page display related values (deadline date + countdown timer, item count badge + item list), they need a cross-reference item to verify consistency |
| Writing API verification when UI exists | If a form/page exercises the API, write the item as a browser interaction — the API call is observed in network tab, not invoked directly |
| Not flagging API-only items | Every API-only item needs `*API-only*` tag and `<!-- API-VERIFICATION-FLAG -->` comment with durability |
| Regenerating visualizations when only items changed | Check staleness hash — only regenerate when flow file content or structure changed, not when items within pages changed |
| Including shared components as nodes in flow diagrams | Shared components (nav, toasts, modals) are infrastructure — exclude from diagrams unless the component IS the interaction |
| Generating HTML artifact without checking preference | Always check memory for HTML visualization preference; ask on first run or when field is missing; respect "skip" choice |
| Inconsistent user type colors across visualizations | Use the deterministic alphabetical palette from flow-visualization.md — never assign colors ad hoc |

## Red Flags — STOP

- About to overwrite manually-curated verification docs without checking diff
- Fix touches shared code or exceeds thresholds
- Analysis shows systemic absence of error handling (> 50% of interaction points missing) — this needs architecture discussion, not item-by-item fixes
- User type discovery finds no roles — auth system may not be conventional, ask the user
