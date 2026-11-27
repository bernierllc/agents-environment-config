# MCP launcher catalog items: a stdio bridge installs, registers and updates through `aec update`

**Status:** planned. Scheduling pending.
**Priority:** high. A hand-run install script sat stale on a machine after two merged fixes, and nothing said so.
**Tracker id:** AEC-MCP-LAUNCHER-ITEM.

**Incumbent (checked 2026-11-27):** AEC already has an `mcp` item type (`aec/lib/apply_core.py` `_apply_mcp`, `aec/lib/mcp_settings.py`,
`mcp-servers/<name>/mcp.json`). It cannot carry a launcher bridge, for the four reasons under Problem. This plan extends that type and
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
3. **It never upgrades on a version bump.** In `plan_apply`, `newer` is computed only `if item.item_type != "mcp"`; an `mcp` item whose
   catalog version differs from the installed one lands in the `noop` branch with reason "installed differs from catalog; keeping". Only a
   changed source or a failed pin produces an `upgrade`. So "installs update on `aec update`" is false for every `mcp` item today.
4. **It cannot say a key is missing.** A launcher without its key exits at start, so replacing a working entry (for example an OAuth one)
   with it breaks the client. The script guards this with a `--has-key` probe that prints nothing; the `mcp` type has no equivalent gate and
   writes the entry unconditionally.

Also missing, and not fixable by installing: nothing detects that a client is still running an older launcher after the file was replaced.

## Root cause

The `mcp` item type models "a package plus a settings entry", and a launcher bridge is "a file plus entries in several clients, gated on a
key, with processes that outlive the file". The staleness is the compound of (3) and the absence of a drift check: an install that cannot
update, and no signal that it did not.

## Correct fix

Each behavior lives in the one component that owns it; callers call. The launcher script itself stays in its owner's catalog source, never
in AEC core (the generic mechanism lands here; a specific bridge is just one item in some source).

### 1. Extend the `mcp.json` schema (aec, `aec/lib/mcp_settings.py` and the catalog validators)

Optional keys, all backwards compatible (an existing `mcp.json` is unchanged):

- `files`: list of `{ "src": <path in the item dir>, "dest": <path under the user's home>, "mode": "0755" }`. Installed by write-beside-and-rename
  (a failed copy must not truncate a working launcher). `dest` must resolve under `$HOME`; anything else is rejected at validation.
- `clients`: subset of `claude`, `codex`, `cursor`; default `["claude"]` (today's behavior).
- `requires_key`: `{ "file": <path under home>, "var": <env var NAME> }`. Names only: the value is never read into AEC output, logs or the
  manifest. The gate asks the launcher (`<launcher> <target> --has-key`, exit 0/1, prints nothing) when the item declares `files`; otherwise it
  tests that the file defines the variable in a subshell and discards output.
- `check`: optional read-only command (exit non-zero on drift) used by the interim and the doctor check in steps 4 and 5.

### 2. Apply: files, per-client registration, key gate (aec, `apply_core._apply_mcp`)

- Install each `files` entry idempotently (compare sha256 with the source; skip when equal) and record the installed sha256 in the manifest
  entry (`record_mcp_install` gains `files: {dest: sha256}`).
- For each target and each client in `clients`: when `requires_key` is declared and the gate fails, print `SKIPPED, key file missing; existing
  client entries kept` and leave that client's entry alone (mirrors the script's semantics); otherwise register, snapshot-and-restore on a
  failed replacement, and confirm the entry the client resolves is ours before reporting success. Codex via `codex mcp add/get/remove`, Cursor via
  atomic JSON replace preserving file mode, Claude via `claude mcp add -s user` (this replaces the hand-written settings.json merge only for
  items that declare `clients`; items that do not keep `write_mcp_server`).
- A SKIPPED target is a non-zero apply result (`ApplyResult.errors`), never a silent success, so `aec update --yes` and CI see it.

### 3. Upgrade on content, not only version (aec, `apply_core.plan_apply`)

For `mcp` items, compare the recorded `files` sha256 with the catalog's; a difference plans an `upgrade` with reason "launcher content changed".
For `mcp` items without `files`, compare versions with `version_is_newer` like every other type (the current `noop` branch is the bug). Add the
test that a catalog version bump on an installed `mcp` item plans an `upgrade`.

