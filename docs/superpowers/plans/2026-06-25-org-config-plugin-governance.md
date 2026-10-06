# Org-config plugin governance

Status: in progress (revised 2026-10-06; implemented on `feat/org-plugin-governance`)
Priority: P2 (correctness gap, silently drops a config block; no data loss)
Discovered: 2026-06-25, adversarial review of `feature/plugin-management-loadout-schema` (Finding G)
Revised: 2026-10-06 — plugin versioning moved to Claude Code (#85, #87); see "What changed since 2026-06-25".

Related: `2026-10-06-plugin-parity-other-agents.md` (non-Claude agents).

## Root cause

`aec/lib/org_config/schema.py` defines `ITEM_TYPES = ("skills", "rules",
"agents", "mcps")` — `plugins` is absent. Every org-config consumer iterates
this tuple, so an org policy that declares an `items.plugins` block is parsed
into nothing and **silently ignored**: never validated, never surfaced in
effective policy, never flagged in conflicts/propagation, never applied.

`RESERVED_SOURCE_IDS` likewise lacks `aec.default.plugins`, so a policy
referencing the canonical default plugin source would fail source validation.

## What changed since 2026-06-25

- **Claude Code owns marketplace plugin versions (#87).** AEC records what
  `claude plugin update` / `claude plugin list` reports via
  `claude_plugins.installed_record()`, not the catalog pin. A policy cannot pin a
  marketplace plugin to a version AEC does not control.
- **Plugin ids are `name@marketplace`** for marketplace plugins (loadout
  validator + `plugin.schema.json`).
- **Execution guards are shared.** `claude_plugins.commands_blocked()` and
  `plugins.execution=instructions-only` gate update, upgrade and apply.
- **Marketplace plugins declare an uninstall** (`claude plugin uninstall <id>`)
  as a `tools` block, so `uninstall_plugin` handles the blocked stance.
- `aec apply` plugin handling now lives in `apply_cmd._apply_plugins`
  (`install_plugin` + `installed_record` + `record_plugin_install`).

## Why this is NOT a one-line fix

Adding `"plugins"` to `ITEM_TYPES` is clean for the *read* side
(`validator.py`, `effective.py`, `conflicts.py`, `propagation.py` loop
generically over `ITEM_TYPES`). The **apply** side does not:

- `apply.py` `_PLURAL_TO_SINGULAR` maps only the four file-copy types;
  `compile_desired_items` and `blocked_item_keys` index it directly, so an
  `items.plugins` policy would raise **`KeyError`** — strictly worse than the
  silent drop.
- `_catalog` hardcodes the four file-copy types; plugins use
  `discover_available(d, "plugins")` (loadout manifests).
- The `DesiredItem`/`plan_apply`/`execute_apply` pipeline assumes file-copy
  semantics. Plugins install through a separate engine (`install_plugin`).

So honoring `items.plugins` means giving org-config its own plugin apply pass.

## Decisions

1. **Stances for plugins:** `required`/`recommended` → install-intent;
   `blocked` → uninstall; `silent` → record-only (as for other types).
2. **`pinned` and `version` are rejected for plugins** at validation
   (`items.plugins.<id>`): the agent's plugin manager owns versions, so a pin
   cannot be honored and must not be silently downgraded. Error names the fix
   (use `required`).
3. **Policy keys are the catalog plugin name** (`ponytail`), matching
   `plugins/<name>/plugin.json`; the apply pass resolves the `name@marketplace`
   id from the manifest.
4. **Reuse, don't reimplement:** the apply pass calls the same
   `install_plugin` / `uninstall_plugin` / `installed_record` /
   `record_plugin_install` used by `aec apply`, with the same
   `plugins.execution` preference (instructions-only never runs anything).

## Correct fix

1. `schema.py`: add `"plugins"` to `ITEM_TYPES`, `"aec.default.plugins"` to
   `RESERVED_SOURCE_IDS`.
2. `validator.py`: reject `stance: pinned` and a `version` field under
   `items.plugins`.
3. `apply.py`: split plugin policies out of `compile_desired_items` /
   `blocked_item_keys` (no `KeyError`); new `apply_plugins(policy, scope, ...)`
   installs install-intent plugins and uninstalls blocked ones through the
   loadout engine; wire into `apply_org_policy`. `_catalog` discovers the
   `plugins` catalog.
4. Docs: org-config schema doc gains plugin stance semantics.

## Affected surfaces

- `aec/lib/org_config/schema.py`, `validator.py`, `apply.py`
- `aec/lib/org_config/effective.py`, `conflicts.py`, `propagation.py` (generic —
  no change beyond schema)
- `aec/lib/apply_core.py` — **unchanged**: plugins stay off the file-copy
  pipeline on purpose
- org-config schema doc
- Tests (real manifest + fake runner, no mocks of our own code):
  - an `items.plugins.<name>` `required` policy records the plugin in the
    installed manifest after apply
  - `plugins.execution=instructions-only` → runner never called
  - `blocked` plugin installed → uninstalled, record removed
  - `pinned` / `version` on a plugin → validation error
  - effective policy / conflicts surface the plugins block (not dropped)

## Punch list (contract change)

Writers of org policy: `aec org` commands, org-config docs/examples, test
fixtures. Grep each for `items:` blocks before closing.
