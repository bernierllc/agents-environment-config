# AEC Discovery — Design Spec

**Date:** 2026-04-10
**Status:** Draft v3 — updated with architecture, workflow, and product review feedback

## Problem

When users set up AEC in a repo that already has agents, skills, or rules in `.claude/` or `.cursor/`, AEC has no way to detect these existing items, compare them to the AEC catalog, or offer to bring them under AEC management. This leads to:

- Duplicate files (untracked local copies alongside AEC-managed versions)
- No update path for items that were manually copied
- Users unaware that AEC already tracks items similar to what they have
- No contribution path for users with custom items the community could benefit from

## Solution

A **similarity discovery** system that scans a repo (or global install) for existing agents, skills, and rules, compares them against the AEC catalog, and lets the user choose which to install under AEC management — with persistent "dismissed" tracking so we never nag.

## Commands

### `aec discover`

Standalone scan command. Scans the current repo (or global with `-g`) for untracked items similar to AEC catalog items.

**Requires:** `.aec.json` must exist in the repo (run `aec setup` first). If missing, exits with error: "This repo is not tracked by AEC. Run `aec setup <path>` first."

**Flags:**
- `-g` / `--global` — scan `~/.claude/` instead of current repo
- `--rediscover` — re-surfaces previously dismissed items
- `--depth 1|2|3` — skip the depth prompt, use specified level. Values outside 1-3 are rejected with an error.
- `--yes` / `-y` — install all exact matches, skip all non-exact matches (conservative: does not auto-replace modified/similar items)
- `--dry-run` — show what would be found and how items would be classified, without writing any files

### Integration points

- **`aec setup <repo>`** — after directory creation and template copying, offers discovery scan. Defaults to Normal depth (no depth prompt — reduces onboarding friction). Use `aec discover --depth 3` for Deep.
- **`aec install` / `aec update`** (global scope) — Quick-level scan (name matching only) of `~/.claude/` for net new untracked items, honoring dismissals. Kept lightweight to avoid adding I/O to every install/update.

## Item Lifecycle

Items have four possible states:

```
untracked → discovered → installed (via aec install)
                       → dismissed (user says "leave alone")

dismissed → discovered (via --rediscover, or auto-recompare if hashes changed and policy is "auto")

installed → untracked  (user runs aec uninstall, or manually deletes file)
```

Notes:
- There is no "dismissed → installed" shortcut. To install a dismissed item, the user either runs `aec install <name>` directly (which always works regardless of dismissal state) or uses `aec discover --rediscover` to re-surface it.
- If the user manually deletes an installed file, the installed record becomes stale. `aec doctor` should detect and clean up orphaned install records.
- `aec uninstall` should check whether the uninstalled item has a local untracked copy that would become a discovery candidate on next scan.

## User Flow

### During `aec setup <repo>`

```
Setting up aihelp...
  ✓ Created directories
  ✓ Copied templates
  ✓ Detected test suites

Scan for files that match items in the AEC catalog? [Y/n]: y

Scanning... done.

Found 3 items similar to AEC tracked items:

  AGENTS
  1) engineering-backend-architect.md  ✓ Exact match
  2) custom-reviewer.md               ⚠ Similar (87%) to engineering-code-reviewer

  SKILLS
  3) webapp-testing/                   ⚠ Modified (hash differs from AEC v1.0.0)

How would you like to handle these?
  1) Install exact matches, then ask me about the rest
  2) Review one by one
  3) Replace all with AEC-managed versions (will ask about backups)
  4) Skip — don't install any

Choose [1]:
```

**Option 1 flow (install exact, ask about rest):**

```
  Back up original before replacing? [Y/n]: y
  ✓ Backed up to .aec-backup/engineering-backend-architect.2026-04-10T18-00-00.md
  ✓ Installed engineering-backend-architect.md (exact match)

Remaining items:
  1) custom-reviewer.md — ⚠ Similar (87%) to engineering-code-reviewer
     View diff? [y/N]: y
     [shows diff]
     Replace with AEC version? [y/N]: n
     ✓ Skipped (won't ask again)

  2) webapp-testing/ — ⚠ Modified (hash differs)
     View diff? [y/N]: n
     Replace with AEC version? [y/N]: n
     ✓ Skipped (won't ask again)

You skipped 2 items. If any would be useful to others, consider contributing:
  https://github.com/bernierllc/agency-agents/blob/main/CONTRIBUTING.md
```

