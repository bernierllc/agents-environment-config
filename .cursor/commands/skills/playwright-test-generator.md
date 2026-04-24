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

## Recommended Operator

This skill is best operated by the **Playwright Test Writer** agent (`playwright-test-writer`) or another agent with deep Playwright expertise. Agents without Playwright-specific knowledge will produce complete tests for simple interactions but may default to stubs for complex ones.

Place the agent definition in `.claude/agents/` (project-level) or `~/.claude/agents/` (user-level) following Claude standards.

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
| `skill-version-mismatch` | Verification doc's `generated_by` (live verification-writer version) is newer than the metadata doc's `source_generated_by` (the version this manifest was synced against) | Yes — user MUST run `--resync` before any other generation work; the skill STOPS otherwise |
| `stamp-missing` | Verification doc has frontmatter but no `generated_by` stamp (pre-v3.1.0 verification-writer output) | Yes — tell user to run verification-writer to add the stamp; proceed cautiously if user overrides |

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
| **`--resync` flag** | Adopt a newer verification-writer skill version: apply that version's ID renames (from verification-writer's migration table) to the manifest and test `@tag` annotations, update every `source_generated_by` field in metadata docs, update every `@source-generated-by` line in test headers. Does NOT regenerate test bodies |

## Checklist

Complete these in order:

1. **Run version check script** — execute `check-versions.js`, read the task list output
2. **Check for `skill-version-mismatch` entries FIRST** — if any item has this status, STOP. Report the gap to the user and direct them to re-run with `--resync`. Do not proceed to step 3 until either every mismatch is resolved by a `--resync` pass OR the user explicitly overrides. Silent adoption of a newer verification-writer version corrupts downstream anchors (see "Skill Version Compatibility")
3. **Triage the remaining task list** — separate into: frontmatter-missing (blocked), stamp-missing (blocked, direct user to verification-writer), metadata-missing (create), source-updated (re-evaluate), test-missing (generate), header-missing (patch), up-to-date (skip)
4. **Handle blocked items** — for `frontmatter-missing` and `stamp-missing`, report to user that verification-writer needs to run before tests can be generated
5. **Create/update metadata docs** — for each page needing metadata, read verification doc frontmatter, evaluate auth requirements, create derivative metadata doc (see "Derivative Metadata Docs" below). Record the source doc's `generated_by` value as `source_generated_by` in the metadata frontmatter
6. **Evaluate auth readiness** — for each metadata doc, check if `helpers/auth.ts` (or equivalent) has a working auth flow for the required user types. Set `ready: true/false` accordingly
7. **Generate tests** — for each ready page, generate Playwright test code with proper auth `beforeEach` blocks. For not-ready pages, generate `.skip()` stubs with clear skip reasons
   - **7a. Before writing each test:** classify the verification item by interaction type (see `references/test-generation-patterns.md`), confirm the planned test will contain all must-have elements for that type, then write the test (Checkpoint A — see Test Completeness Standards)
   - **7b. Pre-flight ID validation (before writing each spec file):** After generating the full text of a spec file, before writing to disk, extract every `@begin:ID` from the generated text and cross-check against the ID set from `parseVerificationItems()`. If any `@begin:ID` is not in that set, refuse to write and report the specific invalid IDs. This is a hard stop — do not write the file.
8. **Handle missing testids** — exhaust stable alternative selectors first (`getByRole` → `getByLabel` → `getByText` for static copy → `getByPlaceholder` for static copy); generate `.skip()` stub only if all fail and only for types that require DOM selectors (not `api-response` or `auth-boundary`); document alternatives tried in stub comment (see stub template in `references/test-generation-patterns.md`); update `testid-gaps.md`
9. **Update manifest** — write changes atomically with lockfile
10. **Rebuild import index** — trace routes to source files, update `manifest/import-index.json`
11. **Patch test headers** — for `header-missing` items, add `@source`, `@source-generated-by`, `@metadata`, and `@generated-by` comments to existing test files
    - **11a. Post-generation audit (Checkpoint B — gates step 12):** count complete tests vs. stubs; for every stub verify it carries one of the four valid skip reasons from Test Completeness Standards; reclassify and implement any stub with an invalid reason; do not proceed to step 12 until every stub has a valid reason
12. **Report** — print summary of generated, updated, skipped, blocked, and pinned tests

