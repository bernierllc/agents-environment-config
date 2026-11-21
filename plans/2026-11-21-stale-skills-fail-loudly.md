# Stale skills fail loudly: `aec update`, `aec upgrade`, run-script, doctor and re-vendoring

**Status:** planned. Scheduling pending.
**Priority:** high. A stale vendored checker ships a weaker merge gate and nothing says so.

**Incumbent (checked 2026-11-21):** [`2026-11-16-upgrade-detects-vendored-skills.md`](2026-11-16-upgrade-detects-vendored-skills.md)
already owns detecting *vendored copies* inside tracked repos (its Correct fix steps 1-4 and its VENDOR-DRIFT-01 section for the
guard files). This plan extends it and does not repeat it: it adds the *exit-code contract*, the `run-script` and `doctor`
behavior, the re-vendor refusal in claude-skills, and the instruction text. Where the two touch (guard-drift items), this plan
points at that section and only adds what is missing there.

## Problem

1. `aec update` fetches sources, prints "review-gate X -> Y", says "Run `aec upgrade` to apply" and exits 0. Agent rules say
   "run `aec update`", so nothing is applied and nothing fails. The process is the defect, not the agent.
2. A re-vendor from a stale skill silently ships the old forged-gate checker. Observed: a global `review-gate` at 3.2.14 while
   upstream was 3.2.16 (the newer `check-forged-review-gate.py` adds provenance validation), and three repos re-vendored from it.
   `pr-merge-flow` was 1.4.6 in one repo against 1.5.4 upstream.
3. `aec upgrade` always exits 0, including when it stops partway or skips repos. One run on a large fleet ended mid-list with
   no message and rc 0.
4. `aec upgrade --yes` edits the working tree of every tracked repo, not the current one, with no commits (a separate
   fix, "repo-local upgrades apply to the current repo only"; it is a prerequisite for step 2 below being safe to automate).
5. `aec run-script <type>:<item> <script>` resolves the repo copy first and the global copy second
   (`_resolve_item_dir` in `aec/commands/run_script_cmd.py`), so a stale repo copy is what runs, silently.
6. `aec doctor` checks manifest/directory consistency only; it never compares a vendored skill's version with what is available.

## Root cause

Staleness is *reported* in prose and never *returned*. Every consumer that could gate on it (an agent, a hook, CI, the re-vendor
installer) has no signal except parsing text. A check that only prints is rung 5 of the "remembering is a failure mode" ladder.

Facts verified in code: `aec update` exits `EXIT_PENDING` (14, `aec/commands/org.py`) only when an org config is pending
(`run_update()` in `aec/commands/update.py` returns that boolean; `aec/cli.py` maps it to the exit code). Staleness
(`any_outdated`, managed plugins) only changes the final message. `aec upgrade` (`run_upgrade` in `aec/commands/upgrade.py`)
returns `None`. `aec outdated` has no exit code.

## Correct fix

Each behavior lives in the one component that owns it; callers call.

### 1. `aec update` exits 14 when anything is left to apply (aec)

- One contract: exit 14 means "the command finished and something remains for a person or `aec upgrade`". Org-pending already
  means that; stale items and unchecked managed plugins now mean it too. The output line names which (`org pending` /
  `N items outdated`) so a reader is not left guessing. Exit 0 only for "Everything is up to date" / "Global and local are up to date".
- Why one code and not a new one: callers gate on "is there work", and both causes need the same next action. A second code can be
  added later without breaking a reader of 14.
- `run_update()` returns the combined boolean (it already computes `any_outdated`, `managed`, `org_pending`); `cli.py` keeps the
  single `raise typer.Exit(EXIT_PENDING)`. No caller re-decides.
- `aec upgrade` calls `run_update()` for its staleness prompt and ignores the return value (it is about to apply).
- Document in `--help`, `docs/qa-verification.md` and the README command table.

### 2. `aec upgrade` returns an honest exit code (aec)

- Exit 0 only when every in-scope item reached the target version. Non-zero (distinct constant `EXIT_UPGRADE_INCOMPLETE`) when any
  scope was skipped, any repo-local upgrade stopped, or any item failed; the last line lists what was skipped and why.
- `run_upgrade` already has a `finally` that persists the manifest; the code is decided after it, so a partial run still saves
  progress and still fails loudly.
- Repo-local upgrades apply to the current repo unless the user passes an explicit `--all` (that behavior change is its own
  fix; this plan only pins the exit code of whatever scope ran, and lists unvisited tracked repos as "skipped").
- Dry run keeps exit 0 unless the upgrade would be non-empty and `--check` is passed (below).

### 3. `aec update --check` / `aec outdated --exit-code` for gating (aec)

- `aec outdated` gets the same exit-14-when-stale behavior behind an explicit flag (it is a report today; changing its default
  would break scripts). A hook or agent gates on `aec outdated --exit-code`, with no network fetch.

### 4. `aec run-script` warns, and prefers the newest copy (aec)

- `_resolve_item_dir` collects candidates as today, then compares versions (SKILL.md frontmatter, the field the manifest uses).
- Prefers the **global** copy when it is newer than the repo copy; when the repo copy is older than the global copy or than the
  source's available version it prints `warning: <item> in this repo is <old>, <new> is available; run aec upgrade` to stderr
  and still runs (a refusal here would break the hook that called it).
