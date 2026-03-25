---
name: "browser-verification"
description: "Use when performing manual QA verification of web application features in a browser, running verification checklists, or testing a feature and its tangential features after code changes"
tags: "["skill"]"
---

# Browser Verification

## Overview

Automated manual QA using browser tools against verification checklists in `docs/verification/`. Walks through every checklist item in a real browser, explores full CRUD on each page, finds issues, fixes what's safe, and logs everything.

**Core principle:** Verify in the browser, not in your head. Evidence from the DOM, console, and network — not assumptions.

**Graceful failure standard:** A feature is not PASS if it works on the happy path but fails ungracefully on any error path. "Works but crashes ugly" is FAIL. Every interaction has a happy path and failure paths — both must behave well. If a checklist item has an `*Expected:*` type, that tells you what kind of outcome to verify. If an item has no explicit error path items nearby, test basic error scenarios anyway (empty input, network failure at deep depth) and flag missing coverage.

**Companion skill:** Verification docs are generated and maintained by the **verification-writer** skill. If you find docs are stale, missing, or incomplete during a run, invoke verification-writer to update them (see "Cross-Skill Integration" below).

## Verification Depth

This skill operates at three depth levels. **Ask the user which depth they want** if not specified. Default to **standard** if they don't have a preference.

| Depth | When to use | What it does |
|---|---|---|
| **Smoke** | Quick sanity check, CI gate, "does it load?" | Load every page in scope, check for render errors, console errors, and failed network requests. No interaction testing. |
| **Standard** | Post-feature verification, routine QA | Walk every checklist item, check console + network per item, basic exploration of uncovered elements. |
| **Deep** | Pre-deploy to production, regression after major refactor, "test everything" | Full completionist audit: every interactive element tested, every form with edge cases, server logs, CRUD round-trips, accessibility checks. Nothing skipped. |

**Keyword detection:** If the user says "quick check", "smoke test", "does it load", or "sanity check" → **smoke**. If they say "verify", "check the feature", or "QA" → **standard**. If they say "deep", "thorough", "everything", "full audit", or "production readiness" → **deep**.

## When to Use

- Pre-deploy QA for staging or production
- After implementing a feature — verify it and tangential features
- Full regression run across all roles
- When user says "verify", "test in browser", "manual QA", or "check the UI"

## Checklist

You MUST complete these in order:

1. **Find verification docs**
2. **Determine scope and depth**
3. **Detect environment**
4. **Load verification docs**
5. **Run verification sections**
6. **Fix or log issues**
7. **Update stale docs** (invoke verification-writer if needed)
8. **Produce log file and summary**

## Step 1: Find Verification Docs

Before anything else, locate the verification docs for this project.

1. **Check memory** for a `verification-docs-config` project memory. This tells you the doc location, organization, and preferences set by verification-writer.
2. **If memory exists:** Verify the path still has docs (files may have been deleted). If docs exist at the path, proceed to Step 2.
3. **If memory exists but docs are missing at the path:** Tell the user:
   > "Memory says verification docs should be at `<path>`, but they're not there. Run `/verification-writer` to generate them, or tell me the correct location."
4. **If no memory exists:** Check `docs/verification/` as a default. If docs exist there, use them and note the location. If nothing exists anywhere, tell the user:
   > "No verification docs found for this project. Run `/verification-writer` to generate them first — it will analyze the codebase and create verification checklists."

   Do not proceed without docs. There is nothing to verify against.

## Step 2: Determine Scope and Depth

Ask the user or infer from context. You need two things: **scope** (which pages/features) and **depth** (smoke, standard, or deep). If the user only specifies one, ask for the other or use defaults (standard depth, git-diff-based scope).

```dot
digraph scope {
    "User request" [shape=box];
    "Full project?" [shape=diamond];
    "Run all checklists" [shape=box];
    "Feature specified?" [shape=diamond];
    "git diff to find changes" [shape=box];
    "Map files to verification sections" [shape=box];
    "Propose scope to user" [shape=box];
    "User approves?" [shape=diamond];
    "Adjust scope" [shape=box];
    "Run approved sections" [shape=box];

    "User request" -> "Full project?";
    "Full project?" -> "Run all checklists" [label="yes"];
    "Full project?" -> "Feature specified?" [label="no"];
    "Feature specified?" -> "Map files to verification sections" [label="yes"];
    "Feature specified?" -> "git diff to find changes" [label="no"];
    "git diff to find changes" -> "Map files to verification sections";
    "Map files to verification sections" -> "Propose scope to user";
    "Propose scope to user" -> "User approves?";
    "User approves?" -> "Run approved sections" [label="yes"];
    "User approves?" -> "Adjust scope" [label="no"];
    "Adjust scope" -> "Propose scope to user";
}
```