## Generated Test Structure

```
tests/verification-playwright/
├── manifest/
│   ├── items.json              # Item-to-test mapping, hashes (hash_version field), pin status
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
source_generated_by: "verification-writer@3.1.0"   # verification-writer version this metadata was synced against
generated_by: "playwright-test-generator@3.2.0"     # this skill's version when the metadata was last written

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
 * @source-generated-by verification-writer@3.1.0
 * @metadata tests/verification-playwright/metadata/event-detail.md@1.0.0
 * @generated-by playwright-test-generator@3.2.0
 */
```

All four lines are required. `@source-generated-by` records the verification-writer version this test was last synced against — `check-versions.js` compares it to the live verification doc's `generated_by` to detect `skill-version-mismatch`. `@generated-by` records the playwright-test-generator version that produced the test.

These headers enable `check-versions.js` to detect staleness without parsing test code. The script reads only:
1. Verification doc frontmatter (`version` and `generated_by` fields)
2. Metadata doc frontmatter (`version`, `source`, `source_generated_by`, `generated_by` fields)
3. Test file header comments (`@source`, `@source-generated-by`, `@metadata`, `@generated-by` lines)

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

## Test Completeness Standards

### What "complete" means

A complete test executes the full interaction described in the verification item, asserts the expected outcome, and runs without `.skip()`. A stub is only acceptable when a specific infrastructure blocker prevents execution.

### Valid skip reasons (exhaustive — exactly four)

Only these four reasons justify a `.skip()` stub:

1. **`auth.ready = false`** in the metadata doc — the auth helper for the required user type is not implemented
2. **`data_setup.ready = false`** in the metadata doc — the seed/fixture infrastructure to create required test data is not implemented. "Requires test data setup" is never a skip reason on its own — only the metadata flag is.
3. **Testid genuinely missing AND no stable alternative selector exists** — see stable alternative priority order below. **Not applicable to `api-response` or `auth-boundary` types**, which use `page.request` or navigation assertions and require no DOM selector. Claiming missing testid as a skip reason for these types is a misclassification.
4. **Item explicitly marked `manual-only`** in the verification doc

### Invalid skip reasons — these are interaction types, not blockers

| This is NOT a valid skip reason | What to do instead |
|---|---|
| "Multi-step interaction" | Classify as `multi-step-workflow`, implement each step |
| "Involves file upload" | Classify as `file-upload`, use `setInputFiles` |
| "Requires waiting for API response / network" | Use `waitForResponse` or `page.request` |
| "API-level test / backend-only" | Classify as `api-response`, use `page.request` |
| "Complex workflow" | Classify by type, implement the steps |
| "Requires test data setup" | Check `data_setup.ready` in metadata — if true, implement setup in `beforeEach` |
| "Too many steps" | Not a skip reason under any circumstance |
| "Involves navigation between pages" | Classify as `multi-step-workflow` |

### Stable alternative selector order (for skip reason 3)

Before claiming a testid is missing and no alternative exists, attempt these in order:

1. `getByRole` with an accessible name — e.g., `getByRole('button', { name: 'Upload' })`
2. `getByLabel` — for form controls with an associated visible label
3. `getByText` — **only for static UI copy** (button labels, column headers, field labels, section titles). **Not valid for dynamic data values** (status strings, counts, user-generated content, locale-sensitive strings). If the text changes based on data, this selector is not stable.
4. `getByPlaceholder` — **only for static placeholder text**, not programmatically-set values

Only if all applicable options are exhausted is the element untargetable without a testid. See `references/test-generation-patterns.md` for the required stub comment format.

### Two completeness checkpoints

**Checkpoint A — Per-item classification (before writing each test):**
Classify the verification item by interaction type (see `references/test-generation-patterns.md`). Confirm the test you are about to write will contain all must-have elements for that type. Then write the test.

**Checkpoint B — Post-generation audit (gates the Report step):**
After all tests are written, before declaring generation complete:
1. Count complete tests vs. stubs
2. For every stub, verify it carries one of the four valid skip reasons above
3. Any stub with an invalid reason must be reclassified and implemented
4. Only after every stub has a valid reason may the Report step proceed

## Testid Strategy

### When testids belong in the codebase

