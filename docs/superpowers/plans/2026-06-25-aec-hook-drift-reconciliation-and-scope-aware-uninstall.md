# AEC Hook Drift Reconciliation + Scope-Aware Uninstall

**Created:** 2026-06-25
**Author:** Matt (with Claude)
**Status:** Proposed — pending ROADMAP tier confirmation
**Depends on:** `2026-04-21-aec-hook-management.md` (hooks lifecycle/state subsystem must be landed)

---

## 1. Root cause

AEC writes per-item hook state to `<repo>/.aec/installed-hooks/<type>.<key>.json`
and writes the actual hook entries into each agent's settings file
(`.claude/settings.json`, `.gemini/settings.json`, `.cursor/hooks.json`, git hooks).

**There is no reconciliation between the two.** When anything edits an agent
settings file outside of AEC — a fresh `tsc` type-check hook bootstrap, the older
`verification-playwright` pipeline wiring, a hand edit, a regenerate-from-scratch —
the AEC-installed hook entries get clobbered while AEC's state file is left behind.
AEC still believes the hooks are installed (state intact, fingerprint recorded), so:

- The hooks silently stop firing.
- Re-running `aec install` may no-op because state hash / fingerprint still matches.
- `aec uninstall` may fail to find the entry it expects, or remove the wrong index.

Drift is possible in **both** directions:
- **MISSING** — state claims a hook; settings file lacks it (clobbered). ← live today
- **ORPHAN** — settings file has an AEC-fingerprinted hook; no state file (stale install / partial uninstall).
- **MODIFIED** — entry exists but content fingerprint no longer matches state.

## 2. Evidence (surveyed 2026-06-25)

`verification-writer` is repo-installed in 9 repos. State-vs-settings audit:

| Repo | State claims | settings.json reality | Verdict |
|---|---|---|---|
| aihelp, formExpert.co, houseofgenius, el_new_app, barevents | hooks present | present, correct index | OK |
| **a10d.info** | `vw-scan-on-edit` @ PostToolUse/1 | recovered (re-installed today 21:52) | OK (recovered) |
| **email_demo** | `vw-scan-on-edit` @ PostToolUse/2 | only `[0] tsc`, `[1] verification-playwright` — vw hook **gone** | **MISSING (drift)** |
| **kylebruns** | both vw hooks @ /1,/2 | only `[0] verification-playwright` — both vw hooks **gone** | **MISSING (drift)** |

Common factor in the broken repos: they carry the **older `verification-playwright`
pipeline hook**, whose `settings.json` wiring overwrote the AEC-installed
`verification-writer` entries. Classic out-of-band clobber.

> Note: the survey's index-existence check is necessary but not sufficient — an
> "OK" index can still hold the wrong content. The real tool must compare by
> **content fingerprint**, which AEC already stores in state.

## 3. Scope: two subsystems + one guard

### A. `aec hooks verify [--repair]` — drift reconciliation

Enumerate repos from the manifest's `repos` map (plus optional `--scan <glob>`).
For each repo with `.aec/installed-hooks/*.json`, for each recorded hook, locate
the target entry in the right agent settings file and compare by **content
fingerprint** (not index — indices shift when other tools insert/remove entries):

- **OK** — present, fingerprint matches.
- **MISSING** — state claims it, settings lacks it.
- **ORPHAN** — settings has an entry carrying an AEC fingerprint, no state backs it.
- **MODIFIED** — present but fingerprint differs.

Default run = **report only** (read-only, safe). `--repair`:
- MISSING → re-wire from the item's `hooks.json` (merge, never clobber), rewrite the
  state pointer to the new index.
- ORPHAN → remove the stale entry (with `--prune-orphans` confirm).
- MODIFIED → show diff; offer reset-to-source.

Reuse: `resolve_hooks_dir`, fingerprints in `state.py`, `evaluate_when` predicates,
existing `install_hooks_for_item` / `remove_hooks_for_item`. Pointers must stop
being trusted as identity — fingerprint is identity; pointer is a cache.

Fold in `aec doctor`: surface a drift count so users discover this without knowing
the subcommand exists.

### B. Scope-aware `aec uninstall <skill> --global`

**The repo install overrides the global install for that repo.** A repo-scoped
install is independently owned and must never be reaped just because the global
version once touched that repo. Global uninstall must:

1. Remove global skill files + global manifest entry.
2. Remove only hooks whose **provenance is global** (see provenance change below) —
   i.e. hooks the *global* install wired into repos (only possible once the
   "global install wires repo hooks" feature exists; today global installs wire no
   hooks, so this set is empty).
3. **Never** touch repo-scoped installs of the same skill automatically. Instead,
   detect every repo with a repo-scoped install (scan `manifest.repos[*].skills`)
   and present an **aggregated prompt**:

   ```
   verification-writer is also repo-installed in 4 repos.
     [a] Uninstall in all 4 repos
     [e] Ask for each
     [s] Show me where it's installed first
     [g] Only uninstall globally — leave repo installs alone   (default)
   ```

   `[s]` lists repo path + version + hook count, then re-presents the prompt.

4. **Non-interactive** (`--yes` / no TTY): require an explicit
   `--repos all|none|<path,...>` flag. Absent the flag, default to `none` (leave
   repo installs alone) and print what was skipped. (Matches the earlier decision:
   destructive cross-repo action requires explicit acknowledgment.)

The inverse already holds: repo-scoped uninstall is repo-scoped and never touches
global.

### Data-model change: hook provenance

Add `source_scope: "global" | "repo"` to `ItemHookState` (default `"repo"` for
back-compat — every hook recorded today came from a repo-scoped install). Lets a
repo that has *both* a global-origin hook and a repo-scoped install separate the
two sets deterministically (fingerprint + source_scope), so global uninstall can
remove its own footprint without disturbing the repo install.

### C. Guard: warn on global install of a hook-bearing skill

When `aec install <skill>` runs with global scope and the skill ships ≥1 hook
(`hooks.json` parsed, count > 0):

- Print a **bold, colored** warning naming the hooks and that they are dormant when
  installed globally (global installs wire no hooks today).
- State the cure: `aec install <skill>` from inside a repo wires the hooks there,
  keeping skill + hooks + state in one self-cleaning scope.
- Interactive: confirm before proceeding (assertiveness level — see Open Question 1).
- Non-interactive: require `--allow-dormant-hooks`, else refuse. (Decided.)
- Do **not** fire for hookless skills (e.g. `browser-verification` ships no `hooks.json`).

Steering users to per-repo install is deliberate: the global-skill + repo-hooks
hybrid is the configuration that manufactures the orphan-tracking problem. Keeping
scope unified means the existing repo-scoped uninstall already cleans up correctly.

## 4. Tasks

1. Add `source_scope` to `ItemHookState` (+ load/save back-compat default).
2. Fingerprint-based locator: given a recorded hook, find its entry in an agent
   settings file by fingerprint, return (found, index, status).
3. `aec hooks verify` — read-only report across manifest repos (+ `--scan`).
4. `--repair` (+ `--prune-orphans`) wired to existing install/remove lifecycle.
5. `aec doctor` integration: drift summary line.
6. Scope-aware global uninstall: detect repo-scoped installs, aggregated prompt,
   `--repos` flag, provenance-filtered global-hook removal.
7. Global-install hook-dormant warning + `--allow-dormant-hooks`.
8. Tests (real files, no mocks): seed repos with each drift class; assert verify
   classification, repair convergence, and that global uninstall leaves repo
   installs untouched without consent. Cover provenance separation in a repo that
   has both global-origin hooks and a repo install.

## 5. Edge cases

- Repo in manifest but deleted from disk → skip with warning, offer to prune manifest.
- settings.json hand-edited (MODIFIED) → never silently overwrite; show diff, require confirm.
- Multiple agents (claude/gemini/cursor/git) per hook → verify/repair each independently
  (state already records per-agent pointers).
- `when` predicate now false (repo structure changed since install) → a
  legitimately-skipped hook is not "MISSING"; verify must read `hooks_skipped`, not
  only `hooks_installed`.
- Git hooks (blocking `pre_commit`, e.g. ptg) drifting is higher severity — a dangling
  absolute path in a blocking hook breaks commits. Flag these louder.

## 6. Immediate remediation (independent of this plan)

`email_demo` and `kylebruns` are broken **now**. Two options:
- Hand-merge the missing `verification-writer` hook into each settings.json + fix the
  state pointer (one-off, manual).
- Leave them as the first real fixtures for `aec hooks verify --repair` and fix them
  by running the tool once built (preferred — proves the tool on real drift).

Also flag: a10d.info's `verification-writer` was installed today (2026-06-25 21:52)
by something other than this session. If unintended, that is a possible
no-auto-install violation worth tracing.
