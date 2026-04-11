---
name: "playwright-test-generator"
description: "Convert verification docs to Playwright tests incrementally. Read verification checklists from docs/verification/, diff against a manifest, and produce or patch Playwright .spec.ts files. Support incremental updates, test pinning, missing data-testid tracking, and hook-driven automation. Use when setting up automated regression testing from verification docs, when verification docs change, or when the pending-generation queue has items."
tags: "["skill"]"
---

# Playwright Test Generator

## Overview

Convert verification checklists (maintained by the verification-writer skill) into automated Playwright test suites. Verification docs are the source of truth. Playwright tests are derived artifacts — translate, do not author.

This skill replaces browser-verification as the regression testing gate. Browser-verification moves to an exploratory-only role (deep dives, new features, visual issues). Regression testing becomes automated and headless via Playwright, eliminating browser contention between concurrent Claude sessions.

**Companion skills:**
- **verification-writer** — produces the docs this skill reads. Layer 3e generates state dependency items that become critical regression tests. Verification docs include YAML frontmatter with versioned page metadata (access control, page characteristics, data dependencies).
- **browser-verification** — exploratory QA only after this skill is active. Feeds findings back to verification-writer, which updates docs, which triggers this skill.

## Document Ownership Model

Each skill owns its own documents and frontmatter. No skill edits another skill's metadata.

```
verification-writer    → owns docs/verification/**
playwright-test-gen    → owns tests/verification-playwright/**
                          including metadata/ (derivative docs)
browser-verification   → reads both, writes neither
```

**Derivative documents:** This skill creates metadata docs in its own directory that reference verification docs by `path@version`. These metadata docs contain test-infrastructure-specific decisions (auth strategy, data setup, readiness state) that don't belong in the upstream verification docs.

## Execution Model

Three modes of operation:

### Script mode (deterministic — runs first)

A JS script at `scripts/verification-playwright/check-versions.js` handles all mechanical staleness detection without LLM involvement. This script:

1. Reads all verification doc frontmatter (version, path, access)
2. Reads all playwright metadata doc frontmatter (version, source reference)
3. Reads all test file header comments (source and metadata references)
4. Compares versions across the chain: verification doc → metadata doc → test file
5. Outputs a structured task list for the agent

**The script produces one of these outputs for each page:**