**Option 3 flow (accept all):**

```
  Back up originals before replacing? [Y/n]: y
  ✓ Backed up 3 items to .aec-backup/ (timestamped)
  ✓ Installed engineering-backend-architect.md (exact match)
  ✓ Installed custom-reviewer.md → engineering-code-reviewer (replaced)
  ✓ Installed webapp-testing/ (replaced)
```

### Zero matches

```
Scanning... done.

No similar items found.
```

### During `aec discover` (standalone)

Same flow, but includes the depth prompt (since the user is explicitly investigating):

```
How deep should we scan?
  1) Quick  — Name matching only (fast, could be false match)
  2) Normal — Name match + content hash comparison (shows identical vs modified)
  3) Deep   — Full content similarity scan, finds renamed/similar files (<1 min for ~500 items)
Choose [2]:
```

If dismissals exist:

```
3 previously dismissed items found.
Include them in this scan? [y/N]:
```

### During `aec install/update` (global)

Quick-level scan only (name matching). Reports net new untracked items found in `~/.claude/agents/` or `~/.claude/skills/`. Honors previous dismissals. Does not re-scan dismissed items.

```
ℹ Found 2 untracked items matching AEC catalog names. Run `aec discover -g` to review.
```

### Dismissal re-comparison preference

Asked once (stored in `preferences.json`):

```
If a skill, agent, or rule you previously dismissed changes or gets updated,
should we compare it to AEC tracked items again?
  1) Yes, re-compare automatically
  2) No, keep dismissed until I run aec discover --rediscover

Choose [1]:
```

Stored as `discovery_recompare_policy`: `"auto"` or `"manual"`.

## Similarity Engine

### Quick (Level 1) — Name matching

- Strip prefixes/suffixes and normalize: `engineering-backend-architect.md` → `backend-architect`
- Compare normalized names against catalog normalized names
- Flag: exact filename match or normalized match
- Fast, could be false match

### Normal (Level 2) — Name match + content hash

Everything from Quick, plus:

- Hash the user's local file
- Compare against `catalog-hashes.json` (pre-computed, ships with AEC)
- Also compare local hashes against all catalog hashes to find **renamed** items (different name, same hash)
- Classify each match:
  - **Exact match** — same name, same hash (identical content)
  - **Modified** — same name, different hash
  - **Renamed** — different name, same hash (user has the exact content under a different filename)
  - **Unmatched** — name matched but content is completely different (false positive from Quick, removed from results)

### Deep (Level 3) — Content similarity

Everything from Normal, plus:

- For files that didn't match by name or hash, compute similarity
- Read both files, normalize whitespace
- Compute overlap ratio (shared lines / total unique lines) — Jaccard similarity on line sets
- **Note:** This is order-insensitive. For markdown agent/rule files this is appropriate. For skills that contain code, reordered functions could score misleadingly high. The similarity percentage should be treated as a hint, not a guarantee.
- Threshold: 70%+ = flag as similar
- Only runs on unmatched local files against unmatched catalog items (not the full cartesian product)
- Pre-filter by file size — skip files that differ in size by more than 5x
- Result: `"similar"` match type with a percentage

### Missing `catalog-hashes.json` recovery

If `catalog-hashes.json` is missing or corrupt:

1. Offer to regenerate locally: "catalog-hashes.json is missing. Generate it from AEC source? [Y/n]"
2. If AEC source not available, offer to fetch: "Download from GitHub? [y/N]"
3. If both fail, fall back to Quick (name-only) with warning: "⚠ Running name-only scan — hash comparison unavailable."

### Performance

- Quick: instant (string comparisons only)
- Normal: sub-second (hash local files, compare against pre-computed catalog)
- Deep: <1 min for ~500 items (read files, line-set comparison, pre-filtered)

### Implementation

Single function pipeline — each level builds on the previous:

```python
def scan(local_items: list, catalog: dict, depth: int = 2) -> list[MatchResult]:
    ...
```

## Match Types

| Type | Name match | Hash match | Description |
|------|-----------|------------|-------------|
| **Exact** | Yes | Yes | Identical content, same name |
| **Modified** | Yes | No | Same name, different content |
| **Renamed** | No | Yes | Different name, identical content |
| **Similar** | No | No | Different name, 70%+ content overlap (Deep only) |

