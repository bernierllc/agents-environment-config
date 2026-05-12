# AEC Agent Blurb — Design Spec

**Date:** 2026-05-12
**Status:** Draft — pending spec review and user approval
**Owner:** Matt Bernier

---

## 1. Summary

Add a feature to AEC that, on install/update or via a dedicated `aec configure-agent` subcommand, writes a versioned, machine-readable instruction block ("the blurb") into the user's agent files (Claude, Cursor, Gemini, Qwen, Codex, etc.). The blurb teaches the agent what AEC is, which AEC operations it may execute autonomously, and which require explicit user permission. This closes the loop so agents can manage their own AEC-tracked items as part of their normal workflow without overstepping.

## 2. Goals & Non-Goals

### Goals

1. Agents that detect missing or outdated AEC-managed items (agents, skills, rules, packages, plugins) can self-remediate by calling `aec` directly instead of stopping to ask the user about every small operation.
2. User optionality is preserved end-to-end: no blurb is written without explicit Y/n consent; no blurb is silently updated.
3. Version + content-hash discipline mirrors how AEC tracks other managed items, so drift between shipped template, last-installed copy, and current on-disk content is always detectable.
4. Parallel-agent-safe: one concern per file; the on-disk source of truth is a single JSON file per scope.
5. Allow/deny scope is bounded by a small, well-known preset profile system with per-item-type overrides. Destructive operations always require asking.

### Non-Goals

- **Not a sandbox.** This is an *instruction* layer, not an *enforcement* layer. Agents that ignore the blurb are not blocked at the system level. Enforcement is a separate concern that can build on top of this.
- **Not per-command granularity.** The user does not configure individual AEC subcommands. They pick a preset profile, optionally tweak per-item-type, and AEC maps that to commands.
- **Not retroactive.** The blurb governs future agent behavior only.
- **Not an MCP server, hook, or runtime intercept.** Pure document write.

## 3. User-Facing Flow

### 3.1 Trigger points

There are two entry points, both gated by user consent:

1. **Install / update prompt** — `aec install` and `aec update` check whether a blurb is present in detected agent files. If missing or out-of-date (see §6 drift detection), AEC prompts:
   > "AEC can add instructions to your agent files so your agent can use AEC as part of its workflow. Add it now? [Y/n]"
2. **Dedicated subcommand** — `aec configure-agent` is the canonical entry point for first-time setup, re-targeting scope, switching profile, or refreshing after AEC version bumps. Subcommands:
   - `aec configure-agent` — interactive setup or update
   - `aec configure-agent --check` — exits non-zero if any selected scope's blurb is stale or drifted (CI-friendly)
   - `aec configure-agent --refresh` — non-interactive: re-render all selected scopes from current config
   - `aec configure-agent --remove` — interactive removal (also prompts per-scope)

### 3.2 Scope prompt (always asked)

When the user accepts the offer, AEC asks two explicit questions every time, regardless of context:

```
You are running within project context. Confirm where to install the blurb:
  [ ] project context
  [ ] global context
(Select one or both; default = [x] project context if run inside a repo, else [x] global)

Which agent files should receive the blurb?
  ( ) All detected agent files
  ( ) Let me choose
```

If "Let me choose" is selected, AEC presents a checklist of detected agent files (e.g., `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md`, `.cursor/rules/*.mdc`, `~/.codex/instructions.md`) with all pre-selected; user toggles individual entries.

If neither scope is selected, AEC exits without writing (treated as decline).

### 3.3 Profile prompt

```
Choose an allow/deny profile:
  ( ) conservative — read-only auto; everything else asks
  (x) balanced    — read-only auto, additive auto for skills/rules; agents/packages/plugins ask; destructive always asks
  ( ) permissive  — read-only + additive auto for all item types; destructive always asks
  ( ) custom      — pick per item type
```

`custom` opens the 5-toggle matrix (one toggle per item type: additive auto vs. additive ask-first). Read-only is always auto; destructive is always ask-first; these are not user-configurable.

When both `project` and `global` scopes are selected in §3.2, the profile prompt (and `custom` matrix prompt, if chosen) runs **once per selected scope**. Profile and matrix may differ between scopes.

### 3.4 Confirmation summary

Before writing, AEC prints a summary:

```
About to write blurb to:
  • ./CLAUDE.md         (project scope, balanced profile)
  • ./AGENTS.md         (project scope, balanced profile)
  • ~/.claude/CLAUDE.md (global scope, conservative profile)

Proceed? [Y/n]
```

