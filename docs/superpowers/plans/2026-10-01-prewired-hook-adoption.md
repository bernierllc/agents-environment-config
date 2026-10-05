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
   identical payloads, so a fingerprint cannot recover it. It must be
   non-empty and unique within the item: `hooks.json` allows id-less agent
   overrides (`validator.py`), which translate to `source_hook_id == ""`, so
   an empty id would collapse distinct entries into one `("", agent)` pair.
   An item whose hook lacks an id cannot be registered until it gains one;
   the freshness test (step 5) loads the registry and fails on an empty or
   duplicate `(item, hook_id, agent)`. Today it
   holds exactly one record: pr-merge-flow → claude →
   `.claude/settings.json` → `PreToolUse`.
2. `hooks/installer.py`: `adopt_prewired_hooks(repo_root)` returns at once
   unless `scope.is_catalog_repo(repo_root)` (true for the aec checkout and
   its linked worktrees): the registry describes what *this* repo commits, so
   an identical payload in any other project is never adopted. It then reads
   the registry and, for each record whose `content_fingerprint` (`fingerprint.py`) matches
   an entry at any index of that event in that config, merges that entry and
   agent into the item's state: one load → union → atomic write per item, so
   ownership already recorded (e.g. Gemini or Cursor hooks from a normal
   install) and other registry records for the same item are kept, and an
   entry already in state is a no-op. No match → nothing written.
   Adoption
   never installs and never renders through the install path, so no
   `when.custom_check` predicate runs; items not in the registry are never
   touched.
3. Catalog refresh calls `adopt_prewired_hooks` before its state-driven pass.
   `dry_run` threads through: under `aec upgrade --dry-run` the adopter only
   reports what it would adopt and writes nothing, matching refresh's
   existing no-mutation contract.
   A fresh clone of the aec repo adopts the committed pr-merge-flow entry on
   its first `aec upgrade`; once adopted, the normal refresh keeps it current.
4. Uninstall always calls `adopt_prewired_hooks` first — with or without
   existing state — then removes everything in scope. Its merge semantics
   (step 2) add the committed entry to state that omitted it (e.g. a
   Gemini/Cursor-only install), so `aec uninstall skill pr-merge-flow`
   removes the committed entry too, and nothing aec cannot prove it
   prewired.
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
- **Adopted scope = matched pairs ∩ current registry.** State gains
  `adopted_pairs`: the `(hook_id, agent)` pairs whose committed entry
  actually matched at adoption (the id `hooks.json` validation keeps unique,
  recorded today as `source_hook_id` and keyed on in `hooks/drift.py`). It is
  its own field, written only by the adopter and never by install, so a
  predicate that skips the hook and replaces `hooks_installed` cannot lose it
  (`hooks_skipped` keeps ids, not agents), and a false→true predicate brings
  the hook back. The scope used everywhere is `adopted_pairs` intersected with
  the current registry on every read: a registry record with no matching
  entry is never owned (a missing or hand-edited entry is not adopted, so
  refresh and repair never install it), and a registry removal de-scopes the
  pair on every path at once, including `verify --repair` before any refresh.
  Filtering is always by exact pairs — never independent id and agent sets,
  which would cross-render `(hook-a, gemini)` from `(hook-a, claude)` +
  `(hook-b, gemini)`. A later version that adds a second Claude hook
  re-renders the adopted entry and neither installs nor claims the new one.
  When the intersection is empty and no normal install scope remains, the
  next adoption pass deletes the state file.
- **One scope function, every state-driven path.** The scope lives on the
  state, not in each caller: `hooks/state.py` gains `render_scope(state)` →
  the union of two independent scopes: `agents_targeted` × all hooks
  (skipped included — unchanged; it already means only the agents a normal
  install chose, so no rename and no state migration) and `adopted_pairs` ∩
  registry. Adoption never writes `agents_targeted`; install never writes
  `adopted_pairs`. So a Gemini/Cursor install plus an adopted Claude pair
  renders every Gemini/Cursor hook and exactly the registered, matched Claude
  hook — never a later unregistered Claude hook — and neither scope narrows
  the other. `adopted_pairs` is optional on load (absent = empty), so
  existing v1 state files load unchanged.
  Every reader of the old `agents_targeted` routes through it — catalog refresh
  (`catalog_hooks._refresh_one`), drift verification (`drift.verify_repo`,
  which renders expected entries per `agents_targeted`) and drift repair
  (`drift.repair_repo` → `install_hooks_for_item`, whose agent default also
  goes) — so `aec hooks verify --repair` cannot install or claim an
  unadopted hook either. A test asserts no module outside `state.py` reads
  `agents_targeted` or `adopted_pairs` directly, so a future state-driven path cannot skip it.
