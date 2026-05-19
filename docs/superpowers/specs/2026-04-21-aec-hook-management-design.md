# AEC Hook Management — Design Spec

**Date:** 2026-04-21
**Status:** Draft v1 — pending spec-document-reviewer pass

> Design spec for adding first-class, generic hook management to AEC. Introduces a
> `hooks.json` contract that any AEC item (agent, skill, rule) can ship, a translation
> layer that targets Claude Code, Gemini CLI, Cursor, and git, a lifecycle with
> install/upgrade/remove/prune, a first-class deprecation system, and the migrations
> required to land all of it cleanly.

---

## Problem

AEC today has three overlapping gaps that block the next wave of ambitious agent
workflows:

1. **Hooks are ad-hoc.** Skills and agents that need to run scripts on file edits,
   commits, or tool calls currently rely on one-off install paths like
   `_post_install_playwright_pipeline`. Each new hook use case requires Python plumbing
   inside AEC itself, and the resulting hooks aren't versioned, tracked, or easily
   removed. There's no way for a third-party skill to declare "I need a
   `PostToolUse` hook on `Edit|Write|MultiEdit`" without editing AEC.

2. **Agent configs are heterogeneous.** Claude Code uses `PostToolUse` in
   `.claude/settings.json`, Gemini CLI uses `AfterTool` in `.gemini/settings.json`,
   Cursor uses `afterFileEdit` in `.cursor/hooks.json`, and git uses
   `.git/hooks/pre-commit` shell files. A skill authored today has to either pick one
   and abandon users of the others, or duplicate itself across four formats.

3. **No deprecation story.** Items like the Anthropic-authored `docx`, `pdf`, `pptx`,
   and `xlsx` skills are now redundant (Claude handles those formats natively), but
   AEC has no way to signal "this item is deprecated" to users. They stay in listings
   indefinitely, get re-installed on new machines, and the only cleanup path is a hard
   delete that breaks anyone who still has them installed.

These three problems are tightly coupled: the first consumer of the new hook system
(verification-writer) also needs the rule→directory promotion, which needs Cursor
translation correctness, which exposes the deprecation gap. This spec treats them as
one coherent change.

---

## Solution

A four-part system, sequenced so each part produces something shippable on its own:

1. **`hooks.json` schema** — a single generic-plus-per-agent-override contract that
   any item can ship. AEC translates to the target agent's native format at install
   time.
2. **Hook lifecycle** — install / upgrade / remove / diff / repair, with per-repo
   state in `.aec/installed-hooks.json`, content-fingerprint drift detection, and
   strict adherence to AEC's "never auto-install" principle.
3. **Deprecation + orphan system** — first-class `deprecated:` frontmatter, listing
   badges, install-time guardrails, and an `aec prune` command that cleans up
   deprecated and orphaned items (and their hooks) interactively.
4. **Cursor translation + rule-directory promotion** — a prerequisite audit, a
   one-time git-archaeology migration to recover original `.mdc` frontmatter, and
   version-driven migration from flat `my-rule.md` to `my-rule/rule.md + hooks.json`
   directory form.

---

## Core Principles

1. **Never auto-install.** Every hook install, upgrade, and prune is user-prompted
   with tiered options. Consistent with AEC's existing core principle.

2. **Agent-agnostic by default.** A hook author writes one generic hook entry; AEC
   translates to Claude, Gemini, Cursor, and git as appropriate. Per-agent overrides
   exist for specialized cases but are the exception, not the rule.

3. **Versioned alongside the item.** A skill at version 1.2.0 ships hooks at version
   1.2.0. There is no separate hook version. Users upgrading the item upgrade the
   hooks.

4. **Per-repo state, content-addressed.** Hook installation state lives in
   `.aec/installed-hooks.json`. We match installed hooks to source hooks by
   content fingerprint (SHA-256 of canonical form), not by inline `_aec` tags in
   agent configs. This keeps Claude/Gemini/Cursor configs clean and diff-friendly.

5. **Scope-aware script resolution.** Skills installed at the project scope resolve
   scripts from the project install path; globally-installed skills resolve from
   `~/.claude/skills/...`. Mismatch fails loudly at install time.

6. **Deprecation is a state, not a deletion.** Deprecated items stay discoverable,
   installable (with warnings), and uninstallable. Hard deletion happens only after
   a `remove_after` date passes and users have been given multiple migration
   windows.

---

## Section 1 — `hooks.json` Schema

Located at the root of any item directory that ships hooks. For file-form rules,
this requires promoting to directory form (see Section 5).

