# Remove the installed-versions section from a repo's `.aec.json`; the manifest is the one record

**Status:** planned. Scheduling pending.
**Priority:** P3 - Everything else. A stale version shown to a
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
   different scope. Any repo that ran `aec repo setup/sync` carries entries copied from global.
2. The only reader of the project-scope section is `aec discover` (`aec/commands/discover_catalog.py:190`), which uses it to skip items
   already tracked. With a copied global list it skips the wrong things.
3. Anything outside aec that reads `.aec.json` for versions (a downstream version reporter) shows the copied value.

## Decision

Option B. `.aec.json` stops carrying installed versions. The v2 manifest's per-repo scope is the single record. Option A (install also
writes the repo entry) was rejected: it adds a second writer to keep in step with the manifest, and the section is already drifting.

## Correct fix

Order matters: consumers move first, the reader is repointed second, and the data and the writer are removed last.

1. **Confirm and enumerate (first, before any code).** Confirm which paths record `manifest["repos"][<path>]`. Reviewed 2026-11-27:
   modern `aec install`, `upgrade` and `uninstall` do; the legacy `skills.py` path writes `installed-skills.json` instead, and
   `aec repo setup` copies instruction and rule files without recording them. Decide per path: record it per repo scope, or retire it
   (step 0 if recording is needed). Sweep every reader and writer of the `installed` key; found so far: `create_skeleton` (a writer),
   `_sync_installed_section`, `update_installed_section`, its re-export in `aec/lib/__init__.py` (import and `__all__`),
   `discover_catalog.py`, assertions and fixtures in `test_aec_json.py`, `test_setup_integration.py`, `test_discover_catalog_cmd.py`
   and `test_dismissals.py`, plus `docs/users/aec-json.md`. Ask the downstream reporter owner how it reads versions. Report the punch
   list in the PR body.
2. **Reporter first (consumer cutover is a prerequisite).** Incumbent: `aec export` already serializes scoped names and installed
   versions as JSON (`export_cmd.py`, `portable_manifest.py`). Evaluate it first: if it gives a repo's items and versions, document it
   as the machine interface and add nothing. Only if a capability is missing (per-repo filter), add `--json` to `aec list`
   (`--scope local` already prints a repo's items from the manifest) and say what `export` lacks. The downstream reader switches
   before step 5 ships; the PR names that consumer.
3. **Reader.** Make `aec discover` (project scope) read the manifest's repo scope instead of `.aec.json`. Keep the global branch.
   Test: a repo with one install in `manifest["repos"][path]` and a different list in the global scope is discovered correctly.
4. **Writer and schema.** Delete `_sync_installed_section`, `update_installed_section` (and remove its `aec/lib/__init__.py` import and
   `__all__` entry, then check the remaining exports import cleanly), stop `create_skeleton` and `aec repo setup/sync` writing the
   section. `load_aec_json` ignores an `installed` key in an existing file. Test: `aec repo sync` and a fresh skeleton leave a
   `.aec.json` without `installed`.
5. **Migration (never loses the only record).** For each tracked repo with an `installed` section: first reconcile against
   `manifest["repos"][resolved path]`; entries the manifest already has are dropped, entries it lacks (missing or partial scope, moved
   repo) are kept and reported as `unresolved`, never deleted. Parse strictly: invalid JSON means no write and a reported error
   (`load_aec_json` substitutes a skeleton for malformed JSON, so the migration must not reuse it for writing). Write atomically and
   preserve every other field. Idempotent; reports changed, kept and failed counts. Tests: moved repo, missing scope, symlink alias,
   distinct worktree scopes, hand-edited extra fields preserved, malformed file untouched, second run changes nothing.
6. **Docs.** Update `docs/users/aec-json.md`, the reference and CHANGELOG; state that installed versions live in the manifest.

## Affected surfaces

`aec/lib/aec_json.py`, `aec/lib/__init__.py`, `aec/commands/repo.py`, `aec/commands/discover_catalog.py`, `aec/commands/migrate*.py`,
`aec/commands/list_cmd.py` or `export_cmd.py`, the tests named in step 1 and `docs/users/aec-json.md`; one external reader (a downstream
version reporter). No catalog, hook or skill content changes.

## Done when

No code path writes or reads `.aec.json` `installed`; `aec discover` agrees with the manifest in a repo whose global scope differs; the
migration acceptance tests in step 5 pass and a run on a fixture repo set reports changed, kept and failed counts; the downstream reporter
reads the manifest value (its own PR) before the migration is released.

## Stopgap (until step 2 lands)

The per-type installed store is global only, so it cannot give a repo's version. Until step 2, read `manifest["repos"][<repo path>]`
from the v2 manifest file, parse `aec list --scope local` text, or use `aec export` if it covers the repo.