**File-to-section mapping:** Match changed file paths to verification docs:
- `app/admin/*` -> `docs/verification/admin.md`
- `app/educator/*` or `app/(educator)/*` -> `docs/verification/educator.md`
- `app/employer/*` or `app/(employer)/*` -> `docs/verification/employer.md`
- `app/student/*` or `app/(student)/*` -> `docs/verification/student.md`
- `app/guardian/*` or `app/(guardian)/*` -> `docs/verification/guardian.md`
- `app/community-center/*` -> `docs/verification/community-center.md`
- `components/*`, `hooks/*`, `lib/*`, `middleware*` -> `docs/verification/shared.md` + all role docs that import the changed file
- `app/api/*` -> Check which UI features call that API, verify those sections

**Tangential detection:** When a changed file is imported by other features, include those features in scope. Use grep/glob to trace imports.

## Step 2: Detect Environment and Start Services

Determine from the base URL:

| Signal | Environment | Login Method | Fix Policy |
|---|---|---|---|
| `localhost` or `127.0.0.1` | Local | Auto via Inbucket | Fix within thresholds |
| Any other URL | Staging/Production | Pause for manual login | Log only, never fix |

**Local environment: auto-start services**

For local environments, automatically start required services rather than asking the user. Run these checks and start anything that's missing:

```dot
digraph startup {
    "Check Supabase" [shape=box];
    "Supabase running?" [shape=diamond];
    "Start Supabase\n(npx supabase start)\nrun_in_background" [shape=box];
    "Check dev server" [shape=box];
    "Dev server running?" [shape=diamond];
    "Start dev server\n(npm run dev)\nrun_in_background" [shape=box];
    "Wait for services" [shape=box];
    "Verify all healthy" [shape=diamond];
    "Proceed to Load Docs" [shape=doublecircle];
    "Report failure" [shape=box];

    "Check Supabase" -> "Supabase running?";
    "Supabase running?" -> "Check dev server" [label="yes"];
    "Supabase running?" -> "Start Supabase\n(npx supabase start)\nrun_in_background" [label="no"];
    "Start Supabase\n(npx supabase start)\nrun_in_background" -> "Check dev server";
    "Check dev server" -> "Dev server running?";
    "Dev server running?" -> "Wait for services" [label="no"];
    "Dev server running?" -> "Wait for services" [label="yes (skip start)"];
    "Wait for services" -> "Start dev server\n(npm run dev)\nrun_in_background";
    "Start dev server\n(npm run dev)\nrun_in_background" -> "Verify all healthy";
    "Dev server running?" -> "Verify all healthy" [label="yes (all running)"];
    "Verify all healthy" -> "Proceed to Load Docs" [label="yes"];
    "Verify all healthy" -> "Report failure" [label="no"];
}
```

1. **Check Supabase** (`curl -s -o /dev/null -w "%{http_code}" http://localhost:54421/rest/v1/`):
   - If not running, start it: `npx supabase start` (use `run_in_background`). Wait for it to be healthy before proceeding. Supabase provides the local database (port 54422) and Inbucket email (port 54424).
2. **Check Inbucket** (`curl -s -o /dev/null -w "%{http_code}" http://localhost:54424`):
   - Inbucket comes up with Supabase. If Supabase is running but Inbucket isn't, something is wrong — report the error.
3. **Check dev server** (`curl -s -o /dev/null -w "%{http_code}" http://localhost:3333`):
   - If not running, start it: `npm run dev` (use `run_in_background`). The dev server serves on port 3333.
   - Wait up to 30 seconds for the server to respond to requests before proceeding.
4. **Verify all healthy**: Confirm all three endpoints respond (dev server 3333, Supabase API 54421, Inbucket 54424). If any fail after startup, report what failed and stop.