```jsonc
{
  "$schema": "https://bernierllc.io/schemas/aec-hooks-v1.json",
  "version": "1.2.0",
  "hooks": [
    {
      "id": "verify-sync-check",
      "event": "on_file_edit",
      "match": "**/*.{ts,tsx,py}",
      "command": "aec run-script verification-writer check.sh",
      "description": "Warn if edited files have stale verification doc references",
      "blocking": false,
      "timeout_ms": 5000,
      "when": { "repo_has_any": ["pyproject.toml", "setup.py"] }
    }
  ],
  "claude": [],
  "cursor": [],
  "gemini": [],
  "git": []
}
```

### 1.1 Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `$schema` | string | yes | Locks the file to a versioned schema URL |
| `version` | semver string | yes | Must match the item's frontmatter version |
| `hooks` | array of GenericHook | yes (may be empty) | Primary authoring surface |
| `claude` / `cursor` / `gemini` / `git` | array of AgentHook | no | Per-agent overrides for specialized cases |

### 1.2 GenericHook fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Unique within this `hooks.json`. Kebab-case. Used as the fingerprint anchor |
| `event` | enum | yes | See event vocabulary below |
| `match` | string | no | Glob pattern; semantics depend on event |
| `command` | string | yes | Shell command. Recommended form: `aec run-script <item> <script>` |
| `description` | string | yes | One-line human-readable purpose |
| `blocking` | boolean | no, default `false` | Whether a non-zero exit blocks the action |
| `timeout_ms` | integer | no, default `5000` | Per-hook timeout |
| `when` | Predicate | no | Per-project conditional install (see 1.4) |

### 1.3 Generic event vocabulary and translation

| Generic | Claude Code | Gemini CLI | Cursor | Git |
|---|---|---|---|---|
| `on_file_edit` | `PostToolUse` + matcher `Edit\|Write\|MultiEdit` | `AfterTool` + matcher `write_file\|replace` | `afterFileEdit` | — |
| `on_file_read` | `PostToolUse` + matcher `Read` | `AfterTool` + matcher `read_file` | — | — |
| `pre_tool_use` | `PreToolUse` | `BeforeTool` | — | — |
| `session_start` | `SessionStart` | `SessionStart` | — | — |
| `pre_commit` | — | — | — | `pre-commit` |
| `pre_push` | — | — | — | `pre-push` |

Events that map to no target for a given agent are silently skipped for that agent
(e.g. `pre_commit` produces nothing under `.claude/settings.json`).

### 1.4 `when` predicate — per-project conditional install

Evaluated at install time and re-evaluated on upgrade. Minimal v1 field set:

| Field | Semantics |
|---|---|
| `repo_has` | List of paths; all must exist relative to repo root |
| `repo_has_any` | List of paths; any must exist |
| `repo_lacks` | List of paths; none may exist |
| `custom_check` | Shell command; install if exit 0 |

If the predicate evaluates false, the hook is recorded in state as "skipped" with
the reason, and not written to any agent config. On upgrade, if the predicate now
evaluates true, the user is prompted as a normal install.

### 1.5 Per-agent override arrays

The `claude` / `cursor` / `gemini` / `git` top-level arrays accept fully-formed
agent-native entries, bypassing translation. Used for hooks that cannot be
expressed in the generic vocabulary (e.g., a Claude `SubagentStop` hook). These
are installed verbatim, fingerprinted on their canonical form, and subject to the
same lifecycle.

### 1.6 Validation rules (enforced by `aec hooks validate`)

- `version` MUST match the item frontmatter's `version`.
- `id` MUST be unique within the file, across `hooks` + all per-agent arrays.
- `event` MUST be in the vocabulary.
- `command` MUST be non-empty. If it begins with `aec run-script <item> `, the
  script file MUST exist under `<item>/scripts/` at install time (validation is
  deferred to install, not to the validator pass).
- `when.custom_check` MUST NOT contain newlines.
- `git`-array hooks MUST target a recognized git hook name.
- If a per-agent override (1.5) targets an event that has a generic equivalent
  (e.g., a `claude` override expressing what `on_file_edit` would translate to),
  the validator emits a **warning** (not an error) recommending the generic form.
  This catches accidental duplication but does not block authors who have a real
  need for agent-specific nuance.

### 1.7 Git hook install format

Git hooks are shell files, not JSON. AEC writes delimited blocks so multiple items
can coexist in a single `pre-commit` or `pre-push`:

```bash
#!/usr/bin/env bash
# >>> AEC:BEGIN item=skill:verification-writer hook_id=verify-post-push version=1.3.0
aec run-script verification-writer regenerate.sh
# <<< AEC:END
```

