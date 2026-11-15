# Recover an interrupted custom-source publication

Status: planned; scheduling pending. **Blocked on PR #132 (custom-source install).** The
code this plan describes (`publish_sources`, `sync_custom_sources`, `sources.prev`,
`source_commits`) exists only on that PR's branch, not on `main`. Do not start until it
merges; if it does not, this plan is void. Origin: review finding on that PR, deferred there
as a tracked follow-up.

## Root cause and affected surfaces

`publish_sources` in `aec/lib/org_config/apply.py` moves each live source checkout aside to
`<org dir>/sources.prev/<source id>`, renames the staged checkout into place, writes the
approval state, then deletes `sources.prev`. Exceptions roll back, but a process killed
between the first rename and the end of the state write never reaches the rollback. The
next apply finds `sources.prev` and deletes it, which throws away the only known-good copy.
Depending on where the kill landed, the live checkout is then either missing or holds a
commit that `source_commits` never approved, and maintenance commands resolve custom items
against that live directory.

Surfaces: `publish_sources`, `sync_custom_sources` (clears `sources.prev` before reuse),
`recover_interrupted` in `aec/lib/org_config/state.py` (the existing crash recovery for org
state files, which is the incumbent to extend), and the maintenance commands that read the
live source directory (`outdated`, `sources.installed_by_source`).

## S1 — Make publication crash-safe

1. Decide the mechanism: extend `recover_interrupted` so every read of org state also
   restores `sources.prev` when the recorded `source_commits` do not match the live
   checkout, or make the live switch a single atomic rename (for example a `current`
   symlink flipped with `os.replace`).
2. Never delete `sources.prev` unless the live checkout matches the approved commit.
3. Test by killing a subprocess between the rename and the state write, and assert the next
   command leaves the approved checkout live and no `sources.prev` behind.