**Monitor background services during verification:** If the dev server or Supabase crashes during verification (network requests start failing, pages return 500s), check the background task output and report the error rather than logging false failures.

**Staging/Production:** Do NOT start any services. Only verify the target URL is reachable. If not, tell the user and wait.

## Step 3: Load Verification Docs

1. Read `docs/verification/index.md` for prerequisites and login credentials
2. Read each verification doc in scope
3. Parse checklist items — format: `- [ ] [depth] **Action** --- Expected result. *Expected: type*`
4. **Filter by depth:** Only run items tagged with the current depth or lower (smoke < standard < deep). Smoke items run at all depths; deep items only run at deep depth.
5. Note the `*Expected: type*` on each item — this tells you what kind of outcome to verify:
   - `success` — happy path works
   - `warning dialog` — warned before destructive action
   - `client-side validation error` — bad input caught before server
   - `graceful server error` — server rejects, UI handles gracefully
   - `auth boundary enforcement` — access control works
   - `success with side effects` — works AND downstream effects happen
   - `graceful empty state` — no-data scenario handled appropriately
6. Note required login credentials per section
7. **If no verification docs exist:** Tell the user and suggest running `/verification-writer` to generate them. Do not proceed without docs.

**Staleness detection:** As you run items, watch for signs the docs are out of date:
- Item describes UI that doesn't exist (button removed, route renamed)
- Item's expected behavior doesn't match actual behavior
- Page has interactive elements with no checklist items
- These get logged and sent to verification-writer for update (see Cross-Skill Integration)

## Step 4: Run Verification Sections

**Browser tool priority:** Use Chrome MCP (`mcp__claude-in-chrome__*`) as primary. Fall back to Playwright (`mcp__playwright__*`) if Chrome fails on a specific interaction.

**For each section:**

### 4a. Login

**Local:** Automate the magic link flow:
1. Navigate to login page
2. Enter the role's email address and click Send Magic Link
3. Retrieve the magic link from Mailpit API (`GET /api/v1/messages`, then `GET /api/v1/message/{id}` and extract the verify URL from the HTML body). Decode `&amp;` to `&` in the extracted URL.
4. Navigate to the magic link URL using `page.evaluate(() => { window.location.href = url })` — **do NOT use `page.goto()`** for Supabase auth verify URLs because the 303 redirect causes Playwright to throw `ERR_HTTP_RESPONSE_CODE_FAILURE`. The `window.location.href` approach lets the browser handle the redirect chain naturally.
5. Wait 10-12 seconds for redirects to complete (auth callback → dashboard)
6. Confirm redirect to the correct dashboard by checking `page.url()`

**To switch roles:** Clear cookies with `page.context().clearCookies()`, clear Mailpit messages with `DELETE /api/v1/messages`, then repeat the flow above.

**Mailpit API (not Inbucket):** The local Supabase instance uses Mailpit at port 54424, NOT Inbucket. The API is:
- `GET /api/v1/messages` — list messages (returns `{ messages: [...] }`)
- `GET /api/v1/message/{id}` — get message with HTML body
- `DELETE /api/v1/messages` — delete all messages

**Staging/Production:** Tell the user which role/email to log in as. Wait for confirmation before proceeding.

---

### Depth: Smoke

**Goal:** Confirm pages load without errors. No interaction testing.

**For each page in scope:**
1. Navigate to the page
2. Verify it renders (no blank screen, no error page, no 500)
3. Read console messages — flag any errors or warnings (`mcp__claude-in-chrome__read_console_messages` or `mcp__playwright__browser_console_messages`)
4. Read network requests — flag any 4xx/5xx responses (`mcp__claude-in-chrome__read_network_requests` or `mcp__playwright__browser_network_requests`)
5. Record: PASS (page loads clean), FAIL (with what broke), or BLOCKED

**Smoke does NOT include:** clicking buttons, filling forms, testing CRUD, checking server logs, or exploring beyond the page load. If you find yourself interacting with elements, you've exceeded smoke depth — stop and confirm with the user.

**Record per page:**
- Status: PASS | FAIL | BLOCKED
- Console errors (list each one, or "none observed")
- Network errors (list each one, or "none observed")
- Screenshot if FAIL

---