### 4. Drift check that fails loudly (aec, `aec doctor` and a SessionStart hook)

- `aec doctor` runs each installed `mcp` item's `check` (when declared) and reports drift with the fix command. It must exit non-zero on drift;
  that depends on the exit-code contract owned by [`2026-11-21-stale-skills-fail-loudly.md`](2026-11-21-stale-skills-fail-loudly.md), which this
  step waits for rather than re-implementing.
- A SessionStart hook shipped with the item runs `check` and exits 2 with the drift report on stderr, so the model sees it (a hook that exits 0
  prints to nowhere the model reads). The hook is wired by the existing catalog-hook mechanism (`aec/lib/catalog_hooks.py` `wire`).
- Scope of "drift": installed file differs from source; a client entry points elsewhere; a running launcher is older than the installed file;
  an orphaned launcher process (parent pid 1). Report pids, parents and ages only, never command lines (a command line can carry a key).

### 5. Interim (before steps 1-3 land), owned by the bridge's repo

Until the mechanism exists, the bridge's owner repo wires its read-only `--check` (the same drift report) into a SessionStart hook so a stale
install fails at session start instead of waiting to be noticed. The check already exists in that repo; the work is the hook and its test. This
plan only records it as the stop-gap; the owner repo's cop carries it.

### 6. Restart stays a human or client action

AEC replaces the file and the registrations; it never restarts a client or kills a launcher process. The drift check reports the running
launchers that predate the installed file and names the restart step. A restart can drop an in-flight tool call, so it is not an automatic side
effect of `aec update`.

### 7. Migrate the first consumer, then retire the script

The owner repo publishes its bridge as an item in its catalog source (custom source or its own catalog) once steps 1-3 ship, proves parity on
two machines (installed sha256 equal, all three clients `ok`, missing key `SKIPPED` and entries kept), then deletes its hand-run script and
points its docs at `aec update`. The owner repo's cop owns this step; AEC does not edit that repo.

## Affected surfaces (contract-change punch list)

Writers of `mcp.json`: `mcp-servers/jcodemunch/mcp.json` (unchanged, new keys optional), any custom-source catalog (validated by the same
validators), `aec/lib/org_config` MCP entries (`schema.py`, `validator.py`, `apply.py`: confirm an org-config `mcp` entry can carry the new keys
or is explicitly limited, and test it). Readers: `apply_core.plan_apply` / `_apply_mcp`, `install_cmd` MCP install path, `uninstall` (must
remove the files and the per-client entries it created, and only those), `portable_manifest`, `skills_manifest`, `manifest_v2`, `doctor`.
Docs: `docs/users` MCP page, `docs/qa-verification.md`, README MCP section (placeholders only).

## Tests

- Schema validation: `files.dest` outside `$HOME` rejected; unknown client rejected; old `mcp.json` still valid.
- `plan_apply`: version bump on an installed `mcp` item plans `upgrade`; content hash change plans `upgrade`; equal hash and version is `noop`.
- Apply against a temp `$HOME` with fake `claude`/`codex` shims on `PATH` and a temp `~/.cursor`: registers all three; re-run is `ok`; failed
  `codex mcp add` restores the previous config; missing key prints SKIPPED, leaves existing entries and returns a non-zero result; a `--has-key`
  probe never prints the key (assert the key value is absent from captured stdout and stderr).
- Uninstall removes only what apply created.
- Drift check: stale file, orphaned process (spawned test child reparented to pid 1), process older than the installed file, unreadable process
  table (never a false pass).

## Sequencing

1. Step 3 first (small, independent, fixes "`aec update` never upgrades an `mcp` item" for everyone, including `jcodemunch`).
2. Steps 1 and 2 together (schema plus apply), behind the same validators.
3. Step 4 after the exit-code contract plan lands; the SessionStart hook can ship earlier because it does not depend on `doctor`.
4. Step 7 in the owner repo after 1-3 ship.

Step 5 (interim) is independent and should not wait for any of these.

## Out of scope

Restarting clients or launcher processes; storing, rotating or reading key values; OAuth flows; adding any specific bridge or its key layout to
this repo (they belong to the source that publishes the item).