Install is idempotent: the installer scans for matching `AEC:BEGIN`/`AEC:END` pairs
and replaces or appends. Non-AEC content outside these blocks is preserved.

---

## Section 2 — AEC's Translation & Install Layer

### 2.1 Library organization

```
aec/lib/hooks/
  __init__.py
  schema.py       # HooksFile, GenericHook, AgentOverride dataclasses; load_hooks_file(path)
  validator.py    # validate_hooks_file(HooksFile) -> list[ValidationError]
  translator.py   # translate_to_agent(HooksFile, agent, resolved_paths) -> list[AgentHook]
  installer.py    # install_item_hooks(item, repo_root, agents)
  state.py        # RepoHookState read/write (.aec/installed-hooks.json)
  scope.py        # Script path resolution (project-first, then global)
```

The existing `aec/lib/hooks.py` (which generates lint/type-check hooks) remains
untouched during Phase 1. In **Phase 2**, its logic is absorbed into
`installer.py` and the old module is deleted. Phase 2 exit includes confirming
`aec/lib/hooks.py` no longer exists and no callers reference it.

### 2.2 Scope-aware script resolution

When a `command` references `aec run-script <item> <script>`:

1. If the item is installed at **project scope**, resolve from the project install
   path (e.g., `.claude/skills/<item>/scripts/<script>`).
2. If the item is installed at **global scope**, resolve from the global install
   path (e.g., `~/.claude/skills/<item>/scripts/<script>`).
3. If neither path resolves, fail loudly at install time. Never silently fall back.

The resolved absolute path is recorded in `.aec/installed-hooks.json` as
`resolved_command` and `resolved_scope`. Upgrades re-resolve.

### 2.3 Validator / pre-push guard in AEC repo

AEC ships its own `pre-push` hook that runs `aec hooks validate` against every
`hooks.json` in the repo and rejects the push on schema errors, id clashes, or
version mismatches. This catches author mistakes before they land in users' hands.

---

## Section 3 — Hook Lifecycle

### 3.1 State file — `.aec/installed-hooks.json`

```jsonc
{
  "schema_version": 1,
  "items": {
    "skill:verification-writer": {
      "item_version": "1.2.0",
      "hooks_file_hash": "sha256:...",
      "installed_at": "2026-04-20T14:22:00Z",
      "agents_targeted": ["claude", "git"],
      "hooks_installed": [
        {
          "source_hook_id": "verify-sync-check",
          "target_agent": "claude",
          "target_config_path": ".claude/settings.json",
          "target_json_pointer": "/hooks/PostToolUse",
          "content_fingerprint": "sha256:a3f9...",
          "installed_command": "aec run-script verification-writer check.sh",
          "resolved_command": "/abs/path/to/.claude/skills/verification-writer/scripts/check.sh",
          "resolved_scope": "project",
          "source_item_scope": "project",
          "when_result": "applied"
        }
      ],
      "hooks_skipped": [
        {
          "source_hook_id": "...",
          "reason": "when.repo_has_any not satisfied",
          "evaluated_at": "2026-04-20T14:22:00Z"
        }
      ]
    }
  }
}
```

**Field placement:** `hooks_file_hash`, `item_version`, `installed_at`, and
`agents_targeted` are per-item-level metadata. `hooks_installed` and
`hooks_skipped` are arrays of per-hook state within that item.

**`hooks_skipped` lifecycle:** Recomputed on every upgrade. If a `when` predicate
that previously evaluated false now evaluates true, the entry moves from
`hooks_skipped` to `hooks_installed` via the normal install prompt. If previously
true now false, the entry moves from `hooks_installed` to `hooks_skipped` after
uninstalling the hook from the target config.

### 3.2 Drift detection

On every `aec upgrade` or `aec doctor` run:

1. Load source `hooks.json`. Compute `hooks_file_hash`. If unchanged vs state, skip.
2. For each installed hook, locate the entry in the agent config by
   `target_config_path` + `target_json_pointer` + `content_fingerprint`. If not
   found → **drift** (user modified config manually). Report in `aec doctor`; offer
   `aec hooks repair` to reinstall.
3. For each source hook, translate to agent form and compute fingerprint. If
   fingerprint differs from installed → **upgrade available**. Prompt with tiered
   options (see 3.3).

### 3.3 Tiered upgrade prompt

Consistent with the CLI option pattern already established in AEC:

```
verification-writer 1.1.0 → 1.2.0 — hooks changed:
  + verify-post-push (new, git:pre-push)
  ~ verify-sync-check (updated: timeout 3000 → 5000)

Apply? [Y/n/d/s/v]
  Y = apply all
  n = skip this upgrade
  d = show diff
  s = skip this version permanently (aec hooks skip-version ...)
  v = apply per-hook, one at a time
```