| Status | Meaning | Agent action required? |
|---|---|---|
| `up-to-date` | All versions match across the chain | No |
| `source-updated` | Verification doc version > metadata doc's `source` version | Yes — re-evaluate metadata, may need test regeneration |
| `metadata-missing` | Verification doc exists but no metadata doc | Yes — create metadata doc, then generate tests |
| `test-missing` | Metadata doc exists (and is ready) but no test file | Yes — generate test file |
| `metadata-outdated` | Metadata doc's own version < test file's `@metadata` version | Yes — investigate (shouldn't happen, may indicate manual edit) |
| `frontmatter-missing` | Verification doc has no YAML frontmatter | Yes — flag to user, cannot proceed without frontmatter |
| `header-missing` | Test file exists but has no `@source` / `@metadata` header comments | Yes — add header comments to existing test |

**This script replaces the full-scan approach.** Instead of the agent parsing every verification doc and test file to figure out what changed, the script does the comparison in milliseconds and hands the agent a precise task list. The agent only processes items that need work.

### Skill mode (LLM-powered)

Invoked by a user or triggered by verification-writer. Reads the task list from `check-versions.js`, then for each item needing work: reads verification docs, understands natural-language item descriptions, evaluates auth requirements, and generates meaningful Playwright test code with correct selectors, setup steps, and assertions.

### Sync mode (deterministic post-hook)

The existing `sync-tests.js` script handles mechanical operations after LLM generation: removing tests for deleted items, updating `@tag` annotations when item IDs change, re-enabling `.skip()` tests when previously-missing testids are found. The postToolUse hook calls this script. Read `references/test-generation-patterns.md` for marker format details.

### Queue bridge

The hook runs `sync-tests.js` first. If the script detects items needing LLM intelligence (new items, substantial changes), it writes them to `pending-generation.json`. The skill reads and processes this queue on next invocation.

## Entry Points

| Trigger | Scope |
|---|---|
| **First run in a project** | Full generation: run `check-versions.js`, create metadata docs for all pages, generate all tests, produce testid-gaps.md report |
| **Pending generation queue** | Read `pending-generation.json`, generate tests for queued items only |
| **User invocation** | Generate or update tests for specified scope (page, flow, or full) |
| **`--check` flag** | Run `check-versions.js` only, report staleness without generating anything |
| **`--force` flag** | Regenerate all tests from scratch, discarding manifest |
| **`--force-index` flag** | Rebuild import-index.json only, preserve item hashes |
| **`--force-items` flag** | Rebuild items.json only, preserve config and index |

## Checklist

Complete these in order:

1. **Run version check script** — execute `check-versions.js`, read the task list output
2. **Triage the task list** — separate into: frontmatter-missing (blocked), metadata-missing (create), source-updated (re-evaluate), test-missing (generate), header-missing (patch), up-to-date (skip)
3. **Handle blocked items** — for `frontmatter-missing`, report to user that verification-writer needs to add frontmatter before tests can be generated
4. **Create/update metadata docs** — for each page needing metadata, read verification doc frontmatter, evaluate auth requirements, create derivative metadata doc (see "Derivative Metadata Docs" below)
5. **Evaluate auth readiness** — for each metadata doc, check if `helpers/auth.ts` (or equivalent) has a working auth flow for the required user types. Set `ready: true/false` accordingly
6. **Generate tests** — for each ready page, generate Playwright test code with proper auth `beforeEach` blocks. For not-ready pages, generate `.skip()` stubs with clear skip reasons
7. **Handle missing testids** — generate `.skip()` stubs, update `testid-gaps.md`
8. **Update manifest** — write changes atomically with lockfile
9. **Rebuild import index** — trace routes to source files, update `manifest/import-index.json`
10. **Patch test headers** — for `header-missing` items, add `@source` and `@metadata` comments to existing test files
11. **Report** — print summary of generated, updated, skipped, blocked, and pinned tests

## Generated Test Structure

```
tests/verification-playwright/
├── manifest/
│   ├── items.json              # Item-to-test mapping, hashes, pin status
│   ├── import-index.json       # Source file → page tag mapping
│   └── config.json             # Tier config, dry-run, test isolation
├── metadata/                   # Derivative docs — this skill's own research
│   ├── admin-dashboard.md      # Auth strategy, data setup, readiness per page
│   ├── event-detail.md
│   └── ...
├── pending-generation.json     # Queue of items needing LLM generation
├── playwright.config.ts        # Extends root config, verification-specific
├── testid-gaps.md              # Missing data-testid work list
├── helpers/
│   ├── auth.ts                 # Login flows per user type
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

## Derivative Metadata Docs

For each verification page doc, this skill creates a metadata doc in `metadata/` that captures test-infrastructure decisions. This metadata is derivative — it references the verification doc but lives in this skill's directory.

### Metadata frontmatter

```yaml
---
version: "1.0.0"
source: "docs/verification/pages/event-detail.md@1.0.0"

# Auth — how THIS test infrastructure satisfies the page's access requirements
auth:
  actor: playwright           # who performs the auth action
  strategy: null              # session-seed | login-flow | api-bypass | token-injection | none | null
  helpers: {}                 # map of user_type → helper function reference
  #   admin: helpers/auth.ts#loginAsAdmin
  #   promoter: helpers/auth.ts#loginAsPromoter
  ready: false                # false = tests generated as .skip()
  skip_reason: "no auth helpers implemented"

# Data setup — how test prerequisites are satisfied
data_setup:
  strategy: null              # api-seed | db-fixture | manual | none | null
  helper: null                # pointer to implementation
  ready: false
  skip_reason: "seed helper not implemented"
---
```

### Metadata content

Below the frontmatter, the metadata doc contains the skill's research notes about the page — what auth decisions were made and why, what data setup is needed, any blockers or gotchas discovered during analysis. This is documentation, not test code.

```markdown
## Auth Analysis

Source page requires: `rbac` with roles `[admin, promoter]`
Public access: `true` (some sections are public, admin/promoter sections need auth)

### Per-user-type auth status

| User Type | Auth Helper | Status | Notes |
|---|---|---|---|
| admin | `helpers/auth.ts#loginAsAdmin` | ready | Uses session seed |
| promoter | — | not ready | Magic link flow not yet automated |
| public | — | ready | No auth needed |

## Data Dependencies

Source page requires:
- "at least one event exists"
- "event has associated venue"

Current setup: No seed helper. Tests will need manual data setup or a fixture.

## Blockers

- Promoter auth requires magic link automation — blocked until email testing infrastructure exists
- Event seed helper needs venue FK — must create venue first
```

### Version tracking

When the source verification doc is updated (version bumps), `check-versions.js` detects the mismatch and adds the page to the agent's task list. The agent then:

1. Reads the verification doc's new frontmatter
2. Diffs against the metadata doc's `source` version
3. If the access model changed (major version bump) → re-evaluate auth strategy, may need to update `helpers/auth.ts`
4. If new items were added (minor version bump) → check if existing auth/data setup covers them
5. If only text changed (patch version bump) → update the `source` reference, check if test regeneration needed
6. Bumps the metadata doc version

## Test File Headers

Every generated test file includes header comments that reference both source documents with versions:

```typescript
/**
 * @source docs/verification/pages/event-detail.md@1.0.0
 * @metadata tests/verification-playwright/metadata/event-detail.md@1.0.0
 * @generated playwright-test-generator v2.0.0
 */
```

These headers enable `check-versions.js` to detect staleness without parsing test code. The script reads only:
1. Verification doc frontmatter (`version` field)
2. Metadata doc frontmatter (`version` and `source` fields)
3. Test file header comments (`@source` and `@metadata` lines)

No test logic parsing, no item-by-item comparison, no LLM involvement.

## Auth-Aware Test Generation

### Reading access requirements

When generating tests for a page, read the verification doc's frontmatter `access` block:

```yaml
access:
  public: false
  auth_model: rbac
  required_roles: [admin]
  mfa_required: false
```

This tells you WHAT the page needs. The metadata doc's `auth` block tells you HOW (and WHETHER) the test infrastructure can satisfy it.

### Auth decision flow

```
1. Read verification doc frontmatter → access.public?
   ├── true → no auth needed, generate tests normally
   └── false → read metadata doc → auth.ready?
       ├── true → generate tests with beforeEach auth from helpers
       └── false → generate tests as .skip() with skip_reason
```

### Generating auth-aware tests

**When auth is ready:**

```typescript
import { loginAsAdmin } from '../helpers/auth';

test.describe('Event Detail - Admin', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('EVT-DTL-ADM-01 Verify edit button is visible @EVT-DTL-ADM-01 @standard @event-detail', async ({ page }) => {
    // ... test code
  });
});
```

**When auth is NOT ready:**

```typescript
test.describe('Event Detail - Admin', () => {
  // SKIP: no auth helper for 'admin' role — see metadata/event-detail.md
  test.skip('EVT-DTL-ADM-01 Verify edit button is visible @EVT-DTL-ADM-01 @standard @event-detail', async ({ page }) => {
    // Auth requirement: rbac, role: admin
    // Implement helpers/auth.ts#loginAsAdmin, then update metadata/event-detail.md auth.ready=true
  });
});
```

### Auth strategy is a per-project decision

The `auth.strategy` field in metadata docs is decided once per project, not per page. Common strategies:

| Strategy | Description | When to use |
|---|---|---|
| `session-seed` | Inject a pre-authenticated session cookie | Fast, no UI interaction, good for most projects |
| `login-flow` | Automate the actual login UI flow | When session seeding isn't possible or login itself needs testing |
| `api-bypass` | Call an auth API endpoint that returns a session | When the app has a test/dev auth bypass |
| `token-injection` | Set a JWT/token directly in storage | For token-based auth (OAuth, API keys) |
| `none` | No auth needed | Public pages |

The chosen strategy should be documented in `helpers/auth.ts` and referenced in all metadata docs. When a new project is initialized, ask the user which strategy fits their auth system.

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

## Version Check Script

The `check-versions.js` script is the key efficiency gain. It replaces agent-driven scanning with deterministic comparison.

### What the script does

```
For each verification doc in docs/verification/pages/:
  1. Parse YAML frontmatter → extract version
  2. Find corresponding metadata doc in metadata/ → extract version + source reference
  3. Find corresponding test file in pages/ → extract @source and @metadata header comments
  4. Compare versions:
     - verification.version vs metadata.source_version → source-updated if mismatch
     - metadata.version vs test.metadata_version → metadata-outdated if mismatch
  5. Check for missing files:
     - No frontmatter → frontmatter-missing
     - No metadata doc → metadata-missing
     - No test file → test-missing
     - No header comments → header-missing
