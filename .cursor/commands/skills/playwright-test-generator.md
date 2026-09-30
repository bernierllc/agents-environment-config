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

A JS script at `scripts/check-versions.js` handles all mechanical staleness detection without LLM involvement. This script:

1. Reads all verification doc frontmatter (version, path, access)
2. Reads all playwright metadata doc frontmatter (version, source reference)
3. Reads all test file header comments (source and metadata references)
4. Compares versions across the chain: verification doc → metadata doc → test file
5. Outputs a structured task list for the agent

```bash
node playwright-test-generator/scripts/check-versions.js [project-dir]
```

It walks the **entire** verification root, excluding only `findings/`, `logs/`,
`visualizations/`, and a top-level `index.md` / `README.md` — the same discovery rule
verification-writer's `scan-versions.py` uses. Docs at the verification root or in
project-specific subdirectories carry real items; a doc not discovered here is invisible
to the whole pipeline.

Output is a JSON report `{total, counts, results}` on stdout. Exit codes:

| Code | Meaning |
|---|---|
| `0` | every doc is `up-to-date` |
| `1` | at least one doc needs agent work |
| `2` | at least one doc is a hard stop (`skill-version-mismatch` — run `--resync` first) |

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
| `affected-path-missing-on-disk` | Verification doc lists a path or glob in `affected_paths` that expands to zero files in the working tree | Yes — flag to user; the source file moved or was deleted. Tests for this page may now be testing nothing. Do not generate or update tests for this page until verification-writer is re-run to re-verify the mapping |

**This script replaces the full-scan approach.** Instead of the agent parsing every verification doc and test file to figure out what changed, the script does the comparison in milliseconds and hands the agent a precise task list. The agent only processes items that need work.

### Skill mode (LLM-powered)

Invoked by a user or triggered by verification-writer. Reads the task list from `check-versions.js`, then for each item needing work: reads verification docs, understands natural-language item descriptions, evaluates auth requirements, and generates meaningful Playwright test code with correct selectors, setup steps, and assertions.

### Sync mode (deterministic post-hook)

The existing `sync-tests.js` script handles mechanical operations after LLM generation: removing tests for deleted items, updating `@tag` annotations when item IDs change, re-enabling `.skip()` tests when previously-missing testids are found. The postToolUse hook calls this script. Read `references/test-generation-patterns.md` for marker format details.

**Item ID collision guard.** Item IDs are globally unique across the per-doc
`manifest/items/*.json` files, so two verification docs that mint the same ID cannot
both be represented (`loadManifest` refuses a manifest with one ID in two files). `sync-tests.js`
refuses to write when an item it is about to add is already owned by a different
`source_doc`: it exits non-zero, names each colliding ID and its current owner, and
leaves the manifest untouched. Without the guard the second doc silently reassigns the
first doc's item and that page's test coverage disappears with no error anywhere.

The usual cause is two docs sharing an `id_namespace` — verification-writer's integrity
pass (`scan-versions.py`, v3.4.0+) reports `duplicate_namespaces` upstream. Fix it there
by giving each doc a unique namespace, then re-run sync.

### Queue bridge

The hook runs `sync-tests.js` first. If the script detects items needing LLM intelligence (new items, substantial changes), it flags their entries `"pending_generation": true` in that doc's `manifest/items/<doc-slug>.json`. The skill processes the flagged items on next invocation and removes the flag from each item it generates (see `references/manifest-format.md` → The pending-generation queue). There is no `pending-generation.json` since 4.0.0.

### Manifest layout (4.0.0+)

The manifest is one file per verification doc (`manifest/items/<doc-slug>.json`) and one per page (`manifest/import-index/<page>.json`), each with `"version": "2.0"` and no repo-wide timestamp — edits to different docs write disjoint files. **Every script reads and writes it through `scripts/lib/manifest.js` (`loadManifest` / `saveManifest`); never parse the files directly.** Full format: `references/manifest-format.md`.