**Per-hook loop behavior (`v`):** AEC iterates over the changed hooks in
declared order. Each hook gets its own `[y/n/d/q]` prompt (`q` = abort the
remaining loop; already-decided hooks are committed, pending ones are left
at their pre-upgrade state). The upgrade is recorded in state only after the
loop completes (or is aborted with `q`), so a partial loop still produces a
consistent `.aec/installed-hooks.json`.

### 3.4 CLI surface

```
aec hooks list [--item <id>] [--agent <name>]
aec hooks validate [<path>]
aec hooks install <item>
aec hooks upgrade [<item>] [--force]
aec hooks remove <item>
aec hooks diff <item>
aec hooks repair <item>
aec hooks skip-version <item> <version>
aec run-script <item> <script>
```

`aec hooks skip-version` records the skipped version in state so the upgrade prompt
doesn't re-fire until a newer version is published.

---

## Section 4 — Skill-ships-scripts Contract (AEC-side only)

AEC does not prescribe what scripts do internally. It only defines how skills
ship and invoke them.

### 4.1 Script directory layout

```
<item>/
  SKILL.md (or rule.md, AGENT.md)
  hooks.json
  scripts/
    check.sh
    regenerate.sh
```

Scripts must:
- Be executable on POSIX systems (AEC's validator checks the executable bit at
  install time on macOS/Linux). On Windows, AEC checks for a shebang line
  (`#!/usr/bin/env bash` or similar) and resolves execution through the
  appropriate interpreter (bash via Git for Windows, `py` for Python scripts).
- Be referenced from `hooks.json` via `aec run-script <item> <script>`.
- Exit 0 for success, non-zero for failure. `blocking: true` hooks propagate the
  exit code; `blocking: false` hooks log the failure and continue.

### 4.2 `aec run-script`

```
aec run-script <item> <script> [args...]
```

Resolves the item install path (scope-aware per 2.2), executes the script with the
resolved absolute path, passes through args and stdin/stdout/stderr. This
indirection lets us change install paths, sandbox in the future, or instrument
without rewriting every skill's `hooks.json`.

### 4.3 What AEC does NOT define

- What individual skills' scripts do internally (e.g., verification-writer's
  behavior, its JSON report schema, its sub-agent orchestration). Those live in
  the skill's own SKILL.md.
- Chained skill invocations (e.g., verification-writer → playwright-test-generator).
  Those are a skill-level concern.
- Any built-in command like `aec verify-docs`. Doc verification is a skill
  behavior, invoked via hooks, not an AEC feature.

---

## Section 5 — Rules Promotion to Directory Format

### 5.1 Two rule shapes

**Flat:**
```
rules/testing-standards.md
```

**Directory:**
```
rules/testing-standards/
  rule.md
  hooks.json
  scripts/
    ...
```

The rule loader accepts both. Directory form is required for any rule that ships
hooks, scripts, or multi-file assets.

### 5.2 Version-driven migration

When a rule needs to move from flat to directory form:

1. Bump the rule's version (e.g., 1.1.0 → 1.2.0) in frontmatter.
2. Create the directory, move the old file to `rule.md`, add `hooks.json`.
3. On `aec upgrade`, AEC sees the version bump, uninstalls the flat form (removing
   `rules/testing-standards.md`), installs the directory form.

Because the migration is tied to a version change, the two shapes never need to
coexist in an installed state.

**AEC version gate:** Directory-form rules require AEC ≥ the version that lands
Phase 5. Older AEC installs encountering a directory-form rule source will fail
upgrade with a clear error directing the user to update AEC first. This is
handled by AEC's existing self-upgrade path and does not require special
handling here.

### 5.3 Collision safety net

`aec doctor` warns if both `rules/<name>.md` and `rules/<name>/rule.md` are present
in an installed location. Prompts the user to choose one; removes the other. This
catches the rare case where migration was interrupted or a user manually copied a
file.

### 5.4 Cursor translation prerequisite

Rules translate to Cursor `.mdc` format on install. This was partially broken
before and is addressed by Section 4 of this spec's migration plan (Phase 4 in
the ordering). Every rule — flat or directory — MUST have agent-namespaced
frontmatter by the time Phase 5 lands.

---

## Section 6 — Deprecated Skill Removal (Soft-Deprecate Path)

### 6.1 Deprecation frontmatter schema

Any item can declare itself deprecated via a frontmatter block:

```yaml
---
name: docx
version: 2.0.0
deprecated:
  since: "2.0.0"
  reason: "Claude now handles .docx creation/editing natively — use Claude's built-in tools."
  replacement: null
  remove_after: "2026-10-01"
---
```

| Field | Semantics |
|---|---|
| `since` | Version in which deprecation was declared |
| `reason` | User-facing sentence explaining why |
| `replacement` | Item name (e.g., `gdocs`) or `null` if no replacement |
| `remove_after` | ISO date after which the item may be hard-deleted from sources |

**Hard-delete trigger is out of scope for this spec.** Hard deletion is a
manual, per-release decision made by a maintainer reviewing items past their
`remove_after` date. It is not automated by AEC, a CI job, or a timed trigger.
This keeps the deprecation window explicit and human-reviewed.

### 6.2 Two states: deprecated vs orphaned

| State | Definition | UX |
|---|---|---|
| **Deprecated** | Source declares `deprecated:`. Item still exists in catalog. | Listed with ⚠ badge + reason. Installable with warning. `aec prune` offers removal. |
| **Orphaned** | Installed locally, but source no longer exists in the catalog (e.g., hard-deleted). | Listed with ✗ badge. Not re-installable. `aec prune` offers removal. |

### 6.3 Listing UX

```
$ aec list
Skills:
  ✓ gdocs                        1.3.0
  ⚠ docx                         2.0.0   deprecated since 2.0.0 — Claude handles natively
  ✓ verification-writer          1.2.0
  ✗ old-skill                    —       orphaned (source not found)

$ aec list --only deprecated
⚠ docx                         2.0.0   deprecated since 2.0.0 — Claude handles natively
⚠ pdf                          2.0.0   deprecated since 2.0.0 — Claude handles natively
...

$ aec list --hide-deprecated
Skills:
  ✓ gdocs                        1.3.0
  ✓ verification-writer          1.2.0
```

### 6.4 Install-time guardrail

```
$ aec install docx
⚠ docx is deprecated since 2.0.0:
    Claude now handles .docx creation/editing natively — use Claude's built-in tools.
  No replacement available.
  Scheduled for removal after 2026-10-01.

Install anyway? [y/N]
```

### 6.5 `aec prune`

Interactive cleanup across all installed item types (agents, skills, rules,
packages, plugins):

```
$ aec prune
Found 3 items that can be cleaned up:

  ⚠ skill:docx (deprecated)
      Reason: Claude now handles .docx creation/editing natively.
      Installed: 2025-11-04    Replacement: none
      Remove? [Y/n/s]

  ⚠ skill:pdf (deprecated) ...

  ✗ rule:old-testing-rule (orphaned)
      Source no longer exists in catalog.
      Remove? [Y/n/s]

Summary: 2 removed, 1 skipped.
Associated hooks uninstalled: 4
```

When an item is pruned, its hooks are uninstalled via the Section 2 uninstall
path. No dangling hook entries in `.claude/settings.json` etc.

### 6.6 Targets for first use

Phase 6 soft-deprecates these Anthropic-authored skills in `bernierllc/claude-skills`:

- `docx` — Claude native support
- `pdf` — Claude native support
- `pptx` — Claude native support
- `xlsx` — Claude native support

`gdocs` and `gslides` (Bernier LLC-authored) are retained.

---

## Section 7 — Documentation Updates

### 7.1 Anti-duplication strategy

- **AEC repo** owns canonical, deep documentation for hooks, deprecation, Cursor
  translation, and CLI reference.
- **Submodule READMEs** carry a brief "AEC-aware" section at the top linking back
  to the canonical AEC docs, plus submodule-specific content (fork origin,
  versioning conventions, CHANGELOG).
- No prose is duplicated across repos. Submodule docs link to AEC docs for shared
  concepts.

### 7.2 Skills submodule (`bernierllc/claude-skills`)

| Doc | Change |
|---|---|
| `README.md` | Add "AEC-aware" link at top. Add hooks.json and deprecation sections. Add fork-origin explanation (why we forked `anthropics/skills`). |
| `CLAUDE.md` | Expand full frontmatter schema — including `version`, `deprecated:`, `hooks` integration hook. |
| `CONTRIBUTING.md` | Document versioning rules, frontmatter requirements, hooks.json authoring, deprecation workflow. |
| `CHANGELOG.md` (new) | Keep-a-Changelog format. Seeded from git log for versioning history. |
| `.github/workflows/lint-skills.yml` (new) | CI check: validate frontmatter, hooks.json schema, version bumps on PR. |
| `scripts/hooks/pre-push` (new) | Local pre-push hook to run the same validator. |
| `scripts/install-hooks.sh` (new) | One-shot install of the pre-push hook into a local clone. |

