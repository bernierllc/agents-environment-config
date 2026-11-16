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
| 1 | `aec setup` writes `AGENTS.md` as the facts file | **Partly wrong.** `_copy_agent_files` calls `_repo_layout`: the repo's detected layout first, else the `instructions_layout` setting, and the default is `agents-md`. In a repo with `AGENTINFO.md` it writes the AGENTINFO.md templates. A fresh repo with no setting gets the AGENTS.md layout. The real gap is that nothing pins an org's repos to `agentinfo` without also pinning every other repo on the machine: `instructions_layout` is a machine-global preference. | `aec/commands/repo.py:_repo_layout`, `_copy_agent_files` |
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
5. **Org pin, scoped to the org's repos.** `instructions_layout` is a machine-global
   preference: `apply_preferences` writes it to the user's preferences file and
   `_repo_layout` reads it for every fresh repo, so enrolling one org would change the
   layout of unrelated repos. Do not document it as an org pin yet. The pin becomes
   an owner-scoped answer under `install.prompts_by_owner` (see
   `2026-11-15-owner-scoped-overlay-answers.md`, which makes `instructions_layout` a
   scope-only key); this plan's step 5 ships with or after that plan. Until then, an org
   that wants every repo on `agentinfo` gets it per repo, because `detect_layout` already
   returns `agentinfo` wherever `AGENTINFO.md` exists. Steps 1-4 do not depend on it.

## Affected surfaces

- `aec/lib/agents_md_layout.py`: gains `repo_layout`; `plan_migration` takes a `pinned` argument or the caller filters.
- `aec/commands/repo.py`: `_repo_layout` removed in favor of the shared function.
- `aec/commands/migrate_cmd.py`: pinned skip, `--force-layout`, `--all` filtering.
- `aec/lib/prompt_catalog/maintenance_area.py`: prompt summary for the bulk run.
- `aec/commands/files.py`, `aec/commands/generate.py`, `aec/cli.py`: rename plus deprecated aliases.
- Generated text that names the old command: `aec/lib/agent_files.py` (emits `aec files generate` into every generated instruction stub), `aec/lib/agents_md_layout.py` (treats that exact text as generated boilerplate: it must recognize both the old and the new command so existing stubs still migrate), `scripts/generate-agent-files.py`, `docs/users/cli-reference.md`, `docs/users/rules-architecture.md`.
- Docs: `README.md` (layout section); `docs/orgs/authoring-org-configs.md` once the owner-scoped plan lands.
- Writers to sweep before changing the contract: `setup`, `repo setup`, `migrate agents-md` (single path, `--all`, maintenance prompt, `--tidy-with`), `generate files`, `rollback`.

## Tests (behavior, not bytes)

- Repo with `AGENTINFO.md` and `instructions_layout=agentinfo`: `aec migrate agents-md .` changes nothing and says why; AGENTINFO.md still exists.
- Same repo with `--force-layout`: migrates, and `aec rollback` restores the exact bytes.
- `--all` over one pinned and one unpinned repo: only the unpinned one is in the plan.
- `aec setup` in a fresh repo with `instructions_layout=agentinfo`: facts file is `AGENTINFO.md`, and `CLAUDE.md`/`GEMINI.md`/`QWEN.md`/`AGENTS.md` are reference stubs that point at it.
- `aec setup` in a fresh repo with no setting: AGENTS.md layout (the default is unchanged).
- Owner-scoped org answer `instructions_layout: agentinfo` (after the owner-scoped plan): holds in a repo whose origin owner matches, and a repo of another owner keeps the default.
- `aec generate templates` outside an AEC checkout exits non-zero with a message and writes nothing; the deprecated aliases warn and delegate.
- Newly generated instruction stubs name `aec generate templates`, not `aec files generate`; a stub generated before the rename is still recognized as boilerplate and migrates cleanly.

## Not in scope

- Changing the default layout for generic users (stays `agents-md`).
- Replacing AGENTINFO.md content with anything: the file is never rewritten by `setup`.
- Owner-scoped overlay answers (separate plan: `2026-11-15-owner-scoped-overlay-answers.md`).

## Decision: what counts as a pin

A pin is an explicit setting only: the user's local `instructions_layout`, and later an
owner-scoped answer. A detected `AGENTINFO.md` is never a pin. `plan_migration` returns a
plan only for repos where `detect_layout(repo) == "agentinfo"`, so every candidate a bulk
run could migrate is detected-`agentinfo`; treating detection as a pin would filter out
all of them and make `--all` and the maintenance prompt dead. The pin check therefore reads
the setting directly (never the detected layout), and a repo that merely has `AGENTINFO.md`
and no setting stays migratable, which is what `aec migrate agents-md` is for. Test:
`--all` over one repo with `AGENTINFO.md` and the pin set, one with `AGENTINFO.md` and no
pin: only the second is planned (already listed above).