**Upgrading from 3.x is automatic.** The first script to load the manifest detects layout-1 files (`manifest/items.json`, `manifest/import-index.json`, `pending-generation.json`) by their `version` field (missing = `1.0`), splits them into the per-doc files, verifies nothing was lost, and deletes them. If anything would be lost it refuses with a non-zero exit and leaves the old files untouched; fix the file it names. A manifest file newer than this skill fails with "upgrade the skill" — it is never downgraded. After the migration, commit `manifest/items/` and `manifest/import-index/` and `git rm` the old files; `verify-pipeline.js` warns when it performed this migration, and fails when a merge brings a layout-1 file back next to the new layout (it folds it in per doc — an existing per-doc file wins — and names the `git rm`).

**Consumers mark the per-doc files `-merge`** in `.gitattributes`, so a conflicting merge is regenerated instead of spliced:

```
tests/verification-playwright/manifest/items/*.json -merge
tests/verification-playwright/manifest/import-index/*.json -merge
```

On a conflict take either side, then re-run `sync-tests.js` for that doc, passing its path (`node scripts/verification-playwright/sync-tests.js docs/verification/<doc>.md`), or `--force-index` for that page.

## Entry Points

| Trigger | Scope |
|---|---|
| **First run in a project** | Full generation: run `check-versions.js` (which also migrates a 3.x manifest to the per-doc layout), create metadata docs for all pages, generate all tests, write one `manifest/items/<doc-slug>.json` per doc and one `manifest/import-index/<page>.json` per page, produce testid-gaps.md report, and add the `-merge` lines above to `.gitattributes` |
| **Pending generation queue** | Generate tests only for items flagged `pending_generation: true` (`pendingIds(loadManifest(dir))`), clearing each flag after its test is written |
| **User invocation** | Generate or update tests for specified scope (page, flow, or full) |
| **`--check` flag** | Run `check-versions.js` only, report staleness without generating anything |
| **`--force` flag** | Regenerate all tests from scratch, discarding `manifest/items/` and `manifest/import-index/` (`config.json` is kept) |
| **`--force-index` flag** | Rebuild every `manifest/import-index/<page>.json` only, preserve item hashes |
| **`--force-items` flag** | Rebuild every `manifest/items/<doc-slug>.json` only, preserve config and index |
| **`--resync` flag** | Adopt a newer verification-writer skill version: apply that version's ID renames (from verification-writer's migration table) to the manifest and test `@tag` annotations, update every `source_generated_by` field in metadata docs, update every `@source-generated-by` line in test headers. Does NOT regenerate test bodies |

## Checklist

Complete these in order:

0. **Preflight** — run `bash scripts/preflight.sh` from the skill directory. If exit code is 0, continue. If non-zero, print its stdout verbatim to the user and STOP. Do not attempt to recover, retry, or work around the failure. The script runs two checks: (a) `docs/verification/pages/*.md` exists — without that, this skill has nothing to translate; (b) Playwright is installed in the target project — without it, generated specs cannot run. The Playwright check is mtime-cached in `.playwright-test-generator.cache` at the project root, so repeated runs cost nothing until the project's dependency manifests change. Add `.playwright-test-generator.cache` to the project's `.gitignore`.
1. **Run version check script** — execute `check-versions.js`, read the task list output
2. **Check for `skill-version-mismatch` entries FIRST** — if any item has this status, STOP. Report the gap to the user and direct them to re-run with `--resync`. Do not proceed to step 3 until either every mismatch is resolved by a `--resync` pass OR the user explicitly overrides. Silent adoption of a newer verification-writer version corrupts downstream anchors (see "Skill Version Compatibility")
3. **Triage the remaining task list** — separate into: frontmatter-missing (blocked), stamp-missing (blocked, direct user to verification-writer), metadata-missing (create), source-updated (re-evaluate), test-missing (generate), header-missing (patch), up-to-date (skip)
4. **Handle blocked items** — for `frontmatter-missing` and `stamp-missing`, report to user that verification-writer needs to run before tests can be generated
5. **Create/update metadata docs** — for each page needing metadata, read verification doc frontmatter, evaluate auth requirements, create derivative metadata doc (see "Derivative Metadata Docs" below). Record the source doc's `generated_by` value as `source_generated_by` in the metadata frontmatter
6. **Evaluate auth readiness** — for each metadata doc, check if `helpers/auth.ts` (or equivalent) has a working auth flow for the required user types. Set `ready: true/false` accordingly
7. **Generate tests** — for each ready page, generate Playwright test code with proper auth `beforeEach` blocks. For not-ready pages, generate `.skip()` stubs with clear skip reasons
   - **7a. Before writing each test:** classify the verification item by interaction type (see `references/test-generation-patterns.md`), confirm the planned test will contain all must-have elements for that type, then write the test (Checkpoint A — see Test Completeness Standards)
   - **7b. Pre-flight ID validation (before writing each spec file):** After generating the full text of a spec file, before writing to disk, extract every `@begin:ID` from the generated text and cross-check against the ID set from `parseVerificationItems()`. If any `@begin:ID` is not in that set, refuse to write and report the specific invalid IDs. This is a hard stop — do not write the file.
   - **7b.1. Artifact-token guard (before writing each spec file):** In the same pre-write pass, scan the generated text for leaked tool-call artifact tokens (stray opening/closing `invoke`, `parameter`, or `function_calls` tags). If any are present the generation is malformed — refuse to write and regenerate. This is a hard stop: a single corrupted spec makes Playwright fail at *collection*, aborting the entire suite before any test runs. `verify-pipeline.js`'s `checkSpecArtifacts` re-checks this on disk as a defense-in-depth gate, but the file must never be written in the first place.