### Depth: Standard

**Goal:** Walk every checklist item and verify it works with evidence.

**4b. Walk the Checklist**

For each checklist item:
1. Perform the action described
2. Check if the expected result matches what's in the browser
3. Read console messages after the action — flag errors and warnings
4. Read network requests after the action — flag 4xx/5xx and slow requests (> 2s)
5. Record result: PASS, FAIL (with details), or BLOCKED (precondition not met)

**A checklist item is not PASS unless you have evidence from the DOM, console, AND network that it works.** "It looked right" is not evidence.

**4c. Basic Exploration**

After completing the checklist for a page, do a quick scan for obvious gaps:
- Are there interactive elements on the page that no checklist item covered?
- If yes, test the most important ones (primary actions, navigation, forms)
- Note any functionality not covered by the checklist — propose additions to verification docs

**Record per item:**
- Status: PASS | FAIL | FIXED | SYSTEMIC | BLOCKED
- For FAIL: What actually happened vs. what was expected
- Console errors (list each one — "none observed" is valid, "not checked" is NOT)
- Network errors (list each one — "none observed" is valid, "not checked" is NOT)
- Screenshots if useful

---

### Depth: Deep

**Goal:** Completionist audit. Every element, every edge case, every log source. Nothing is assumed to work.

**4b. Per-Page Deep Audit (MANDATORY for every page visited)**

**This audit runs on EVERY page you navigate to, whether it's part of a checklist item or not.** Loading a page without completing this audit is a skill violation.

**Visual inspection:**
1. Read the full page content — every heading, label, paragraph, tooltip, badge, and status indicator
2. Identify every interactive element: buttons, links, dropdowns, toggles, tabs, form fields, modals, accordions, pagination, sort controls
3. Check for visual defects: broken layouts, overlapping elements, truncated text, missing images, incorrect spacing, inconsistent styling
4. Verify empty states, loading states, and error states render correctly where applicable

**Functional inspection — interact with EVERYTHING:**
5. Click every button and verify its behavior (does it do what the label says?)
6. Click every link and verify it navigates correctly (then come back)
7. Open every dropdown/select and verify options are populated and selectable
8. Toggle every toggle/checkbox and verify state changes
9. Expand every accordion/collapsible section
10. Switch every tab and verify content loads
11. If there's a form: submit it empty, submit it with valid data, submit it with edge cases (special characters, very long input, boundary values)
12. If there's a table/list: verify sorting, filtering, pagination all work
13. If there's CRUD: create an item, read it, update it, delete it — verify each operation round-trips correctly

**Console audit (REQUIRED — not optional):**
14. Read ALL console messages after every interaction (`mcp__claude-in-chrome__read_console_messages` or `mcp__playwright__browser_console_messages`)
15. Log every warning and error — do NOT dismiss console warnings as unimportant
16. If a console error appears, note which interaction triggered it

**Network audit (REQUIRED — not optional):**
17. Read ALL network requests after every interaction (`mcp__claude-in-chrome__read_network_requests` or `mcp__playwright__browser_network_requests`)
18. Flag any failed requests (4xx, 5xx status codes)
19. Flag any unusually slow requests (> 2 seconds)
20. Verify API calls return expected data shapes (spot-check response bodies)

**Server log audit (REQUIRED for local environments):**
21. Check the dev server terminal output for errors, warnings, or unhandled exceptions after each page load and after significant interactions
22. Check Supabase logs if database operations are involved
23. Correlate any server-side errors with the client-side behavior you observed

**4c. Walk the Checklist**

For each checklist item:
1. Perform the action described
2. Check if the expected result matches what's in the browser
3. Run the console audit (steps 14-16 above) — this is not a suggestion, it is required
4. Run the network audit (steps 17-20 above) — this is not a suggestion, it is required
5. Run the server log audit (steps 21-23 above) if local
6. Record result: PASS, FAIL (with details), or BLOCKED (precondition not met)

**A checklist item is not PASS unless you have evidence from the DOM, console, AND network that it works.** "It looked right" is not evidence.

**4d. Explore Beyond the Checklist**

