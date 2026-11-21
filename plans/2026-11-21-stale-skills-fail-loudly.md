# Stale skills fail loudly: `aec update`, `aec upgrade`, run-script, doctor and re-vendoring

**Status:** planned. Scheduling pending.
**Priority:** high. A stale vendored checker ships a weaker merge gate and nothing says so.

**Incumbent (checked 2026-11-21):** [`2026-11-16-upgrade-detects-vendored-skills.md`](2026-11-16-upgrade-detects-vendored-skills.md)
already owns detecting *vendored copies* inside tracked repos (its Correct fix steps 1-4 and its VENDOR-DRIFT-01 section for the
guard files). This plan extends it and does not repeat it: it adds the *exit-code contract*, the `run-script` and `doctor`
behavior, the re-vendor refusal in claude-skills, and the instruction text. Detection itself (the helper that finds a vendored copy
and compares versions) is built by the incumbent plan; every step here that needs it waits for it (see Sequencing).

## Problem

1. `aec update` fetches sources, prints "review-gate X -> Y", says "Run `aec upgrade` to apply" and exits 0. Agent instructions say
   "run `aec update`", so nothing is applied and nothing fails.
2. A re-vendor from a stale skill silently ships the old forged-gate checker. Observed: a global `review-gate` at 3.2.14 while
   upstream was 3.2.16 (the newer `check-forged-review-gate.py` adds provenance validation), and three repos re-vendored from it.
   `pr-merge-flow` was 1.4.6 in one repo against 1.5.4 upstream.
3. `aec upgrade` always exits 0, including when it stops partway or skips repos.
4. `aec upgrade --yes` edits the working tree of every tracked repo, not the current one, with no commits (a separate fix:
   "repo-local upgrades apply to the current repo only"; step 2 below is not safe to automate until it lands).
5. `aec run-script <type>:<item> <script>` resolves the repo copy first and the global copy second
   (`_resolve_item_dir` in `aec/commands/run_script_cmd.py`), so a stale repo copy runs silently.
6. `aec doctor` checks manifest/directory consistency only; it never compares a vendored skill's version with what is available,
   and `doctor_cmd` in `aec/cli.py` discards `run_doctor()`'s `(all_passed, issues)` result, so it **exits 0 whatever it finds**.

## Root cause

Staleness is *reported* in prose and never *returned*. Every consumer that could gate on it (an agent, a hook, CI, the re-vendor
installer) has no signal except parsing text. A check that only prints depends on someone remembering to read it.

Facts verified in code (2026-11-21): `aec update` exits `EXIT_PENDING` (14, `aec/commands/org.py`) only when an org config is
pending (`run_update()` returns that boolean; `aec/cli.py` maps it to the exit code); staleness only changes the final message.
`aec upgrade` (`run_upgrade`) returns `None`. `aec outdated` has no exit code. `doctor_cmd` never exits non-zero. Claude-managed
plugins are counted as "found" by `_refresh_claude_plugins` (`update.py`) and `_print_outdated` (`outdated.py`) whether or not
they are current, because Claude Code has no check-only command.

## Correct fix

Each behavior lives in the one component that owns it; callers call.

### 1. Opt-in gate: `aec update --check` and `aec outdated --exit-code` (aec)

- **Default `aec update` exit codes do not change for staleness.** `aec update && aec upgrade` is documented (README, the
  generated project instructions in `aec/lib/tracking.py`), and staleness is the normal case there, so a non-zero default would
  short-circuit the chain and abort `set -e` scripts. The org-pending exit 14 stays as it is.
- `aec update --check` exits 14 when any version-compared item is outdated, or an org config is pending; `aec outdated
  --exit-code` does the same for outdated items only, without fetching. One meaning for 14: "finished, and something remains to
  apply". The last line names the cause (`N items outdated` / `org pending`) and its remedy (`aec upgrade` vs `aec org apply`).
- **Unchecked managed plugins never count toward the exit code.** Claude Code cannot be asked "is this current" without
  upgrading, so counting them would make the code unclearable after a successful `aec upgrade`. They stay printed as
  "unchecked", as today. Plugins whose version is unknown are treated the same way. The found-flags in `_report_scope_outdated`
  (`update.py`) and `_print_outdated` (`outdated.py`) currently set for these plugins; they are split so only a real
  version comparison increments `outdated_count`.
- `run_update()` returns a small result (`org_pending`, `outdated_count`, `unchecked_plugins`) instead of a bare boolean;
  `cli.py` is the single place that maps it to an exit code. No caller re-decides. `run_upgrade` calls `run_update()`
  (`upgrade.py`) and the update tests call it directly; both move to the result object in the same PR (a truthiness check
  on the new object would always be true).
