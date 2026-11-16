# `aec upgrade` must detect and upgrade vendored skill copies

Status: planned. Scheduling pending (Tracker row, Owner `Needs-PM`).

## Problem

`aec outdated` / `aec upgrade` print "(up to date)" for a repo whose committed (vendored) skill copies are
stale. Vendored skills are not in the manifest's per-repo (Local) list, so `_report_scope_outdated` never
compares them with the source version. A downstream repo carried an old `pr-merge-flow` (1.3.0) while the
global copy was 1.4.1; its merge guard lacked a fix the newer version had, and misfired for days while AEC
reported everything current.

## Root cause

The "up to date" verdict is computed from the install manifest only (`aec/commands/update.py`,
`aec/lib/apply_core.py`). A skill that was copied into a repo (committed, or installed by a teammate)
has no manifest row on this machine, so it is invisible to the comparison. Silence reads as success.

## Correct fix (rung 1, then rung 3 of the "remembering is a failure mode" ladder)

1. Detect vendored copies: for each tracked repo, find skill directories under the agent skill roots that carry
   a version (frontmatter `version` or the skill's own version file) and match a name AEC ships. Verify the
   exact version source before coding; do not guess a layout.
2. `aec outdated` lists them as their own scope ("vendored in <repo>") with installed vs available version.
3. `aec upgrade` upgrades them in place when the tree is clean for that path (a dirty vendored copy is reported,
   never overwritten), writing the manifest row so the next run is a normal comparison.
4. Never say "(up to date)" for a scope it did not check: when vendored copies exist and the check cannot run,
   the summary names what was skipped and the command that fixes it (`aec doctor` fails loudly on the same
   condition).

## Tests

- A repo with a vendored skill one version behind: `outdated` lists it, `upgrade` updates it, a second run is
  clean.
- A vendored copy with local edits: reported, not overwritten.
- A repo with no vendored copies: unchanged output.
- `doctor` exits non-zero and names the fix when a vendored copy is stale.

## Affected surfaces

`aec/commands/update.py`, `aec/commands/upgrade.py`, `aec/lib/apply_core.py`, `aec/commands/run_doctor.py`
(or its equivalent), docs for `outdated` / `upgrade`.