Testids are a **development artifact, not a testing artifact**. They should be added when a component is built, not retroactively when tests fail. The standard: every interactive element, dynamic state container, and structural landmark gets a `data-testid` as part of component development — the same way accessible `aria-label` attributes are required on icon buttons.

**Elements that always need a testid:**
- Every interactive element (buttons, inputs, selects, file inputs, links that trigger behavior)
- Every element that displays dynamic state (error messages, success banners, empty states, loading indicators, count badges, status fields)
- Structural landmarks (sidebar, header, main content area, modal container, form containers)

**Elements that do not need a testid:**
- Static decorative elements (icons, dividers, static copy)
- Elements reliably targetable by stable accessible role + name (e.g., a labeled `<button>Submit</button>` is targetable via `getByRole('button', { name: 'Submit' })`)

### The anti-pattern this skill must not reinforce

Generating stubs and treating "testid will be added later" as an acceptable holding state. Stubs accumulate. The correct path when a testid is missing: exhaust stable alternative selectors first (see Test Completeness Standards), generate a `.skip()` stub only if all alternatives fail, document which alternatives were tried, and record the gap in `testid-gaps.md`.

### Upstream ownership

Testid enforcement belongs upstream in the workflow:
- **Frontend development rules** (CLAUDE.md, cursor rules) — require testids as part of "done" for any component
- **Frontend agent definitions** — agents that write components must add testids to all interactive and state-displaying elements before declaring a component complete
- **verification-writer skill** — may note expected testids alongside verification items

**This skill's position:** for new feature development, testids should already exist when this skill runs. `testid-gaps.md` is not deprecated — it remains active as the retrofit backlog for existing code that predates the testid standard, and as the fallback until upstream enforcement is fully in place. Gaps on *new features* are an upstream process failure. Gaps on *existing code* are expected and tracked here.

## ID Source Discipline

The single most important invariant in this skill: **every `@begin:ID` and `@end:ID` marker emitted must correspond to an ID returned by `parseVerificationItems()` on the source doc.** Never invent, derive, or slugify an ID.

The failure mode this prevents: 91 orphan `@begin` markers appeared in one project because the generator was "being creative" — emitting markers for IDs that `parseVerificationItems()` never returned. The orphan check (`verify-pipeline.js --check-orphans`) caught them at the pre-commit gate, but they had already been merged across 5 PRs before the gate existed.

**The rule:**

1. Call `parseVerificationItems()` on the source doc before writing any test.
2. Build a set of the returned IDs.
3. For each test you generate, look up the item's ID in that set.
4. If the ID is in the set → emit `@begin:ID` and `@end:ID` normally.
5. If the ID is NOT in the set → do NOT emit markers. Log the gap: "Item has no parseable ID in source doc — skipping markers. Check doc format." Do not generate a test for this item. This is a doc format gap, not a generator decision point.

**Consequences:**
- Format B IDs (slugified from action text) may or may not match what `parseVerificationItems()` returns, depending on which slugify function was used and when. This is exactly why Format A (explicit `**ID**` in bold) is required in verification docs — it gives the parser an unambiguous ID to return.
- If `parseVerificationItems()` returns no IDs for a doc, STOP. Do not generate tests. Report: "No items parseable from [doc path] — verification-writer may need to add Format A IDs to this doc."
- Flow docs: FLOW-PREFIX-NN IDs in flow step items are valid Format A IDs. They must appear in the flow doc as `**FLOW-PREFIX-NN**` for `parseVerificationItems()` to return them. If a flow doc uses only narrative steps with no explicit IDs, report the gap to the user — do not mint FLOW-* IDs.

**Shared slugify:** Both this skill and `sync-tests.js` must use the same slugify function. During pipeline initialization, extract or confirm that `scripts/verification-playwright/lib/slugify.js` exists and that both files import from it. Divergent slugify implementations produce different IDs for the same input, which causes drift whenever both tools touch the same item.

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

On initial runs against existing code, some testids may be missing. This is a tracked gap, not a blanket skip reason.

Before generating a skip stub for a missing testid:
1. Confirm the item's interaction type requires DOM selectors (`api-response` and `auth-boundary` often do not)
2. Attempt stable alternative selectors in order: `getByRole` → `getByLabel` → `getByText` (static copy only) → `getByPlaceholder` (static copy only)
3. Only if all applicable alternatives fail, generate a `.skip()` stub
4. The stub comment MUST document which alternatives were tried and why each was rejected (see stub template in `references/test-generation-patterns.md`)

