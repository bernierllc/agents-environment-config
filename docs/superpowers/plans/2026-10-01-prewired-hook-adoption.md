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

Add an **adoption-only** mode: render an item's hooks, and for each target
config look for an existing entry whose content fingerprint matches the render.
A match is recorded in state; no match means no write. Adoption never
installs: a hook-bearing item the user never installed must stay inactive.

1. `hooks/installer.py`: an `adopt_item_hooks(...)` sibling of
   `install_item_hooks` that renders, matches by `content_fingerprint`
   (`fingerprint.py`) at any index of the target event, and writes only the
   state file, recording just the matched entries. Zero matches → no state
   file, nothing written.
2. Catalog refresh: for catalog items that ship `hooks.json` but have no state,
   call `adopt_item_hooks` (never `install`). A fresh clone of the aec repo
   thereby adopts the committed pr-merge-flow entry on its first
   `aec upgrade`; every other hook-bearing skill stays untouched. Once
   adopted, the normal refresh path keeps it current.
3. Uninstall with no state: call `adopt_item_hooks`, then remove what was
   adopted — so `aec uninstall` removes a committed entry it can prove it
   owns, and nothing it cannot.

4. **The committed entry can never be stale** — the precondition for
   exact-match adoption. The fingerprint hashes the whole payload, so an entry
   rendered from `hooks.json` version N cannot be matched against N+1. Rather
   than teach adoption to recognise old renders, make a stale commit
   impossible: a test (`tests/test_prewired_hooks.py`) renders every hook the
   repo commits (today: pr-merge-flow into `.claude/settings.json`) from the
   checked-out submodule and asserts the committed entry equals the render. A
   submodule bump that changes a prewired hook fails CI until the entry is
   re-rendered in the same PR, so a fresh checkout always holds an adoptable,
   current payload.

## Affected surfaces

`aec/lib/hooks/installer.py`, `aec/lib/catalog_hooks.py`,
`aec/lib/hooks/lifecycle.py`; tests in `tests/test_catalog_hooks.py` and the
installer tests (fresh clone with committed entry → refresh adopts, no
duplicate; a hook-bearing item with no committed entry stays uninstalled;
uninstall removes an adopted entry; a hand-edited, non-matching entry is left
alone) and `tests/test_prewired_hooks.py`.