8. **Handle missing testids** — exhaust stable alternative selectors first (`getByRole` → `getByLabel` → `getByText` for static copy → `getByPlaceholder` for static copy); generate `.skip()` stub only if all fail and only for types that require DOM selectors (not `api-response` or `auth-boundary`); document alternatives tried in stub comment (see stub template in `references/test-generation-patterns.md`); update `testid-gaps.md`
   - **8a. Selector verification (Checkpoint A.5 — gates every live test):** Before emitting any live (non-`.skip()`) test that depends on a DOM selector, the selector MUST be verified against actual component source. Open the component file (use `manifest/import-index/` to locate it) and confirm the exact `data-testid`, label, role+name, or static text exists. **Best-guess selectors are forbidden in live tests.** If you cannot read the component source, or the component does not expose the expected hook, the test MUST be a `.skip()` stub citing skip reason 3 with "selector unverified" and a `testid-gaps.md` entry. See "Selector Verification" below.
   - **8b. Data dependency classification:** If a verification item asserts the presence of dynamic content (cards, list items, feed entries, table rows, counts > 0), classify as data-dependent. Set the page's metadata `data_setup.ready` accordingly. If `data_setup.ready = false`, generate a `.skip()` stub citing skip reason 2 — do not paper over with `hasCards || hasEmptyState` fallbacks unless the verification item is explicitly typed as `graceful empty state`. See "Live Data Dependencies" below.
9. **Update manifest** — write changes atomically with lockfile
10. **Rebuild import index** — trace routes to source files, write one `manifest/import-index/<page>.json` per page you rebuilt (a `files` list; see `references/manifest-format.md`). Index paths are **repo-root-relative** (the git toplevel), not relative to the Playwright project dir. This matters in monorepos where the project root is a subdirectory and sources span multiple packages: `map-changes.js --since-main` matches these keys against `git diff --name-only`, which always emits repo-root-relative paths. `verify-pipeline.js`/`map-changes.js` resolve the repo root via `git rev-parse --show-toplevel` and fall back to the project dir when not in a git repo (so single-root projects are unaffected).
10b. **Link specs back into the manifest** — run
    `node <skill-dir>/scripts/link-specs.js <projectDir>`, by absolute skill path with the target
    project passed explicitly. The skill's scripts do not live inside the project, so a bare
    `scripts/link-specs.js` resolves to the *project's* scripts directory, and relying on
    `process.cwd()` breaks the moment the caller runs from the skill directory. `projectDir`
    defaults to the cwd for the common case. Specs are written by
    this skill, not by `sync-tests.js`, and nothing else writes `spec_file` back onto the manifest.
    **Without this step three of `verify-pipeline.js`'s checks — `checkSpecFiles`,
    `checkSpecArtifacts`, and the marker half of `checkItemConsistency` — silently iterate an empty
    set, so the gate passes because it inspects nothing.** Run it after any generation pass and
    before `verify-pipeline.js`.