(Scope and profile can differ between project and global. The user picks once per scope.)

## 4. Blurb Structure

The blurb is a delimited block inserted into each target agent file. Surrounding user content is never modified.

### 4.1 Delimiters

```markdown
<!-- aec-blurb:start v1 schema=1 aec=2.37.4 template-hash=<sha256-16> content-hash=<sha256-16> profile=balanced scope=project -->
## AEC — Agent Environment Config

(prose framing — what AEC is, where to read docs, how to invoke it)

### Operations you may run without asking

- `aec list <type>` — list installed items
- `aec status` — show drift / version info
- `aec doctor` — diagnose configuration
- `aec add skill <name>` — install a skill   (balanced: skills additive = auto)
- `aec add rule <name>`  — install a rule    (balanced: rules additive = auto)
- … (generated from profile)

### Operations that require explicit user permission

- `aec add agent <name>`   (balanced: agents additive = ask-first)
- `aec add package <name>` (balanced: packages additive = ask-first)
- `aec add plugin <name>`  (balanced: plugins additive = ask-first)
- `aec remove <anything>`  (destructive — always ask)
- `aec update`             (mutates AEC itself — always ask)
- … (generated from profile)

### How to interpret this block

This block is managed by AEC. Do not hand-edit between the start/end markers; use
`aec configure-agent` to change scope or profile. The `content-hash` is recomputed
on every render; if you must hand-edit, run `aec configure-agent --check` to see
the drift report and `--refresh` to re-render.

<!-- aec-blurb:end -->
```

### 4.2 Marker fields

| Field            | Purpose                                                   |
| ---------------- | --------------------------------------------------------- |
| `v1`             | Block format version (for future renames/restructures)    |
| `schema=N`       | Prose template schema version (bumps when prose changes)  |
| `aec=x.y.z`      | AEC version at write time (diagnostics)                   |
| `template-hash`  | SHA256 (first 16 hex) of the shipped template at write    |
| `content-hash`   | SHA256 (first 16 hex) of the rendered body actually written |
| `profile`        | Profile name (or `custom`)                                |
| `scope`          | `project` or `global`                                     |

### 4.3 Rendering

Rendering is deterministic from `(profile/matrix, scope, AEC version, shipped template)`. Re-rendering with identical inputs produces byte-identical output (sorted keys, fixed timestamp-free header). This makes idempotency trivially testable.

## 5. Source of Truth & Persistence

The agent file is a **render target**, not a config store. The source of truth is a separate JSON file per scope.

### 5.1 File layout

```
Project scope:
  <repo>/.aec/agent-blurb.json

Global scope:
  ~/.aec/agent-blurb.json

Decline state (separate, per "one concern per file"):
  Project: <repo>/.aec/agent-blurb-decline.json
  Global:  ~/.aec/agent-blurb-decline.json
```

### 5.2 JSON shape (v1)

```json
{
  "schema": 1,
  "aec_version_last_write": "2.37.4",
  "scope": "project",
  "profile": "balanced",
  "matrix": {
    "agents":   { "additive": "ask" },
    "skills":   { "additive": "auto" },
    "rules":    { "additive": "auto" },
    "packages": { "additive": "ask" },
    "plugins":  { "additive": "ask" }
  },
  "targets": [
    { "path": "CLAUDE.md", "template_hash": "ab12…", "content_hash": "cd34…", "written_at": "2026-05-12T14:03:00Z" },
    { "path": "AGENTS.md", "template_hash": "ab12…", "content_hash": "ef56…", "written_at": "2026-05-12T14:03:00Z" }
  ]
}
```

Read-only operations and destructive operations are **not** in the matrix — they are hard-coded constants in AEC and rendered into the blurb from there. The matrix governs only the `additive` axis per item type.

### 5.3 Why a separate file (D from brainstorm Q5)

- One concern per file → parallel-agent-safe per existing AEC pattern.
- Trivially diffable in PR review.
- Render is a pure function of JSON + AEC version + shipped templates.
- Manual blurb edits in agent files become detectable drift rather than silent state.

## 6. Versioning & Drift Detection

Three independent signals are stored per target:

1. **Template hash** — hash of the shipped template AEC used to render. Changes when AEC ships a new template.
2. **Content hash** — hash of what AEC actually wrote to disk. Changes when render inputs change (profile, matrix, scope, template, AEC version).
3. **AEC version at write** — for diagnostics and release-note correlation.

### 6.1 Drift states

For each target file, AEC computes four values at check time:
- `shipped_template_hash` — current AEC build
- `stored_template_hash` — `.aec/agent-blurb.json` → `targets[i].template_hash`
- `stored_content_hash` — `.aec/agent-blurb.json` → `targets[i].content_hash`
- `on_disk_content_hash` — hash of the body currently between the start/end markers in the agent file

| Condition                                              | State                | Action                                       |
| ------------------------------------------------------ | -------------------- | -------------------------------------------- |
| shipped == stored && stored == on_disk                 | **clean**            | no-op                                        |
| shipped != stored && stored == on_disk                 | **upstream update**  | offer refresh                                |
| shipped == stored && stored != on_disk                 | **manual edit**      | show diff; offer refresh-or-keep             |
| shipped != stored && stored != on_disk                 | **conflict**         | show both diffs; require explicit choice     |
| marker missing                                         | **not installed**    | offer initial install                        |

`aec configure-agent --check` exits non-zero on anything other than `clean` and `not installed` (when installation was never elected for that scope).

### 6.2 Refresh flow

`aec configure-agent --refresh`:
1. Reads `.aec/agent-blurb.json`.
2. Re-renders the blurb body from current profile/matrix + shipped template.
3. For each target: locates the start/end markers, replaces the block (atomically via temp-file + rename), updates `template_hash`, `content_hash`, `written_at` in the JSON.
4. If markers not found in a target that's listed in JSON, surfaces the discrepancy and skips that target.

## 7. Allow/Deny Model

### 7.1 Three classes (only one is user-configurable)

| Class       | Examples                                           | Configurable? |
| ----------- | -------------------------------------------------- | ------------- |
| Read-only   | `aec list`, `aec status`, `aec doctor`, `aec --help` | No — always auto |
| Additive    | `aec add <type> <name>`                            | **Yes — per item type** |
| Destructive | `aec remove`, `aec uninstall`, `aec update`, `aec reset`, `aec init` | No — always ask |

`aec init` is classified destructive because it scaffolds `.aec/` and can overwrite existing config; it is always ask-first regardless of profile.

`aec update` is classified destructive because it mutates AEC itself and can change the very contract this blurb describes.

### 7.2 Preset profiles

| Profile        | agents | skills | rules | packages | plugins |
| -------------- | ------ | ------ | ----- | -------- | ------- |
| `conservative` | ask    | ask    | ask   | ask      | ask     |
| `balanced` (default) | ask | auto | auto | ask      | ask     |
| `permissive`   | auto   | auto   | auto  | auto     | auto    |

`custom` lets the user pick per item type. Stored as both `profile` name and expanded `matrix` — on AEC upgrade, if the profile definition changes (e.g., a new item type is added), the user is prompted to re-confirm.

### 7.3 New item types

When AEC adds a new item type in a future release:
1. `aec update` detects that the stored matrix lacks the new type.
2. Prompts the user: "AEC now manages `<new-type>`. For each profile/scope, choose initial setting: auto / ask."
3. Updates JSON, re-renders, re-hashes.

## 8. CLI Surface

```
aec configure-agent                 # interactive: install or update
aec configure-agent --check         # CI mode: exit nonzero on drift
aec configure-agent --refresh       # non-interactive re-render
aec configure-agent --remove        # interactive removal
aec configure-agent --scope project|global|both
aec configure-agent --profile conservative|balanced|permissive|custom
aec configure-agent --agent-files all|<comma-list>
aec configure-agent --dry-run       # show planned writes, do not write
```

Integration points:
- `aec install` — if no blurb config exists, offer `configure-agent` flow inline.
- `aec update` — runs `--check`; if drift, offers `--refresh` inline.
- `aec doctor` — surfaces drift state in standard health output.

## 9. Edge Cases & Failure Modes