### 7.3 Agents submodule (`bernierllc/agency-agents`)

| Doc | Change |
|---|---|
| `README.md` | Add "AEC-aware" link at top. Hooks section (brief). |
| `CLAUDE.md` | Add hooks.json and deprecation-aware authoring conventions. |
| `.github/workflows/lint-agents.yml` | Extend to validate hooks.json if present. |
| `scripts/hooks/pre-push` (extend existing or new) | Run agent frontmatter + hooks.json validator. |

### 7.4 AEC repo

| Doc | Change |
|---|---|
| `docs/hooks.md` (new, canonical) | Full hook authoring guide: schema, event vocabulary, `when` predicates, script conventions, translation table, state file, lifecycle. |
| `docs/deprecation.md` (new) | Deprecation workflow, frontmatter schema, prune UX, timelines. |
| `docs/cursor-rule-translation.md` (new) | How AEC translates rules to `.mdc`, frontmatter schema, heuristic fallback, migration history. |
| `docs/cli.md` | Add all new `aec hooks *` commands + `aec prune` + `aec run-script`. |
| `README.md` | Top-level blurb pointing at hooks + deprecation docs. |
| `AGENTINFO.md` | Add hooks + deprecation to project-specific standards. |
| `CLAUDE.md` / `GEMINI.md` / `QWEN.md` / `AGENTS.md` | Sync via `scripts/generate-agent-files.py`. |

### 7.5 Cross-repo link convention

Each submodule README opens with:

```markdown
> **AEC-aware:** This repo is managed alongside
> [agents-environment-config](https://github.com/bernierllc/agents-environment-config).
> For hook authoring, deprecation workflow, and versioning conventions, see
> [AEC docs/hooks.md](https://github.com/bernierllc/agents-environment-config/blob/main/docs/hooks.md)
> and [AEC docs/deprecation.md](https://github.com/bernierllc/agents-environment-config/blob/main/docs/deprecation.md).
```

### 7.6 What is NOT documented here

- verification-writer's internal JSON report schema, sub-agent orchestration, or
  chained skill behavior. Those live in the skill's own `SKILL.md`.
- Playwright test generator chain. Skill-level concern.

### 7.7 Documentation deliverables

17 items, grouped by repo and estimated effort (S/M/L):

| ID | Repo | Deliverable | Effort |
|---|---|---|---|
| D1 | aec | `docs/hooks.md` (canonical) | L |
| D2 | aec | `docs/deprecation.md` | M |
| D3 | aec | `docs/cursor-rule-translation.md` | S |
| D4 | aec | `docs/cli.md` updates | M |
| D5 | aec | `README.md` top-level link section | S |
| D6 | aec | `AGENTINFO.md` updates | S |
| D7 | aec | Sync CLAUDE/GEMINI/QWEN/AGENTS.md via generator | S |
| D8 | skills | `README.md` updates | M |
| D9 | skills | `CLAUDE.md` full schema expansion | L |
| D10 | skills | `CONTRIBUTING.md` rewrite | M |
| D11 | skills | `CHANGELOG.md` (new) | S |
| D12 | skills | `.github/workflows/lint-skills.yml` | M |
| D13 | skills | `pre-push` + `install-hooks.sh` | S |
| D14 | agents | `README.md` hooks section | S |
| D15 | agents | `CLAUDE.md` hooks/deprecation | S |
| D16 | agents | `lint-agents.yml` extension | S |
| D17 | agents | `pre-push` extension | S |

---

## Section 8 — Phasing & Order of Implementation

Each phase has a clean exit: AEC compiles, existing tests pass, no items appear
broken in `aec list`.

### 8.1 Phase overview

```
Phase 0 — Prerequisite audits (no code changes)
  ↓
Phase 1 — Hooks foundation (schema, validator, translator; no install yet)
  ↓
Phase 2 — Install / upgrade / remove lifecycle
  ↓
Phase 3 — Deprecation + orphan + aec prune
  ↓
Phase 4 — Cursor translation migration (git archaeology)
  ↓
Phase 5 — Rules file→directory promotion
  ↓
Phase 6 — First real consumers (verification-writer hooks; soft-deprecate docx/pdf/pptx/xlsx)
  ↓
Phase 7 — Documentation (D1–D17) and first-use migration prompts
```

### 8.2 Phase 0 — Prerequisite audits

Three audit docs under `docs/superpowers/audits/2026-04-21-*.md`:

1. **Cursor rule format audit.** Per-rule current state: is it `.mdc`? frontmatter
   present? agent-namespaced? Feeds Phase 4.