## File Architecture

### Global files (`~/.agents-environment-config/`)

| File | Purpose | Notes |
|------|---------|-------|
| `installed-skills.json` | Globally installed skills | Existing (migrate from v1 format) |
| `installed-agents.json` | Globally installed agents | New |
| `installed-rules.json` | Globally installed rules | New |
| `dismissed-skills.json` | Globally dismissed skills | New |
| `dismissed-agents.json` | Globally dismissed agents | New |
| `dismissed-rules.json` | Globally dismissed rules | New |
| `tracked-repos.json` | Repo references + .aec.json paths | Replaces `setup-repo-locations.txt` |
| `ports-registry.json` | Global port dedup/lookup | Existing — only file that aggregates from repos |
| `preferences.json` | User preferences | Existing — gains `discovery_recompare_policy` |

### Why separate files (not a single manifest)

Users run multiple AI agents in parallel on the same machine (e.g., 8 concurrent Claude Code agents working on different repos). A single manifest file creates write contention — parallel agents installing a skill in repo A and dismissing an agent in repo B would race on the same file. Separate files per concern (installed-skills, dismissed-agents, etc.) allow concurrent writes without contention, since different operations touch different files.

This is not speculative — it reflects the actual usage pattern of the tool.

### Deprecated (migrate out)

| File | Replacement |
|------|-------------|
| `installed-manifest.json` | Per-type `installed-*.json` files |
| `setup-repo-locations.txt` | `tracked-repos.json` |

### Per-repo (`.aec.json`)

Existing `installed` section stays. New `dismissed` section added:

```json
{
  "dismissed": {
    "agents": {
      "custom-reviewer.md": {
        "dismissedAt": "2026-04-10T18:00:00Z",
        "matchedCatalogItem": "engineering-code-reviewer",
        "matchedCatalogVersion": "1.0.0",
        "matchedCatalogHash": "sha256:abc123...",
        "localHash": "sha256:def456...",
        "matchType": "similar",
        "scanDepth": 3,
        "similarity": 0.87
      }
    },
    "skills": {},
    "rules": {}
  }
}
```

### Dismissal precedence

Per-repo dismissals (in `.aec.json`) take precedence over global dismissals (in `dismissed-*.json`). If an item is dismissed per-repo, the global state is irrelevant for that repo. Global dismissals only apply to items in `~/.claude/` (the global scope).

### AEC repo (shipped with releases)

`catalog-hashes.json` — pre-computed hashes for every skill, agent, and rule:

```json
{
  "generatedAt": "2026-04-10T...",
  "aecVersion": "2.18.2",
  "agents": {
    "engineering-backend-architect": {
      "version": "1.0.0",
      "contentHash": "sha256:abc123..."
    }
  },
  "skills": {},
  "rules": {}
}
```

Updated incrementally by a pre-commit hook — only recomputes hashes for items where the version has changed since the hash was created.

## Data Structures

### Dismissed item (global `dismissed-{type}.json`)

```json
{
  "schemaVersion": 1,
  "items": {
    "custom-reviewer.md": {
      "dismissedAt": "2026-04-10T18:00:00Z",
      "matchedCatalogItem": "engineering-code-reviewer",
      "matchedCatalogVersion": "1.0.0",
      "matchedCatalogHash": "sha256:abc123...",
      "localHash": "sha256:def456...",
      "matchType": "similar",
      "scanDepth": 3,
      "similarity": 0.87
    }
  }
}
```

Fields:
- `dismissedAt` — ISO8601 timestamp
- `matchedCatalogItem` — which AEC catalog item this was compared to
- `matchedCatalogVersion` — version of the catalog item at dismissal time
- `matchedCatalogHash` — hash of the catalog item at dismissal time
- `localHash` — hash of the user's local file at dismissal time
- `matchType` — `"exact"`, `"modified"`, `"renamed"`, or `"similar"`
- `scanDepth` — 1, 2, or 3 — which depth level produced this match (needed for correct re-comparison)
- `similarity` — float, only present for `"similar"` match type

### Tracked repos (`tracked-repos.json`)