| Case                                                          | Handling |
| ------------------------------------------------------------- | -------- |
| Agent file does not exist                                     | Offer to create it; if declined, skip target. |
| Start marker present, end marker missing (or vice versa)      | Refuse to write; report corruption; suggest manual cleanup or `--remove` then re-install. |
| Two `aec-blurb:start` markers in one file                     | Refuse to write; report duplicate; require manual cleanup. |
| File is read-only / permission denied                         | Skip target with clear error; other targets still process. |
| `.aec/agent-blurb.json` exists but `targets` empty            | Treat as "configured but no targets" — `--check` is clean; `configure-agent` lets user add targets. |
| Hand-edit inside the block detected on `aec update`           | Always show diff first; never silently overwrite; default action is "keep manual edit, mark as drifted." |
| Repo is a git submodule or worktree                           | Project scope writes go to the inner repo's `.aec/`. Implementation must reference AEC's existing repo-root resolution (see `feedback_repo_sync_expectations` + `project_hook_worktree_quirks` memories and current `aec install` behavior) — the planner needs to identify the exact resolver function before implementing. |
| `.aec/agent-blurb.json` is gitignored                         | Warn user during `configure-agent` — recommends committing for team consistency. |
| Concurrent `aec configure-agent` invocations                  | File-lock `.aec/agent-blurb.json` during write; second invocation waits or errors with clear message. |

## 10. Testing Strategy

Per project testing standards (`~/.agent-tools/rules/agents-environment-config/frameworks/testing/standards.md`):

### 10.1 Unit tests
- Renderer is a pure function — golden tests for each (profile × scope × AEC-version × shipped-template) combination.
- Hash computation determinism — same inputs → same hashes across runs and platforms.
- Marker parsing — extract block from arbitrary surrounding markdown; reject malformed states.

### 10.2 Integration tests (real filesystem, no mocks of internals per CLAUDE.md)
- `configure-agent` end-to-end against temp dirs containing real agent files.
- Drift detection across all five states in §6.1.
- `--refresh` idempotency — running twice produces byte-identical output.
- Atomic write — simulate failure between temp-write and rename; verify original file unchanged.
- Concurrent invocation — verify file lock prevents corruption.

### 10.3 Contract tests
- For every command name listed in the blurb (read-only, additive, destructive), assert it exists in `aec --help` output. Prevents the blurb from referencing commands that don't exist.

### 10.4 Coverage audit (per CLAUDE.md "Contract Change Coverage")
- Every place AEC currently writes to agent files must be reviewed to ensure none of them step on the blurb's markers.

## 11. QA Verification Update

Per CLAUDE.md, `docs/qa-verification.md` must be updated alongside this feature with:
- Install-time prompt verification (Y/n behavior, scope multi-select, agent-file selection)
- Drift-state verification (induce each of the 5 states, confirm `--check` output and exit code)
- Refresh idempotency verification
- Remove flow verification

## 12. Migration & Rollout

- This is a net-new feature; no existing blurb to migrate.
- Ship behind a single AEC minor version bump.
- First run of `aec install` / `aec update` after upgrade detects no blurb and offers the feature. Users who decline are not asked again until they run `aec configure-agent` explicitly or until a major AEC version bump.

## 13. Open Questions

1. **Decline persistence.** If a user declines the install-time prompt, should the decline persist (don't ask again until next major) or expire (ask again on next minor)? *Suggested default:* persist via `~/.aec/agent-blurb.json` with `{"declined": true, "declined_at_version": "x.y.z"}`. Re-prompt on major version change.
2. **`.cursor/rules/*.mdc` format.** Cursor's per-rule MDC files aren't a single document — should the blurb go in one `aec.mdc` rule file, or be merged into an existing global rule? *Suggested default:* dedicated `<repo>/.cursor/rules/aec.mdc` (project) and `~/.cursor/rules/aec.mdc` (global), respecting Cursor's globs.
3. **Read-only command list.** Is the read-only set truly static, or does it grow per release? If it grows, it should be sourced from a manifest, not hard-coded. *Suggested default:* hard-code v1, source from `aec` introspection (`aec list-commands --class=read-only`) in v2.
4. **Team / shared profiles.** Should orgs be able to ship a default profile via the org-config overlay system (existing AEC feature)? *Suggested default:* yes — phase 2; out of scope for v1 but design must not preclude it.

## 14. Out of Scope (Future Work)

- Enforcement layer (hook or MCP) that actually blocks ask-first commands when the calling agent has not surfaced user consent.
- Org-defined profile defaults via overlay (Question 13.4).
- Per-agent (Claude vs. Cursor vs. Gemini) profile differentiation. v1 uses one profile per scope across all agent files in that scope.
- Telemetry on which commands agents actually invoke autonomously vs. ask-first (would inform profile tuning).