2. **Existing hook-like side effects audit.** Grep `_post_install_playwright_pipeline`
   and similar one-offs. List everything that will be replaced by
   `_install_item_hooks`.
3. **Deprecation candidates audit.** Confirm docx/pdf/pptx/xlsx are the only
   near-term candidates.

**Exit:** three audit docs written, no code changes.

### 8.3 Phase 1 — Hooks foundation (library only)

Build under `aec/lib/hooks/`:
- `schema.py`, `validator.py`, `translator.py`, `scope.py`
- Unit tests for each (pure functions, no I/O)
- CLI: `aec hooks validate <path>` works against a hand-crafted `hooks.json`

Existing `aec/lib/hooks.py` (lint/type-check generator) untouched.

**Exit:** validator works end-to-end. No install behavior yet.

### 8.4 Phase 2 — Install / upgrade / remove lifecycle

- `installer.py` — idempotent writes to all four agent targets
- `state.py` — `.aec/installed-hooks.json` with content fingerprints
- Upgrade detection with tiered prompts
- Integration into `aec install` / `aec upgrade`
- New CLI: `aec hooks list | install | upgrade | remove | diff | repair | skip-version`
- Generalize `_post_install_playwright_pipeline` → `_install_item_hooks`

**Exit:** hand-crafted test skill with `hooks.json` installs/upgrades/removes
cleanly across Claude/Gemini/Cursor/git.

### 8.5 Phase 3 — Deprecation + orphan + prune

Built before any real item is soft-deprecated, so we can dogfood on fixtures:

- Parse `deprecated:` frontmatter
- Listing badges + `--only deprecated` / `--only orphaned` / `--hide-deprecated`
- `aec prune` — interactive, per-item, associated hooks removed
- Install-time deprecation warning

**Exit:** fixture skill with `deprecated:` shows badge, installs with warning,
`aec prune` removes cleanly including hooks.

### 8.6 Phase 4 — Cursor translation migration

Uses Phase 0.1 audit.

- `scripts/migrate-cursor-rules.py`:
  - For each rule missing Cursor frontmatter: `git log --all --follow -p -- <path>`
    to find last `.mdc` variant in history
  - If found: lift `description`/`globs`/`alwaysApply` into agent-namespaced
    `cursor:` block
  - If not found: heuristic guess + flag `# AEC: heuristic-inferred, needs review`
  - Output migration report at `docs/superpowers/audits/cursor-migration-report.md`
- Update rule loader to produce `.mdc` with proper frontmatter on install

**Exit:** every rule has explicit or heuristic-flagged Cursor frontmatter.
`aec install` produces correct `.mdc` in a test project.

### 8.7 Phase 5 — Rules file→directory promotion

- Rule loader accepts both shapes
- Version-driven migration path (uninstall old form, install new form)
- `aec doctor` warns on ambiguous (both forms present)

**Exit:** test rule can be promoted with hooks, upgrade is collision-free.

### 8.8 Phase 6 — First real consumers

- Write `verification-writer` `hooks.json` with `scripts/check.sh` (version bump)
- Soft-deprecate `docx`, `pdf`, `pptx`, `xlsx` in claude-skills submodule
  (version bump each, add `deprecated:` frontmatter)
- End-to-end validation in scratch repo: install → see deprecated badges →
  prune → confirm hooks install/upgrade/remove cleanly

**Exit:** real production skills consuming the new system. First real prune run.

### 8.9 Phase 7 — Documentation + first-use UX

- Land D1–D17 per 7.7
- First-use migration prompt: repo has existing hooks but no
  `.aec/installed-hooks.json` → offer to adopt via fingerprint matching, or leave
  alone
- `aec doctor` extensions: orphaned hook detection, fingerprint drift,
  deprecated-installed report
- Sync CLAUDE.md / GEMINI.md / QWEN.md / AGENTS.md via `generate-agent-files.py`

**Exit:** docs complete and cross-linked. First-use prompt tested against a repo
with pre-existing Claude hooks.

### 8.10 Order dependencies

```
0.1 ──► 4 ──► 5 ──► 6
0.2 ──► 2
0.3 ──► 3 ──► 6
1   ──► 2 ──► 3 ──► 6
6   ──► 7
```

**Parallelizable vs serial:**
- Phase 0's three audits (0.1, 0.2, 0.3) can run fully in parallel — they
  produce independent output docs.
- Phase 1 (hooks foundation library) and Phase 4 (Cursor translation migration)
  can proceed in parallel once Phase 0 completes. They touch disjoint code
  paths: hooks library vs rule loader.