```json
{
  "schemaVersion": 1,
  "repos": {
    "/Users/mattbernier/projects/aihelp": {
      "aecJsonPath": "/Users/mattbernier/projects/aihelp/.aec.json",
      "trackedAt": "2026-04-08T03:32:24Z",
      "aecVersion": "2.18.2"
    }
  }
}
```

### Catalog hashes (`catalog-hashes.json`)

```json
{
  "generatedAt": "2026-04-10T...",
  "aecVersion": "2.18.2",
  "agents": {
    "engineering-backend-architect": {
      "version": "1.0.0",
      "contentHash": "sha256:abc123..."
    }
  },
  "skills": {},
  "rules": {}
}
```

## Backup Strategy

When replacing a local file with an AEC-managed version, the user is asked:

```
Back up original before replacing? [Y/n]:
```

- **Yes:** Original file is copied to `<repo>/.aec-backup/` with a timestamp postfix:
  - Files: `.aec-backup/engineering-backend-architect.2026-04-10T18-00-00.md`
  - Directories: `.aec-backup/webapp-testing.2026-04-10T18-00-00/`
- Flat directory structure — easy to browse with `ls .aec-backup/`
- Timestamps prevent silent overwrites on repeated runs
- `.aec-backup/` should be added to `.gitignore` during setup

## Atomic Writes

All JSON file writes use the write-then-rename pattern:

1. Write to `<file>.tmp` (same directory)
2. `os.rename('<file>.tmp', '<file>')` — atomic on POSIX
3. If the process crashes before rename, the `.tmp` file is orphaned but the original is untouched

This applies to: `.aec.json`, `dismissed-*.json`, `installed-*.json`, `tracked-repos.json`, `preferences.json`, `catalog-hashes.json`.

### Ctrl-C handling

Writes are committed per-item, not batched. If the user interrupts mid-flow:
- Items already installed/dismissed are persisted
- The current item in progress may be lost (acceptable — user can re-run)
- No partial/corrupt state because each write is atomic

## Error Handling

### Malformed `.aec.json`

If `.aec.json` exists but contains invalid JSON:
- Discovery aborts with error: "`.aec.json` contains invalid JSON. Fix or delete it and re-run `aec setup`."
- No silent fallback — bad config should be fixed, not ignored.

### Pre-migration repos (`.aec.json` missing `dismissed` key)

If `.aec.json` is valid JSON but has no `dismissed` section, treat it as empty dismissals (no items dismissed). The section is created on first dismissal write.

### Catalog item removed from future AEC version

Dismissed records referencing removed catalog items become inert. On scan, if `matchedCatalogItem` no longer exists in the catalog, the dismissal is silently pruned from the file. The local item becomes a candidate for fresh discovery.

## Design Principles

### CLI option-giving principle

All interactive prompts follow the established AEC CLI patterns:

1. **Smart default + Y/n** — one obvious right answer, uppercase = default
2. **y/N (conservative default)** — destructive or irreversible actions
3. **Numbered menu** — 3+ valid options where none is obviously right
4. **Multi-select with batch options** — install all / select / skip
5. **--yes flag** — installs exact matches, skips non-exact (conservative)
6. **--dry-run flag** — preview without acting
7. **Preference persistence** — don't re-ask answered questions
8. **EOFError = safe default** — non-interactive defaults to conservative "no"

### Dismissed = "known, leave alone"

A dismissal means "I've seen this, it's intentional, stop asking about it." It stores both the local hash and the catalog hash at dismissal time, plus the scan depth that produced the match. Depending on the user's `discovery_recompare_policy`, changed hashes may trigger re-comparison automatically or stay dismissed until `--rediscover`.

### Separate files per concern

Each data type gets its own JSON file. This enables concurrent writes from parallel agents without file contention and keeps each file small and focused.

The only exception is `ports-registry.json`, which aggregates from per-repo `.aec.json` files because port conflict detection requires a global view.

### Contribution encouragement

When a user dismisses an item, show a brief message encouraging contribution to the appropriate open-source repo:

- Agents: `https://github.com/bernierllc/agency-agents/blob/main/CONTRIBUTING.md`
- Skills: `https://github.com/bernierllc/claude-skills/blob/main/CONTRIBUTING.md`
- Rules: `https://github.com/bernierllc/agents-environment-config/blob/main/CONTRIBUTING.md`

## Migration Plan

### Phase 1: New file infrastructure