- All gaps are logged to `testid-gaps.md` (read `references/test-generation-patterns.md` for format)
- The first run walks through each verification page doc section by section, reporting progress
- On subsequent runs, check if previously-missing testids have been added and un-skip those tests
- Do NOT fall back to fragile CSS/text selectors as a substitute — the `.skip()` stub is correct; the fix belongs in the component source

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

## Hash Algorithm

The `generated_hash` field in `items.json` records the content hash of each test (content between `@begin`/`@end` markers). A hash mismatch signals that a developer manually edited the test — the test is then pinned and never overwritten.

### Normalization (must be applied before hashing)

The normalization algorithm must be consistent across all runs. Lock it:

1. Strip trailing whitespace from each line
2. Normalize line endings: CRLF → LF
3. Trim leading and trailing blank lines from the block
4. Encode as UTF-8

Any deviation from this algorithm produces a different hash for the same logical content — triggering false "manually edited" detections and flooding the pinned test list.

### hash_version field

`items.json` includes a top-level `hash_version` field that records which version of the normalization algorithm was used to produce the hashes in that file:

```json
{
  "hash_version": 1,
  "items": { ... }
}
```

- Drift within the same `hash_version` is a bug — the algorithm is non-deterministic.
- Drift across `hash_version` values is expected — bump `hash_version` when the normalization algorithm changes, and regenerate all hashes on the next `--force` run.
- When reading `items.json`, if the `hash_version` is absent, treat it as version 0 (legacy, pre-normalization-lock). All hashes from version 0 are suspect — a `--force` regeneration is recommended.

## Skill Version Compatibility

This skill consumes documents produced by verification-writer. When verification-writer evolves (new item ID conventions, frontmatter changes, structural renames), the manifests and test markers in this skill's territory are pinned to the OLD naming. Silent adoption of a newer verification-writer version will corrupt the `@tag` annotations, break `@begin:ID`/`@end:ID` marker alignment, and produce misleading diffs.

The solution: the verification doc carries a `generated_by: "verification-writer@<semver>"` stamp. This skill records it as `source_generated_by` in its own metadata docs and as `@source-generated-by` in test file headers. `check-versions.js` compares the live stamp to the stored value and reports `skill-version-mismatch` when they diverge.

### Refusal behavior

When `check-versions.js` reports any `skill-version-mismatch` entries, this skill STOPS before generating or updating anything:

1. Print the mismatch list: each page, its `source_generated_by` (old), and the doc's current `generated_by` (new)
2. Direct the user to re-run with `--resync` to adopt the new version across manifests, metadata docs, and test headers
3. Do NOT silently update stamps — the version gap exists for a reason (ID renames, structural changes) that must be applied explicitly

Silent adoption is the specific failure mode this system exists to prevent.

### `--resync` behavior

`--resync` adopts a newer verification-writer version across this skill's artifacts without regenerating test bodies:

1. Read verification-writer's migration table (in its "Skill Version Tracking and Migration" section) for every version hop between the stored `source_generated_by` and the live `generated_by`
2. Apply each hop's `ID renames` column to:
   - `manifest/items.json` — rekey entries from OLD-ID to NEW-ID
   - Test file `@tag` annotations — rewrite `@OLD-ID` to `@NEW-ID` in test titles
   - Test file `@begin:OLD-ID` / `@end:OLD-ID` markers — rewrite to NEW-ID
3. Apply each hop's `Structural changes` column — e.g., rekey frontmatter fields the metadata doc mirrors
4. Update every `source_generated_by` field in metadata docs to the new verification-writer version
5. Update every `@source-generated-by` line in test file headers to the new verification-writer version
6. Bump each metadata doc's own `version` (patch) and update its `generated_by` to this skill's current version
7. Report: for each page, which IDs were renamed and how many test files were touched
8. Do NOT alter test bodies, `generated_hash`, or pin status — `--resync` is an identifier-rewrite pass, not a regeneration pass

After `--resync`, run `check-versions.js` again. If no `skill-version-mismatch` entries remain, normal generation can proceed.

### When structural changes exceed a rename pass