11. **Patch test headers** — for `header-missing` items, add `@source`, `@source-generated-by`, `@metadata`, and `@generated-by` comments to existing test files
    - **11a. Post-generation audit (Checkpoint B — gates step 12):** count complete tests vs. stubs; for every stub verify it carries one of the four valid skip reasons from Test Completeness Standards; reclassify and implement any stub with an invalid reason; do not proceed to step 12 until every stub has a valid reason
12. **Report** — print summary of generated, updated, skipped, blocked, and pinned tests

## Generated Test Structure

```
tests/verification-playwright/
├── manifest/
│   ├── items/                  # One <doc-slug>.json per verification doc: items, hashes, pins, pending flags
│   ├── import-index/           # One <page>.json per page tag: source files that affect it
│   └── config.json             # Tier config, dry-run, test isolation
├── metadata/                   # Derivative docs — this skill's own research
│   ├── admin-dashboard.md      # Auth strategy, data setup, readiness per page
│   ├── event-detail.md
│   └── ...
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

  // @begin:EVT-DTL-ADM-01
  test('@EVT-DTL-ADM-01 @standard @event-detail edit button is visible', async ({ page }) => {
    // ... test code
  });
  // @end:EVT-DTL-ADM-01
});
```

**When auth is NOT ready:**

```typescript
test.describe('Event Detail - Admin', () => {
  // @begin:EVT-DTL-ADM-01
  test.skip('@EVT-DTL-ADM-01 @standard @event-detail edit button is visible', async ({ page }) => {
    // SKIP REASON: auth.ready = false (skip reason 1) — no auth helper for 'admin' role
    // Auth requirement: rbac, role: admin
    // TODO: Implement helpers/auth.ts#loginAsAdmin, set auth.ready=true in metadata/event-detail.md, then remove .skip()
  });
  // @end:EVT-DTL-ADM-01
});
```

Both examples — live and `.skip()` — wrap each test in its own `@begin:ID`/`@end:ID` markers, **including inside a `test.describe` block**. This is not optional: a marker-less stub is invisible to `sync-tests.js` and is flagged as an orphan by `verify-pipeline.js`. See "ID Source Discipline" and "Generating Tests" for the invariant.

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

### Selector Verification

**Live tests must use verified selectors. Best-guess selectors are forbidden.**

A selector is *verified* when one of the following is true:

1. **`data-testid` confirmed in source** — grep the component file (located via the `manifest/import-index/` route → source mapping) for the exact `data-testid` value the test will use. Match found = verified.
2. **`getByRole` + accessible name confirmed in source** — the component's JSX shows the exact role-bearing element with the exact accessible name (visible text, `aria-label`, or label association). Verified.
3. **`getByLabel` confirmed in source** — the component renders a `<label>` with matching text bound to the input. Verified.
4. **`getByText` for static copy confirmed in source** — the literal string is present in the JSX as static markup, not interpolated from data. Verified.
5. **`getByPlaceholder` for static copy confirmed in source** — placeholder is a literal string in JSX. Verified.

Anything else — including `[data-testid*="activity"]`, `locator('form').first()`, `nav a` filters, multi-fallback OR-chains like `[data-testid*="article-card"], article, .article-card`, or any selector composed by analogy from the verification doc's natural-language description — is **unverified**.

**Required workflow before writing a live test:**

1. Locate the page's component source via `manifest/import-index/`.
2. Read the component(s) actually rendered for the route.
3. For each selector the test will use, confirm it matches by one of the five criteria above.
4. If all selectors verify → emit a live test.
5. If any selector is unverified after a reasonable attempt to read the source → emit a `.skip()` stub with skip reason 3, add a row to `testid-gaps.md` with the `Status` column set to either `confirmed-missing` (source was read; testid not present) or `unverified` (source could not be confidently located; testid may or may not exist). Propose the testid that should be added in the suggested-testid column. See the `testid-gaps.md` schema in `references/test-generation-patterns.md` — every skip-reason-3 stub is required to have a matching row.

