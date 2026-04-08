---
name: "playwright-test-generator"
description: "Convert verification docs to Playwright tests incrementally. Read verification checklists from docs/verification/, diff against a manifest, and produce or patch Playwright .spec.ts files. Support incremental updates, test pinning, missing data-testid tracking, and hook-driven automation. Use when setting up automated regression testing from verification docs, when verification docs change, or when the pending-generation queue has items."
tags: ["skill"]
---


# Playwright Test Generator

## Overview

Convert verification checklists (maintained by the verification-writer skill) into automated Playwright test suites. Verification docs are the source of truth. Playwright tests are derived artifacts — translate, do not author.

This skill replaces browser-verification as the regression testing gate. Browser-verification moves to an exploratory-only role (deep dives, new features, visual issues). Regression testing becomes automated and headless via Playwright, eliminating browser contention between concurrent Claude sessions.

**Companion skills:**
- **verification-writer** — produces the docs this skill reads. Layer 3e generates state dependency items that become critical regression tests.
- **browser-verification** — exploratory QA only after this skill is active. Feeds findings back to verification-writer, which updates docs, which triggers this skill.

## Execution Model

Two modes of operation:

### Skill mode (LLM-powered)

Invoked by a user or triggered by verification-writer. Read verification docs, understand natural-language item descriptions, and generate meaningful Playwright test code with correct selectors, setup steps, and assertions. This is the primary authoring mode — run during initial generation, when new items are added, and when items are substantially rewritten.

### Script mode (deterministic)

A Node.js script at `scripts/verification-playwright/sync-tests.js` handles mechanical operations without LLM involvement: removing tests for deleted items, updating `@tag` annotations when item IDs change, re-enabling `.skip()` tests when previously-missing testids are found. The postToolUse hook calls this script. Read `references/test-generation-patterns.md` for marker format details.

### Queue bridge

The hook runs `sync-tests.js` first. If the script detects items needing LLM intelligence (new items, substantial changes), it writes them to `pending-generation.json`. The skill reads and processes this queue on next invocation.

## Entry Points

| Trigger | Scope |
|---|---|
| **First run in a project** | Full generation: walk each verification page doc section by section, generate all tests, produce testid-gaps.md report |
| **Pending generation queue** | Read `pending-generation.json`, generate tests for queued items only |
| **User invocation** | Generate or update tests for specified scope (page, flow, or full) |
| **`--force` flag** | Regenerate all tests from scratch, discarding manifest |
| **`--force-index` flag** | Rebuild import-index.json only, preserve item hashes |
| **`--force-items` flag** | Rebuild items.json only, preserve config and index |

## Checklist

Complete these in order:

1. **Check for pending generation queue** — read `pending-generation.json`, process if non-empty
2. **Determine scope** — first run (no manifest), incremental (manifest exists), or force
3. **Read verification docs** — parse items from page and flow docs in `docs/verification/`
4. **Read manifest** — load `manifest/items.json`, `manifest/import-index.json`, `manifest/config.json`
5. **Diff and generate** — for each new or changed item, generate Playwright test code
6. **Handle missing testids** — generate `.skip()` stubs, update `testid-gaps.md`
7. **Update manifest** — write changes atomically with lockfile
8. **Rebuild import index** — trace routes to source files, update `manifest/import-index.json`
9. **Report** — print summary of generated, updated, skipped, and pinned tests

## Generated Test Structure

```
tests/verification-playwright/
├── manifest/
│   ├── items.json              # Item-to-test mapping, hashes, pin status
│   ├── import-index.json       # Source file → page tag mapping
│   └── config.json             # Tier config, dry-run, test isolation
├── pending-generation.json     # Queue of items needing LLM generation
├── playwright.config.ts        # Extends root config, verification-specific
├── testid-gaps.md              # Missing data-testid work list
├── helpers/
│   ├── auth.ts                 # Login flows (magic link, OAuth mock)
│   └── assertions.ts           # Reusable assertion patterns per expectation type
├── pages/
│   ├── admin-event-form.spec.ts    # 1:1 with verification page doc
│   ├── admin-event-detail.spec.ts
│   └── ...
└── flows/
    ├── event-lifecycle.spec.ts     # 1:1 with verification flow doc
    └── ...
```

Read `references/manifest-format.md` for detailed schema documentation.