- Hook-bearing skills (for example `review-gate`) are never installed globally (`Refusing global install of hook-bearing ...`),
  so the global comparison does not apply to them; the available-source comparison does, and that is what catches them.
- Equal versions keep today's order (repo first) so a repo pinned on purpose still works.
- A hook that must not run a stale script sets `AEC_RUN_SCRIPT_STRICT=1` to turn the warning into exit 14. Default stays a warning.

### 5. `aec doctor` flags an older vendored skill (aec)

- Extends the incumbent plan's step 1 (vendored copy detection) into doctor: for each `.claude/skills/<name>` in the current repo
  that is also in the available catalog, a version lower than available is a doctor **failure** naming the fix
  (`aec upgrade`, or the skill's own installer for hook-bearing skills), and doctor's existing non-zero exit carries it.
- Reuses the detection helper from the incumbent plan; doctor does not grow its own parser.

### 6. Re-vendor tooling refuses a stale source (claude-skills; owner claude-skills)

- `review-gate` `install-workflow.py` (and the `pr-merge-flow` equivalent) compare the version of the skill directory they copy
  from against the newest tag/manifest version they can see, and refuse (non-zero, one message naming both versions and the fix)
  when the source is older. `--allow-stale` exists for the offline case and is printed in the refusal.
- The source of truth is the skill directory of the aec or claude-skills checkout at a released tag, never an assumed
  `~/.claude/skills` copy (a hook-bearing skill has no global copy at all).
- Tests live in claude-skills, run from the **vendored path** too : a parity test that only runs from
  the source directory passes while the vendored copy is broken. The test resolves `dir_path` from the file under test, not
  from a hard-coded layout.
- The installer rewrites every version line it owns in `docs/qa-verification.md` (today it leaves the old review-gate version stated there). A test asserts that after install, no line in the doc states an older version.

### 7. Guard-drift items (aec; extends the incumbent's VENDOR-DRIFT-01)

- `scripts/check-vendored-drift.py` runs automatically (CI weekly and in `aec outdated`'s "vendored guard files" scope), not by hand.
- The stale OLD-shape `main-via-staging.yml` found in three repos  is the case the check must catch:
  compare against the blob in the latest released tag.
- No new mechanism here: only the trigger and the exit code for the incumbent's script.

### 8. Instruction text (owner: whoever maintains the global agent instruction file)

- The global agent instructions say `aec update`, then `aec upgrade` (or gate on `aec outdated --exit-code`), never `aec update`
  alone. After steps 1-3 land, the sentence can say "a non-zero `aec update` means run `aec upgrade`", which is a rule a tool
  enforces rather than prose. Not edited in this repo.

## Tests (pin behavior, not prose)

- `tests/test_update_cmd.py`: stale item -> exit 14 with the "N items outdated" line; up to date -> 0; org pending only -> 14;
  both -> 14 once.
- `tests/test_upgrade_cmd.py`: a failing item, a skipped repo and an interrupted run each exit non-zero; manifest progress is
  still saved; a clean run exits 0.
- `tests/test_outdated_cmd.py`: `--exit-code` stale -> 14, current -> 0; without the flag always 0.
- New `tests/test_run_script_staleness.py`: one test pins **both** run-script and doctor against the same fixture (a repo copy
  at an older version than the catalog): run-script prints the warning and runs the script; with `AEC_RUN_SCRIPT_STRICT=1`
  exits 14; global-newer case runs the global copy; equal versions run the repo copy; `aec doctor` in that repo fails and names
  `aec upgrade`. Real directories and a real catalog fixture, no mocks of our own code.
- claude-skills: refusal when the source is older (exit non-zero, message), `--allow-stale` passes, vendored-path parity run,
  qa-doc version lines rewritten.

## Affected surfaces (grep before coding; contract change coverage)

Writers/callers of the exit codes: `aec/cli.py` (`update_cmd`, `upgrade_cmd`, `outdated_cmd`), `aec/commands/update.py`,
`upgrade.py`, `outdated.py`, `run_script_cmd.py`, `doctor.py`, `aec/commands/org.py` (`EXIT_*`), hook bodies that call
`aec run-script`, scripts and CI that run `aec update` (grep `.github/`, `scripts/`, `docs/`, installed `AGENTS.md` blurb text),
`docs/qa-verification.md`, the README command table. claude-skills: `review-gate/scripts/install-workflow.py`,
`pr-merge-flow` installer, their tests, `skills-manifest.json`.

## Sequencing

1. Steps 1-3 and 5 (aec) first: they make staleness observable, so everything else can gate on it.
2. Step 4 (run-script) next.
3. Step 6 (claude-skills) and step 7 once a released aec tag carries 1-3.
4. Step 8 text change after step 1 merges.
Each step is its own PR; step 2 waits on the current-repo-only upgrade fix.

## Done when

Staleness anywhere an agent can hit it (update, outdated, run-script, doctor, re-vendor) returns non-zero or warns on stderr with
the fix named; the global instruction text is updated; repos that re-vendored from a stale copy are told to re-vendor once.