After completing listed items, you are NOT done with the page. Go back and find what the checklist missed:
- Identify every interactive element on the page that was NOT covered by a checklist item
- Test each one using the functional inspection steps from 4b
- Try edge cases the checklist didn't mention: empty forms, special characters, very long input, rapid clicks, back-button navigation
- Check responsive behavior if relevant
- Look for accessibility issues: missing labels, keyboard navigation, focus indicators
- Note any functionality not covered by the checklist — these become proposed additions to the verification docs

**Record per item:**
- Status: PASS | FAIL | FIXED | SYSTEMIC | BLOCKED
- For FAIL: What actually happened vs. what was expected
- Console errors encountered during this item (list each one — "none observed" is valid, "not checked" is NOT)
- Network errors encountered during this item (list each one — "none observed" is valid, "not checked" is NOT)
- Server log errors if local environment (list each one)
- Screenshots if useful (`mcp__playwright__browser_take_screenshot`)
- Elements tested beyond the checklist item (from 4d exploration)

## Step 5: Fix or Log Issues

After completing ALL items in a section, process failures:

```dot
digraph fix_decision {
    "Issue found" [shape=box];
    "Local environment?" [shape=diamond];
    "Log to systemic issues" [shape=box];
    "Under 75 lines?" [shape=diamond];
    "3 or fewer components?" [shape=diamond];
    "2 or fewer routes?" [shape=diamond];
    "Touches shared code?" [shape=diamond];
    "Fix it now" [shape=box];
    "Ask the user" [shape=box];

    "Issue found" -> "Local environment?";
    "Local environment?" -> "Log to systemic issues" [label="no (staging/prod)"];
    "Local environment?" -> "Under 75 lines?" [label="yes"];
    "Under 75 lines?" -> "3 or fewer components?" [label="yes"];
    "Under 75 lines?" -> "Ask the user" [label="no"];
    "3 or fewer components?" -> "2 or fewer routes?" [label="yes"];
    "3 or fewer components?" -> "Ask the user" [label="no"];
    "2 or fewer routes?" -> "Touches shared code?" [label="yes"];
    "2 or fewer routes?" -> "Ask the user" [label="no"];
    "Touches shared code?" -> "Fix it now" [label="no"];
    "Touches shared code?" -> "Ask the user" [label="yes"];
}
```

**Fix thresholds (local only) — ALL must be true:**
- < 75 lines of changes
- Isolated to <= 3 components
- Isolated to <= 2 routes
- Does NOT touch shared code (shared components, utilities, middleware, hooks used across features)

**When fixing:**
1. Fix the code
2. Update tests if the fix changes tested behavior
3. Update verification docs if the fix changes expected behavior
4. Re-verify the fixed item in the browser
5. Log the fix in the "Fixes Applied" section of the run log

**When logging systemic issues:**
- Describe the issue and what's broken
- List affected areas
- Explain why it can't be fixed inline
- Suggest an approach for resolution

## Step 6: Produce Log File and Summary

### Log File

Write to `docs/verification/logs/YYYY-MM-DD-verification-run.md`:

```markdown
# Verification Run - YYYY-MM-DD

## Summary
- Depth: [smoke | standard | deep]
- Scope: [full | feature + tangential]
- Environment: [local | staging | production]
- Sections run: X
- Items checked: X
- Passed: X | Failed: X | Fixed: X | Logged (systemic): X

## Section Results
### [Role - Section Name]
- [PASS] Item description
- [FAIL] Item description - what happened
- [FIXED] Item description - what was wrong, what was changed
- [SYSTEMIC] Item description - why this needs broader discussion

## Console/Network Errors
- [route] error description

## Fixes Applied
### Fix: [description]
- Files changed: ...
- Lines changed: X
- Tests updated: [yes/no]
- Docs updated: [yes/no]

## Systemic Issues
### Issue: [description]
- Affected areas: ...
- Why it can't be fixed inline: ...
- Suggested approach: ...

## Proposed Verification Doc Additions
### [filename] - [Section Name]
- [ ] **Proposed new item** --- Expected result.

## Doc Staleness Detected
- [item]: [what the doc says vs. what reality is]

## Doc Updates Triggered
- verification-writer invoked for [scope]: [stale items updated, missing items added, fixed items revised]
```

### Terminal Summary

