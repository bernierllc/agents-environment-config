# Org-config plugin governance

Status: proposed (not yet placed on ROADMAP — gating to controller)
Priority: P2 (correctness gap, silently drops a config block; no data loss)
Discovered: 2026-06-25, adversarial review of `feature/plugin-management-loadout-schema` (Finding G)

## Root cause

`aec/lib/org_config/schema.py:24` defines `ITEM_TYPES = ("skills", "rules",
"agents", "mcps")` — `plugins` is absent. Every org-config consumer iterates
this tuple, so an org policy that declares an `items.plugins` block is parsed
into nothing and **silently ignored**: it is never validated, never surfaced in
effective policy, never flagged in conflicts/propagation, and never applied.

`RESERVED_SOURCE_IDS` (same file, lines 16-21) likewise lacks
`aec.default.plugins`, so even if a plugins block were read, a policy referencing
the canonical default plugin source would fail source validation.

## Why this is NOT a one-line fix

Adding `"plugins"` to `ITEM_TYPES` (+ `aec.default.plugins` to
`RESERVED_SOURCE_IDS`) is clean for the *read* side — `validator.py:113`,
`effective.py:118/158`, `conflicts.py:77/106`, `propagation.py:80/212` all loop
generically over `ITEM_TYPES` with guarded `.get(...)`, so they would honor a
plugins block with no further change.

But the **apply** side does not loop generically and does not model plugins:

- `apply.py:71` `_PLURAL_TO_SINGULAR` maps only the four file-copy types.
  `compile_desired_items` (apply.py:85) and `blocked_item_keys` (apply.py:100)
  index `_PLURAL_TO_SINGULAR[plural]` directly — an `items.plugins` policy with
  an install/blocked stance would raise **`KeyError`**, turning today's silent
  drop into a hard crash during `aec org apply`. That is strictly worse.
- `apply.py:163` `_catalog` hardcodes `("skills","rules","agents","mcps")` for
  catalog discovery; plugins use `discover_available(d, "plugins")` →
  `_discover_available_plugins` (loadout manifests), a different shape.
- `apply_core.py` `TYPE_TO_PLURAL` has no `plugin` entry, and the
  `DesiredItem`/`plan_apply`/`execute_apply` pipeline assumes file-copy
  semantics (`installed_dst_path`, `version_is_newer`, per-type `*_dir`).
  Plugins install through a separate engine: `install_plugin` (loadout manifest,
  `plugins.execution` policy with the never-auto-install / instructions-only
  guarantee, marketplace/per-tool/external branches) + `record_plugin_install`.
  That engine already runs in `apply_cmd._apply_plugins`, but is **not** wired
  into the org-config applier.

So honoring `items.plugins` end-to-end means giving org-config its own plugin
apply pass, not extending a tuple.

## Correct fix

1. `schema.py`: add `"plugins"` to `ITEM_TYPES` and `"aec.default.plugins"` to
   `RESERVED_SOURCE_IDS`. (Read side now honors the block.)
2. `apply.py`: stop using `_PLURAL_TO_SINGULAR` as a total map for plugins.
   Split plugin policies out of `compile_desired_items`/`blocked_item_keys` and
   route them through a new `_apply_org_plugins(policy, scope, ...)` that mirrors
   `apply_cmd._apply_plugins`: discover loadout catalog, resolve
   `plugins.execution` pref, call `install_plugin` (instructions-only honored —
   see this branch's Finding A fix), and `record_plugin_install`. Blocked-stance
   plugins route to `uninstall_plugin` via `run_uninstall("plugin", ...)`.
3. `_catalog`: discover the `plugins` catalog alongside the four file types
   (guarded by source-dir existence, same as the others).
4. Decide stance semantics for plugins: `pinned`/`required`/`recommended` →
   install-intent; `blocked` → uninstall; `silent` → record-only. Document in
   the org-config schema doc.

## Affected surfaces

- `aec/lib/org_config/schema.py` (ITEM_TYPES, RESERVED_SOURCE_IDS)
- `aec/lib/org_config/validator.py` (generic — no change beyond schema)
- `aec/lib/org_config/effective.py` (generic — no change beyond schema)
- `aec/lib/org_config/conflicts.py` (generic — no change beyond schema)
- `aec/lib/org_config/propagation.py` (generic — no change beyond schema)
- `aec/lib/org_config/apply.py` (new plugin apply pass; `_PLURAL_TO_SINGULAR`
  and `_catalog` must stop assuming four file-copy types)
- `aec/lib/apply_core.py` (only if plugins are forced into DesiredItem; the
  plan deliberately keeps them on the separate `install_plugin` engine instead)
- `docs/loadout/schema/` / org-config schema doc (stance semantics for plugins)
- Tests: org-config apply test proving an `items.plugins` policy installs via
  the loadout engine and honors `plugins.execution=instructions-only`, plus a
  conflicts/effective test proving the block is surfaced (not dropped).

## Test that should exist (proves the gap)

An org config with `items.plugins.<name>` at stance `required` currently yields
zero effect from `apply_org_policy`. The regression test asserts the plugin is
recorded in the installed manifest after apply, and that with
`plugins.execution=instructions-only` nothing executes (no runner calls).
