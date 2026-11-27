# MCP launcher catalog items: a stdio bridge installs, registers and updates through `aec upgrade`

**Status:** planned. Scheduling pending.
**Priority:** high. A hand-run install script sat stale on a machine after two merged fixes, and nothing said so.
**Tracker id:** AEC-MCP-LAUNCHER-ITEM.

**Incumbent (checked 2026-11-27):** AEC already has an `mcp` item type (`aec/lib/apply_core.py` `_apply_mcp`, `aec/lib/mcp_settings.py`,
`mcp-servers/<name>/mcp.json`). It cannot carry a launcher bridge, for the reasons under Problem. This plan extends that type and
adds no second install path. Nothing else in AEC provides a check that a registered MCP server's installed launcher matches its source.

## Problem

An MCP server can be a small launcher script (a stdio bridge that reads a key from a file and execs a remote-MCP proxy) that must exist on
disk and be registered with each agent client. Today that is a repo-owned script run by hand on each machine. A fix merged to the script
does not reach any machine until someone remembers to re-run it; in the observed case the installed copy was stale after two merged fixes.

Why the existing `mcp` item type cannot replace the hand-run script (verified in code, 2026-11-27):

1. **It installs no files.** `_apply_mcp` runs `pip install` for `install.pip` and writes `mcpServers.<name>` entries. A launcher script
   has nowhere to come from, so the entry would point at a file that is not there.
