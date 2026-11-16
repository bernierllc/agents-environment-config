# Honor the AGENTINFO.md layout everywhere AEC writes or moves instruction files

Status: planned. Scheduling pending (Tracker row, Owner `Needs-PM`).

## Why

A repo that keeps its project facts in `AGENTINFO.md`, with `CLAUDE.md`, `GEMINI.md`,
`QWEN.md`, `AGENTS.md` and the Cursor rule as generated, reference-only files, is a
supported layout (`instructions_layout: agentinfo`, and `detect_layout` returns
`agentinfo` whenever `AGENTINFO.md` exists). Three reports (aec 2.52.7) say AEC
contradicts it. Checked against the code at `973e583`:

| # | Report | Verdict | Evidence |
|---|---|---|---|
| 1 | `aec setup` writes `AGENTS.md` as the facts file | **Partly wrong.** `_copy_agent_files` calls `_repo_layout`: the repo's detected layout first, else the `instructions_layout` setting, and the default is `agents-md`. In a repo with `AGENTINFO.md` it writes the AGENTINFO.md templates. A fresh repo with no setting gets the AGENTS.md layout. The real gap is that nothing pins a whole org to `agentinfo`: the org config key exists (`instructions_layout` is allow-listed) but is not set by the catalog. | `aec/commands/repo.py:_repo_layout`, `_copy_agent_files` |
| 2 | `aec migrate agents-md` moves AGENTINFO.md into AGENTS.md | **True, and unguarded.** `run_migrate_agents_md` calls `plan_migration(repo)` for every target and never reads `instructions_layout`. `--all` runs it over every tracked repo, and the maintenance prompt `MIGRATE_AGENTS_MD_CONFIRM` offers that bulk run. A user who chose `agentinfo` is offered the opposite layout, and a bulk `yes` deletes their AGENTINFO.md (recorded and undoable with `aec rollback`, but still wrong). | `aec/commands/migrate_cmd.py:run_migrate_agents_md`, `aec/lib/prompt_catalog/maintenance_area.py` |
| 3 | `aec generate files` writes into AEC's own `templates/` | **True.** `files.generate()` uses `require_repo_root()` and writes `templates/*.md` in the AEC checkout. It is a maintainer command that generates AEC's shipped templates, but its name and `aec generate` group read as "generate this project's agent files". Run in a user repo it fails or, in an AEC clone, rewrites AEC's templates. | `aec/commands/files.py:generate` |

## Root cause

AEC has no single answer to "which layout does this repo use, and may AEC change it?".
`_repo_layout` answers it for `setup`; `migrate` and the maintenance prompt do not ask.
The layout is also a *setting*, not an *assertion*: nothing says "this repo or org is
pinned to agentinfo, never offer to migrate it".

## Correct fix

1. **One owner for the layout decision.** Move `_repo_layout` into `aec.lib.agents_md_layout`
   (it already owns `detect_layout`) and have `setup`, `migrate` and the maintenance
   prompt call it. Callers never re-decide (global rule: each piece of code does its own job).
2. **`migrate agents-md` honors a pinned layout.** When `instructions_layout` is
   `agentinfo` (user preference or org config), `plan_migration` skips the repo with the
   line `pinned to the AGENTINFO.md layout by instructions_layout; nothing to migrate`.
   An explicit `aec migrate agents-md <path> --force-layout` overrides, so a deliberate
   one-off migration stays possible. `--all` and the maintenance prompt never override.
3. **The maintenance prompt lists only migratable repos** and is not offered at all
   when every repo is pinned or already migrated.
4. **`aec generate files` is renamed and scoped as the maintainer command it is.**
   New name `aec generate templates` (AEC checkout only, errors with a clear message
   elsewhere); `aec generate files` and `aec files generate` stay as deprecated aliases
   for one release through the existing `deprecation_warning`. Nothing in a user repo
   is written by it.
5. **Org pin.** Org configs already accept `instructions_layout`. Document it in
   `docs/orgs/authoring-org-configs.md` as the way an org keeps every repo on one
   layout. The org's own catalog owns the value; AEC carries nothing org-specific.

## Affected surfaces

- `aec/lib/agents_md_layout.py`: gains `repo_layout`; `plan_migration` takes a `pinned` argument or the caller filters.
- `aec/commands/repo.py`: `_repo_layout` removed in favor of the shared function.
- `aec/commands/migrate_cmd.py`: pinned skip, `--force-layout`, `--all` filtering.
- `aec/lib/prompt_catalog/maintenance_area.py`: prompt summary for the bulk run.
- `aec/commands/files.py`, `aec/commands/generate.py`, `aec/cli.py`: rename plus deprecated aliases.
- Docs: `README.md` (layout section), `docs/orgs/authoring-org-configs.md`.
- Writers to sweep before changing the contract: `setup`, `repo setup`, `migrate agents-md` (single path, `--all`, maintenance prompt, `--tidy-with`), `generate files`, `rollback`.

## Tests (behavior, not bytes)

- Repo with `AGENTINFO.md` and `instructions_layout=agentinfo`: `aec migrate agents-md .` changes nothing and says why; AGENTINFO.md still exists.
- Same repo with `--force-layout`: migrates, and `aec rollback` restores the exact bytes.
- `--all` over one pinned and one unpinned repo: only the unpinned one is in the plan.
- `aec setup` in a fresh repo with `instructions_layout=agentinfo`: facts file is `AGENTINFO.md`, and `CLAUDE.md`/`GEMINI.md`/`QWEN.md`/`AGENTS.md` are reference stubs that point at it.
- `aec setup` in a fresh repo with no setting: AGENTS.md layout (the default is unchanged).
- Org overlay `instructions_layout: agentinfo`, no local setting: all of the above hold (depends on the overlay loading at CLI startup, shipped in PR #148).
- `aec generate templates` outside an AEC checkout exits non-zero with a message and writes nothing; the deprecated aliases warn and delegate.

## Not in scope

- Changing the default layout for generic users (stays `agents-md`).
- Replacing AGENTINFO.md content with anything: the file is never rewritten by `setup`.
- Owner-scoped overlay answers (separate plan: `2026-11-15-owner-scoped-overlay-answers.md`).

## Open question

Should `detect_layout` returning `agentinfo` pin the repo on its own, so repos that predate the
setting are never migrated by a bulk run? Recommendation: yes for `--all` and the maintenance
prompt (an existing AGENTINFO.md is a choice someone made), no for an explicit path argument,
which already asks for a confirmation.