If verification-writer's migration table lists a hop as "requires regeneration" (e.g., a frontmatter schema change that splits one item into many), `--resync` alone is insufficient. Report that to the user and recommend `--force` for affected pages after `--resync` has updated the headers.

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
| Stubbing a `file-upload` item as "too complex" | `file-upload` is an interaction type, not a skip reason — locate the file input, use `setInputFiles`, trigger upload, wait for completion signal, assert result |
| Skipping API response items as "backend-only" | Classify as `api-response` and use `page.request` — API response assertions are Playwright tests |
| Stubbing `multi-step-workflow` items | `multi-step-workflow` is an interaction type, not a skip reason — execute each step in sequence, assert intermediate and final states |
| Generating a testid-missing stub without trying stable alternatives | Try `getByRole`, `getByLabel`, `getByText` (static copy only), `getByPlaceholder` (static copy only) before generating a stub; document what was tried |
| Claiming "missing testid" for `api-response` or `auth-boundary` items | These types use `page.request` or URL/navigation assertions — they do not need DOM selectors; this is a misclassification |
| Declaring generation complete while stubs with invalid skip reasons exist | Checkpoint B (step 11a) must pass before reporting — every stub must have a valid skip reason from the four-item list |
| Silently regenerating tests when verification-writer has been upgraded | `check-versions.js` reports `skill-version-mismatch` for this exact case — STOP and require `--resync`; never auto-update the `source_generated_by` field |
| Regenerating test bodies during a `--resync` pass | `--resync` rewrites IDs, stamps, and headers only; `generated_hash` and test content are preserved so pinned tests stay pinned |
| Creating a metadata doc without recording `source_generated_by` | Every metadata doc MUST stamp the verification-writer version it was synced against — without it `check-versions.js` cannot detect skill-version drift |
| Generating `@begin:ID` for an ID not returned by `parseVerificationItems()` | Every marker ID must exist in the parsed item set — if the ID isn't in the set, the test is an orphan. Log the gap and skip the block |
| Writing a spec file without pre-flight ID validation | Validate every `@begin:ID` against the parsed item set before calling Write — orphans at commit time are expensive to clean up |
| Using a different slugify implementation than sync-tests.js | Both tools must import from `scripts/verification-playwright/lib/slugify.js` — divergent implementations produce different IDs for the same input |
| Generating tests for a flow doc with no Format A IDs | Flow docs without `**FLOW-PREFIX-NN**` IDs have nothing for `parseVerificationItems()` to return — report the gap, don't mint IDs |
| Hash drift within the same hash_version | The normalization algorithm must be deterministic — strip trailing whitespace, normalize CRLF→LF, trim surrounding blank lines, encode UTF-8; any variation produces false manual-edit detections |
| Writing absolute paths into manifest files | All paths in `items.json`, `import-index.json`, and `pending-generation.json` must be project-relative — absolute paths (especially worktree paths) break on any other machine or after worktree cleanup |

## Red Flags — STOP

- About to overwrite a pinned test without `--force`
- Manifest files are corrupted — run `verify-pipeline.js` and report
- More than 50% of items are missing testids on a non-initial run — something is wrong with the codebase or the testid detection
- Import index has no entries — the index rebuild failed or the project structure is not recognized
- `check-versions.js` reports `frontmatter-missing` for any doc — verification-writer must add frontmatter before this skill can proceed
- About to edit a file in `docs/verification/` — this skill does not own those files
- More than 20% of generated tests are stubs with invalid skip reasons — the classification system is being bypassed
- Declaring generation complete (step 12 Report) while any stub has an invalid skip reason — Checkpoint B must pass first
- `check-versions.js` reports `skill-version-mismatch` and `--resync` has not been run — STOP; silent adoption of a newer verification-writer version corrupts manifests and test markers
- About to overwrite a `source_generated_by` or `@source-generated-by` value as part of normal generation — these only change during a `--resync` pass
- `check-versions.js` reports `stamp-missing` on a verification doc — tell the user to re-run verification-writer so it stamps the doc; do not invent a `source_generated_by` value
- `items.json`, `import-index.json`, or `pending-generation.json` contain absolute paths (including worktree paths like `.claude/worktrees/...`) — these paths break on any machine other than where they were written; rebuild the manifest with project-relative paths
- Multiple parallel agents were used to generate tests and their work has been merged — run `verify-pipeline.js` before declaring done; parallel worktree merges silently discard all-but-last for shared files
