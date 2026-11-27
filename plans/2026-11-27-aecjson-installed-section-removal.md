# Remove the installed-versions section from a repo's `.aec.json`; the manifest is the one record

**Status:** planned. Scheduling pending.
**Priority:** P3 - Everything else (tier set by the project manager on the intake row, 2026-11-22). A stale version shown to a
reader (a downstream reporter showed 1.3.0 against an installed 1.4.7) is a wrong fact, not a crash. No merge gate depends on it.
**Decision:** Option B approved 2026-11-27 (reversible tooling design).

**Incumbent (checked 2026-11-27):** the v2 manifest already records every install per scope. `record_install`
(`aec/lib/manifest_v2.py:97`) writes `manifest["repos"][<repo path>][<type>][<name>]` with version and content hash, and
`aec install` calls it (`aec/commands/install_cmd.py:~346`). A second record, the repo's `.aec.json` `installed` section, is written
only by `update_installed_section` (`aec/lib/aec_json.py:113`) through `_sync_installed_section` (`aec/commands/repo.py:872`, run by
`aec repo setup/sync`). That writer copies the GLOBAL manifest section, so it cannot describe a repo's own installs. Nothing new is
built here; a duplicate is removed.

## Problem

1. `aec install` never writes `.aec.json`; `aec repo setup/sync` copies the global list into it. The section is therefore a stale copy of a
   different scope. Of 30 local repos with a `.aec.json`, 12 have an empty section and 18 hold 7 to 24 entries copied from global.
2. The only reader of the project-scope section is `aec discover` (`aec/commands/discover_catalog.py:190`), which uses it to skip items
   already tracked. With a copied global list it skips the wrong things.
3. Anything outside aec that reads `.aec.json` for versions (a downstream version reporter) shows the copied value.

## Decision

Option B. `.aec.json` stops carrying installed versions. The v2 manifest's per-repo scope is the single record. Option A (install also
writes the repo entry) was rejected: it adds a second writer to keep in step with the manifest, and the section is already drifting.

## Correct fix

1. **Confirm and enumerate (first, before any code).** Confirm `manifest["repos"][<path>]` is populated by every install path
   (`aec install`, `aec upgrade`, `aec uninstall`, `aec repo setup`, vendored copies). Grep every reader and writer of the
   `.aec.json` `installed` key across `aec/`, `tests/`, `docs/`, schema files and templates, and ask the downstream reporter owner how it
   reads versions. Report the punch list in the PR body. If a path fails to record per repo scope, fix that first; this plan then has a
   step 0.
2. **Reader.** Make `aec discover` (project scope) read the manifest's repo scope instead of `.aec.json`. Keep the global branch as is.
   Test: a repo with one install in `manifest["repos"][path]` and a different list in the global scope is discovered correctly.
3. **Writer.** Delete `_sync_installed_section` and `update_installed_section`, and stop `aec repo setup/sync` from writing the
   section. Test: `aec repo sync` leaves a `.aec.json` without an `installed` key.
4. **Schema.** Drop `installed` from the skeleton (`create_skeleton`) and from any schema doc. `load_aec_json` ignores an `installed`
   key in an existing file (no error), so old files keep loading.
5. **Migration.** One step in `aec migrate` (or `aec repo sync`) that removes the stale `installed` section from tracked repos' `.aec.json`,
   reports how many were changed, and is idempotent. Never touches anything else in the file. Test: file with `installed` loses only that key.
6. **Reporter.** `aec list` already prints a repo's items from the manifest (`--scope local`, `aec/commands/list_cmd.py`) but has no
   `--json` output (checked 2026-11-27). Add `--json` to it so a machine reader gets a repo's installed items and versions. Name the consumer (a downstream version reporter) in the PR so its owner switches.
7. **Docs.** Update the `.aec.json` reference and CHANGELOG; state that installed versions live in the manifest.

## Affected surfaces

`aec/lib/aec_json.py`, `aec/commands/repo.py`, `aec/commands/discover_catalog.py`, `aec/commands/migrate*.py`, `aec/commands/list_cmd.py`,
the `.aec.json` docs and tests; one external reader (a downstream version reporter). No catalog, hook or skill content changes.

## Done when

No code path writes or reads `.aec.json` `installed`; `aec discover` agrees with the manifest in a repo whose global scope differs; the
migration has run on this machine's repos with the count reported; the downstream reporter reads the manifest value (its own PR).

## Stopgap (until step 6 lands)

The per-type installed store is global only, so it cannot give a repo's version, and `aec list` has no `--json` yet. Until step 6, read
`manifest["repos"][<repo path>]` from the v2 manifest file, or parse `aec list --scope local` text output.
