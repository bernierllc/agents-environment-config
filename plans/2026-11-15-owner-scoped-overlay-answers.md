# Owner-scoped org overlay answers

Status: planned. Scheduling pending (Tracker row, Owner `Needs-PM`).

Prerequisite: PR #148 (`repo.git.license_kind` / `repo.git.license_holder` prompts, their
allow-list entries, and `_load_org_prompt_answers` at CLI startup). None of those exist on
`staging` until #148 merges, so this plan cannot be implemented or tested before it.

## Why

Org overlay answers (`install.prompts` in an enrolled org config) are machine-global:
`set_overlay_answers` holds one process-wide dict and `effective_policy` unions the
prompts of every enrolled org. Since the overlay now loads at every CLI startup
(`_load_org_prompt_answers`), an answer such as `repo.git.license_kind: proprietary`
applies to every repo `aec` touches on that machine, including repos that do not belong
to the org. One person working on an org's repos and an open-source repo gets the org's
license choice stamped on both.

## Root cause

Overlay answers carry no scope. A prompt answer is keyed by prompt id only; the repo or
owner the command runs against is not part of the lookup.

## Correct fix

1. Let an org config scope prompt answers by repo owner: `install.prompts_by_owner:
   {<owner>: {<prompt-id>: <value>}}`. Owner is the `origin` remote's owner (GitHub org or user).
2. One lookup, `scoped_answer(key, repo)`, resolves an owner-scoped answer for a repo's
   `origin` owner. The repo context is bound per repository, never per command: a
   context manager (`with repo_context(repo):`) that `prompt()` reads, entered inside each
   loop iteration of the bulk paths (`setup --all`, `migrate agents-md --all`, the
   maintenance prompt), so one owner's answers cannot govern the next repo. Machine-global
   keys resolve unscoped as before. Repo-shaped keys resolve only through `scoped_answer`.
3. Machine-global keys (preferences, install behavior) stay unscoped. Repo-shaped keys
   (`repo.git.*`, and the `instructions_layout` pin from the AGENTINFO plan) are
   scope-only: the allow-list marks them, and an unscoped value for one under
   `install.prompts` is rejected by validation with an error naming `prompts_by_owner`.
   The unscoped form PR #148 accepts is a stopgap for an org whose users only use AEC on its
   repos; it is removed when this ships, never kept as a fallback (a fallback would keep
   the cross-repo leakage this plan exists to stop). The same rule covers the existing
   path: `install.preferences.instructions_layout` in an org config is rejected by
   validation (it would be persisted machine-wide by `apply_preferences`), with an error
   naming `prompts_by_owner`. A user's own local `instructions_layout` setting stays valid;
   it is the user's default, not an org's.
4. `instructions_layout` is not a prompt, so the context manager alone cannot reach it.
   The shared layout resolver (`repo_layout` in `agents_md_layout.py`, from the AGENTINFO
   plan) consumes `scoped_answer("instructions_layout", repo)`: detected layout first, then
   the scoped answer, then the `instructions_layout` setting, then the default.
5. Conflicts. Today `conflicts.py:detect_conflicts` never looks at prompt answers and
   `effective.py` merges prompts with a last-writer-wins `dict.update`. Extend
   `detect_conflicts` to report two enrolled orgs giving different values for the same
   `(owner, prompt-id)`, and make `effective.py` merge scoped answers per `(owner, key)`
   and hold a conflicted pair (no answer applied, the conflict surfaced like other
   conflicts) instead of picking one.

## Affected surfaces

`aec/lib/prompts.py`, `aec/lib/org_config/{allow_lists,apply,conflicts,effective}.py`, the org-config validator, the
org-config schema and `docs/orgs/authoring-org-configs.md`, the two overlay tests, and every repo-aware
command that must set the context (`setup`, `repo setup`, `migrate`).

## Tests

- Owner-scoped `repo.git.license_kind: proprietary` applies in a repo whose origin owner matches and not in one whose owner differs.
- `install.preferences.instructions_layout` in an org config is rejected by validation and never reaches `apply_preferences`; a user's own local setting still works.
- Two enrolled orgs giving different scoped answers for one `(owner, prompt-id)`: reported as a conflict and neither applied.
- An unscoped `repo.git.license_kind` in `install.prompts` is rejected (validation error), not applied; machine-global unscoped keys keep working.
- Bulk `setup --all` and `migrate agents-md --all` over two repos with different owners: each gets only its own owner's answers, in either order (mixed-owner test).
- A scoped `instructions_layout: agentinfo` changes the layout `setup` and `migrate` choose for a matching-owner repo and not for another owner's repo.
- A repo with no `origin` gets no scoped answers: repo-shaped keys use their defaults, machine-global unscoped keys still apply.