Note that **skip-reason-2 (data-setup) stubs do NOT go in `testid-gaps.md`** — they go in a separate `data-setup-gaps.md` report (or a clearly labeled section). Component-testid gaps and seed-data gaps are owned by different people and must not be conflated.

**Sample-and-confirm rule for repeated patterns:** When generating tests across many similar items on a page (e.g., 10 form fields, 20 list items), read at least 3 representative components to confirm the selector pattern holds before generating tests for the rest. If the sample shows the pattern is inconsistent, treat each item individually rather than projecting the pattern.

**The anti-pattern this section prevents:** generating live tests with optimistic CSS like `[data-testid*="article-card"], article, .article-card` and shipping them — they fail with `Expected: true, Received: false` and waste the developer's time on triage. The correct outcome is a `.skip()` stub plus a `testid-gaps.md` entry that surfaces the missing hook to the component owner.

### Live Data Dependencies

A verification item is **data-dependent** when its assertion requires content that does not exist by virtue of the page rendering — e.g., "recent activity is visible", "article cards appear", "feed shows posts", "X count is > 0", "table contains at least one row of type Y".

These items cannot be tested reliably against an empty dev database. The skill must distinguish them from items that assert structure (which is data-independent) and handle them explicitly.

**Classification:**

When generating tests for the page, identify every data-dependent item. For each such item:

1. **Record it in the metadata doc** under a `data_dependencies` block (extend the existing `data_setup` section). List the specific data shape required (e.g., "≥1 published article with image and title").
2. **Check `data_setup.ready`** in the metadata doc:
   - If `true` and a seed helper exists → the test's `beforeEach` calls the seed helper to create the required data, then the assertion runs against known-present data.
   - If `false` → emit a `.skip()` stub with skip reason 2 (`data_setup.ready = false`). Do not generate a live test that assumes the dev database has the right data.
3. **Do not paper over with empty-state fallbacks.** Assertions like `expect(hasCards || hasEmptyState).toBe(true)` are an anti-pattern when the verification item asserts the populated state. The empty-state branch is only valid when the verification item itself is typed `graceful empty state` (see Expectation Type Mapping in patterns ref).

**Metadata frontmatter extension:**

```yaml
data_setup:
  strategy: api-seed       # api-seed | db-fixture | manual | none | null
  helper: helpers/seed.ts#seedArticles
  ready: true
  required_shape:
    - "≥1 published article with title and image"
    - "≥1 activity event in last 7 days"
  skip_reason: null
```

When `ready: false`, list the required shape so the seed-helper author has a precise spec to implement against. The `required_shape` field is a contract between this skill and whoever implements `helpers/seed.ts` — vague entries ("some data") force re-discovery later.

**Reporting:** Step 12's report must include a `data_setup_blocked` count: tests that are stubbed because the required seed isn't implemented. This makes the seed gap visible alongside the testid gap.

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
- `@begin:ITEM-ID` / `@end:ITEM-ID` markers wrapping each test function — **including `.skip()` stubs**. Skip stubs are never marker-less: `sync-tests.js` locates, patches, and un-skips them by their markers, and `verify-pipeline.js` flags any `status: skipped` item whose marked block contains no `.skip()` (and any spec-backed item missing markers) as an orphan. A skip stub without markers is invisible to the pipeline — it can never be removed or re-enabled.
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
2. It sets `"pinned": true` on the item in its doc's `manifest/items/<doc-slug>.json`
3. Pinned tests are never overwritten — reported as "pinned (manually edited)" in the generation log
4. Un-pin by setting `"pinned": false` on that entry, or use `--force`

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

The `generated_hash` field on each manifest item records the content hash of each test (content between `@begin`/`@end` markers). A hash mismatch signals that a developer manually edited the test — the test is then pinned and never overwritten.

### Normalization (must be applied before hashing)

The normalization algorithm must be consistent across all runs. Lock it:

1. Strip trailing whitespace from each line
2. Normalize line endings: CRLF → LF
3. Trim leading and trailing blank lines from the block
4. Encode as UTF-8

Any deviation from this algorithm produces a different hash for the same logical content — triggering false "manually edited" detections and flooding the pinned test list.

### hash_version field