- **Scope is applied at load, not at translation.** Two paths render an
  item's hooks from source, and each runs work over every hook before
  `translate_to_agent`: `install_item_hooks` (consent checks, `when`
  predicates, `_resolve_script_commands`) and `drift._rendered` (predicates,
  `_resolve_script_commands`, returning `None` — no drift opinion — when any
  script is missing). Both call `schema.load_hooks_file`; the scope filter is
  one helper applied to its result (`scoped_hooks(hf, state, agent)`) by both
  callers, before anything else touches the hook list. An unadopted hook added
  in a later version is then never consent-checked, never has its
  `custom_check` executed, and cannot fail script resolution or blank out
  STALE detection for the adopted entry. The no-direct-scope-read test
  also asserts both render paths call `scoped_hooks`.
- **Ordinary installs keep today's refresh scope.** State from a normal
  install is unchanged: refresh still re-evaluates its full intended scope,
  including hooks recorded only in `hooks_skipped` (e.g. a `repo_has`
  predicate that was false at install and is true now) and every agent the
  install targeted. Adoption merging into existing install state (step 2)
  only adds `adopted_pairs`, so nothing it already tracked narrows or widens.

Tests: adopting into an item whose state already owns Gemini/Cursor hooks
keeps them, and a later version adding an unregistered Claude hook installs
it for neither Claude nor the adopted pair; uninstalling an item whose
existing state omits the committed entry removes that entry too; two registry records for one item where only one committed entry matches
adopts only that one, and refresh/repair never install the other; an
existing state file without `adopted_pairs` loads with its scope intact; a dry-run
refresh on a fresh checkout leaves `.aec/installed-hooks/` absent; an
unregistered hook-bearing item with an identical committed entry is
not adopted; an item with a `custom_check` that would write a sentinel file is
never evaluated; a Claude-only adoption followed by a `hooks.json` version bump
leaves `.gemini/settings.json` absent; a version bump that adds a second
Claude hook to an adopted item re-renders only the adopted entry and leaves
the new hook uninstalled and out of state; adopted state holding
`(hook-a, claude)` and `(hook-b, gemini)` refreshes to exactly those two
entries; a normal install whose `repo_has` hook was skipped picks it up on
a later refresh once the file exists; `aec hooks verify --repair` on an
adopted item whose new version adds a second Claude hook reports no drift
and installs nothing; an adopted refresh whose new version adds an
unadopted hook with a sentinel-writing `custom_check` and a missing
`aec run-script` target succeeds and the sentinel never appears; the
registered payload committed in an unrelated tracked repo is not adopted
and survives `aec uninstall`; a registry record with an empty or duplicate
hook id fails the freshness test; removing a record and its committed
entry while the item still ships the hook, then running `verify --repair`
with no refresh first, reports nothing and reinstalls nothing; an adopted
hook whose `repo_has` predicate goes false then true is retracted and then
re-rendered by refresh and repair; `verify` on an adopted item whose
new version adds an unadopted hook with a missing script still reports the
adopted entry STALE and repair fixes it; the registry/committed-entry freshness
test above.

## Affected surfaces

`aec/data/prewired-hooks.json`, `scripts/render-prewired-hooks.py`,
`aec/lib/hooks/installer.py` (+ `translate_to_agent` filter), `aec/lib/catalog_hooks.py`,
`aec/lib/hooks/lifecycle.py`, `aec/lib/hooks/state.py`, `aec/lib/hooks/drift.py`, `aec/lib/hooks/schema.py`; tests in `tests/test_catalog_hooks.py` and the
installer tests (fresh clone with committed entry → refresh adopts, no
duplicate; an unregistered item stays untouched;
uninstall removes an adopted entry; a hand-edited, non-matching entry is left
alone) and `tests/test_prewired_hooks.py`.