- Create `installed-agents.json`, `installed-rules.json` (empty, same schema as `installed-skills.json`)
- Create `dismissed-agents.json`, `dismissed-skills.json`, `dismissed-rules.json` (empty)
- Create `tracked-repos.json` by migrating entries from `setup-repo-locations.txt`
- Add `dismissed` section to `.aec.json` schema
- Generate initial `catalog-hashes.json` and add pre-commit hook
- Implement atomic write utility (write-tmp-then-rename)
- **Source of truth during transition:** New per-type files are authoritative for reads. `install_cmd.py` writes to BOTH old manifest and new per-type files until Phase 3 completes. This ensures no data loss during the transition window.

### Phase 2: Discovery engine

- Implement `scan()` pipeline (Quick/Normal/Deep)
- Implement `aec discover` command
- Integrate discovery into `aec setup` flow
- Integrate Quick-level discovery into `aec install/update` (global)
- Add `discovery_recompare_policy` preference
- Add backup-before-replace flow (`.aec-backup/`)
- Update `aec uninstall` to check for local untracked copies that become discovery candidates

### Phase 3: Deprecation

- Stop writing to `installed-manifest.json` (new per-type files are sole source of truth)
- Migrate any remaining entries from `installed-manifest.json` into per-type files
- Migrate per-repo entries from `installed-manifest.json` into `.aec.json`
- Remove `installed-manifest.json` reads (keep file for one version for safety)
- Remove `setup-repo-locations.txt` reads

### Migration callsite inventory

Files that reference `installed-manifest.json` or `setup-repo-locations.txt` and need updating:
- `aec/lib/manifest_v2.py` — manifest read/write
- `aec/commands/install_cmd.py` — install writes
- `aec/commands/upgrade.py` — upgrade reads/writes
- `aec/commands/uninstall.py` — uninstall writes
- `aec/lib/scope.py` — repo location reads
- `aec/commands/repo.py` — setup writes to tracking log
- `aec/commands/doctor.py` — health checks
- All other callsites to be identified via grep before implementation begins.

## Review Feedback Addressed

### From Software Architect review (2026-04-10)

1. **Separate files justified** — Multi-agent parallelism is the real use case, not speculative. Added "Why separate files" section.
2. **Migration source-of-truth** — Added dual-write contract for Phase 1-3 transition.
3. **`scanDepth` on dismissals** — Added to data structures.
4. **Deep similarity order-insensitivity** — Added note about Jaccard limitation for code files.
5. **File size pre-filter** — Changed from 3x to 5x.
6. **Lightweight scan depth defined** — Quick-level only for install/update integration.
7. **`aec uninstall` check** — Added to Phase 2.

### From Workflow Architect review (2026-04-10)

1. **Install action specified** — Uses existing `aec install` path under the hood, with backup option.
2. **`--yes` semantics defined** — Installs exact matches, skips non-exact (conservative).
3. **`--dry-run` output** — Shows classifications without writing.
4. **Zero matches output** — Added "No similar items found" message.
5. **Ctrl-C handling** — Per-item writes, atomic, no batch.
6. **Malformed `.aec.json`** — Hard fail with clear error.
7. **Missing `catalog-hashes.json`** — Three-tier fallback (regenerate, fetch, fall back to Quick).
8. **Global vs per-repo precedence** — Per-repo wins, added section.
9. **Non-tracked repo** — Error with guidance to run setup.
10. **Backup before replace** — Added backup strategy section.
11. **State transitions** — Added complete lifecycle section.
12. **Atomic writes** — Added write-then-rename section.
13. **Stale dismissals** — Pruned when catalog item is removed.

### From Product Manager review (2026-04-10)

1. **Depth prompt removed from setup** — defaults to Normal during `aec setup`. Depth prompt reserved for standalone `aec discover`.
2. **"Dismissed" → "Skipped"** in user-facing text. Internal data model stays `dismissed`.
3. **Contribution message once per session** — shown after all items processed, not per-item.
4. **Shortened scan prompt** — "Scan for files that match items in the AEC catalog? [Y/n]"
5. **Timestamped backups** — flat directory with timestamp postfix on filenames, no nested dirs.
6. **Consequence text on Option 3** — "Replace all with AEC-managed versions (will ask about backups)"
7. **Tighter integration message** — dropped path detail, added clear next step.
