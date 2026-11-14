# AGENTS.md layout, opt-in migration, and `aec rollback`

Status: in progress on `feat/agents-md-migration`.

## Why

AEC writes `AGENTINFO.md` as the one file every agent should read, plus per-agent
stubs (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `QWEN.md`) that tell the agent to
read it. Nothing loads `AGENTINFO.md` automatically: each agent has to follow the
stub's instruction. `AGENTS.md` is now that shared file natively. Codex and Cursor
read it, and Claude Code reads it too
([docs](https://code.claude.com/docs/en/memory#agents-md)). By default Claude loads
`AGENTS.md` when a project has no `CLAUDE.md`, and a `CLAUDE.md` containing
`@AGENTS.md` imports it. Gemini CLI and Qwen Code expand `@file` imports the same
way.

So the new layout is:

- `AGENTS.md` holds the project content (what `AGENTINFO.md` held) plus the rules
  reference.
- `CLAUDE.md`, `GEMINI.md` and `QWEN.md` hold `@AGENTS.md`, followed by any
  content the user added that AEC did not generate.

## Design: departures from the first sketch, and why

The first sketch had a headless agent perform the migration and write its own
rollback instructions, with a rollback command on top of that. Changes:

1. **AEC performs the migration itself, deterministically.** Splitting a generated
   stub from user-added content is mechanical: known headings and known
   blockquote lines. Concatenating `AGENTINFO.md` into `AGENTS.md` loses nothing.
   An LLM there adds cost and nondeterminism, and makes it impossible to promise
   that nothing was lost.
2. **AEC records rollbacks itself; an agent never writes them.** An agent's own
   account of what it changed can't be checked. AEC snapshots every file it is
   about to touch: the bytes, and the sha256 before and after. Rollback is a
   byte-exact restore that AEC can verify.
3. **The agent is optional polish.** `--tidy-with <agent>` runs a detected agent
   headless with a prompt that is shown to the user first. It removes duplication
   left by the concatenation. The run is wrapped in its own changeset, so it is
   undone with the same `aec rollback` as everything else.
4. **Rolling back a rollback is free.** A changeset stores the before and after
   bytes for each file. Applying a rollback is itself recorded as a new changeset
   linked back to the original (`reverses` / `reversed_by`). Undoing the undo is
   a redo.
5. **No agent handoff for conflicts.** If a file was edited after AEC changed it
   (its current hash ≠ the recorded after-hash), `aec rollback` shows a diff and
   asks before overwriting. Restoring is lossless anyway: the new changeset keeps
   the edited bytes, so a mistaken restore is one more `aec rollback apply` away.
6. **No global-file migration.** Global instruction files never referenced
   `AGENTINFO.md`. The blurb importer de-duplication (`drop_importers`) already
   handles a global `CLAUDE.md` that imports `AGENTS.md`. Nothing to migrate.
7. **Cross-platform by construction.** Pure-Python `pathlib`, `hashlib`, temp file
   plus `os.replace`, and binary-safe reads and writes. No git, symlinks, shell or
   patch tools, so it behaves the same on Windows, macOS and Linux.

## Both layouts stay supported

- The per-repo layout is detected from disk: `AGENTINFO.md` present means
  `agentinfo`. Existing repos keep working untouched until the user migrates them.
- New setting `instructions_layout` (`agents-md` | `agentinfo`, default
  `agents-md`) decides what `aec repo setup` writes into a repo that has neither.
- The port-registry block goes into whichever file the repo's layout treats as
  canonical, and the port rule names both files.

## Stages

| # | Stage | Files owned | Tier |
|---|-------|-------------|------|
| S1 | Changeset store: begin/commit, list, load, conflicts, revert with inverse link | `aec/lib/changesets.py`, `tests/test_changesets.py` | sonnet |
| S2 | Layout transform: detect layout, plan migration (pure), render new layout from templates | `aec/lib/agents_md_layout.py`, `tests/test_agents_md_layout.py` | sonnet |
| S3 | Commands and wiring: `aec rollback`, `aec files migrate-agents-md` (with `--tidy-with`), `instructions_layout` setting, setup honours layout, port block targets canonical file, port rule text, setup hint for legacy repos | `aec/commands/*`, `aec/cli.py`, `aec/lib/preferences.py`, org allow-lists, `agents.json` (+ generated), `.cursor/rules` port rule, tests | sonnet |
| S4 | Docs: README section, `docs/users/rules-architecture.md`, user guide for migrate and rollback | docs only | sonnet |
| S5 | Adversarial review (Codex first), fix P0/P1, PR | | |

S1 and S2 run in parallel (disjoint files). S3 depends on both. S4 depends on S3.

## Acceptance

- Migrating a legacy repo produces the new layout. Every byte of user-authored
  content survives (asserted in tests). The change is recorded as a changeset.
- `aec rollback apply <id>` restores byte-exact, refuses silently overwriting
  edited files (diff plus confirm, `--force` to skip), and records the inverse.
  Applying the inverse redoes the migration.
- A repo that is already migrated is a no-op.
- Full suite passes on 3.9 and 3.12 in CI (Windows matrix included).
