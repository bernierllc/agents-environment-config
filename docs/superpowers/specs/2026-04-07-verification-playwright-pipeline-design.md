# Verification-to-Playwright Pipeline Design

> **Date:** 2026-04-07
> **Status:** Approved (design phase)
> **Scope:** verification-writer Layer 3e + playwright-test-generator skill + hook-driven automation + AEC integration

## Problem Statement

Manual QA by a human tester found 23 bugs in the barevents project in one day — bugs that the existing verification-writer / browser-verification loop should have caught. Root causes:

1. **Missing state dependency coverage** — verification-writer generates per-field validation items but not cross-field state interaction items (e.g., "change event type after setting flyer config" → FK error)
2. **No automated regression testing** — browser-verification runs manually via Claude, one instance at a time, with browser contention between concurrent Claude sessions
3. **No commit-time gate** — code ships without running verification items against the UI

## Solution

A three-component pipeline where verification docs remain the source of truth, Playwright tests are derived artifacts, and hooks enforce testing at commit/push time:

```
Code change → verification-writer → docs → playwright-test-generator → .spec.ts → hooks → Playwright runner
```

## Components

### 1. verification-writer: Layer 3e (State Dependency Analysis)

**Purpose:** Detect cross-field state dependencies in forms and generate verification items that cover state transition edge cases.

**What Layer 3e traces in code:**

1. **Conditional rendering chains** — `if (eventType === 'private')` controlling section visibility. Generates items: "Change event type to Private → verify dependent sections hide AND their state is cleared from the submission payload."

2. **useEffect/watch dependencies** — React Hook Form `watch('field')` or `useEffect` reacting to field changes. These are explicit dependency declarations. Layer 3e reads dependency arrays and effect bodies to understand cascading behavior.

3. **Cascading clears** — When field A changes and field B's value becomes invalid (e.g., removing a promoter who was selected as flyer uploader). Traces which fields reference other fields' values and generates "remove X → verify Y is cleared or revalidated" items.

4. **Submission payload validation** — Reads submit handlers to check: does the payload include stale references? Catches bugs like "removed artist still in responsibility state" or "deleted promoter still referenced as flyer uploader."

**Output format:** New verification items with `<!-- STATE-DEPENDENCY -->` annotations:

```markdown
- [ ] [deep] **EVT-FRM-SD-01** Add promoter, set as flyer uploader,
  then change event type to Private --- Promoter-dependent flyer config
  is cleared or form prevents submission. *Expected: success*
<!-- STATE-DEPENDENCY:
  trigger: eventType field change to non-music type
  affected_fields: [flyer_uploader_id, responsibility_person_id]
  expected_cascade: [clear flyer_uploader_id, clear responsibility selections, hide artist/promoter sections]
  code_ref: EventForm.tsx:useEffect watching eventType
  failure_mode: FK constraint violation if stale ID submitted
-->
```

**Severity elevation:** Most state dependency items are tagged `[deep]`, but items whose failure mode is data corruption or FK constraint violation are elevated to `[standard]`.

**Relationship to existing annotations:** `<!-- STATE-DEPENDENCY -->` is a new annotation type alongside the existing `<!-- BUSINESS-CONTEXT -->` and `<!-- API-VERIFICATION-FLAG -->` annotations defined in `verification-item-format.md`. The verification-writer's reference doc must be updated to include this type.

**How playwright-test-generator consumes STATE-DEPENDENCY annotations:**

- `trigger` → becomes the test's setup sequence (the action that initiates the state change)
- `affected_fields` → becomes assertion targets (each field is checked for correct state after the trigger)
- `expected_cascade` → becomes an ordered sequence of `expect()` calls, one per cascade step
- `code_ref` → embedded as a code comment in the generated test for traceability
- `failure_mode` → determines assertion strategy: FK violations check that the form prevents submission or shows a validation error, not that the server returns a 500

Example: the annotation above generates a test that: (1) adds a promoter and sets as flyer uploader, (2) changes event type to Private, (3) asserts flyer_uploader_id field is cleared or hidden, (4) asserts responsibility selections are cleared, (5) asserts artist/promoter sections are hidden, (6) attempts form submission and asserts success (no FK error).

### 2. playwright-test-generator (New Skill)

**Purpose:** Read verification docs, diff against a manifest, and produce/patch Playwright .spec.ts files incrementally. Never regenerates from scratch unless explicitly asked (`--force` flag to force full regeneration, discarding manifest).

#### Execution model

The playwright-test-generator has two execution modes:

1. **Skill mode (LLM-powered)** — Invoked by a user or triggered by verification-writer. Claude reads the verification doc, understands the natural-language item descriptions, and generates meaningful Playwright test code with correct selectors, setup steps, and assertions. This is the primary authoring mode — it runs during initial generation, when new items are added, and when items are substantially rewritten. This is the mode that runs on the first invocation per project and when the postToolUse hook detects new or substantially changed items (content hash changed).

2. **Script mode (deterministic)** — A Node.js script at `scripts/verification-playwright/sync-tests.js` that handles mechanical operations without needing an LLM: removing tests for deleted items, updating `@tag` annotations when item IDs change, re-enabling `.skip()` tests when previously-missing testids are found in the codebase. This script is what the postToolUse hook calls for lightweight changes (item removed, item ID renamed). It reads the manifest, diffs hashes, and patches .spec.ts files using tagged code block boundaries (each generated test is wrapped in `// @begin:ITEM-ID` / `// @end:ITEM-ID` markers).

**How the postToolUse hook decides which mode:** The hook runs `sync-tests.js` first. If the script detects items that need LLM intelligence (new items with no existing test, items whose content hash changed significantly), it writes them to a `pending-generation.json` queue file. The next time Claude runs (either the current session or the next), the skill reads the queue and generates the tests. The hook itself never invokes Claude — it only queues work for the skill to pick up.

**The `--force` flag:** Pass `--force` when invoking the skill to regenerate all tests from scratch, discarding the manifest and rebuilding it. Use sparingly — this is for recovery from manifest corruption or major restructuring of verification docs.

#### Generated test structure

```
tests/verification-playwright/
├── manifest/
│   ├── items.json                   # Item-to-test mapping, content hashes, testid status
│   ├── import-index.json            # Source file → verification page mapping
│   └── config.json                  # Tier configuration, pipeline settings
├── pending-generation.json          # Queue of items needing LLM generation (transient)
├── playwright.config.ts             # Extends root config, verification-specific settings
├── testid-gaps.md                   # Report of verification items missing data-testids
├── helpers/
│   ├── auth.ts                      # Login flows (magic link retrieval, OAuth mock)
│   └── assertions.ts                # Reusable assertion patterns per expectation type
├── pages/
│   ├── admin-event-form.spec.ts     # 1:1 with verification page doc
│   ├── admin-event-detail.spec.ts
│   ├── admin-artist-form.spec.ts
│   └── ...
└── flows/
    ├── event-lifecycle.spec.ts      # 1:1 with verification flow doc
    └── ...
```

#### Verification item → Playwright test mapping

```markdown
# In verification doc:
- [ ] [standard] **EVT-FRM-TKT-03** Enter ticket_price_min greater than
  ticket_price_max --- Validation error. *Expected: client-side validation error*
```

Becomes:

```typescript
test('@EVT-FRM-TKT-03 @standard @admin-event-form min price > max price',
  async ({ page }) => {
    await page.goto('/events/new?event_type=music');
    await page.fill('[data-testid="ticket-price-min"]', '50');
    await page.fill('[data-testid="ticket-price-max"]', '25');
    await page.click('[data-testid="submit-event"]');
    // Expected: client-side validation error
    await expect(page.locator('[data-testid="ticket-price-error"]'))
      .toBeVisible();
    await expectNoConsoleErrors(page);
    await expectNoNetworkErrors(page);
  });
```

#### Tag format

Every generated test gets three tags in its test name:

- `@EVT-FRM-TKT-03` — item ID (for surgical test selection via `--grep`)
- `@standard` — depth tier (for filtering by smoke/standard/deep)
- `@admin-event-form` — page file name (for running all tests for a page)

#### Manifest structure (split files)

The manifest is split into three independent files so each can fail and be rebuilt independently. `--force-index` rebuilds only the import index without losing item hashes. `--force-items` rebuilds item mappings without losing config. `--force` rebuilds everything.

**`manifest/items.json`** — Item-to-test mapping:

```json
{
  "version": "1.0",
  "generated_at": "2026-04-07T18:00:00Z",
  "items": {
    "EVT-FRM-TKT-03": {
      "source_doc": "docs/verification/pages/admin-event-form.md",
      "spec_file": "tests/verification-playwright/pages/admin-event-form.spec.ts",
      "content_hash": "a1b2c3d4e5f6...",
      "generated_hash": "f6e5d4c3b2a1...",
      "depth": "standard",
      "status": "active",
      "pinned": false,
      "testids_required": ["ticket-price-min", "ticket-price-max", "submit-event", "ticket-price-error"],
      "testids_missing": ["ticket-price-error"]
    }
  }
}
```