- Phases 2, 3, 5 are serial per the dependency graph. Each depends on the
  previous phase's output being merged and tested.
- Phase 6 is a hard synchronization point — it needs all of 2, 3, 5 merged
  before it can proceed.
- Phase 7 documentation work (D1–D17) can be split across parallel agents, but
  per the project's parallel-agent coordination rules, assignments must split
  by file ownership (one agent owns each specific doc) rather than by topic
  area, since topic areas share cross-cutting edits to `cli.md` and agent
  instruction files.

### 8.11 Out of scope (explicit)

- `aec run-script` sandboxing / capability model beyond "exit code + stderr
  surfaces to user." Future spec if we ever accept third-party authored hooks.
- Multi-repo global hook registry. Hooks are per-item-per-repo.
- Retroactive migration of hooks already installed by
  `_post_install_playwright_pipeline`. Handled by Phase 7 first-use prompt.

### 8.12 Testing posture per phase

| Phase | Strategy |
|---|---|
| 1 | Unit tests (schema/validator/translator as pure functions) |
| 2 | Integration tests with temp repo fixtures; real filesystem writes |
| 3 | Integration tests against fixtures with `deprecated:` frontmatter; snapshot `aec list` |
| 4 | Fixture repo with frontmatter-less `.md` rules + pre-seeded git history; assert recovery |
| 5 | Fixture: flat → dir-form migration; assert cleanliness |
| 6 | Manual end-to-end in scratch repo + CI smoke tests |
| 7 | Docs: broken-link lint; first-use prompt unit-tested via mocked prompt |

Per global testing rules: do NOT mock the database or internal AEC APIs — those
use real instances and real HTTP/filesystem calls. Only Claude Code / Gemini /
Cursor *runtimes* are mocked (we don't spawn them in CI); the config files they
read, we write and read for real.

---

## Decisions Embedded in This Spec

| ID | Decision | Alternative | Rationale |
|---|---|---|---|
| D1 | Phase 6 ships deprecation + verification-writer hooks together | Hooks-only first, deprecation follow-up | Clean one-release story; both are independent but low-risk; docs narrative is simpler |
| D2 | Phase 0 audit docs live in-repo under `docs/superpowers/audits/` | Scratch files, delete after use | Justify future "heuristic-inferred" flags; historical record of migration reasoning |
| D3 | Content-fingerprint matching, not inline `_aec` tags in agent configs | Inline sidecar fields in each hook entry | Keeps agent configs clean, diff-friendly, and resilient to strict schema validators |
| D4 | Git hook blocks use delimited `# >>> AEC:BEGIN ... # <<< AEC:END` comments | Shell-native solutions per hook | Idempotent multi-item coexistence in a single shell file; no token-overhead concern since shell files aren't loaded into model context |
| D5 | Version-driven file→directory migration, no ad-hoc coexistence | Run both forms side-by-side during transition | Tied to the item's own version semantics; uninstall old + install new is atomic |
| D6 | Soft-deprecation for docx/pdf/pptx/xlsx rather than hard delete | Immediate removal from catalog | Exercises the new deprecation feature on real targets; gives installed users a clean migration window |
| D7 | `when.custom_check` accepts any single-line shell command | Restrict to a DSL of allowed predicates | Matches author expectations from other hook systems; single-line constraint (per 1.6) prevents most pitfalls; documented with examples and warnings |

---

## Success Criteria

- A new skill author can add `hooks.json` to their skill and have it work across
  Claude Code, Gemini CLI, Cursor, and git without touching AEC source.
- A user running `aec upgrade` against an older hooks-using skill sees a clear
  diff and a Y/n/d/s/v tiered prompt; skipping one upgrade never nags again at
  the same version.
- `aec prune` cleanly removes deprecated skills + their hooks with no dangling
  state in `.claude/settings.json` or elsewhere.
- Every rule in both submodules either has explicit Cursor frontmatter or is
  flagged `# AEC: heuristic-inferred, needs review` for follow-up.
- A first-time AEC user in a repo with existing hooks gets a one-time prompt to
  adopt or ignore them — no silent corruption of their setup.
- Documentation is canonical in AEC, linked from submodules; no duplicated prose.

---

## Open Questions

1. Should `aec hooks skip-version` persist across repo clones (via
   `.aec/installed-hooks.json`) or user-global (`~/.agents-environment-config/`)?
   Proposal: **per-repo**, since the decision is repo-specific.
2. Do we want a `deprecated` field on individual *hooks* (not just items), for
   cases where an item remains supported but a specific hook is retired?
   Proposal: **defer to v2** of the hooks schema.
