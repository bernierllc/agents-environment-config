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
   **The copy must also keep the release's own hidden files.** `place_installed_item` copies with
   `shutil.ignore_patterns(".*")` (`aec/lib/filesystem.py`), which drops every hidden path from the source, so an
   accepted upgrade of an unchanged copy would delete a dotfile or dot-directory that the release itself ships
   (the file list above includes it, so the check passes). The fix changes the copy to carry the release's hidden
   paths (copy the full source tree, excluding only VCS and cache entries such as `.git`, `.DS_Store`,
   `__pycache__`, named explicitly), so replacing a destination never loses a file the canonical release contains.
   **One gate, at the real chokepoint.** `_install_single_item` is not the one writer: the directory replacement
   happens in `place_installed_item` (`aec/lib/filesystem.py`, "the one write chokepoint"), which is called from
   `_install_single_item` (`install_cmd.py`), from `aec/commands/upgrade.py` directly (the main item, and the
   dependency upgrade and install paths), and from `aec/lib/global_install_prompt.py`. The provenance gate therefore
   lives in `place_installed_item`, so `aec upgrade` (including dependencies), `aec update`, the declarative
   `aec apply` (`plan_apply` classifies a vendored skill with no manifest row as `install`, and `execute_apply`
   calls `_install_single_item(..., yes=True)`, which today replaces the directory unchecked) and the global
   migration all pass through it, and a new caller cannot bypass it. A dependency whose directory already exists as
   a state-less vendored fork is classified `to_install` by `resolve_install_graph`; the gate sees that destination
   too. `yes=True` means "no prompt", never "skip provenance": a non-canonical, unknown, modified or forked
   destination is reported and left untouched unless the caller passes an explicit overwrite/adopt confirmation.
   **Preflight before any delete, mirroring `check_install_paths`.** The gate is a function
   (`check_install_provenance`, beside `check_install_paths` in `aec/lib/filesystem.py`) that `place_installed_item`
   always runs before it deletes anything, and that every caller which deletes something of its own first runs
   too, ahead of those deletions. `migrate_item_to_global` (`aec/lib/global_install_prompt.py`) removes every
   per-repo copy and its manifest rows before it reaches `place_installed_item`; it must call the preflight for the
   global destination (and `replaces`) before that loop, so a refusal loses nothing, exactly as the existing
   `check_install_paths` call there already guarantees for path escapes. The same applies to any other caller that
   removes or rewrites state before placing; the per-caller enumeration records which ones do.
   The gate only applies when the destination exists and is not already an AEC-tracked install (a normal
   re-install over a tracked copy keeps its current behaviour); the first implementation step is to enumerate every
   `place_installed_item` caller and state, per caller, whether its destination can be a vendored copy.
4. Never say "(up to date)" for a scope it did not check: when vendored copies exist and the check cannot run,
   the summary names what was skipped and the command that fixes it (`aec doctor` fails loudly on the same
   condition).

## Tests

- A repo with a vendored skill one version behind: `outdated` lists it, `upgrade` updates it, a second run is
  clean.
- `aec outdated` itself (not only the `update` summary) lists the vendored copy.
- Cross-repo: the stale vendored-only skill sits in a tracked repo other than the current one, with no manifest row
  for it. `aec upgrade` from the current repo reaches that repo: `_find_outdated_repos` (`aec/commands/upgrade.py`)
  currently examines manifest entries only, so it must also return a repo whose only stale item is a vendored copy
  before `_upgrade_scope` runs on it. The test fails if `outdated --all` lists it and `upgrade` skips it.
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
- Canonical hidden file: a release that ships a dotfile or a file under a dot-directory, vendored unchanged one version
  behind: the upgrade succeeds and the hidden file is still present afterwards (and a fresh install of that release
  carries it too). Excluded VCS and cache entries are not copied.
- `aec apply` (declarative path), one test each for a vendored skill that is: canonical (upgraded), unknown version
  (reported, untouched), locally modified (reported, untouched), and a clean committed fork (reported, untouched,
  `yes=True` notwithstanding). A test also pins that `execute_apply` reaches the same gate as `aec upgrade`, so a
  new caller of `place_installed_item` cannot bypass it.
- Dependency collision: upgrading a skill that introduces a dependency whose directory already exists as a
  state-less vendored fork (classified `to_install`): the dependency write is gated, the fork is reported and
  left untouched, and the same for a dependency upgrade path in `aec/commands/upgrade.py`. A test enumerates every
  `place_installed_item` caller (including `global_install_prompt.py`) so a caller added later must pass it.
- Global migration collision: the global destination already holds a state-less vendored fork and per-repo copies
  of the same skill exist. The provenance refusal happens before the per-repo copies are deleted: every per-repo
  copy, the manifest rows and the fork are all unchanged afterwards, and the refusal is reported.
- A repo with no vendored copies: unchanged output.
- `doctor` exits non-zero and names the fix when a vendored copy is stale.

## Affected surfaces

`aec/commands/update.py`, `aec/commands/outdated.py`, `aec/commands/upgrade.py` (including `_find_outdated_repos`),
`aec/lib/filesystem.py` (`place_installed_item`, its copy of hidden release files, and the `check_install_provenance` preflight, the gate), `aec/commands/install_cmd.py` (`_install_single_item`),
`aec/lib/global_install_prompt.py`, `aec/lib/apply_core.py`,
`aec/lib/catalog_hashes.py`, `aec/lib/skills_manifest.py`, the release/catalog generation step, `aec/commands/run_doctor.py`
(or its equivalent), docs for `outdated` / `upgrade`.
