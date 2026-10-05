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

Adopt only what aec itself declares it prewires. Content equality proves an
entry is *identical* to a render, not that aec *owns* it: a user may have
hand-copied the same payload, or kept a hook-bearing skill's entry on purpose
after uninstalling it. So ownership comes from an explicit, committed
registry, never from scanning the catalog.

1. **Registry** — `aec/data/prewired-hooks.json` (committed, reviewed with the
   change that commits the entry). One record per prewired entry:
   `{item_type, item_key, hook_id, agent, config_path, event, fingerprint}`.
   `hook_id` is stored, not derived: validation allows two ids to render
   identical payloads, so a fingerprint cannot recover it. Today it
   holds exactly one record: pr-merge-flow → claude →
   `.claude/settings.json` → `PreToolUse`.
2. `hooks/installer.py`: `adopt_prewired_hooks(repo_root)` reads the registry
   and, for each record whose `content_fingerprint` (`fingerprint.py`) matches
   an entry at any index of that event in that config, merges that entry and
   agent into the item's state: one load → union → atomic write per item, so
   ownership already recorded (e.g. Gemini or Cursor hooks from a normal
   install) and other registry records for the same item are kept, and an
   entry already in state is a no-op. No match → nothing written. Adoption
   never installs and never renders through the install path, so no
   `when.custom_check` predicate runs; items not in the registry are never
   touched.
3. Catalog refresh calls `adopt_prewired_hooks` before its state-driven pass.
   `dry_run` threads through: under `aec upgrade --dry-run` the adopter only
   reports what it would adopt and writes nothing, matching refresh's
   existing no-mutation contract.
   A fresh clone of the aec repo adopts the committed pr-merge-flow entry on
   its first `aec upgrade`; once adopted, the normal refresh keeps it current.
4. Uninstall with no state: call `adopt_prewired_hooks`, then remove what was
   adopted — `aec uninstall skill pr-merge-flow` removes the committed entry,
   and nothing aec cannot prove it prewired.
5. **The registry and the committed entry can never be stale** — the
   precondition for exact-match adoption (the fingerprint hashes the whole
   payload, so a version-N render never matches N+1). A test
   (`tests/test_prewired_hooks.py`) renders every registry record from the
   checked-out submodule and asserts the committed entry and the registry
   fingerprint both equal the render. A submodule bump that changes a
   prewired hook fails CI until entry and registry are regenerated in the
   same PR. A small generator (`scripts/render-prewired-hooks.py`) rewrites
   both, so the fix is a command, not hand-editing.

### Constraints (from PR #103 review)

- **Ownership is declared, not inferred.** Only registry records are adoption
  candidates; an identical entry for an unregistered item is left alone.
- **No predicate execution.** Adoption fingerprints the stored registry value;
  it never calls the install render path, which evaluates `when.custom_check`
  with `shell=True` and would inherit `aec upgrade --yes` as consent.
- **Adopted refresh stays within the adopted entries — exact `(hook_id,
  agent)` pairs.** Adopted state records each entry's `hook_id` (copied from
  the registry record; the id `hooks.json` validation keeps unique, recorded
  today as `source_hook_id` and keyed on in `hooks/drift.py`) and agent, and is
  marked `origin: "adopted"`. For adopted state, `catalog_hooks._refresh_one` →
  `wire()` → `install_item_hooks` passes the recorded `(hook_id, agent)` pairs
  — never independent id and agent sets, which would cross-render
  `(hook-a, gemini)` from `(hook-a, claude)` + `(hook-b, gemini)` — and
  `translate_to_agent` renders only those pairs. A later version that adds a
  second Claude hook re-renders the adopted entry and neither installs nor
  claims the new one.
- **Ordinary installs keep today's refresh scope.** State from a normal
  install is unchanged: refresh still re-evaluates its full intended scope,
  including hooks recorded only in `hooks_skipped` (e.g. a `repo_has`
  predicate that was false at install and is true now) and every agent the
  install targeted. The pair filter applies only to `origin: "adopted"`. When
  adoption merges into existing install state (step 2), the item keeps its
  install scope and the adopted pairs are added to it, so nothing it already
  tracked narrows.

Tests: adopting into an item whose state already owns Gemini/Cursor hooks
keeps them (and two registry records for one item both land); a dry-run
refresh on a fresh checkout leaves `.aec/installed-hooks/` absent; an
unregistered hook-bearing item with an identical committed entry is
not adopted; an item with a `custom_check` that would write a sentinel file is
never evaluated; a Claude-only adoption followed by a `hooks.json` version bump
leaves `.gemini/settings.json` absent; a version bump that adds a second
Claude hook to an adopted item re-renders only the adopted entry and leaves
the new hook uninstalled and out of state; adopted state holding
`(hook-a, claude)` and `(hook-b, gemini)` refreshes to exactly those two
entries; a normal install whose `repo_has` hook was skipped picks it up on
a later refresh once the file exists; the registry/committed-entry freshness
test above.

## Affected surfaces

`aec/data/prewired-hooks.json`, `scripts/render-prewired-hooks.py`,
`aec/lib/hooks/installer.py` (+ `translate_to_agent` filter), `aec/lib/catalog_hooks.py`,
`aec/lib/hooks/lifecycle.py`; tests in `tests/test_catalog_hooks.py` and the
installer tests (fresh clone with committed entry → refresh adopts, no
duplicate; an unregistered item stays untouched;
uninstall removes an adopted entry; a hand-edited, non-matching entry is left
alone) and `tests/test_prewired_hooks.py`.