```

### Script output format

```json
{
  "generated_at": "2026-04-10T18:00:00Z",
  "summary": {
    "up_to_date": 12,
    "source_updated": 3,
    "metadata_missing": 2,
    "test_missing": 1,
    "frontmatter_missing": 0,
    "header_missing": 1,
    "total": 19
  },
  "items": [
    {
      "page": "event-detail",
      "status": "source-updated",
      "verification_doc": "docs/verification/pages/event-detail.md",
      "verification_version": "1.2.0",
      "metadata_doc": "tests/verification-playwright/metadata/event-detail.md",
      "metadata_source_version": "1.0.0",
      "test_file": "tests/verification-playwright/pages/event-detail.spec.ts",
      "version_delta": "minor"
    }
  ]
}
```

The `version_delta` field tells the agent whether the change is `patch`, `minor`, or `major` — informing how much re-evaluation is needed.

### When the script runs

| Trigger | How |
|---|---|
| Skill invocation (step 1 of checklist) | Agent runs script, reads output |
| `--check` flag | Script runs, output printed, no generation |
| postToolUse hook | `sync-tests.js` runs first, then `check-versions.js` if sync detected changes |

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

After verification-writer updates docs (and bumps their version), the postToolUse hook triggers `sync-tests.js`. If new or substantially changed items are detected, they are queued in `pending-generation.json`. On next skill invocation, `check-versions.js` detects the version mismatch and the agent processes the queue.

### Relationship to browser-verification

After this skill is active in a project, browser-verification's role changes:
- **Before:** primary regression gate (manual browser runs)
- **After:** exploratory QA only (deep dives, new features, visual/contextual issues)

Browser-verification findings feed back to verification-writer, which updates docs, which triggers this skill. The cycle is: explore → document → automate → regress.

## Common Mistakes

| Mistake | Prevention |
|---|---|
| Regenerating all tests when docs change | Use `check-versions.js` — only process items where versions mismatch |
| Overwriting manually edited tests | Check `generated_hash` — pin tests that were manually edited |
| Blocking commits when pipeline not initialized | Guard clause: exit 0 if `scripts/verification-playwright/` missing |
| Using CSS selectors instead of data-testid | Flag missing testids in testid-gaps.md, generate `.skip()` stubs |
| Running full suite on every commit | Use tag-based `--grep` to run only affected tests |
| Ignoring pending-generation.json | Check the queue at the start of every invocation |
| Hardcoding tier configuration | Read from `manifest/config.json` — tiers are user-configurable |
| Generating tests for authenticated pages without auth setup | Read verification doc frontmatter `access` block → check metadata `auth.ready` → generate `.skip()` if not ready |
| Agent scanning all files to find what changed | Run `check-versions.js` first — it compares versions in milliseconds, hands agent only items that need work |
| Editing verification doc frontmatter | This skill owns `metadata/` docs only. Verification doc frontmatter is owned by verification-writer |
| Missing test file header comments | Every generated test MUST have `@source` and `@metadata` header comments with `path@version` — `check-versions.js` depends on these |
| Not creating metadata docs | Every page needs a metadata doc in `metadata/` before tests can be generated — metadata captures auth and data readiness |
| Generating tests when auth is not ready | Check `auth.ready` in metadata doc — if false, generate `.skip()` with clear reason, don't generate tests that will always fail on the login page |

## Red Flags — STOP

- About to overwrite a pinned test without `--force`
- Manifest files are corrupted — run `verify-pipeline.js` and report
- More than 50% of items are missing testids on a non-initial run — something is wrong with the codebase or the testid detection
- Import index has no entries — the index rebuild failed or the project structure is not recognized
- `check-versions.js` reports `frontmatter-missing` for any doc — verification-writer must add frontmatter before this skill can proceed
- About to edit a file in `docs/verification/` — this skill does not own those files
