# Hook lifecycle transactions

**Status:** planned (Tier 2) · **Origin:** PR #99 review, Codex rounds 3–7 (2026-09-30)
**Priority:** High — every item is small and scoped; item 1 is a live defect on the normal upgrade path.

## Root cause

A hook install or removal writes up to five stores for one item:
`.claude/settings.json`, `.gemini/settings.json`, `.cursor/hooks.json`, the git
hook files under the resolved hooks dir, and the item's state file in
`.aec/installed-hooks/`. None of them is written in a single atomic step, so a
failure part-way leaves some configs changed and others not, or live hooks
that state does not record.

## Already fixed in #99

- `install_item_hooks` renders every agent's entries (script resolution and
  translation) before it retracts anything, so a render failure changes nothing.
- `install_item_hooks` and `remove_item_hooks` snapshot every config file they
  may touch. Retraction, writes and the state write/removal happen inside one
  `try`, and a failure restores the snapshot.
- Paths that exist but are not files are left out of the snapshot, so restore
  never unlinks a directory.
- Catalog `refresh()` runs each item on its own, so one failure never stops
  the rest.

## Remaining work

1. **`aec upgrade` removes, then reinstalls (live defect).** `aec/commands/upgrade.py`
   (hook refresh after `record_install`) calls `remove_hooks_for_item` and then
   `install_hooks_for_item`. If the install fails, the item is left with no
   hooks, and its recorded `allow_custom_check` consent is dropped, so a
   non-`--yes` upgrade of an item using `when.custom_check` raises PermissionError
   and ends hookless.
   **Fix:** delete the `remove_hooks_for_item` call. `install_item_hooks` already
   retracts the recorded hooks inside its transaction. Pass
   `allow_custom_check=yes or <recorded state>.allow_custom_check`, the same as
   `catalog_hooks.refresh`. Test: upgrade with a missing script keeps the old
   hooks; upgrade without `--yes` keeps consent.
2. **Restore can itself fail part-way.** `_restore_configs` stops at the first
   write error. **Fix:** attempt every path, collect the errors, then raise one
   error naming every path that could not be restored, and put that in the
   command's warning, so the user knows which files to check.
3. **A corrupt state file blocks every other item.** `_remove_recorded_hooks`
   loads every item's state to find co-owned entries, so one unparseable state
   file makes every install/remove in that repo fail. Failing is correct (we
   cannot know what the corrupt item owns), but the error must name the file
   and the fix. **Fix:** raise a typed error from `list_installed_items`/
   `load_state` that names the state file and tells the user to run
   `aec hooks remove <item>` or delete it. Surface it once per command, not once
   per item.
4. **Other callers of the pair.** `apply_core.py` (org apply), `hooks/drift.py`
   (drift repair) and `install_cmd.py` all call `install_hooks_for_item`; check
   that none does its own remove first (grep `remove_hooks_for_item`), and add
   the same missing-script test for each.
5. **Findings from later #99 Codex rounds** in this class, listed below.

## Affected surfaces

`aec/lib/hooks/installer.py`, `aec/lib/hooks/state.py`, `aec/commands/upgrade.py`,
`aec/lib/apply_core.py`, `aec/lib/hooks/drift.py`, tests under `tests/`.

## Done when

Every hook lifecycle entry point (install, upgrade, uninstall, org apply,
drift repair, catalog refresh) either fully applies or leaves configs and state
exactly as they were, with a test per entry point that injects a failure after
retraction.

## Later #99 findings (triaged)

- Round 7 (catalog refresh skipped a hooks.json removed without a version bump):
  in #99's own code, fixed there.
