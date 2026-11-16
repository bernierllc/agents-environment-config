# `aec upgrade` must detect and upgrade vendored skill copies

Status: planned. Scheduling pending (Tracker row, Owner `Needs-PM`).

## Problem

`aec outdated` / `aec upgrade` print "(up to date)" for a repo whose committed (vendored) skill copies are
stale. Vendored skills are not in the manifest's per-repo (Local) list, so neither `_report_scope_outdated`
(`aec/commands/update.py`) nor `_print_outdated` (`aec/commands/outdated.py`, the `aec outdated` command itself)
ever compares them with the source version. A downstream repo carried an old `pr-merge-flow` (1.3.0) while the
global copy was 1.4.1; its merge guard lacked a fix the newer version had, and misfired for days while AEC
reported everything current.

## Root cause

The "up to date" verdict is computed from the install manifest only, in two independent places
(`_report_scope_outdated` in `aec/commands/update.py` and `_print_outdated` in `aec/commands/outdated.py`) and in
`aec/lib/apply_core.py`. A skill that was copied into a repo (committed, or installed by a teammate)
has no manifest row on this machine, so it is invisible to the comparison. Silence reads as success.

## Correct fix (rung 1, then rung 3 of the "remembering is a failure mode" ladder)

1. Detect vendored copies: for each tracked repo, find skill directories under the agent skill roots that carry
   a version (frontmatter `version` or the skill's own version file) and match a name AEC ships. Verify the
   exact version source before coding; do not guess a layout.
2. `aec outdated` (`_print_outdated`) and the `aec update` summary list them as their own scope ("vendored in
   <repo>") with installed vs available version.
3. Provenance before any write: a vendored copy is treated as AEC-owned only when its content hash matches the
   canonical hash of the release version it claims (the same hashing the catalog uses). That history must ship
   with AEC: today `generate_catalog_hashes` (`aec/lib/catalog_hashes.py`) stores only the current
   `{version, contentHash}` per item and `build_skill_manifest_item` (`aec/lib/skills_manifest.py`) builds
   `versionHashes` only from this machine's earlier installs, so a teammate's or fresh machine's vendored 1.3.0
   has no hash to match. Ship a version-indexed hash history per item in the catalog (each release appends its
   `{version: [contentHash, ...]}`, backfilled once from the tagged releases) and have the provenance check read it,
   not the local manifest. The value is a set, not a single hash: contents can change without a frontmatter version
   bump (`incremental_update` rewrites `contentHash` in that case), so several releases may legitimately carry
   different hashes under one declared version, and a single-value map would drop all but one of them and reject a
   genuine copy as a fork. A copy matches when its hash is any member of its version's set. A version absent from
   the shipped history is reported as unknown, never upgraded. A clean git tree proves
   only that the copy matches the repo's HEAD, not that it came from AEC, so a committed fork with the same name
   and an older version is reported as "differs from <version>" and is never overwritten without explicit
   adoption/overwrite confirmation. Only a hash-matching, clean copy is upgraded in place (a dirty one is
   reported, never overwritten), and then the manifest row is written so the next run is a normal comparison.
   **The hash alone is not the provenance test.** `hash_skill_directory` deliberately excludes every hidden path
   (dotfiles and anything under a dot-directory), while a replacement deletes the whole destination directory, so a
   fork whose only change is a hidden file would hash as canonical and lose that file. The provenance check is
   therefore hash match AND a complete-tree check: the shipped history stores, per released hash, the file list of
   that release (hidden paths included), and the destination's full tree (hidden entries included) must contain
   nothing outside that list. Any extra path is reported as "local additions: <paths>" and blocks the overwrite
   without explicit confirmation; the install never deletes a path that was not in the canonical tree.
   **One gate, in the one writer.** The provenance gate lives in the function that writes a skill directory
   (`_install_single_item` in `aec/commands/install_cmd.py`), not in each caller, so `aec upgrade`, `aec update` and the declarative `aec apply`
   (`plan_apply` classifies a vendored skill with no manifest row as `install`, and `execute_apply` calls
   `_install_single_item(..., yes=True)`, which today replaces the directory unchecked) all pass through it. `yes=True`
   means "no prompt", never "skip provenance": a non-canonical, unknown, modified or forked destination is reported
   and left untouched unless the caller passes an explicit overwrite/adopt confirmation.
4. Never say "(up to date)" for a scope it did not check: when vendored copies exist and the check cannot run,
   the summary names what was skipped and the command that fixes it (`aec doctor` fails loudly on the same
   condition).

## Tests

- A repo with a vendored skill one version behind: `outdated` lists it, `upgrade` updates it, a second run is
  clean.
- `aec outdated` itself (not only the `update` summary) lists the vendored copy.
- A vendored copy with local edits: reported, not overwritten.
- Fresh machine with no manifest history and a vendored copy that matches a shipped historical hash (for example
  the previous release): upgraded. The same copy with a version missing from the shipped history: reported as
  unknown, not upgraded.
- The release/catalog generator appends each release's hash to the version's set and never drops an earlier
  entry (a test fails if a prior version's hash disappears).
- Two released contents carrying the same declared version (no version bump between releases): both hashes are in
  the shipped set, and a vendored copy matching either one is upgraded, not reported as a fork.
- A clean, committed fork with the same name and an older version but a different content hash: reported, not
  overwritten without explicit confirmation.
- Hidden-file fork: a copy whose only difference from the canonical release is an added dotfile, a modified dotfile
  or a file under a dot-directory: reported as "local additions", not overwritten, and the file survives.
- `aec apply` (declarative path), one test each for a vendored skill that is: canonical (upgraded), unknown version
  (reported, untouched), locally modified (reported, untouched), and a clean committed fork (reported, untouched,
  `yes=True` notwithstanding). A test also pins that `execute_apply` reaches the same gate as `aec upgrade`, so a
  new caller of `_install_single_item` cannot bypass it.
- A repo with no vendored copies: unchanged output.
- `doctor` exits non-zero and names the fix when a vendored copy is stale.

## Affected surfaces

`aec/commands/update.py`, `aec/commands/outdated.py`, `aec/commands/upgrade.py`,
`aec/commands/install_cmd.py` (`_install_single_item`, the gate), `aec/lib/apply_core.py`,
`aec/lib/catalog_hashes.py`, `aec/lib/skills_manifest.py`, the release/catalog generation step, `aec/commands/run_doctor.py`
(or its equivalent), docs for `outdated` / `upgrade`.