Each `manifest/items/<doc-slug>.json` includes a top-level `hash_version` field that records which version of the normalization algorithm was used to produce the hashes in that file (the 3.x → 4.0 migration copies the old repo-wide value into every doc file):

```json
{
  "version": "2.0",
  "hash_version": 1,
  "source_doc": "docs/verification/pages/admin-event-form.md",
  "items": { ... }
}
```

- Drift within the same `hash_version` is a bug — the algorithm is non-deterministic.
- Drift across `hash_version` values is expected — bump `hash_version` when the normalization algorithm changes, and regenerate all hashes on the next `--force` run.
- When reading a doc file, if the `hash_version` is absent, treat it as version 0 (legacy, pre-normalization-lock). All hashes from version 0 are suspect — a `--force` regeneration is recommended.

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
   - `manifest/items/<doc-slug>.json` — rekey entries from OLD-ID to NEW-ID (through `loadManifest` / `saveManifest`)
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

The gate enforces that table rather than describing it:

- **Depth** comes from `tiers.gate.depths`, as a **positive allowlist**: a test must carry a gate depth AND an affected suite tag. Deriving exclusions from other tiers' depths leaked anything no tier declared — one consumer had `@error` and `@edge` items running at commit time — so unrecognised depths are out by default.
- **Browsers** come from `tiers.gate.browsers`, so adding a browser to the config changes the gate rather than silently affecting pre-push alone.
- **The cap** is compared against the number of tests Playwright actually resolves (`--list`), not the number of tags. Tags are suite-level: a single changed file can pull in a whole suite, so a tag count is not a test count and a cap compared against one never fires.
- **Playwright owns the server; the hook does not start one.** `webServer` already starts the app when down and passes the right env, and reimplementing that in the hook produced six Critical review findings in two rounds — process groups, EXIT traps, env parity — none of it the hook's job. The one check Playwright cannot make is kept: a checkout whose `node_modules` is a symlink can never serve the app (Turbopack refuses it), so the gate skips with a one-line reason instead of a wall of connection failures.
- **Set `reuseExistingServer: false` on the verification config, and take the port from `VERIFICATION_PORT`.** With reuse on, Playwright adopts whatever is listening — including a dev server started with a different env, which for a suite pointed at a mock API means silently reaching the real one; an unauthenticated probe cannot tell the two apart, so do not try. With reuse off, a busy port ends the run before a single test, and on a shared machine the default port is usually busy. So the hook picks the first free port in a small range and exports `VERIFICATION_PORT`; the config reads it for `baseURL`, `webServer.port` and the dev command. Any fixed port a globalSetup binds (a mock API, say) needs the same treatment — the template exports `MOCK_SENDGRID_PORT` as the worked example; rename to taste. No free port is an environmental skip with a reason, never a block.
- **Suite tags need a terminator in the grep.** `@onboarding` also matches `@onboarding-domains`; one consumer selected 195 tests for a one-file change instead of 38, tripped the cap, and skipped the gate for the tests that were affected. The template follows each tag and depth with `(?:\s|$)`.
- **The gate runs a dev server, never a build.** If the verification config builds and serves a production bundle for the batched runner (paying the build once per suite run), the hook exports `VERIFICATION_SERVER=dev` and the config swaps the command for `next dev` on the chosen port: a `next build` per commit takes minutes and writes into the same `.next` a running batched server may be serving from. `next dev` writes under `.next/dev` and its first-hit compile is bounded by the gate's own `--timeout`.
- **The gate never blocks a commit for an environmental reason.** No server, no dependencies, an empty selection at gate depth, or a selection over the cap all skip with a reason and exit 0. Only a genuine test failure blocks.

## Cross-Skill Integration

### When invoked by verification-writer