2. **It registers with Claude Code only.** `get_settings_path` returns `~/.claude/settings.json` (or the repo's `.claude/settings.json`).
   Codex (`codex mcp add`) and Cursor (`~/.cursor/mcp.json`) are never written, although the script registers all three.
3. **It never upgrades on a version bump, through any public command.**
   - `aec update` only fetches and reports (`aec/commands/update.py`); it takes no options and applies nothing.
   - `aec upgrade [--yes] [--dry-run]` (`aec/commands/upgrade.py` `_upgrade_scope`) has its own version loop that never calls `plan_apply`
     or `_apply_mcp`. It treats an `mcp` item like a file tree: `_target_base` falls through to the rules directory, the generic branch copies
     the `mcp-servers/<name>` directory there, and no client registration is written.
   - `plan_apply` (used by `aec apply` and `aec org apply`) computes `newer` only `if item.item_type != "mcp"`; an `mcp` item whose catalog
     version differs lands in the `noop` branch with reason "installed differs from catalog; keeping". Its equal-version branch also returns
     `noop` before any content comparison could run.

   So "installs update" is false for every `mcp` item through every route.
4. **It cannot say a key is missing.** A launcher without its key exits at start, so replacing a working entry (for example an OAuth one)
   with it breaks the client. The script guards this with a `--has-key` probe that prints nothing; the `mcp` type has no equivalent gate and
   writes the entry unconditionally.

Also missing, and not fixable by installing: nothing detects that a client is still running an older launcher after the file was replaced.

## Root cause

The `mcp` item type models "a package plus a settings entry", and a launcher bridge is "a file plus entries in several clients, gated on a
key, with processes that outlive the file". On top of that, "apply an `mcp` item" has no single owner: `install_cmd._install_mcp`,
`apply_core._apply_mcp` and the generic branch of `upgrade._upgrade_scope` each do part of it and disagree, and `aec update` only reports a
newer catalog version (`_report_scope_outdated`), never same-version content, registration or installed-state drift. The staleness is the compound of an install path that cannot update, no single owner of the apply, and the absence of a drift check.

## Correct fix

Each behavior lives in the one component that owns it; callers call. The launcher script itself stays in its owner's catalog source, never
in AEC core (the generic mechanism lands here; a specific bridge is just one item in some source).

**One apply engine.** `apply_core._apply_mcp` (extracted to `aec/lib/mcp_apply.py` if it outgrows the file) is the only code that installs,
registers, upgrades or removes an `mcp` item. `aec install mcp`, `aec apply`, `aec org apply` and `aec upgrade` all call it; none
re-implements any part of it. Its result is the existing `ApplyResult` (`applied` / `skipped` / `errors`), and every caller maps a non-empty
`errors` to a non-zero exit.

### 1. Extend the `mcp.json` schema (aec, `aec/lib/mcp_settings.py` and the catalog validators)

Optional keys, all backwards compatible (an existing `mcp.json` is unchanged):

- `files`: list of `{ "src": <path in the item dir>, "dest": <path under the user's home>, "mode": "0755" }`.
  - `src` must stay inside the item directory: no `..`, no absolute path, no symlink component; rejected at validation and again at apply.
  - `dest` must be a normalized path under `$HOME` with no `..`. Validation alone is not confinement; the filesystem boundary is enforced at
    write time (step 2).
  - An item that declares `files` is global-scope only in this version (a global file shared by repo-scoped installs would let two
    repositories overwrite or remove each other's launcher). A repo-scoped install of such an item is rejected before any mutation.
- `clients`: subset of `claude`, `codex`, `cursor`; default `["claude"]` (the client an existing item targets today, now registered through the client; see the legacy migration in step 2).
- `requires_key`: `{ "file": <path under home>, "var": <env var NAME> }`. Names only: the value is never read into AEC output, logs or the
  manifest. The gate asks the launcher (`<launcher> <target> --has-key`, exit 0/1, prints nothing) when the item declares `files`; otherwise it
  tests that the file defines the variable in a subshell and discards output.
- `check`: optional read-only command (exit non-zero on drift) used by the doctor check and the SessionStart adapter in step 4.

### 2. Apply: files, per-client registration, key gate (aec, the one apply engine)

**Scope first, before any mutation.** Resolve the target scope (`DesiredItem.scope`: global or a repository) and validate the whole item
against it; reject unsupported combinations with a clear message and no partial writes:

| Client | Global scope | Repository scope |
|---|---|---|
| `claude` | `claude mcp add -s user` (Claude Code stores user registrations in `~/.claude.json`) | `claude mcp add -s project` (the repository's `.mcp.json`), never the user scope |
| `cursor` | `~/.cursor/mcp.json`, atomic JSON replace preserving file mode | the repo's `.cursor/mcp.json`, same replace semantics |
| `codex` | `codex mcp add/get/remove` | not supported: rejected before mutation (Codex registrations are user-global) |

Readback, snapshot-and-restore and removal are scope-aware per client and touch only the entry for that scope. A repository-scoped apply
never reads, writes or removes a global registration, and one repository's apply never touches another's. Claude readback is client-backed
(`claude mcp get <name>` resolved for that scope), not a JSON assertion on a file the client may not read.

**Legacy Claude registrations move to the supported locations.** Today's `write_mcp_server` writes `mcpServers.<name>` into
`~/.claude/settings.json` (or the repo's `.claude/settings.json`), which Claude Code does not document as an MCP registration location, so a
successful install can leave no usable server. The engine stops using it for every `mcp` item, existing items included (the bundled
`jcodemunch` item is one). A legacy manifest record has no fingerprint, so step 3 treats it as drifted once; that upgrade registers through
the client, then removes the old settings entry **only when ownership is provable**. `record_mcp_install` stores no server names or
registration snapshot today (only version, `installedAt`, `package` and source fields), so a legacy record proves nothing about which keys the
old install wrote. The engine therefore removes a legacy `mcpServers.<key>` only when that key is one the current catalog item declares in its
`mcpServers` or equals the item name (the two names `write_mcp_server` could have used for this item), and the entry's content still matches
the catalog's old shape for that key. Any other key it cannot prove it owns (a renamed server, a hand-added entry) is left untouched and
reported by `doctor` as "unrecorded legacy entry `<key>`; remove by hand if unused". Records written from this change on carry the ownership
data (`registrations`: client, scope, server name; plus `files`), so this ambiguity exists for legacy records only. Tests: a legacy record
whose key equals the catalog name is migrated and the old entry removed; a legacy record whose server key differs from the catalog name and
whose new catalog renames that key registers the new name, leaves the unproven old key in place and reports it; a legacy record with an
unknown old key removes nothing; other settings keys are never touched.

**Files, enforced at the mutation boundary** (a validation-time `resolve()` check alone leaves a window for a parent-directory swap):

- Read the source once into memory, hash those exact bytes, and write those bytes. The digest recorded in the manifest is the digest of the
  staged bytes, never a second read of a source that can change mid-copy.
- Open the destination parent directory without following symlinks and pin it (a directory file descriptor); stage with
  `O_CREAT | O_EXCL | O_NOFOLLOW` in that directory, set the mode, then `rename` relative to the pinned descriptor. Fail closed when any
  component of `dest` under `$HOME` is a symlink or changed identity between validation and rename, including the final component (policy:
  AEC never writes through or over a symlink at `dest`; it reports the path and stops).
- Idempotent: skip only when the installed file matches the staged bytes (sha256) **and** the declared mode; a mode-only change rewrites
  (or chmods through the pinned descriptor) so a launcher whose mode went from `0644` to `0755` ends up executable. Record `files: {dest: sha256}` in the
  manifest entry (`record_mcp_install` gains it).
- A failed write never truncates a working launcher (write-beside-and-rename).
- Uninstall applies the same confinement and removes a file only when its sha256 still matches the record.

**Registration and key gate.**

- For each target and each client in `clients`: when `requires_key` is declared and the gate fails, print `SKIPPED, key file missing; existing
  client entries kept` and leave that client's entry alone (mirrors the script's semantics); otherwise register, snapshot-and-restore on a
  failed replacement, and confirm the entry the client resolves is ours before reporting success.
- A SKIPPED target is an `ApplyResult.errors` entry (non-zero exit), never a silent success, so `aec upgrade --yes`, `aec apply` and CI see it.

**One manifest transaction owner.** The engine does not load or save the manifest itself (today `_apply_mcp` does, while `run_upgrade` keeps an
earlier manifest object in memory and saves it unconditionally in `finally`, which would overwrite the engine's new version, fingerprint and
file hashes with stale state). The caller owns the load and the single save; the engine mutates the manifest object it is handed. The
non-MCP writer is the same defect: `execute_apply` has no in-memory manifest, and every item (`_apply_mcp` and, for skills, rules and agents,
`install_cmd._install_single_item`) loads and saves the file by path, so one object saved at the end would overwrite those records. So:
`_install_single_item` takes an optional `manifest` object and, when given, mutates it and does not save (the interactive `aec install` path
passes none and keeps loading and saving as today); `execute_apply` loads once, hands that object to both the MCP engine and
`_install_single_item`, and saves once in a `finally`; `run_upgrade` passes the manifest it already holds. Two writers must never save competing
copies of the same manifest.

**Spec changes retract what the previous record owned.** The manifest entry records every resource the engine created: files (`dest` and
sha256), per-client registrations (client, server name, scope) and the hook. On an upgrade the engine diffs the new spec against that
record before replacing it: a client dropped from `clients`, a renamed server and a changed `dest` have their old registration or file
removed, except a file whose sha256 no longer matches the record (hand-edited), which is kept and reported. The record is replaced only after
the retractions succeed, so a failure leaves the old record intact and re-runnable rather than orphaning resources nothing owns any more.

**Public commands.** The engine only helps if the commands call it:

- `aec upgrade [--yes] [--dry-run]`: in `_upgrade_scope`, an `mcp` item branches to the engine instead of the generic copy (which on its own
  is a bug: it copies the `mcp-servers/<name>` directory into the rules directory). It exits non-zero when the engine reports errors.
- `aec update`: already reports a newer catalog version for an `mcp` item; it additionally reports fingerprint and installed-state drift
  (step 3), so the report and the apply agree; its exit contract is unchanged.
- `aec outdated`, `aec apply`, `aec org apply` and `aec install mcp` (`install_cmd._install_mcp`): same predicate, same engine.

### 3. Upgrade on version, full effective spec and installed state (aec, `apply_core.plan_apply` and discovery)

One predicate, owned by a helper next to `plan_apply` and used by `aec update`, `aec outdated`, `aec upgrade` (including
`upgrade._find_outdated_repos`, which decides which other tracked repositories `aec upgrade --yes` visits and today filters on
`version_is_newer` alone, so drift there would never be repaired) and `aec apply`: an installed
`mcp` item needs an upgrade when **the catalog version is newer (`version_is_newer`), its spec fingerprint differs from the recorded one, or
the engine's installed-state verification fails**.

- **Installed-state verification** (`engine.verify(item)`, read-only): each recorded `files` entry exists with its recorded sha256 and
  declared mode, and each registered client entry resolves to ours for that scope. This is what makes the fix command real: a launcher
  deleted or edited by hand with an unchanged catalog is drift that `aec upgrade` repairs, so `doctor` can honestly recommend it.
  Test detect → recommended command → drift cleared.
- **Fingerprint** = sha256 over the canonical JSON of the whole effective item: version, `mcpServers`, `install`, `clients`, `requires_key`,
  `check`, each `files` entry's `dest` and `mode`, the sha256 of each `files` source, and the item's hook inputs (`hooks.json` and every
  hook script it references), so a hook-only change at the same catalog version still plans a refresh. So a version bump, a changed registration (args,
  clients, key gate, check) or a changed launcher mode upgrades the item even when the launcher bytes are identical. The fingerprint is
  recorded in the manifest entry next to `version`.
- **Placement:** the fingerprint comparison runs before the equal-version shortcut (`if installed_version == avail_version: noop`), and the
  current `item_type != "mcp"` exclusion around `version_is_newer` is removed.
- **Discovery:** `sources._discover_available_mcps` returns only `version`, `description` and `path` today; it also returns the fingerprint
  so every command above reads the same value.
- **Legacy records:** an installed `mcp` entry with no recorded fingerprint is treated as drifted once; the idempotent apply re-registers it
  and backfills the record (this includes the bundled `jcodemunch` item).

### 4. Drift check that fails loudly (aec, `aec doctor` and a SessionStart hook)

- `aec doctor` runs each installed `mcp` item's `check` (when declared) and reports drift with the fix command (`aec upgrade`). It must exit
  non-zero on drift; that depends on the exit-code contract owned by [`2026-11-21-stale-skills-fail-loudly.md`](2026-11-21-stale-skills-fail-loudly.md),
  which this step waits for rather than re-implementing.
- **SessionStart adapter, not exit 2.** Per the Claude Code hooks reference, a SessionStart hook cannot block, and its exit code 2 shows
  stderr to the user only (the model never sees it). The shipped hook is a small adapter around `check`: it runs the check (which keeps its
  own non-zero drift contract for `doctor` and CI, every non-zero code counting as drift) and always exits 0. On drift it prints one JSON
  object on stdout: `systemMessage` carries the report for the user and `hookSpecificOutput` (with `hookEventName` set to `SessionStart`, which
  the hooks reference requires) carries it for the model in `additionalContext`. No
  drift prints nothing. Test the adapter's output: drift gives valid JSON with `systemMessage`, `hookEventName: SessionStart` and `additionalContext` and exit 0; no drift gives nothing; a check that is
  unreadable, crashed or missing gives a report saying so, never silence.
- **The hook needs an MCP install path; the existing catalog-hook mechanism does not cover it.** `aec/lib/catalog_hooks.py` maps only
  `skill`, `rule` and `agent` (`_PLURAL`), and `_apply_mcp` never invokes a hook lifecycle, so `wire(repo, "mcp", ...)` raises `LookupError`.
  Add an explicit MCP hook lifecycle that reuses the existing installer (`aec/lib/hooks/lifecycle.install_hooks_for_item`, driven by the
  item's `hooks.json`): install on apply, refresh on upgrade, removal on uninstall, called from the one apply engine. Scope and source
  resolution: global installs write the hook into the user-level client settings (the installer takes a `repo_root` today, so it needs a
  user-scope target); repository installs use the repository; the item directory comes from the source the item was installed from (default
  catalog or custom source), recorded in the manifest.
- Scope of "drift": installed file differs from source; a client entry points elsewhere; a running launcher is older than the installed
  file; an orphaned launcher process (parent pid 1). Report pids, parents and ages only, never command lines (a command line can carry a key).

### 5. Interim (before steps 1-4 land), owned by the bridge's repo

Until the mechanism exists, the bridge's owner repo wires its read-only `--check` (the same drift report) into a SessionStart hook so a stale
install is reported at session start instead of waiting to be noticed. The hook must use the step 4 adapter shape (exit 0, JSON on stdout
with `systemMessage` for the user and `additionalContext` for the model), because SessionStart cannot block and an exit 2 shows stderr to
the user only. The check already exists in that repo; the work is the adapter, the hook and its
test. This plan only records it as the stop-gap; the owner repo's cop carries it.

### 6. Restart stays a human or client action

AEC replaces the file and the registrations; it never restarts a client or kills a launcher process. The drift check reports the running
launchers that predate the installed file and names the restart step. A restart can drop an in-flight tool call, so it is not an automatic
side effect of `aec upgrade`.

### 7. Migrate the first consumer, then retire the script

The owner repo publishes its bridge as an item in its catalog source (custom source or its own catalog) once steps 1-3 ship, proves parity
on two machines (installed sha256 equal, all three clients `ok`, missing key `SKIPPED` and entries kept), then deletes its hand-run script
and points its docs at `aec upgrade`. The owner repo's cop owns this step; AEC does not edit that repo.

## Affected surfaces (contract-change punch list)

Writers of `mcp.json`: `mcp-servers/jcodemunch/mcp.json` (unchanged, new keys optional), any custom-source catalog (validated by the same
validators), `aec/lib/org_config` MCP entries (`schema.py`, `validator.py`, `apply.py`: confirm an org-config `mcp` entry can carry the new
keys or is explicitly limited, and test it).

Readers and callers of the apply path: `apply_core.plan_apply` / `execute_apply` / `_apply_mcp`; `commands/install_cmd._install_mcp`;
`commands/apply_cmd.run_apply`; `commands/install_cmd._install_single_item` (optional manifest object, no save when given); `commands/upgrade.run_upgrade` (manifest load/save ownership) and `_upgrade_scope` / `_target_base` (the generic branch must stop handling `mcp`);
`aec/lib/mcp_settings` (`write_mcp_server` / `remove_mcp_server` retired for registration, kept only to remove a recorded legacy entry);
`commands/upgrade._find_outdated_repos` (filters through the shared predicate, so repository-scoped drift in other tracked repos is found and
repaired) and `_report_scope_outdated`; `commands/update.run_update` and `outdated` reporting; `cli.py` exit mapping for `update` / `upgrade`; `sources._discover_available_mcps`
(fingerprint); `commands/uninstall` (must remove the files, the per-client entries and the hook it created, and only those, by recorded
sha256); `aec/lib/hooks` lifecycle and `catalog_hooks` (MCP hook install, refresh, removal); `portable_manifest`, `skills_manifest`,
`manifest_v2` (`files`, `fingerprint`), `doctor`.

Docs: `docs/users` MCP page, `docs/qa-verification.md`, README MCP section (placeholders only).

## Tests

- Schema validation: `files.dest` outside `$HOME` rejected; `..` and absolute `src` rejected; unknown client rejected; old `mcp.json` still
  valid; a repo-scoped item with `files`, or with `codex` in `clients`, rejected before any mutation (assert no file or config was touched).
- Filesystem confinement: `..` in `dest`; symlinked parent; symlinked final component; a parent swapped for a symlink between validation and
  rename (via a test seam); the recorded sha256 equals the sha256 of the bytes written even when the source changes during the copy;
  uninstall removes only a file whose sha256 matches the record.
- Manifest transaction: after the CLI exits, the persisted manifest holds the engine's new version, fingerprint and file hashes **and** the
  records of the non-MCP items in the same batch, for `aec upgrade --yes`, `aec apply` and `aec org apply` (mixed skill + MCP batches through
  each); `execute_apply` and `run_upgrade` each save exactly once; interactive `aec install` still persists its own record.
- Retraction through upgrade: dropping a client from `clients`, renaming a server and changing a launcher `dest` each remove the old
  registration or file; a hand-edited old launcher is kept and reported; a failed retraction leaves the old record intact.
- Mode and hooks through the CLI: a mode-only change leaves the launcher executable (assert the filesystem mode and execute it); a
  `hooks.json`-only or hook-script-only change at the same version plans and performs a hook refresh.
- Client compatibility: Claude registrations go through `claude mcp add/get/remove`; the fake-CLI shim is validated against recorded output of
  the real CLI (fixture), and a contract test runs against the real `claude` binary when present and is skipped, visibly, when not.
- Predicate and discovery: version bump on an installed `mcp` item plans `upgrade`; a config-only change (args, clients, `requires_key`,
  `check`, mode) with identical launcher bytes plans `upgrade`; a launcher deleted or edited by hand with an unchanged catalog plans `upgrade`; launcher content change plans `upgrade`; everything equal is `noop`; a legacy
  record with no fingerprint upgrades once and is backfilled; `_discover_available_mcps` exposes the fingerprint.
- Other tracked repositories: a repository-scoped `mcp` item with fingerprint or installed-state drift (same version) in a tracked repo other
  than the current one is listed by `aec upgrade` and repaired by `aec upgrade --yes`; an up-to-date other repo is not visited.
- Public commands (run through the CLI, not the helpers): `aec update` reports the outdated `mcp` item; `aec upgrade --yes` installs the
  launcher, registers the clients and exits non-zero on a SKIPPED target; `aec upgrade` no longer copies an `mcp` item into the rules
  directory.
- Apply against a temp `$HOME` with fake `claude`/`codex` shims on `PATH` and a temp `~/.cursor`: registers all three; re-run is `ok`;
  failed `codex mcp add` restores the previous config; missing key prints SKIPPED, leaves existing entries and returns a non-zero result; a
  `--has-key` probe never prints the key (assert the key value is absent from captured stdout and stderr).
- Scope: two repositories plus an existing global registration; each repo's apply and removal leaves the other repo and the global entry
  intact.
- Hook lifecycle: install on apply, refresh on upgrade, removal on uninstall, for global, repository and custom-source installs; the
  SessionStart adapter exits 0 and prints the drift report as JSON (`systemMessage`, `hookEventName`, `additionalContext`) on stdout.
- Drift check: stale file, orphaned process (spawned test child reparented to pid 1), process older than the installed file, unreadable
  process table (never a false pass).

## Sequencing

1. Step 3 plus the `aec upgrade` / `aec update` / `aec outdated` routing from step 2 first, together with the single manifest transaction
   owner and the client-backed Claude registration with legacy migration (they are what make the routing correct; shipping the routing
   alone would be overwritten by `run_upgrade`'s save). Fixes "an `mcp` item never upgrades" for everyone, including `jcodemunch`.
2. Steps 1 and 2 together (schema, scope rules, filesystem safety, apply), behind the same validators.
3. The MCP hook lifecycle and the SessionStart adapter from step 4; they do not depend on `doctor`.
4. The `doctor` check after the exit-code contract plan lands.
5. Step 7 in the owner repo after 1-3 ship.

Step 5 (interim) is independent and should not wait for any of these.

## Out of scope

Restarting clients or launcher processes; storing, rotating or reading key values; OAuth flows; adding any specific bridge or its key layout
to this repo (they belong to the source that publishes the item).
