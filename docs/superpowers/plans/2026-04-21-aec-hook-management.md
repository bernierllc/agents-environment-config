# AEC Hook Management — Implementation Plan

**Spec**: `docs/superpowers/specs/2026-04-21-aec-hook-management-design.md`
**Status**: In progress — foundation shipped, lifecycle/deprecation/promotion pending
**Owner**: Matt
**Date**: 2026-04-21 (plan written 2026-05-05)

## Purpose

Lock in what already shipped from the hook-management spec, identify drift, and define the remaining work as concrete, sequenced tasks. The spec covers: agent-agnostic `hooks.json` schema, AEC translation/install layer for Claude/Gemini/Cursor/git, install/upgrade lifecycle with state tracking, deprecation/prune, Cursor `command` → `hook` migration, rule file→directory promotion, real consumers, and docs.

Most of the **foundation** (Phase 1) and the **multi-target installer** (Phase 4 Cursor migration plumbing + git block writer) shipped without a plan file. This document closes that gap and sequences the rest.

## Phase status (per spec §8.1)

### Phase 0 — Audits & Prereqs ✅ Shipped
Discovery hint regression fix, per-type installed manifests (`installed-{agents,skills,rules,mcps}.json`), and the hooks module skeleton are in place. Audit of existing hooks (Claude `.claude/settings.json`, Cursor `.cursor/hooks`, Gemini, git) was done implicitly through the installer work in PR #37/#38.

### Phase 1 — Foundation (schema + validator + translator) ✅ Mostly shipped
Shipped:
- `aec/lib/hooks/schema.py` — load + parse `hooks.json` (`load_hooks_file`, `HooksSchemaError`)
- `aec/lib/hooks/validator.py` — spec §1.6 rule checks (`validate_hooks_file`)
- `aec/lib/hooks/translator.py` — generic event vocabulary → per-agent native shape
- `aec/lib/hooks/predicates.py` — `when` predicate evaluation incl. `repo_has`/`repo_has_any`/`repo_lacks`/`custom_check` gating (`21a4871`)
- `aec/lib/hooks/fingerprint.py` — content fingerprints for drift detection
- `aec/lib/hooks/git_blocks.py` — delimited `AEC:BEGIN/END` markers for git hooks (`5ac876d`)
- `aec/lib/hooks/state.py` — `.aec/installed-hooks.json` state file
- `aec/lib/hooks/installer.py` — Claude/Gemini/Cursor/git install paths (`2ab88ba`, `9abdad3`)
- `aec hooks validate <path> --item-version <v>` CLI (`aec/commands/hooks_cmd.py`)
- `aec run-script` resolution to absolute paths in translator (`d38c8e3`) — see Drift item 1.
- Repair pass for malformed flat-shape Claude hook entries (`7caff4b`)

**Drift / open items in Phase 1:**
1. `aec run-script <item> <script>` CLI command (spec §4.4) — translator emits absolute paths, but the runtime entrypoint that scripts are invoked through does not exist as a typer command. Confirm: is this still the intended UX, or has the translator's path-resolution superseded it?
2. `aec hooks` sub-app currently exposes only `validate`. The spec lists `list | install | upgrade | remove | diff | repair | skip-version` as Phase 1+2 surface — see Phase 2 below.

### Phase 2 — Lifecycle (install/upgrade/state/CLI) 🟡 Partial
Shipped under-the-hood:
- Installer can write Claude/Gemini/Cursor/git targets given a parsed `hooks.json` (PR #37/#38).
- State file format is defined in `state.py`.
- Quick-scan notification hint is wired into install/upgrade flows (`de7ea75`) — separate from hook-management but in the same lifecycle envelope.

**Remaining for Phase 2:**
1. **`aec hooks install`** — read item's `hooks.json`, run validator, evaluate `when` predicates per scope, call installer, persist state.
2. **`aec hooks upgrade`** — diff item-version vs. recorded fingerprint, prompt tiered Y/n/d/s/v (apply / no / diff / skip-version / view), update state.
3. **`aec hooks remove`** — strip AEC:BEGIN/END blocks from git hooks, remove agent entries from Claude/Gemini/Cursor settings, clear state.
4. **`aec hooks list`** — show installed hooks per scope with version + drift status.
5. **`aec hooks diff <item>`** — show pending changes between installed fingerprint and current item.
6. **`aec hooks repair`** — reconcile state file with on-disk reality (orphans, drift).
7. **`aec hooks skip-version <item> <version>`** — record a version skip in state.
8. **Wire install/upgrade into `aec install` / `aec upgrade`** — currently top-level install does not invoke hook install; today's hook installs are manual (and that's how `2ab88ba` was tested). This is the integration that turns hooks from a feature into the default path.