## Generating Tests

### Item-to-test mapping

Each verification item becomes one Playwright test function. Read `references/test-generation-patterns.md` for the complete mapping rules, including:

- Tag format: `@ITEM-ID @depth @page-name` in test names
- `@begin:ITEM-ID` / `@end:ITEM-ID` markers wrapping each test function
- How each annotation type (`STATE-DEPENDENCY`, `BUSINESS-CONTEXT`, `API-VERIFICATION-FLAG`) maps to test setup, assertions, and comments
- Content hash normalization algorithm
- Test pinning behavior

### Annotation consumption

**`<!-- STATE-DEPENDENCY -->`** annotations drive the most important regression tests:
- `trigger` → test setup sequence (the action that initiates the state change)
- `affected_fields` → assertion targets (each field checked after trigger)
- `expected_cascade` → ordered `expect()` calls, one per cascade step
- `code_ref` → embedded as a code comment for traceability
- `failure_mode` → determines assertion strategy (FK violations check form prevents submission)

**`<!-- BUSINESS-CONTEXT -->`** annotations inform value assertions:
- `rule` → code comment with the business rule
- `valid_range` → bounds check assertions
- `cross_reference` → assertions comparing related values on the same page
- `red_flags` → negative assertions (specific wrong values to watch for)

### Missing data-testid handling

On initial runs, many testids will be missing. This is expected and welcomed — the skill surfaces this as a work list.

- Items with missing testids get a test stub with `.skip()` and a TODO comment
- All gaps are logged to `testid-gaps.md` (read `references/test-generation-patterns.md` for format)
- The first run walks through each verification page doc section by section, reporting progress
- On subsequent runs, check if previously-missing testids have been added and un-skip those tests

### Test pinning

When a developer manually edits a generated test to fix a bad selector or add project-specific setup:

1. `sync-tests.js` detects the content between `@begin`/`@end` markers no longer matches `generated_hash`
2. It sets `"pinned": true` in `items.json`
3. Pinned tests are never overwritten — reported as "pinned (manually edited)" in the generation log
4. Un-pin by setting `"pinned": false` in `items.json`, or use `--force`

## Tiered Test Execution

Read `references/hook-templates.md` for the complete hook configuration. Summary:

| Tier | Trigger | Browsers | Depth | Scope |
|---|---|---|---|---|
| **Gate** | pre-commit | Chromium | smoke + standard | Changed tests only, maxTests cap |
| **Thorough** | pre-push to staging | Chromium + Firefox + WebKit | All depths | Changed tests only |
| **Full** | pre-push to main/prod | All + mobile | All depths | All tests |

Tier configuration is fully user-configurable in `manifest/config.json`.

## Cross-Skill Integration

### When invoked by verification-writer

After verification-writer updates docs, the postToolUse hook triggers `sync-tests.js`. If new or substantially changed items are detected, they are queued in `pending-generation.json`. The skill processes the queue on next invocation.

### Relationship to browser-verification

After this skill is active in a project, browser-verification's role changes:
- **Before:** primary regression gate (manual browser runs)
- **After:** exploratory QA only (deep dives, new features, visual/contextual issues)

Browser-verification findings feed back to verification-writer, which updates docs, which triggers this skill. The cycle is: explore → document → automate → regress.

## Common Mistakes

| Mistake | Prevention |
|---|---|
| Regenerating all tests when docs change | Use incremental diff — only generate for new/changed items |
| Overwriting manually edited tests | Check `generated_hash` — pin tests that were manually edited |
| Blocking commits when pipeline not initialized | Guard clause: exit 0 if `scripts/verification-playwright/` missing |
| Using CSS selectors instead of data-testid | Flag missing testids in testid-gaps.md, generate `.skip()` stubs |
| Running full suite on every commit | Use tag-based `--grep` to run only affected tests |
| Ignoring pending-generation.json | Check the queue at the start of every invocation |
| Hardcoding tier configuration | Read from `manifest/config.json` — tiers are user-configurable |

## Red Flags — STOP

- About to overwrite a pinned test without `--force`
- Manifest files are corrupted — run `verify-pipeline.js` and report
- More than 50% of items are missing testids on a non-initial run — something is wrong with the codebase or the testid detection
- Import index has no entries — the index rebuild failed or the project structure is not recognized