Print a concise summary:
```
Verification complete. Log: docs/verification/logs/YYYY-MM-DD-verification-run.md

Results: X passed | X failed | X fixed | X systemic
Fixes applied: [list of short descriptions]
Systemic issues: [list of short descriptions]
Proposed doc additions: X new items across Y files (see log for details)
```

## Log Management

**Check the `verification-docs-config` memory** for log preferences. If preferences are already stored (set by verification-writer), follow them.

**If no preferences exist (first run, verification-writer hasn't been run):** Ask the user:

1. **Git tracking:** "Should verification run logs be tracked in git, or should I add `<verification-path>/logs/` to `.gitignore`?"
   - If gitignored: add the path to `.gitignore`
   - If tracked: leave `.gitignore` unchanged
   - Default suggestion: gitignore run logs (they're ephemeral per-run output)

2. **Old log cleanup:** "Should I clean up old verification run logs, or keep them all?"
   - If cleanup: keep only the most recent 5 run logs, delete older ones
   - If keep all: leave everything

Save preferences to the `verification-docs-config` memory so future runs don't re-ask.

## Common Mistakes

| Mistake | Prevention |
|---|---|
| Asking user to start services locally | Auto-start Supabase and dev server in background; only ask if startup fails |
| Using `page.goto()` for Supabase auth verify URLs | Use `page.evaluate(() => { window.location.href = url })` instead — Playwright throws on 303 redirects |
| All pages returning 500 after `.next` corruption | Kill dev server, run `npm run dev` again — the routes-manifest rebuilds on restart |
| Skipping console/network checks | At ALL depths: check console and network. Even smoke checks these. |
| Defaulting to smoke when user said "verify" | "Verify" means standard. Smoke is only for explicit "quick check" / "does it load" requests. |
| Running deep when user wanted a quick check | Respect the user's time. Smoke means smoke — don't click every button. |
| Loading a page and moving on (standard/deep) | At standard: walk the checklist. At deep: full audit of every element. |
| Checking console once per page (standard/deep) | At standard: check after each checklist action. At deep: check after EVERY interaction. |
| Skipping server logs (deep) | Deep requires server log checks after page loads and significant interactions. |
| Only testing the happy path (deep) | Deep means edge cases: empty, invalid, boundary, special characters for every form. |
| Marking PASS without evidence (standard/deep) | You need DOM, console, AND network evidence — "looked fine" is not PASS. |
| Fixing on staging/production | ALWAYS check environment before fixing |
| Fixing shared code without asking | Trace imports — if file is used outside the current feature, ask |
| Not re-verifying after fix | Re-run the failed item after every fix |
| Missing tangential features | Grep for imports of changed files to find affected features |
| Trusting the checklist is complete | Explore beyond listed items on every page |
| Proceeding without login confirmation | On staging/prod, always wait for user to confirm login |

## Cross-Skill Integration with verification-writer

### When to invoke verification-writer

During a verification run, track staleness. After completing all sections, if any of the following are true, invoke verification-writer with an update payload:

- **Stale items found:** Checklist items describe UI/behavior that doesn't match current code
- **Missing coverage:** Interactive elements found on pages with no corresponding checklist items
- **Fixes applied:** You fixed code during the run, changing expected behavior
- **No docs exist:** `docs/verification/` is empty or missing for the feature in scope

### How to invoke

After completing Step 5 (fixes) and before Step 6 (log), invoke verification-writer:

```
Invoke verification-writer to update docs:
- Section: [role/feature/route]
- Stale items: [list of items that don't match reality]
- Missing items: [elements/interactions with no checklist coverage]
- Fixed items: [items where expected behavior changed due to fixes in this run]
```

Verification-writer will re-analyze the affected sections against current code and update the docs. After it returns, note the updates in your verification log under "Doc Updates Triggered."

### When NOT to invoke

- If the only issues are FAIL items where the code is broken (not the docs) — that's a fix or systemic issue, not a doc update
- If running on staging/production — doc updates should happen against local code
- If the user explicitly said not to update docs

## Red Flags - STOP

- About to edit code on staging/production run
- Fix touches more than 3 components or 2 routes
- Fix exceeds 75 lines
- Changed file is imported by many features (shared code)
- Console shows auth/session errors (may indicate environment issue, not code bug)
- Multiple failures in the same section suggest a systemic issue — consider logging instead of fixing individually