### Phase 3 — Deprecation & Prune ❌ Not started
- `deprecated:` frontmatter field (since / reason / replacement / remove_after) on items.
- Discovery emits deprecation warning on install/upgrade.
- `aec prune` already exists as a top-level command (per `aec/cli.py`) but does not honor `remove_after` or scan for deprecated items. Audit `aec/commands/generate.py:run_prune` and extend.
- Spec §6.6 first deprecation targets: `docx`, `pdf`, `pptx`, `xlsx` skills.

### Phase 4 — Cursor migration 🟡 Partial
Shipped:
- Cursor install path in `installer.py` (`9abdad3`).
- Per-target translator output for Cursor (`2ab88ba`).

**Remaining:**
- `command` → `hook` migration for legacy Cursor entries (spec §1.4 / §4.3).
- Doctor / migration command surface (`aec migrate cursor-hooks` or fold into `aec upgrade`).

### Phase 5 — Rule file→directory promotion ❌ Not started
Version-driven, no coexistence (spec §5). Touches `aec/lib/installed_store.py` rules layout and `aec install`/`aec upgrade` for rules. Has cascading effects on the `~/.agent-tools/rules/` layout that CLAUDE.md references.

### Phase 6 — Real consumers ❌ Not started
First items to ship a `hooks.json` against the new schema. Spec §8.1 phase 6 lists candidate items; the pre-commit catalog-hashes hook (`8fa6e82`) is currently installed via the older mechanism and is the obvious first migrant.

### Phase 7 — Documentation ❌ Not started
17 deliverables D1–D17 per spec §7. README/CLAUDE.md updates, contributor guide for `hooks.json`, user guide for `aec hooks ...` CLI, deprecation policy doc.

## Sequencing & dependencies

Per spec §8.10:
- **Phase 2 must follow Phase 1** (we have Phase 1, so Phase 2 is unblocked).
- **Phase 4 can run parallel to Phase 2** after Phase 0 — but Cursor installer already ships, so what's left is migration logic which is small.
- **Phase 5 (rule promotion) is independent** of hooks but in the same spec; can be sequenced after Phase 2 to avoid touching `installed_store.py` twice.
- **Phase 6 (consumers)** depends on Phase 2 being end-to-end usable.
- **Phase 7 (docs)** lags the corresponding feature phase by one.

## Recommended next slice (next 5–7 PRs)

1. **`aec hooks list` + `aec hooks diff`** (read-only, lowest risk, validates state.py end-to-end against real installs).
2. **`aec hooks install`** wired into `aec install` with a feature flag / opt-in until Phase 6 has a real consumer.
3. **`aec hooks upgrade`** with tiered prompts; reuse the Y/n/d/s/v pattern.
4. **`aec hooks remove`** + `aec hooks repair`.
5. **`aec hooks skip-version`** + state migration if the schema changes.
6. **Migrate the catalog-hashes pre-commit hook** to `hooks.json` (Phase 6 first consumer; proves end-to-end).
7. **Phase 3 deprecation field + `aec prune` extension** + first deprecations (`docx`, `pdf`, `pptx`, `xlsx`).

Phases 4 (Cursor migration), 5 (rule promotion), and 7 (docs) get their own plan slices once the Phase 2 surface is real.

## Open questions for user

1. Is `aec run-script <item> <script>` still part of the UX, or has translator-side absolute-path resolution made it unnecessary?
2. Should hook install be opt-in (feature flag) or default-on once `aec hooks install` lands? Default-on risks surprising users with hooks they didn't ask for; opt-in delays the consumer migrations in Phase 6.
3. Phase 5 rule promotion has the largest blast radius (all `~/.agent-tools/rules/` consumers). Do we want a separate plan file for it before sequencing?