After verification-writer updates docs (and bumps their version), the postToolUse hook triggers `sync-tests.js`. If new or substantially changed items are detected, they are flagged `pending_generation: true` in their doc's manifest file. On next skill invocation, `check-versions.js` detects the version mismatch and the agent processes the queue.

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
| Ignoring `pending_generation` flags | Check `pendingIds(loadManifest(dir))` at the start of every invocation |
| Parsing `manifest/items/*.json` or `manifest/import-index/*.json` directly | Go through `scripts/lib/manifest.js` — it migrates older layouts, enforces ID uniqueness and writes only changed files |
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
| Emitting a live test with a guessed/unverified selector (e.g., `[data-testid*="article-card"], article, .article-card`, `locator('form').first()`, `nav a` filters constructed from the verification doc's natural language) | Live tests require selector verification against component source — read the component via `manifest/import-index/` and confirm the testid/role/label/static text exists. If unverified, emit a `.skip()` stub with skip reason 3 and a `testid-gaps.md` entry. Best-guess selectors are forbidden in live tests. |
| Asserting presence of dynamic content (cards, feed entries, list rows) without checking `data_setup.ready` | Data-dependent items must check the metadata doc's `data_setup.ready`. If false, stub with skip reason 2; if true, seed required data in `beforeEach`. Do not assume the dev database is populated. |
| Papering over data-dependence with `expect(hasContent || hasEmptyState).toBe(true)` | This is only valid when the verification item is explicitly typed `graceful empty state`. Otherwise it masks the actual assertion and silently passes against an empty database — classify the item correctly and either seed data or stub with skip reason 2. |
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
| Writing absolute paths into manifest files | All manifest paths must be relative, never absolute — absolute paths (especially worktree paths) break on any other machine or after worktree cleanup. Two relative bases apply: `manifest/import-index/*.json` paths are **repo-root-relative** (they match `git diff` output and may span packages); `spec_file` / `source_doc` paths in `manifest/items/*.json` are **project-dir-relative** (under `tests/verification-playwright/`). In a single-root project the two bases coincide. |

## Red Flags — STOP

- About to overwrite a pinned test without `--force`
- Manifest files are corrupted — run `verify-pipeline.js` and report
- More than 50% of items are missing testids on a non-initial run — something is wrong with the codebase or the testid detection
- Import index has no entries — the index rebuild failed or the project structure is not recognized
- `check-versions.js` reports `frontmatter-missing` for any doc — verification-writer must add frontmatter before this skill can proceed
- About to edit a file in `docs/verification/` — this skill does not own those files
- More than 20% of generated tests are stubs with invalid skip reasons — the classification system is being bypassed
- About to emit a live test with a selector that has not been confirmed against component source — verify or stub; never ship a guessed selector as a live test
- A data-dependent assertion is being generated against a page whose metadata `data_setup.ready` is `false` or unknown — stub with skip reason 2 until the seed helper exists
- Declaring generation complete (step 12 Report) while any stub has an invalid skip reason — Checkpoint B must pass first
- `check-versions.js` reports `skill-version-mismatch` and `--resync` has not been run — STOP; silent adoption of a newer verification-writer version corrupts manifests and test markers
- About to overwrite a `source_generated_by` or `@source-generated-by` value as part of normal generation — these only change during a `--resync` pass
- `check-versions.js` reports `stamp-missing` on a verification doc — tell the user to re-run verification-writer so it stamps the doc; do not invent a `source_generated_by` value
- `manifest/items/*.json` or `manifest/import-index/*.json` contain absolute paths (including worktree paths like `.claude/worktrees/...`) — these paths break on any machine other than where they were written; rebuild the manifest with project-relative paths
- Multiple parallel agents were used to generate tests and their work has been merged — run `verify-pipeline.js` before declaring done; parallel worktree merges silently discard all-but-last for shared files

## Changelog

### 4.0.3

**Fix: a truncated hook payload on stdin fails loudly.** If the writer sent part of the JSON and went quiet past the idle bound, the partial text failed to parse, `sync-tests.js` printed usage and exited 0, and the manifest sync was skipped with no error. A non-empty payload that doesn't parse now exits 2 like no payload at all. A complete payload for a file that isn't a verification doc still exits 0.

### 4.0.2

**Fix: `sync-tests.js` with no argument no longer hangs.** With no doc path it read stdin for the hook's `{"tool_input":{"file_path":…}}` payload using a blocking read, which never returns when stdin is a terminal (run by hand) or a pipe that stays open without writing (run by an agent). It now reads stdin with a 2 s idle bound, reset by each chunk, so a slow hook writer is never cut off and a writer that goes quiet without closing still has its payload used. If stdin is a terminal, sends nothing, or is already closed (`</dev/null`), it prints usage to stderr and exits 2. The hook still writes its payload and closes at once, so it is unaffected. The docs' "re-run `sync-tests.js` for that doc" steps now show the path form.

### 4.0.1

**Fix: tier validation checks the order tiers are selected in, not config key order.** `selectTier()` always checks `full`, `thorough`, `gate` in that order (`TIER_ORDER`, now exported), but `validateTierOrder()` walked the keys of `config.json` as `JSON.parse` returned them. A config listing `gate: "*"` first is valid, yet it threw on every branch, so no tier ever ran. Validation now rejects only a catch-all that really shadows a tier checked after it.

**Fix: the pre-commit harness tests the gate in a worktree that symlinks `node_modules`.** From such a checkout every `check()` case hit the hook's symlink skip, so 9 of 12 failed while testing nothing. When `node_modules` is a symlink, the cases now run from a sandbox mirror of the checkout that has a real, empty `node_modules`.

**Fix: the mixed-state fold never lets a layout-1 file overwrite an existing per-doc file.** A branch cut before 4.0.0 re-saves `items.json` with a fresh repo-wide `generated_at`, so under the old "newer timestamp wins" rule its stale entries overwrote every newer per-doc file on merge. An existing 2.0 file now always wins; layout-1 entries only fill docs and pages that have no 2.0 file. A kept doc the stale branch really did change is re-flagged by `sync-tests` on its next run, since its `content_hash` no longer matches.

**Fix: `verify-pipeline.js` fails on a bootstrapped manifest with no item files.** If `manifest/items/` was deleted or emptied, the loader returned an empty map and every check passed over nothing. It now fails and names the restore, and it warns when `manifest/import-index/` is empty while items exist.

**Fix: the pre-push template passes the tier's browsers as `--project` flags.** It read no browser list, so a `playwright.config.ts` with more projects than `tiers.<tier>.browsers` ran all of them.

### 4.0.0

Combines the per-doc manifest layout (was PR #39) with the running-app commit gate (was PR #32), so they land in one release.

**Breaking: on-disk manifest layout 1.0 → 2.0.**
- `manifest/items.json` and `manifest/import-index.json` are split into `manifest/items/<doc-slug>.json` and `manifest/import-index/<page>.json`, each `"version": "2.0"`. Two PRs touching different verification docs now touch different files, so they no longer conflict on a repo-wide `-merge` file.
- `pending-generation.json` is gone. An item is queued when its entry carries `pending_generation: true`.
- Every script loads and saves through `scripts/lib/manifest.js`, which migrates older layouts on first load. The migration is ordered by `LAYOUT_STEPS`, lossless (it refuses rather than drop data), and idempotent. It also folds a layout-1 file that an old branch brings back, and it refuses to read a newer layout or to downgrade. Two item files that declare the same `source_doc`, or two index files that declare the same page, are refused, and concurrent first loads use per-process temp files.
- Consumers: commit the new directories, `git rm` the old aggregate files, and change `.gitattributes` `-merge` lines to the per-doc globs (see the "Upgrading from 3.x" paragraph under Execution Model).

**Commit gate (`templates/hooks/pre-commit.sh`).** See "Tiered Test Execution" for details.
- Selects tests by `tiers.gate.depths` as a positive allowlist and by `tiers.gate.browsers`.
- Terminates each tag in the grep, so `@onboarding` no longer also matches `@onboarding-domains`.
- Counts resolved tests with `--list` rather than counting tags.
- Picks a free port and exports `VERIFICATION_PORT` and `VERIFICATION_SERVER=dev`. It uses `lsof` when present and falls back to a node `net` probe, never to guessing. Playwright's `webServer` starts the app.
- Never blocks a commit for an environmental reason. Only a genuine test failure blocks.
- Reports a `map-changes.js` failure (for example, a refused manifest migration) and skips, rather than reading it as "no affected tags" and going silent.
- Has a bash harness in `templates/hooks/__tests__/pre-commit.test.sh`.

**CLI entry points resolve symlinks.** Every script compares real paths through `isEntryPoint()` in `lib/repo.js`. Before this, a script run through a symlinked `scripts/` directory exited silently.
