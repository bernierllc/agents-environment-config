# Owner-scoped org overlay answers

Status: planned. Scheduling pending (Tracker row, Owner `Needs-PM`).

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
2. `prompt()` receives the active repo context (set once per command by the repo-aware
   commands) and resolves overlay answers as: owner-scoped match > unscoped answer.
3. Machine-global keys (preferences, install behavior) stay unscoped; repo-shaped keys
   (`repo.git.*`) become scope-eligible only. The allow-list marks which are which.
4. Conflict handling for two enrolled orgs scoping the same owner reuses the existing
   `detect_conflicts` policy.

## Affected surfaces

`aec/lib/prompts.py`, `aec/lib/org_config/{allow_lists,apply,policy}.py`, the
org-config schema and `docs/orgs/authoring-org-configs.md`, the two overlay tests, and every repo-aware
command that must set the context (`setup`, `repo setup`, `migrate`).

## Tests

- Owner-scoped `repo.git.license_kind: proprietary` applies in a repo whose origin owner matches and not in one whose owner differs.
- Unscoped answers keep working; scoped beats unscoped; two orgs scoping one owner is a reported conflict.
- A repo with no `origin` falls back to unscoped answers only.
