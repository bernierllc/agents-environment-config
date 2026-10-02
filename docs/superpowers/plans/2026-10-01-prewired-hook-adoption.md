# Adopt prewired (committed) hooks into the aec lifecycle

**Status:** planned (Tier 2) · **Origin:** PR #101 review (Codex P2, 2026-09-30)
**Priority:** Medium. The guard works today and its script tracks the submodule;
what is missing is aec's ability to refresh or remove the committed entry.

## Root cause

Hook ownership lives only in per-checkout state
(`.aec/installed-hooks/<type>.<key>.json`). A repo that commits a wired hook
(PR #101: the pr-merge-flow PreToolUse entry in `.claude/settings.json`) hands
every fresh clone a live settings entry with no state file. Every lifecycle
path keys off state:

- catalog refresh iterates state files only (`aec/lib/catalog_hooks.py`), so a
  changed hook definition never re-renders the committed entry;
- `remove_hooks_for_item` returns False when state is absent
  (`aec/lib/hooks/lifecycle.py`), so `aec uninstall skill pr-merge-flow`
  leaves the guard active.

Committing the state file is not the fix: it also records per-agent installs
whose configs are machine-specific and untracked (the gemini `BeforeTool` entry
renders an absolute script path), so a fresh clone's state would describe
files it does not have.

## Correct fix

Add an adoption path: when aec renders an item's hooks into a config and finds
an existing entry whose content fingerprint matches the render, it records
ownership in state instead of appending a duplicate.

1. `installer._install_rendered`: before inserting, look for an entry with the
   same `content_fingerprint` (`fingerprint.py`) at any index of the target
   event; if found, record its pointer in `hooks_installed` and skip the write.
2. Catalog refresh: for catalog items that ship `hooks.json` but have no state,
   run install (which now adopts) instead of skipping — so a fresh clone of the
   aec repo adopts the committed entry on its first `aec upgrade`.
3. Uninstall with no state: run the render, adopt matches, then remove — so
   `aec uninstall` removes a committed entry it can prove it owns, and nothing
   it cannot.

## Affected surfaces

`aec/lib/hooks/installer.py`, `aec/lib/catalog_hooks.py`,
`aec/lib/hooks/lifecycle.py`; tests in `tests/test_catalog_hooks.py` and the
installer tests (fresh clone with committed entry → refresh adopts, no
duplicate; uninstall removes it; a hand-edited, non-matching entry is left
alone).