- `aec outdated --exit-code` has no org logic: it exits 14 for outdated items only. The org-pending cause belongs to
  `aec update --check`, which does fetch and read org state.
- Move `EXIT_PENDING` (and the other `EXIT_*`) out of the org module into a neutral `aec/lib/exit_codes.py`; the org module
  re-exports during the transition. Document in `--help`, `docs/qa-verification.md` and the README.
- Rejected: making the default `aec update` non-zero when stale. Revisit only after the documented chains are changed to
  `aec upgrade` alone (it already offers to run `update` first) and a release note has gone out.

### 2. `aec upgrade` returns an honest exit code (aec)

- Exit 0 only when every in-scope item reached the target version. Non-zero (`EXIT_UPGRADE_INCOMPLETE`) when any scope was
  skipped, a repo-local upgrade stopped, or an item failed; the last line lists what was skipped and why.
- `run_upgrade`'s `finally` still persists manifest progress; the code is decided after it, so a partial run saves progress and
  still fails loudly.
- Scope itself (current repo unless `--all`) is the separate fix named in Problem 4; this plan only pins the exit code of
  whatever scope ran and reports unvisited tracked repos as "skipped".

### 3. `aec run-script` warns; it never swaps copies (aec)

- Resolution order stays repo first, then global. A committed repo copy is what CI and teammates run, so a hook must not run
  different code on each machine because of a developer's global copy.
- After resolving, ask the **incumbent plan's staleness helper** (version AND content hash: an equal version with different
  content is still stale) for a verdict on the chosen copy. This step builds no comparator of its own and therefore waits for
  that helper (Sequencing). Hot path: run-script runs on every hook call, so the helper is read from local files only (no
  network, no subprocess, `skills-manifest.json` lookup rather than a scan of every skill directory), and the PR states the
  measured added latency. When the verdict is stale, print `warning: <item> in this repo is <old>; <new> is available; run aec
  upgrade` (or `older content at <version>`) to stderr and still run the script (a refusal here would break the hook that
  called it).
- Hook-bearing skills (for example `review-gate`) are never installed globally, so the comparison is against the catalog, which
  is what catches them.
- `AEC_RUN_SCRIPT_STRICT=1` turns the warning into exit 2 (the code Claude Code hooks treat as blocking), for hooks that must not
  run a stale script. Default stays a warning. Strict **fails closed**: when no catalog is available (no AEC checkout, so no
  verdict can be computed) it exits 2 with "cannot verify freshness", never silently passes. Exit 2 also means "not installed"
  or "script not found" in `run_script_cmd.py`; the message text is what tells the three apart, and the tests pin each message.
- Rejected: preferring the global copy when newer (the originally filed shape). It makes behavior depend on the machine and
  contradicts a repo that pins a version on purpose.

### 4. `aec doctor` fails on an older vendored skill, and exits non-zero on any issue (aec)

- **Contract change:** `doctor_cmd` raises `typer.Exit(1)` when `run_doctor()` reports issues. Today it always exits 0 (see
  Problem 6), so this also changes every existing caller of `aec doctor` (grep: hooks, CI jobs, docs, the install flow that
  runs it); each is listed in the PR that makes the change.
- For each `.claude/skills/<name>` in the current repo that is also in the catalog, a stale verdict (lower version, or equal
  version with older content) is a doctor issue naming the fix (`aec upgrade`, or the skill's own installer for hook-bearing
  skills).
- Reuses the detection helper from the incumbent plan (the same one step 3 calls); neither doctor nor run-script grows its own
  parser or comparator.
- `docs/qa-verification.md` already says "`aec doctor` fails" in the org-pending scenario, which is false today; the same PR
  makes it true and corrects any other doc that states doctor's exit behavior.

### 5. Re-vendor tooling refuses a stale source (claude-skills; separate PR in that repo, its own owner)

- `review-gate` `install-workflow.py` (and the `pr-merge-flow` equivalent) compare the version of the skill directory they copy
  from against the newest released tag/manifest version they can see, and refuse (non-zero, one message naming both versions and
  the fix) when the source is older. `--allow-stale` exists for the offline case and is named in the refusal.
- The source of truth is the skill directory of an aec or claude-skills checkout at a released tag, never an assumed
  `~/.claude/skills` copy (a hook-bearing skill has no global copy at all).
- The skills' own tests also run from the **vendored path**: a parity test that only runs from the source directory passes while
  the vendored copy is broken. The test resolves `dir_path` from the file under test, not from a hard-coded layout.
