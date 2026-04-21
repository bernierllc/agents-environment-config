---
name: "playwright-test-runner"
description: "Autonomous Playwright test execution, environment management, profiling, and bug-fixing loop. Spins up isolated test environments (database, server), executes test suites, profiles performance, diagnoses failures, implements fixes, cleans up all test artifacts, and tears down the environment. Companion to playwright-test-generator. Use when running Playwright test suites, when tests are failing and need diagnosis/fixing, when validating a feature branch before merge, or when the test suite needs a full pass with autonomous repair. Triggered by test failures, CI red builds, pre-merge validation, or explicit user request to run and fix tests."
tags: ["skill"]
---


# Playwright Test Runner

## Overview

Execute Playwright test suites autonomously with full environment lifecycle management. This skill spins up isolated test infrastructure (database, server), confirms which tests to run, executes them with profiling, diagnoses and fixes failures, cleans up all test data, tears down the environment, and delivers a comprehensive report. Fixes are committed incrementally so passing work is never lost.

**Companion skills:**
- **playwright-test-generator** — produces the test files this skill runs. Owns `tests/verification-playwright/` structure, manifest, metadata, and test generation patterns.
- **verification-writer** — produces the verification docs that test-generator reads. Source of truth for what to test.
- **browser-verification** — exploratory QA only. Feeds findings back to verification-writer.

**This skill does NOT generate new tests.** It runs existing tests, fixes code or test infrastructure that causes failures, and reports results. If new tests are needed, invoke playwright-test-generator.

## Prerequisites

Before first invocation, verify:

1. **Playwright is installed** — `npx playwright --version` succeeds
2. **Test files exist** — `tests/verification-playwright/pages/*.spec.ts` or equivalent project test directory contains `.spec.ts` files
3. **Test command is known** — identify the project's test runner command (check `package.json` scripts, `playwright.config.ts`, or ask user)
4. **Dev server is running** (if tests hit a local app) — confirm `baseURL` in playwright config and verify the server is up

If any prerequisite fails, report to user and stop. Do not attempt to fix infrastructure that does not exist.

## Test Scope Confirmation

Before running anything, confirm exactly which tests will execute. Ambiguity about scope wastes time and environment resources.

### When scope is provided as input

If the user specifies scope when invoking the skill (file path, grep pattern, `--changed`, `--all`), echo back the resolved test list before executing:

```
Running 14 tests in 3 files:
  tests/verification-playwright/pages/admin-event-form.spec.ts (8 tests)
  tests/verification-playwright/pages/admin-event-detail.spec.ts (4 tests)
  tests/verification-playwright/pages/admin-event-list.spec.ts (2 tests)

Proceed? [Y/n]
```

Use `npx playwright test --list <scope-args>` to resolve the actual test list without running them.

### When scope is NOT provided

Ask the user before running. Present the available options with context:

```
Which tests to run?
  1. Full suite (N tests across M files)
  2. Changed files only (N tests — based on git diff against <base-branch>)
  3. Specific file(s) — provide path(s)
  4. Specific test(s) — provide grep pattern or test ID
  5. Last failed (N tests from previous run)
```

Populate the counts by running `npx playwright test --list` and checking git status. Do not guess — show real numbers.

### Why this matters

Running the wrong scope leads to: spinning up environments unnecessarily, running tests the user didn't intend to validate, wasting time on unrelated failures, and producing reports that mix signal with noise. Always confirm.

## Test Environment Lifecycle

Tests must run against isolated infrastructure — never against shared, development, or production environments. This skill manages the full lifecycle: detect → spin up → run → clean up → tear down.

### Environment detection (step 0 — before any test runs)

Inspect the project to determine what test infrastructure exists:

1. **Check playwright config** — read `playwright.config.ts` for `globalSetup`, `globalTeardown`, `webServer`, and `baseURL` settings. These reveal whether the project already has environment management.
2. **Check for test database config** — look for `.env.test`, `docker-compose.test.yml`, `scripts/test-db-setup.sh`, or similar. Check `package.json` scripts for `test:setup`, `test:teardown`, `db:test:*` patterns.
3. **Check for containerized test infra** — look for Docker Compose files with test profiles, Testcontainers usage in config, or CI scripts that spin up services.
4. **Check for seed/fixture mechanisms** — look for `globalSetup` files that seed data, `beforeAll` blocks that create test users/records, fixture directories.

### Environment audit result

After detection, classify the project into one of these states and report it to the user:

| State | Description | Action |
|---|---|---|
| **Self-contained** | Tests have `globalSetup`/`globalTeardown` that manage their own database and server. `webServer` config starts the app automatically. | Proceed — environment is managed. Verify teardown actually runs (check for orphaned processes/containers after a previous failed run). |
| **Partial** | Some infrastructure is managed (e.g., `webServer` starts the app) but database is shared or not isolated. | **WARN the user:** "Tests share the development database. Test data will be written to and read from the same database used for development. Recommend adding a test-specific database." Report this in the environment section of the final report. |
| **Manual** | No `globalSetup`, no `webServer`, no test database config. Tests assume everything is already running. | **WARN the user:** "No isolated test environment detected. Tests require manual setup. The following must be running before tests can execute: [list based on config inspection]." Report this as an environment gap. |
| **Unknown** | Cannot determine — config is non-standard or missing. | Ask the user how their test environment works before proceeding. |

**This is a hard gate.** Do not silently run tests against a shared database. If the environment is not isolated, the user must acknowledge the risk before proceeding.

### Spin-up sequence

When the project has test environment management, execute setup in order:

1. **Kill orphans** — check for leftover processes from a previous failed run (orphaned dev servers, zombie database containers). Clean them up. Common checks: `lsof -i :<port>` for the app port, `docker ps --filter` for test containers.
2. **Start test database** — if Docker-based: `docker compose -f docker-compose.test.yml up -d`. If local: run the project's test DB setup script. Wait for readiness (connection check, not just process start).
3. **Run migrations** — if the test database needs schema setup, run migrations against it.
4. **Seed baseline data** — if `globalSetup` handles seeding, it will run automatically. If manual, run the seed script.
5. **Start test server** — if `webServer` in playwright config handles this, Playwright starts it automatically. If manual, start with the test environment variables.
6. **Verify readiness** — hit the `baseURL` health endpoint (or homepage) and confirm a 200 response before running any tests.

Record the start time of each step for the profiling report.

### Teardown sequence (after ALL tests complete, including fix loop)

Teardown runs regardless of test outcome — even on error, timeout, or user interrupt. Execute in reverse order of setup:

1. **Stop test server** — if Playwright's `webServer` manages it, Playwright handles this. If manual, send SIGTERM and wait for graceful shutdown.
2. **Clean test data** — if the project has a cleanup script, run it. If using `globalTeardown`, it handles this. If neither exists, note in the report that test data may persist.
3. **Stop test database** — `docker compose -f docker-compose.test.yml down -v` (with `-v` to remove volumes — test data should never persist). If local database, run the teardown script.
4. **Kill orphans (again)** — final check for any processes that survived teardown. Log what was found.
5. **Verify clean state** — confirm the test port is free, test containers are stopped, and no test-specific processes remain.

Record the end time of each step for the profiling report.

### Cleanup between tests

Individual test cleanup is separate from environment teardown. Each test must clean up after itself so the next test starts with known state:

- **`afterEach` cleanup** — if tests create data (users, records, files), `afterEach` hooks should delete it. If this pattern is missing, note it as a test hygiene gap in the report.
- **Storage state** — clear cookies, localStorage, and sessionStorage between tests unless auth persistence is intentional (e.g., testing session behavior).
- **File system** — if tests write temp files (uploads, downloads, screenshots), clean them in `afterEach` or `globalTeardown`. Check the project's `testConfig.outputDir` and Playwright's `test-results/` directory.
- **Database state** — if tests use transactions that roll back, no action needed. If tests commit data, `afterEach` must delete it. Check for growing row counts across test runs as a signal of missing cleanup.