Fields:
- `content_hash` — SHA-256 of the normalized verification item (see hash normalization below). Used to detect doc changes.
- `generated_hash` — SHA-256 of the generated test code between `@begin`/`@end` markers. Used to detect manual edits.
- `pinned` — When `true`, the skill will not overwrite this test. Set automatically when `generated_hash` no longer matches the actual file content (developer manually edited the test). Can also be set manually. `--force` overrides pinned tests.

**`manifest/import-index.json`** — Source file to page mapping:

```json
{
  "version": "1.0",
  "generated_at": "2026-04-07T18:00:00Z",
  "entries": {
    "admin/static/admin/src/components/EventForm.tsx": ["admin-event-form"],
    "admin/static/admin/src/components/ArtistSection.tsx": ["admin-event-form", "admin-artist-form"],
    "admin/app/routers/events.py": ["admin-event-form", "admin-event-detail", "admin-event-list"]
  }
}
```

**`manifest/config.json`** — Tier configuration and pipeline settings:

```json
{
  "version": "1.0",
  "dry_run": false,
  "tiers": {
    "gate": {
      "trigger": "pre-commit",
      "branches": "*",
      "browsers": ["chromium"],
      "depths": ["smoke", "standard"],
      "maxTests": 30,
      "timeoutMs": 60000
    },
    "thorough": {
      "trigger": "pre-push",
      "branches": ["staging", "develop"],
      "browsers": ["chromium", "firefox", "webkit"],
      "depths": ["smoke", "standard", "deep"],
      "maxTests": 100,
      "timeoutMs": 300000
    },
    "full": {
      "trigger": "pre-push",
      "branches": ["main", "production"],
      "browsers": ["chromium", "firefox", "webkit", "Mobile Chrome", "Mobile Safari"],
      "depths": ["smoke", "standard", "deep"],
      "maxTests": null,
      "timeoutMs": null
    }
  },
  "test_isolation": {
    "strategy": "per-test-user",
    "cleanup": "after-each",
    "notes": "Project-specific. Set during init."
  }
}
```

#### Content hash normalization

All content hashes use SHA-256 of a normalized representation to prevent churn from whitespace reformatting:

1. Strip leading/trailing whitespace per line
2. Collapse multiple consecutive spaces to a single space
3. Lowercase the item ID
4. Remove HTML comment markers (`<!--`, `-->`) from annotations before hashing annotation content
5. Sort annotation fields alphabetically within each annotation block

This ensures reformatted docs with identical semantic content produce identical hashes.

#### Concurrency safety

Multiple Claude sessions editing different verification docs simultaneously can both trigger `sync-tests.js`. To prevent silent overwrites:

1. **Atomic writes:** All manifest file updates write to `<file>.tmp` first, then rename atomically. This prevents partial writes from corrupting the file.
2. **Lockfile:** `sync-tests.js` acquires a lockfile (`manifest/.lock`) before reading/writing any manifest file. The lock uses PID-based staleness detection — if the lock is held by a process that no longer exists, or is older than 10 seconds, it is considered stale and overridden.
3. **Queue deduplication:** When the skill reads `pending-generation.json`, it deduplicates item IDs before processing. Multiple sync-tests.js runs may append the same item ID — the skill handles this gracefully.

#### Test pinning

When a developer manually edits a generated test to fix a bad selector, wrong assertion, or add project-specific setup:

1. On the next `sync-tests.js` run, the script detects that the test file content between `@begin:ID`/`@end:ID` markers no longer matches `generated_hash` in `items.json`
2. It sets `"pinned": true` for that item
3. Pinned tests are never overwritten by the skill — they are reported as "pinned (manually edited)" in the generation log
4. To un-pin (allow regeneration), either: set `"pinned": false` in `items.json`, or use `--force` to regenerate everything

This gives developers an escape hatch for tests that need manual tuning without fighting the pipeline or resorting to `--no-verify`.

#### Dry-run mode

For the first weeks of pipeline adoption, set `"dry_run": true` in `manifest/config.json`. In dry-run mode:

- Pre-commit and pre-push hooks run the affected tests but always exit 0 (report results, never block)
- Output is prefixed with `[DRY RUN]` so the developer sees what would have been blocked
- Can also be enabled via environment variable: `VERIFICATION_PIPELINE_DRY_RUN=1`

