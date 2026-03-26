---
name: "ux-audit"
description: "Systematically identify user experience problems in web applications through browser inspection and code analysis. Covers navigation flow, task completion friction, error states, feedback/system status, consistency, forms/input UX, content clarity, accessibility (WCAG 2.1 AA), responsive behavior, trust/support risk, onboarding/discoverability, visual hierarchy, recovery/reversibility, performance/perceived speed, data/table UX, search UX, dark mode/theming, and i18n/l10n. Audits through multiple user personas. Use when asked to audit UX, find confusing UI, review user experience, identify support risks, improve usability, or check accessibility. Produces a prioritized findings list with impact/effort scoring, then fixes small issues directly and proposes mockups/plans for larger ones."
tags: ["skill"]
---


# UX Audit

Systematically scan a web application for user experience problems, prioritize findings, and fix or propose solutions.

## Severity Criteria

Use these definitions consistently when rating findings:

| Severity | Definition | Examples |
|----------|-----------|----------|
| **Critical** | Blocks task completion, causes data loss, or breaks accessibility for assistive tech users | Form submits silently fail; destructive action has no confirmation; keyboard users cannot reach primary CTA |
| **Major** | Significantly degrades experience, causes confusion, or requires workarounds to complete tasks | Validation errors appear only on submit with no field-level hints; empty states show blank space with no guidance; error messages show raw status codes |
| **Minor** | Cosmetic issues, inconsistencies, or polish problems that don't block users | Inconsistent button placement across pages; date formats vary; hover states missing on some elements |

When in doubt, rate one level higher — it's better to triage down than to miss a real problem.

## Workflow

### Phase 1: Scope

1. Confirm the target URL and which pages/flows to audit
2. Confirm authentication state (logged in if auditing app pages)
3. **Detect the framework** — check `package.json`, file structure, or page source to identify the stack (Next.js, Vue, Svelte, plain React, etc.). This determines code-level inspection patterns in Phase 2.
4. Read `references/audit-checklist.md` for the full checklist
5. Select relevant categories based on the app and user's focus
6. **Identify user personas** to audit through:
   - **New user**: First-time visitor, no prior context
   - **Power user**: Frequent user, uses advanced features and keyboard shortcuts
   - **Admin**: Manages settings, permissions, billing
   - **Read-only / limited permissions**: Can view but not modify
   - Ask the user which personas are relevant; default to new user + power user if unspecified
7. **Prioritize pages** using these heuristics (audit in this order):
   - High-traffic pages (landing, dashboard, primary list views)
   - Primary user flows (onboarding, core CRUD operations, checkout/billing)
   - Settings and account management
   - Edge-case pages (error pages, empty states, search results)

### Phase 2: Crawl & Inspect

Use a **tiered inspection approach** to avoid spending equal time on every page:

**Quick scan** (all pages):
1. Screenshot the page
2. Check interactive elements (`read_page` filter "interactive")
3. Note obvious issues (broken layout, missing labels, dead-end flows)

**Deep inspection** (key flows, pages with issues, and pages flagged by user):
1. Screenshot the page
2. Read the accessibility tree (`read_page` filter "all")
3. Check interactive elements (`read_page` filter "interactive")
4. Read console for JS errors (`read_console_messages`)
5. Check network for failed requests (`read_network_requests`)
6. Walk through each relevant checklist category
7. **Test as each relevant persona** — note differences in what's visible, enabled, and accessible

**Cross-flow analysis** (after individual pages):
1. Walk through end-to-end user journeys (signup → first value, error → recovery → retry, create → edit → delete)
2. Check for state consistency across page transitions
3. Verify that completing a flow lands the user somewhere useful
4. Test flow interruptions (navigate away mid-form, session timeout, back button)

Record every finding with:
- **Page/URL** where it occurs
- **Category** from the checklist
- **Severity**: Critical / Major / Minor (using the criteria above)
- **Persona**: which user type is affected (or "all")
- **Description**: what's wrong and why it matters for users
- **Evidence**: screenshot ID or code reference

### Phase 3: Report

Present findings in a severity-sorted table with impact/effort scoring:

| # | Sev | Impact | Effort | Category | Page | Persona | Finding | Fix |
|---|-----|--------|--------|----------|------|---------|---------|-----|
| 1 | Critical | High | S | Forms | /signup | All | Submit with empty fields shows no validation | S |

- **Impact**: How much this affects users — **High** (affects primary flows or many users), **Medium** (affects secondary flows or specific user types), **Low** (edge cases or cosmetic)
- **Effort**: How much work to fix — **S** (direct code fix, < 30 min), **M** (needs mockup/design, hours), **L** (needs plan, days+)

**Prioritization**: Address findings in this order:
1. High impact + S effort (quick wins)
2. High impact + M effort (important improvements)
3. Critical severity regardless of effort
4. Medium impact + S effort
5. Everything else

### Phase 4: Fix

- **S fixes**: Edit source directly, type-check, verify in browser, commit
- **M fixes**: Create a mockup (HTML artifact or ASCII) showing current vs proposed. Describe the problem and solution clearly. Implement after user approval.
- **L fixes**: Write an implementation plan in `plans/`. Don't implement.

Re-verify S fixes in browser after applying them.

### Phase 5: Verify & Track

After all S fixes are applied:

1. **Re-screenshot** every page that had an S fix applied — confirm the fix visually
2. **Re-run quick scan** on fixed pages to check for regressions (did the fix break something else?)
3. **Produce a summary** of remaining M and L items as a tracking list:
   ```
   ## Remaining Items
   - [ ] M: #3 — /settings has no confirmation on destructive actions
   - [ ] L: #7 — Search UX needs full redesign
   ```
4. Save the summary to `docs/ux-audit-results/YYYY-MM-DD-audit.md` (or the user's preferred location)
5. **Recommend re-audit cadence**: suggest when to re-run (e.g., after M/L fixes are implemented, after major feature launches, or quarterly)

## Browser Tools

Use `claude-in-chrome` or `playwright` MCP tools:
- `navigate`, `read_page`, `computer` (screenshot), `find`
- `read_console_messages`, `read_network_requests`
- `javascript_tool` for DOM inspection when click/screenshot fail

Fall back to code inspection (Grep/Read) when browser tools are unreliable.

### Baseline Capture

Before starting fixes (between Phase 3 and Phase 4), capture baseline screenshots of all pages with findings. Save or record these so fixes can be compared before/after. Use `gif_creator` to record multi-step flow walkthroughs when useful.

## Code-Level Inspection

Supplement browser inspection by reading source. **Adapt patterns to the detected framework:**

### Framework Detection

Check for framework indicators and use the appropriate patterns:

| Framework | Indicators | Page pattern |
|-----------|-----------|-------------|
| Next.js App Router | `src/app/**/page.tsx`, `app/` dir | `src/app/**/page.tsx` or `app/**/page.tsx` |
| Next.js Pages Router | `pages/` dir | `pages/**/*.tsx` |
| Vue / Nuxt | `.vue` files, `nuxt.config` | `pages/**/*.vue` or `src/views/**/*.vue` |
| Svelte / SvelteKit | `.svelte` files, `svelte.config` | `src/routes/**/+page.svelte` |
| React (plain/CRA/Vite) | `src/App.tsx`, no `app/` dir | `src/pages/**/*.tsx` or `src/components/**/*.tsx` |
| Angular | `angular.json`, `.component.ts` | `src/app/**/*.component.ts` |

### Common Patterns (framework-agnostic)

- **Error handling**: grep for `catch`, `error`, `toast`, `alert`, `notification`
- **Loading states**: grep for `loading`, `skeleton`, `spinner`, `Loader`, `Suspense`
- **Empty states**: grep for `empty`, `no.*found`, `no.*results`, `no.*data`
- **Form validation**: grep for `required`, `validate`, `schema`, `yup`, `zod`, `formik`
- **Accessibility**: grep for `aria-`, `role=`, `alt=`, `tabIndex`, `focus`, `sr-only`
- **Search**: grep for `search`, `query`, `filter`, `autocomplete`
- **Theming**: grep for `dark`, `theme`, `prefers-color-scheme`, `data-theme`
- **i18n**: grep for `t(`, `i18n`, `intl`, `locale`, `formatMessage`, `Trans`

## Detailed Checklist

See `references/audit-checklist.md` for the complete category-by-category checklist.