## Profiling

Collect performance data throughout the entire run. Profiling is not optional — it is always captured and always reported.

### What to profile

| Metric | How to capture | Why it matters |
|---|---|---|
| **Environment spin-up time** | Wall time from first setup step to readiness verified | Slow setup compounds across runs; identifies infra bottlenecks |
| **Per-test duration** | From JSON reporter `duration` field per test | Identifies slow tests that need optimization |
| **Per-file duration** | Sum of test durations per spec file | Identifies files that dominate the suite |
| **Fix loop time per test** | Wall time from diagnosis start to verified fix (or escalation) | Identifies tests that are expensive to debug |
| **Full suite wall time** | Total time from first test to last result | The number the team feels day-to-day |
| **Regression check time** | Wall time for the final full-suite re-run | Measures cost of the safety net |
| **Environment teardown time** | Wall time from first teardown step to clean state verified | Slow teardown blocks the next run |
| **Total session time** | Wall time from skill invocation to report delivery | The full cost of running this skill |

### Performance flags

Flag any of these in the report:

| Flag | Threshold | Implication |
|---|---|---|
| Slow test | Single test >30s | Likely unnecessary navigation, missing `waitFor` targeting, or heavy data setup that should be shared |
| Slow file | File >2min total | Consider splitting into smaller spec files or parallelizing with `test.describe.parallel` |
| Slow setup | Environment spin-up >60s | Cache Docker images, use persistent test databases, or pre-build containers |
| Slow teardown | Teardown >30s | Containers not stopping cleanly, or cleanup scripts doing too much work |
| Suite too long | Full suite >10min | Cross the threshold where developers skip running tests locally — needs parallelization or tier-based selection |

## Execution Model

### The autonomous loop

```
┌──────────────────────────────────────────────────────┐
│ 1. CONFIRM scope (which tests, how many)             │
│    ↓                                                 │
│ 2. AUDIT environment (isolated? shared? manual?)     │
│    ↓                                                 │
│ 3. SPIN UP test environment (db, server, seed)       │
│    ↓                                                 │
│ 4. RUN confirmed scope (JSON reporter + profiling)   │
│    ↓                                                 │
│ 5. PARSE failures from JSON output                   │
│    ↓                                                 │
│ 6. For each failing test:                            │
│    a. READ test file + source code it exercises      │
│    b. DIAGNOSE root cause                            │
│    c. CLASSIFY fix target (app code vs test)         │
│    d. IMPLEMENT fix                                  │
│    e. RE-RUN single test to verify                   │
│    f. If pass → COMMIT fix, next failure             │
│       If fail → try different approach               │
│       (max 3 attempts per test)                      │
│    ↓                                                 │
│ 7. RUN scope again (catch regressions)               │
│    ↓                                                 │
│ 8. CLEAN UP test data + TEAR DOWN environment        │
│    ↓                                                 │
│ 9. REPORT (results + profiling + environment)        │
└──────────────────────────────────────────────────────┘
```

### Scope modes

| Mode | Trigger | What runs |
|---|---|---|
| **Full suite** | Default, `--all` | Every test file |
| **Changed files** | `--changed` | Tests mapped to changed source files (uses `manifest/import-index.json` if available) |
| **Single file** | `--file path/to/spec.ts` | One test file |
| **Single test** | `--grep "TEST-ID"` | One test by grep pattern |
| **Failed only** | `--last-failed` | Re-run only tests that failed in the previous run |

## Checklist

Complete these in order:

1. **Identify test command** — read `package.json` scripts and `playwright.config.ts` to determine the correct run command. Common patterns: `npx playwright test`, `npm run test:e2e`, `npm run test:playwright`. Record the base command for use in all subsequent steps.
2. **Confirm test scope** — resolve which tests will run (see "Test Scope Confirmation" above). If the user provided scope, echo back the resolved list and confirm. If no scope was provided, ask the user. Do not proceed until scope is confirmed. Record: number of tests, number of files, scope mode used.
3. **Audit test environment** — run the environment detection flow (see "Test Environment Lifecycle" above). Classify the project's environment state. If the environment is not isolated, warn the user and get acknowledgment before proceeding. Record the environment state for the report.
4. **Spin up test environment** — execute the spin-up sequence. Time each step. Verify readiness before proceeding. If spin-up fails, report the failure and stop.
5. **Run suite with JSON reporter and profiling** — execute `<base-command> --reporter=json 2>&1` for the confirmed scope. Capture output. Record start/end timestamps and wall time for the profiling report.
6. **Parse results** — extract from JSON output: total tests, passed, failed, skipped, timed out. For each failure, extract: test file path, test name, error message, error stack trace, and expected vs. actual values. Extract per-test and per-file durations for the profiling report.
7. **Triage failures** — categorize each failure before attempting fixes (see "Failure Classification" below). Group by category. Address categories in priority order: environment → test infrastructure → app bugs → flaky tests.
8. **Fix loop** — for each failing test, up to 3 attempts:
   - **8a. Read context** — read the test file (focus on the failing test function via `@begin`/`@end` markers if present). Read the source code the test exercises (use import-index.json or trace from the test's navigation/API calls).
   - **8b. Diagnose** — determine root cause from error message, stack trace, and code inspection. See "Diagnosis Patterns" in `references/diagnosis-patterns.md`.
   - **8c. Classify fix target** — decide whether the fix belongs in app code, test code, test helpers, or test infrastructure. See "Fix Target Decision" below.
   - **8d. Implement fix** — make the minimal change that addresses the root cause. Do not refactor surrounding code.
   - **8e. Verify** — re-run only the specific test: `<base-command> --grep "TEST-ID"`. If it passes, proceed. If it fails, increment attempt counter and try a different approach. Record wall time per attempt for the profiling report.
   - **8f. Commit** — if the fix passes, commit immediately with a descriptive message: `fix(<scope>): <what was wrong and why>`. Include the test ID in the commit body.
9. **Handle stuck tests** — after 3 failed attempts on a single test, stop fixing it. Record: test ID, all three approaches tried, error messages for each, and best diagnosis. Add to the escalation list.
10. **Regression check** — after all individual fixes, run the confirmed scope again. New failures introduced by fixes must be addressed before reporting success (repeat from step 7 for new failures only, max 1 regression pass). Record regression run duration.
11. **Clean up and tear down** — execute the teardown sequence (see "Test Environment Lifecycle" above). Time each step. Verify clean state. If cleanup fails (orphaned containers, undeletable test data), report the failure in the environment section of the report.
12. **Report** — produce the full report (see "Report Format" below), including environment lifecycle, profiling, test results, fixes, and escalations.

## Failure Classification

Classify each failure into exactly one category before attempting a fix. The category determines the approach.

| Category | Signals | Fix approach |
|---|---|---|
| **Environment** | Connection refused, ECONNREFUSED, timeout on navigation, "Target page, context or browser has been closed" | Check dev server, baseURL config, port conflicts. Do NOT fix code — fix environment. |
| **Selector stale** | "Element not found", strict mode violation, locator resolved to 0 elements | Testid was removed/renamed in app code. Grep for the testid in source. Update selector in test or add testid back to source. |
| **Timing** | "Waiting for selector" timeout, flaky pass/fail, "Element is not visible" but element exists | Add or adjust `waitFor`, use `toBeVisible()` with timeout, or use `waitForResponse`/`waitForLoadState`. Fix in test. |
| **Assertion mismatch** | Expected X, received Y — where Y is a plausible real value | App behavior changed. Read the source to determine if X or Y is correct. Fix whichever is wrong. |
| **Auth failure** | Redirect to login, 401/403 response, "Session expired" | Auth helper is broken or session strategy changed. Fix in `helpers/auth.ts`. |
| **Data dependency** | "No rows", empty list, "404 Not Found" for a resource | Seed data is missing or seed helper is broken. Fix in test setup (`beforeEach`/`beforeAll`). |
| **Test logic error** | Test does something that never made sense (wrong URL, wrong field) | Fix in test. Likely a generation error from playwright-test-generator. |
| **App bug** | Test is correct, app behavior is wrong (regression, new bug) | Fix in app code. This is the most valuable category — the test caught a real bug. |
| **Flaky / Non-deterministic** | Same test passes and fails on identical code across runs | Add explicit waits, stabilize selectors, add retry logic. If unfixable in 3 attempts, escalate. |

### Fix Target Decision

```
Is the test asserting the correct expected behavior?
├── No → fix the test (test logic error or stale assertion)
└── Yes → is the app producing the correct actual behavior?
    ├── No → fix the app code (app bug — this is a real catch)
    └── Yes, but intermittently → fix test stability (timing, waits, selectors)
```

**Critical rule:** when the test expects behavior A and the app produces behavior B, determine which is correct by reading the verification doc (source of truth), not by assuming the app is right. Tests derived from verification docs encode the intended behavior. If the app diverges from the verification doc, the app has a bug.

## User Confirmation Required

The autonomous loop runs without asking questions for most fixes. However, STOP and confirm with the user before:

1. **Changing app business logic** — if the diagnosis indicates the app's behavior is intentionally different from what the test expects (feature change, not a bug), do not "fix" the app to match the old test. Ask the user whether to update the test or revert the app change.
2. **Deleting or skipping tests** — never delete a test or add `.skip()` without user approval. If a test seems fundamentally wrong, escalate it.
3. **Modifying more than 3 files for a single test fix** — a fix that touches many files may be a design change, not a bug fix. Confirm scope.
4. **Database or infrastructure changes** — migrations, seed data modifications, config changes that affect shared environments.

For everything else (selector updates, timing fixes, auth helper patches, straightforward app bug fixes), proceed autonomously and document in the commit message.

## Incremental Commits

Every passing fix is committed immediately. This ensures:
- Passing work is never lost if a later fix attempt breaks something
- Each fix is isolated and reviewable
- `git bisect` works if a fix introduces a new issue

### Commit format

```
fix(<scope>): <concise description of what was wrong>

Test: <TEST-ID>
Category: <failure category>
Root cause: <one-line diagnosis>

Co-Authored-By: Claude <tool-name> <noreply@anthropic.com>
```

**Scope** is the area of code fixed: component name, helper name, or `test` for test-only fixes.

## Report Format

After the full run (including teardown), produce this report. Every section is mandatory — if a section has no entries, include it with "None" or "N/A" rather than omitting it.

```markdown
## Playwright Test Runner Report

**Suite:** <test command used>
**Scope:** <what was run — e.g., "Full suite", "Changed files (3 files)", "Single file: admin-event-form.spec.ts">
**Date:** <ISO timestamp>
**Total session time:** <wall time from invocation to report delivery>

### Test Scope

| Detail | Value |
|---|---|
| Scope mode | Full suite / Changed files / Single file / Grep / Last failed |
| Files in scope | N |
| Tests in scope | N |
| Tests actually run | N |
| Tests skipped (by design) | N |

### Environment

| Detail | Value |
|---|---|
| Environment state | Self-contained / Partial / Manual / Unknown |
| Test database | Isolated (Docker) / Isolated (local) / Shared (⚠️) / None detected |
| Test server | Playwright webServer / Manual / Already running |
| Seed data | globalSetup / beforeAll fixtures / Manual / None |
| Isolation method | Per-test transactions / Per-test user / Database reset / None detected (⚠️) |

**Environment warnings:**
- (List any warnings issued during environment audit — shared database, manual setup required, missing teardown, etc.)
- (If none: "No warnings — environment is fully isolated and self-managed.")

**Spin-up log:**

| Step | Duration | Status |
|---|---|---|
| Kill orphans | 0.2s | Clean (no orphans found) |
| Start test database | 3.4s | OK |
| Run migrations | 1.2s | OK |
| Seed baseline data | 0.8s | OK |
| Start test server | 2.1s | OK |
| Verify readiness | 0.3s | OK (200 from http://localhost:3001) |
| **Total spin-up** | **8.0s** | |

**Teardown log:**

| Step | Duration | Status |
|---|---|---|
| Stop test server | 0.5s | OK |
| Clean test data | 0.3s | OK |
| Stop test database | 1.8s | OK (volumes removed) |
| Kill orphans (final) | 0.1s | Clean |
| Verify clean state | 0.2s | OK (port 3001 free, no test containers) |
| **Total teardown** | **2.9s** | |

**Cleanup warnings:**
- (List any issues during teardown — orphaned processes found, containers that wouldn't stop, test data that couldn't be deleted, etc.)
- (If none: "Clean teardown — no residual processes or data.")

### Test Results Summary

| Metric | Count |
|---|---|
| Total tests | N |
| Passed (before fixes) | N |
| Failed (before fixes) | N |
| Fixed autonomously | N |
| Still failing (escalated) | N |
| Skipped (by design) | N |
| New regressions from fixes | N |

### Profiling

**Timing breakdown:**

| Phase | Duration | % of session |
|---|---|---|
| Environment spin-up | Xs | N% |
| Initial suite run | Xs | N% |
| Fix loop (total) | Xs | N% |
| Regression check run | Xs | N% |
| Environment teardown | Xs | N% |
| **Total session** | **Xs** | **100%** |

**Slowest tests (top 5):**

| Test ID | File | Duration | Flag |
|---|---|---|---|
| EVT-FRM-TKT-03 | admin-event-form.spec.ts | 45s | ⚠️ >30s |
| ... | ... | ... | |

**Slowest files (top 5):**

| File | Tests | Total Duration | Flag |
|---|---|---|---|
| admin-event-form.spec.ts | 36 | 3m 12s | ⚠️ >2min |
| ... | ... | ... | |

**Fix loop profiling:**

| Test ID | Attempts | Total fix time | Outcome |
|---|---|---|---|
| EVT-FRM-01 | 1 | 42s | Fixed |
| EVT-DTL-03 | 2 | 1m 38s | Fixed |
| EVT-LST-07 | 3 | 4m 12s | Escalated |

**Performance flags:**
- (List any flags triggered — slow tests, slow files, slow setup, suite too long, etc.)
- (If none: "No performance flags — all thresholds within limits.")

### Fixes Applied

| Test ID | Category | Root Cause | Fix | Commit |
|---|---|---|---|---|
| EVT-FRM-01 | Selector stale | testid renamed in refactor | Updated selector in test | abc1234 |
| EVT-DTL-03 | App bug | Null check missing on venue FK | Added null guard in EventDetail.tsx | def5678 |

### Escalated (Needs Human Judgment)

| Test ID | Category | Attempts | Best Diagnosis | Why Escalated |
|---|---|---|---|---|
| EVT-LST-07 | Flaky | 3 | Race condition in list hydration | Could not stabilize with waits; may need app-level fix |

### Test Hygiene Observations

- **Cleanup gaps:** (List tests or files missing `afterEach` cleanup, growing database row counts, temp files not cleaned)
- **Isolation issues:** (List tests that depend on other tests' state, shared mutable fixtures, or order-dependent behavior)
- **Missing infrastructure:** (List gaps — no test database, no seed mechanism, no teardown script)
- (If none: "Test hygiene is healthy — all tests clean up after themselves and run in isolation.")

### Assumptions Made

List any judgment calls made during autonomous fixing:
- Assumed X was the correct behavior based on verification doc Y
- Updated selector Z based on current DOM structure; original testid may have been intentionally removed
```

## Integration with Test Generator

When this skill discovers issues that belong to playwright-test-generator's domain:

| Discovery | Action |
|---|---|
| Test was generated with wrong interaction type | Fix the test, note in report that generator should be re-run for this item |
| Testid is missing and no stable alternative exists | Do NOT add `.skip()` — escalate as "needs testid" in report. Generator owns skip decisions. |
| Verification doc has changed but test was not regenerated | Note staleness in report. Run `check-versions.js` if available, or flag for generator invocation. |
| Auth helper needs to be created from scratch | Out of scope — escalate. Generator owns auth helper creation via metadata docs. |
| Test file has no `@begin`/`@end` markers | Still fixable — use test name/function to locate. Note in report that markers should be added. |

## Parallel Execution Strategy

When the failure count is high (>10 failures), consider parallel diagnosis:

1. Run the full suite once to get all failures
2. Group failures by file
3. Dispatch parallel agents per file (each agent handles all failures in one file)
4. Merge fixes, run full suite for regression check

**Constraint:** no two agents may fix the same file. If failures in different test files trace to the same source file, serialize those fixes.

## Timeout and Circuit Breakers

| Threshold | Action |
|---|---|
| Single test takes >60s to run | Flag as slow; check for missing `waitFor` or unnecessary navigation |
| Fix loop exceeds 30 minutes wall time | Stop, report progress, ask user whether to continue |
| More than 50% of tests fail | Likely an environment or infrastructure issue, not individual bugs. Stop individual fixing, diagnose the systemic issue first. |
| Full suite run after fixes produces >5 NEW failures | Fixes are causing regressions. Stop, revert last batch of fixes, escalate. |
| 3 consecutive tests in the same file fail with the same error | File-level issue (likely import, auth, or setup). Fix the shared root cause before proceeding with individual tests. |

## Common Mistakes

| Mistake | Prevention |
|---|---|
| Fixing app code to match a stale test | Always check the verification doc for intended behavior before changing app code |
| Adding `.skip()` to a failing test | Never skip without user approval. Fix or escalate. |
| Running the full suite after every single fix | Run individual test to verify fix, full suite only at the end |
| Fixing symptoms instead of root cause | If 5 tests fail because auth is broken, fix auth once, not 5 tests |
| Committing a fix that breaks other tests | Full regression run at the end catches this; revert if needed |
| Ignoring timeout failures as "flaky" | Timeouts usually indicate a real issue (missing wait, slow server, navigation error) |
| Refactoring while fixing | Minimal fix only. Refactoring belongs in a separate task. |
| Fixing tests for pages with `auth.ready: false` in metadata | These tests are intentionally skipped. If they fail, the skip was removed incorrectly — restore it, don't fix the test. |
| Running without JSON reporter | Always use `--reporter=json` for parseable output. Human-readable reporters miss structured failure data. |
| Running tests against shared/dev database without warning | Always audit environment first. If not isolated, warn user and get acknowledgment. |
| Skipping teardown after test failures | Teardown runs regardless of outcome. Orphaned containers and test data corrupt future runs. |
| Not confirming test scope before running | Always resolve and display the test list before executing. Wrong scope wastes environment spin-up time. |
| Ignoring slow tests in the report | Profile every run. Slow tests compound into suites developers stop running. |
| Leaving test data behind | Verify cleanup ran. Check for orphaned rows, temp files, and stale containers after teardown. |

## Red Flags — STOP

- More than 50% of tests fail on the first run — diagnose environment/infrastructure first
- A fix requires changing a verification doc — this skill does not own verification docs
- A fix requires generating new tests — invoke playwright-test-generator instead
- About to modify a pinned test (check `items.json` for `"pinned": true`) without user approval
- Dev server is not running and cannot be started — report and stop
- Fix attempt introduces a security vulnerability (e.g., disabling auth checks to make tests pass)
- About to commit changes to `.env`, credentials, or secrets files
- Environment teardown failed — orphaned containers or processes remain. Report and guide manual cleanup.
- Tests are running against a production or shared staging database — stop immediately
- Test scope was never confirmed with the user — do not run tests without explicit scope agreement