This smooths adoption across multiple projects — enable the pipeline, observe its behavior for a week, then disable dry-run when confident.

#### Test isolation

Generated Playwright tests that modify application state (creating events, adding artists) will interfere with each other if run in parallel. The `test_isolation` config in `manifest/config.json` defines the project-specific strategy:

| Strategy | Description | When to use |
|---|---|---|
| `per-test-user` | Each test uses a unique test user account (e.g., `test-user-{uuid}@example.com`) | Projects with user-scoped data |
| `per-test-seed` | Each test seeds its own data in a `beforeEach` and cleans up in `afterEach` | Projects with API-based seed endpoints |
| `serial` | Tests run sequentially, no parallelism | Small test suites or shared-state projects |
| `database-reset` | Reset database to seed state before each test file | Projects with fast seed scripts |

The skill asks about isolation strategy during project initialization and configures `playwright.config.ts` accordingly (e.g., setting `fullyParallel: false` for `serial`, or generating fixture setup code for `per-test-seed`).
```

#### Import index construction

The `import_index` in the manifest maps source files to the verification page docs they affect. This is the linchpin of change-scoped test execution — if the mapping is wrong, either too many or too few tests run.

**How it's built (during initial generation and refreshed on each skill invocation):**

1. **From verification docs outward:** Each verification page doc covers specific routes (listed in its header, e.g., `/events/new`, `/events/{id}/edit`). The skill traces these routes to their page/component files via the project's routing structure (Next.js app directory, React Router config, etc.).
2. **From components inward:** For each component file found, the skill follows its import tree (1 level deep) to capture direct dependencies — shared components, hooks, utilities.
3. **From API routes:** Verification items that reference API behavior (form submissions, data loading) are mapped to the backend route handlers they call.

The index is rebuilt on every full skill invocation. The `sync-tests.js` script reads the existing index but does not rebuild it — if the index is stale, the skill must be invoked to refresh it.

**Staleness detection:** Two types of staleness are handled:

1. **New files not in index:** If `map-changes.js` encounters a staged file not present in `import-index.json`, it logs a warning: "File `X` not in import index — run playwright-test-generator to refresh." The commit is not blocked; it just means that file's changes won't trigger tests until the index is refreshed.
2. **Stale entries pointing to deleted/moved files:** `map-changes.js` validates that every file it looks up in the index actually exists on disk (`fs.existsSync`). If an index entry points to a nonexistent file, it is excluded from results and a warning is logged: "Index entry `X` is stale (file no longer exists)." This prevents mapping changes from new files at an old path to incorrect test tags.

#### map-changes.js specification

`scripts/verification-playwright/map-changes.js` is a deterministic Node.js script (no LLM) that maps changed files to affected test tags.

**Inputs:**
- File paths (positional args): `map-changes.js file1.tsx file2.py docs/verification/pages/foo.md`
- `--since-main` flag: uses `git diff --name-only $(git merge-base HEAD main)..HEAD` to find all changed files since branching from main

**Algorithm:**
1. Read `manifest/import-index.json`. If the file does not exist, output nothing and exit 0 (pipeline not initialized).
2. For each input file:
   - If it's a verification doc (`docs/verification/**`): extract its page tag directly (filename minus extension)
   - If it's a source file: look up in `import_index` → get associated page tags
   - If not found in index: log warning, skip (no false positives)
3. Deduplicate and output the union of affected `@page-tag` values, space-separated

**Outputs:** Space-separated tag list to stdout, e.g., `@admin-event-form @admin-artist-form`. Empty output means no affected tests.

#### select-tier.js specification

`scripts/verification-playwright/select-tier.js` reads `manifest/config.json`'s tier config and matches the target branch.

**Input:** Target branch name (positional arg)
**Algorithm:** For each tier (checked in order: full → thorough → gate), check if the branch matches the tier's `branches` pattern (glob matching, `*` matches all). Return the first match. **Order is significant:** tiers are checked most-restrictive-first. Since `gate` has `branches: "*"` (catch-all), it must always be checked last. The script validates this on startup and errors if a catch-all tier is not last.
**Output:** Tier name to stdout (`gate`, `thorough`, `full`), or empty string if no match (feature branch push, skip tests).

#### Dependency bootstrapping

During project initialization, the skill checks for and installs required dependencies:

1. **@playwright/test** — If not in devDependencies, asks: "Playwright is required for the verification pipeline. Add @playwright/test to devDependencies?" Installs if confirmed.
2. **Browser binaries** — After installing Playwright, runs `npx playwright install chromium` (gate tier minimum). For thorough/full tiers, installs additional browsers: `npx playwright install firefox webkit`. Warns about download size (~150MB per browser).
3. **Node.js scripts** — Copies `map-changes.js`, `select-tier.js`, `sync-tests.js`, and `verify-pipeline.js` to `scripts/verification-playwright/`. These are managed by AEC and updated via `aec upgrade`.

#### Pipeline health diagnostic

`scripts/verification-playwright/verify-pipeline.js` is a diagnostic command that checks pipeline integrity:

1. **Manifest integrity:** All three manifest files parse as valid JSON
2. **Source file existence:** Every file in `import-index.json` exists on disk. Stale entries are reported.
3. **Spec file existence:** Every spec file referenced in `items.json` exists on disk. Orphaned entries are reported.
4. **Item-to-test consistency:** Every item ID in `items.json` has a corresponding `@begin:ID`/`@end:ID` block in its spec file. Orphaned tests (tests without manifest entries) are reported.
5. **Import index coverage:** Routes from verification doc headers are traced to source files and compared against the index. Missing entries are reported.
6. **Pinned test audit:** Reports which tests are pinned and why (manual edits detected).
7. **Pending generation queue:** Reports items in `pending-generation.json` that haven't been generated yet.

**Invocation:** `node scripts/verification-playwright/verify-pipeline.js` or via `aec doctor` (which runs it for every project with the pipeline enabled).

**Output:** A status report with pass/warn/fail per check. Example:

```
Pipeline Health Check
  ✓ Manifest files valid (3/3)
  ✓ Source files exist (47/47)
  ⚠ 2 stale import index entries (run --force-index to rebuild)
  ✓ Spec files exist (32/32)
  ✓ Item-to-test consistency (298/298)
  ⚠ 3 pinned tests (manually edited)
  ✓ No pending generation items
```

#### testid-gaps.md format

```markdown
# Verification Playwright: Missing data-testids

> Generated: 2026-04-07T18:00:00Z
> Total items: 432 | Active tests: 298 | Skipped (missing testids): 134

## Priority: High (standard depth items)

| Item ID | Description | Suggested testid | Component file |
|---------|-------------|-----------------|----------------|
| EVT-FRM-TKT-04 | Negative ticket price validation | `ticket-price-min-error` | EventForm.tsx |
| EVT-FRM-SD-01 | State cascade on type change | `event-type-select` | EventForm.tsx |

## Priority: Normal (deep depth items)

| Item ID | Description | Suggested testid | Component file |
|---------|-------------|-----------------|----------------|
| EVT-FRM-19 | Duplicate event constraint | `event-form-server-error` | EventForm.tsx |
```

#### Hook management strategy

Git hooks are managed via the project's existing hook framework:

1. **If husky is present** (detected by `.husky/` directory or `husky` in devDependencies): add verification-playwright as a sourced script within the existing hook files. Each hook file sources `scripts/verification-playwright/hooks/pre-commit.sh` or `pre-push.sh`. Uninstall removes the source line.
2. **If lefthook/lint-staged is present:** add verification-playwright commands to the existing config file (`.lefthookrc.yml`, `.lintstagedrc`). Uninstall removes the entries.
3. **If no hook framework:** install hooks directly in `.git/hooks/` with clear comment markers (`# BEGIN verification-playwright` / `# END verification-playwright`). Uninstall removes only the marked section. If other hook content exists outside the markers, it is preserved.

The postToolUse hook is always in `.claude/settings.json` (not a git hook) and is managed independently — added/removed by editing the settings JSON.

#### Full tier safety

The full tier has `maxTests: null` and `timeoutMs: null` by default, meaning no artificial limits. This is intentional — when pushing to main/production, you want to know about every failure, not just the first 100. However, the user can set limits during configuration if their test suite grows large enough that full runs become impractical. The suggested default is documented as "no limit (recommended for production gates)" with a note that projects with 500+ tests may want to set a timeout of 600000ms (10 minutes).

**`timeoutMs` is the primary constraint, `maxTests` is the secondary circuit breaker.** A state-dependency test that sets up a multi-step form flow takes 10x longer than a field validation test. 30 state-dependency tests could take 5 minutes, but 30 simple validation tests take 30 seconds. The timeout prevents unexpectedly slow runs from blocking the developer regardless of test count.

**Tier configuration is fully user-configurable.** The values above are suggested defaults. During skill initialization, the user is asked which tiers to enable and can customize branches, browsers, depths, and caps. All settings are stored in the manifest and read by the hooks at runtime.

#### Incremental update algorithm

1. Parse the changed verification doc
2. For each item, compute a content hash (action text + expected result + annotations)
3. Compare against manifest's stored hashes
4. **Added items** → append new test function to .spec.ts, add to manifest
5. **Modified items** → find test function by item ID tag, replace it, update manifest hash
6. **Removed items** → delete test function, remove from manifest
7. **Unchanged items** → skip entirely

#### Missing data-testid handling

On initial runs, many testids will be missing. This is expected and welcomed — the skill is designed to surface this as a work list, not treat it as an error.

- Items with missing testids get a test stub with `.skip()` and a TODO comment
- All gaps are logged to `testid-gaps.md` with the item ID, description, and suggested testid name
- The first run walks through each verification page doc section by section, reporting progress: "Processing admin-event-form.md (36 items) → 22 tests generated, 14 skipped (missing testids)"
- On subsequent runs, the skill checks if previously-missing testids have been added and un-skips those tests

The `testid-gaps.md` report is the prioritized work list for adding test infrastructure to the codebase.

### 3. Hook-Driven Automation

#### postToolUse hook (on verification doc edits)

**Implementation:** A shell command in `.claude/settings.json` that calls `scripts/verification-playwright/sync-tests.js`. The hook receives `$CLAUDE_FILE_PATH` from the Claude Code harness to know which file was edited.

```json
{
  "matcher": "Edit|Write",
  "hooks": [{
    "type": "command",
    "command": "if echo \"$CLAUDE_FILE_PATH\" | grep -q 'docs/verification/'; then node scripts/verification-playwright/sync-tests.js \"$CLAUDE_FILE_PATH\" 2>&1 | tail -5; fi"
  }]
}
```

**What sync-tests.js does (deterministic, no LLM, runs in <2 seconds):**

1. Parse the changed verification doc file
2. Acquire lockfile (`manifest/.lock`). Compute content hashes for each item, compare against `manifest/items.json`
3. For each change detected:
   - **Removed items:** delete test function (between `@begin:ID` / `@end:ID` markers), remove from manifest
   - **ID renamed:** update `@tag` in test name, update manifest key
   - **testid now exists (was missing):** remove `.skip()` from the test, update manifest status to `active`
   - **Minor text change (hash changed but structure same):** update the comment in the test, update hash. "Structure same" means: same item ID, same depth tier, same expected result type, same annotation type and fields — only the description text or annotation values changed. If depth, expected type, or annotation type changed, it's a substantial change and gets queued.
   - **New item or substantial change:** write item ID to `pending-generation.json` for the skill to pick up
4. Report summary to stdout (piped through `tail -5` to keep hook output concise)

**What the skill does when invoked (LLM-powered):**

1. Check for `pending-generation.json` — if items are queued, generate tests for them
2. Clear the queue after generation
3. This happens automatically when Claude is active in the project, or explicitly via `/playwright-test-generator`

This split means the hook is fast and non-blocking (shell script, no LLM), while complex test generation is deferred to the next Claude interaction.

#### Pre-commit hook (gate tier)

```bash
# Fires on every commit

# Check pipeline is initialized
if [ ! -f "scripts/verification-playwright/map-changes.js" ]; then
  exit 0  # Pipeline not initialized, pass through silently
fi

# Check for dry-run mode
dry_run=$(node -e "try{const c=require('./tests/verification-playwright/manifest/config.json');console.log(c.dry_run||false)}catch(e){console.log(false)}" 2>/dev/null)
if [ "$VERIFICATION_PIPELINE_DRY_RUN" = "1" ]; then dry_run="true"; fi

staged_files=$(git diff --staged --name-only)

# Categorize files
verification_docs=$(echo "$staged_files" | grep "^docs/verification/")
source_files=$(echo "$staged_files" | grep -v "^docs/verification/" | grep -v "^tests/verification-playwright/")

# Map source files → affected page tags via manifest import_index
affected_tags=$(node scripts/verification-playwright/map-changes.js $source_files $verification_docs)

# Count affected tests
test_count=$(echo "$affected_tags" | wc -w)

if [ "$test_count" -eq 0 ]; then
  exit 0  # No affected tests, commit proceeds
fi

# Read maxTests from config (default 30)
max_tests=$(node -e "const c=require('./tests/verification-playwright/manifest/config.json'); console.log(c.tiers.gate.maxTests || 30)")

if [ "$test_count" -gt "$max_tests" ]; then
  if [ -t 1 ]; then
    # Interactive terminal: ask the user
    echo "⚠ $test_count tests affected (shared component change, cap is $max_tests)."
    read -p "Run all / Run capped at $max_tests / Skip? [a/c/s]: " choice
    case "$choice" in
      s) exit 0 ;;
      c) affected_tags=$(echo "$affected_tags" | tr ' ' '\n' | head -n "$max_tests" | tr '\n' ' ') ;;
      *) ;; # run all
    esac
  else
    # Non-interactive (CI, IDE, scripted commit): run capped at maxTests
    affected_tags=$(echo "$affected_tags" | tr ' ' '\n' | head -n "$max_tests" | tr '\n' ' ')
  fi
fi

# Run only affected tests, chromium only, smoke+standard depths
npx playwright test \
  --config tests/verification-playwright/playwright.config.ts \
  --project chromium \
  --grep "$(echo $affected_tags | tr ' ' '|')"

# In dry-run mode: report results but never block
if [ "$dry_run" = "true" ]; then
  echo "[DRY RUN] Tests completed. Commit would have been $([ $? -eq 0 ] && echo 'allowed' || echo 'blocked')."
  exit 0
fi
```

#### Pre-push hook (branch-aware tiers)

```bash
# Pre-push hooks receive refspecs on stdin: <local ref> <local sha> <remote ref> <remote sha>
# Parse the remote ref to determine actual target branch (more reliable than @{push})
target_branch=""
while read local_ref local_sha remote_ref remote_sha; do
  # Extract branch name from remote ref (e.g., refs/heads/staging → staging)
  target_branch=$(echo "$remote_ref" | sed 's|refs/heads/||')
  break  # Use the first refspec
done

# Fallback to @{push} if stdin was empty (shouldn't happen in normal git push)
if [ -z "$target_branch" ]; then
  target_branch=$(git rev-parse --abbrev-ref @{push} 2>/dev/null || echo "")
fi

# Check pipeline is initialized
if [ ! -f "scripts/verification-playwright/select-tier.js" ]; then
  exit 0  # Pipeline not initialized, pass through
fi

# Read tier config from manifest
tier=$(node scripts/verification-playwright/select-tier.js "$target_branch")

case "$tier" in
  "thorough")
    # staging push: 3 browsers, all depths, changes only
    npx playwright test \
      --config tests/verification-playwright/playwright.config.ts \
      --grep "$(node scripts/verification-playwright/map-changes.js --since-main)"
    ;;
  "full")
    # main/production push: all browsers, all tests
    npx playwright test \
      --config tests/verification-playwright/playwright.config.ts
    ;;
  *)
    exit 0  # Feature branch push, skip
    ;;
esac
```

### 4. AEC Integration

#### Installation

```bash
aec install skill playwright-test-generator
```

Installs the skill globally. Does nothing until initialized in a project.

#### Project initialization

When run for the first time in a project with verification docs (or via `aec setup`):

1. Detects verification docs at the project's configured path
2. Asks:
   > "This project has verification docs at `docs/verification/`. Enable the verification-to-Playwright pipeline? This adds hooks for incremental test generation and commit-time testing."
3. If yes, asks tier configuration preferences (with defaults)
4. Sets up:
   - postToolUse hook in `.claude/settings.json` for `docs/verification/**`
   - Pre-commit hook (gate tier)
   - Pre-push hook (thorough/full tiers, branch-aware)
   - Initial manifest files at `tests/verification-playwright/manifest/` (items.json, import-index.json, config.json)
   - Runs initial full generation from existing verification docs (section by section, reports progress)
5. Records in AEC project tracking that this project has the pipeline enabled

#### Uninstallation

```bash
aec uninstall skill playwright-test-generator
```

1. Removes the postToolUse hook entries from `.claude/settings.json` in every opted-in project
2. Removes the pre-commit and pre-push hook entries (or the verification-specific portions, per hook management strategy)
3. Asks: "Remove generated Playwright tests and manifest too, or keep them as static tests?"
4. Updates AEC project tracking

#### Diagnostics

```bash
aec doctor
```

When the pipeline is enabled for a project, `aec doctor` runs `verify-pipeline.js` as part of its health check. Reports stale index entries, orphaned tests, pending generation items, and pinned test counts.

#### Upgrades

```bash
aec upgrade
```

When the skill or hook logic updates, `aec upgrade` propagates changes to hooks in every project that opted in. Same pattern as rule updates.

## Role Clarity After This Change

| Skill | Role | When used |
|---|---|---|
| **verification-writer** | Source of truth. Analyzes code, produces/updates verification docs. Now with Layer 3e for state dependency edge cases. | After code changes, new features, or on demand |
| **playwright-test-generator** | Derived artifact producer. Reads docs, writes tests. Translates, does not author. | Automatically via postToolUse hook on doc changes |
| **browser-verification** | Exploratory QA. Deep dives on new features, pre-deploy spot checks, visual/contextual issues that automated tests can't catch. Feeds findings back to verification-writer. | Manual, for discovery — no longer the regression gate |
| **Playwright runner** | Headless, deterministic, no browser contention. Runs on hooks. | Automatically via pre-commit and pre-push hooks |

## Pipeline Flow

```
                    ┌─────────────────────────┐
                    │    Code Changes          │
                    └────────┬────────────────┘
                             │
                    ┌────────▼────────────────┐
                    │  verification-writer     │
                    │  (Layer 3e: state deps)  │
                    │  Updates docs only       │
                    └────────┬────────────────┘
                             │ postToolUse hook
                    ┌────────▼────────────────┐
                    │  playwright-test-gen     │
                    │  Diffs docs → patches    │
                    │  .spec.ts incrementally  │
                    └────────┬────────────────┘
                             │ pre-commit / pre-push
                    ┌────────▼────────────────┐
                    │  Playwright runner       │
                    │  (headless, no browser   │
                    │   contention)            │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼───┐    ┌────▼───┐    ┌─────▼────┐
         │  PASS  │    │  FAIL  │    │  SKIP    │
         │commit/ │    │block,  │    │missing   │
         │push    │    │report  │    │testids   │
         └────────┘    └────┬───┘    └─────┬────┘
                            │              │
                            │         testid-gaps.md
                            │         (work list)
                            │
                    ┌───────▼─────────────────┐
                    │  browser-verification    │
                    │  (exploratory only now)  │
                    │  Deep dives, new feature │
                    │  verification, edge case │
                    │  hunting                 │
                    └────────┬────────────────┘
                             │ finds new issues
                    ┌────────▼────────────────┐
                    │  verification-writer     │
                    │  Updates docs with       │
                    │  findings                │
                    └─────────────────────────┘
                             ↑ cycle repeats
```

## What This Prevents

Mapping back to the original 23 bugs found in barevents:

| Bug class | Example | Prevention mechanism |
|---|---|---|
| State transition / cross-field (bugs 4, 8, 11, 13-18) | Removed artist still in responsibility state allows invalid event creation; changing event type keeps stale flyer config causing FK error | Layer 3e generates state dependency items; Playwright tests run on every commit |
| Missing validation (bugs 19, 21) | Min ticket price > max accepted; description required on edit but not create | verification-writer Layer 3a already covers these; Playwright automates the check |
| Data not persisting on save (bugs 14, 20) | Flyer toggle and ticket pricing revert after save/reopen | Edit form pre-population checks (Layer 3a rule 4) become automated Playwright tests |
| Display / formatting bugs (bugs 9, 22) | Duration shows raw decimal; event type label always shows "Event" | Standard verification items become regression tests |
| UI flicker / rendering (bugs 2, 12) | Responsibility section flickers rapidly on mode switch | browser-verification deep exploratory catches visual issues that Playwright can't |
| FK constraint violations (bugs 10, 18) | Removed promoter still submitted as flyer uploader, DB returns FK violation | Layer 3e traces submission payload for stale references; elevated to `[standard]` depth |

## Open Questions

1. **CI integration** — Should the full tier also run in CI (GitHub Actions / Railway) as a safety net beyond local hooks? Likely yes, but deferred to a separate spec.
2. **Existing hand-written Playwright tests** — Migration plan: verification-writer generates docs covering what the hand-written tests check, playwright-test-generator produces the automated versions, then hand-written tests are removed. Incremental, not big-bang.

## Resolved During Design

1. **Test data management** — Resolved via `test_isolation` config in `manifest/config.json`. Project-specific strategy selected during init (per-test-user, per-test-seed, serial, or database-reset).
2. **Browser contention** — Resolved by architecture. Regression testing uses headless Playwright (no browser MCP needed). Browser-verification moves to exploratory-only role. No queue system needed.
3. **Manifest corruption recovery** — Resolved by splitting manifest into three independent files with per-file `--force` flags and `verify-pipeline.js` diagnostic.