- The installer rewrites every version line it owns in `docs/qa-verification.md` (today it leaves the old review-gate version
  stated there). A test asserts that after install no line in the doc states an older version.

### 6. Guard-drift items (aec; extends the incumbent's VENDOR-DRIFT-01)

- `scripts/check-vendored-drift.py` runs automatically (scheduled CI and `aec outdated`'s "vendored guard files" scope), not by
  hand. The stale OLD-shape `main-via-staging.yml` seen in three repos is the case it must catch: compare against the blob in
  the latest released tag. No new mechanism: only the trigger and the exit code for the incumbent's script.

### 7. Instruction text (owner: whoever maintains the global agent instruction file; not edited here)

- Instructions say `aec update --check` (non-zero means act on the last line: `aec upgrade` for outdated items, `aec org apply`
  for a pending org config) instead of `aec update` alone. After step 1 this is a rule a tool enforces rather than prose.

## Tests (pin behavior, not prose)

- `tests/test_update_cmd.py`: `--check` with a stale item -> 14 and the "N items outdated" line; up to date -> 0; org pending
  only -> 14; both -> 14 once; **a recorded Claude-managed plugin and nothing else outdated -> 0**; default `aec update` with a
  stale item still -> 0 (pins the `update && upgrade` chain).
- `tests/test_upgrade_cmd.py`: a failing item, a skipped repo and an interrupted run each exit non-zero; manifest progress is
  still saved; a clean run exits 0; `--yes` across other tracked repos reports them as skipped or upgraded, never silent.
- `tests/test_outdated_cmd.py`: `--exit-code` stale -> 14, current -> 0, managed plugin only -> 0; without the flag always 0.
- `tests/test_doctor_cmd.py`: any reported issue -> non-zero; healthy -> 0.
- New `tests/test_run_script_staleness.py` (added by the run-script PR) and doctor cases in `tests/test_doctor_cmd.py` (added by
  the doctor PR) share one fixture module (`tests/fixtures/stale_skill.py`: a repo copy older than the catalog, and one at the
  same version with older content). Run-script: warns on stderr and runs the repo copy's script for both fixtures; identical
  copy runs silently; `AEC_RUN_SCRIPT_STRICT=1` exits 2 with the stale message, exits 2 with "cannot verify freshness" when
  no catalog is available, and the three exit-2 messages (stale, not installed, script not found) differ. Doctor: both
  fixtures exit non-zero and name `aec upgrade`. Once both PRs have landed, one cross-check test runs both commands on the
  same fixture and asserts they agree. Real directories and a real catalog fixture, no mocks of our own code.
- `tests/test_exit_codes.py`: `EXIT_PENDING` is importable from `aec/lib/exit_codes.py` and still from the org module.
- claude-skills: refusal when the source is older (non-zero, message), `--allow-stale` passes, vendored-path parity run, qa-doc
  version lines rewritten.

## Affected surfaces (grep before coding; contract change coverage)

Callers of the exit codes and chains: `aec/cli.py` (`update_cmd`, `upgrade_cmd`, `outdated_cmd`, `doctor_cmd`),
`aec/commands/update.py`, `upgrade.py` (it calls `run_update()`), `outdated.py`, `tests/test_update_cmd.py` (calls `run_update()`), `run_script_cmd.py`, `doctor.py`, `aec/commands/org.py` (`EXIT_*` move),
every `aec update && aec upgrade` chain (README lines 83 and 264, `aec/lib/tracking.py` generated text), hook bodies that call
`aec run-script`, scripts/CI/docs that run `aec update` or `aec doctor` (grep `.github/`, `scripts/`, `docs/`, the installed
instruction-blurb text), `docs/qa-verification.md`, the README command table. claude-skills: `review-gate/scripts/install-workflow.py`,
the `pr-merge-flow` installer, their tests, `skills-manifest.json`.

## Sequencing

1. Steps 1 and 2 (aec): make staleness observable. Step 2 also waits on the current-repo-only upgrade fix.
2. The incumbent plan's detection helper (version AND content verdict).
3. Steps 3 (run-script) and 4 (doctor), each calling that helper; either order, separate PRs.
4. Steps 5 and 6 once a released aec tag carries 1.
5. Step 7 after step 1 merges.
Each step is its own PR.

## Done when

Staleness anywhere an agent can hit it (update `--check`, outdated, run-script, doctor, re-vendor) returns non-zero or warns on
stderr with the fix named; the instruction text is updated; repos that re-vendored from a stale copy have been told to
re-vendor once.
