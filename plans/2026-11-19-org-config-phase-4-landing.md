# Land org-config Phase 4 (policy expressiveness) from the parked branch

**Status:** Scheduling pending (Needs-PM). Decided 2026-11-19: keep the branch, land it by this plan.
**Branch:** `claude/org-config-phase-4`, tip `7aa296725c25390cc3b0e3f9ae2b437443f7841e`, 15 commits, no PR was ever opened.
**Merge base with `staging`:** `1e42850`. `staging` is now 208 commits ahead, 9 of them touch `aec/lib/org_config/` or `aec/commands/org.py`.

## Problem

Org configs cannot yet express time-bound rules, per-project overlays, an `enrollment_script`, or branding.
The design (`docs/superpowers/specs/2026-05-04-org-config-overlay-design.md`) and the build plan
(`docs/superpowers/plans/2026-05-25-org-config-overlay-phase-4.md`) both exist, and the work was built, tested and
documented on the branch above. It never reached a PR, so none of it is on `staging` or `main`, and the build plan
on `staging` still says "build-ready". The unreleased work is only as safe as the branch ref: it exists nowhere else.

## What exists only on that branch

Counts are from `git diff --stat` against the merge base: 29 files, +2186 / -81.

| Feature | Commits | New or changed code | Tests |
|---|---|---|---|
| 4b time-bound rules (`required_after`, `expires_at` per item) | `289f21f`, `28ff874`, `2ee13f8` | `timebound.py`, validator, `apply.py` | `test_timebound.py`, validator tests |
| 4a per-project overlays (`projects[]`, match by git remote or directory, first match wins, repo-scope apply) | `97d8813`, `efa9bb8`, `f2dc87d`, `3b6a845` | `projects.py`, `schema.py`, `effective.py`, `apply.py` | `test_projects.py`, `test_effective_projects.py`, `test_org_apply_repo.py` |
| 4c `enrollment_script` (closed action set, no shell) | `782a29e`, `838bcc4`, `7ffab1e` | `enrollment.py`, validator, `aec/commands/org.py` | `test_enrollment.py`, `test_org_enroll_script.py` |
| 4c custom source clone with per-source error capture | `d9e00a4` | `sources_sync.py` | `test_sources_sync.py` |
| 4d branding (`display_name`, `welcome_message`, `doctor_footer`) | `fdc05ec` | `aec/commands/org.py`, `aec/commands/doctor.py` | `test_branding.py` |
| Public surface, docs, example | `fe96bfd`, `e2e5a45`, `7aa2967` | `__init__.py`, `docs/orgs/authoring-org-configs.md`, `docs/users/org-configs.md`, `docs/orgs/examples/phase4-features.yaml` | `tests/docs/test_org_examples.py` |

The roadmap's icebox row "Executable shell in `enrollment_script`" stays true: the closed action set is `add_source`,
`install_items`, `set_hooks`, `run_doctor`, `set_pref`.

## What would have to change before it can land

A trial `git merge-tree` of the branch onto `staging` conflicts in two files, `aec/lib/org_config/apply.py` and
`aec/lib/org_config/validator.py`. The text conflicts are the small part. The design drift is the large one:

1. **Custom source clone is already on `staging` in another shape.** `aec/lib/org_config/git_source.py` and the
   publish path in `apply.py` (PR #132, plus `2026-11-14-custom-source-version-ranges.md`,
   `2026-11-15-custom-source-validation-hardening.md` and `2026-11-15-local-org-ref-tip-check.md`) own cloning,
   ref pinning, validation and crash-safe publication. The branch's `sources_sync.py` (`d9e00a4`) is a second clone
   implementation that predates all of that. Per "check what already provides it", it is dropped, not rebased.
   Its one idea worth keeping is per-source error capture, so a failed source skips only its own items: S2 checks
   whether `staging` already does that and adds only the gap.
2. **The validator was rewritten around it.** `validator.py` on the branch changed by about 286 lines and assumes
   the old `projects`/`enrollment_script` rejection seams (validator lines 82 and 88 at the merge base). `staging`
   added source, version-range and hardening checks in the same functions. Re-apply the Phase 4 checks onto the
   current validator instead of merging the old file.
3. **Overlay answers are machine-global on `staging`.** `2026-11-15-owner-scoped-overlay-answers.md` is the
   open plan for that. Per-project overlays apply at repo scope, so S3 states how they interact with it and
   either sequences after it or pins today's behavior with a test.
4. **Python 3.9.** CI runs 3.9 and 3.12 on macOS. The branch was written against that rule; re-run on 3.9 after the rebase.
5. **The plan move.** `7aa2967` archives the build plan to `docs/superpowers/plans/archive/`. Do that only in the
   last PR, once the work is actually on `staging`.

## Steps

Each step is one dispatchable unit and its own PR into `staging`, rebased fresh from `staging`, not merged from the branch.

- **S1. Time-bound rules (4b).** Cherry-pick `289f21f`, `28ff874`, `2ee13f8` onto a fresh branch, resolve in `apply.py`
  and `validator.py`, tests green on 3.9 and 3.12. Smallest, no dependency on the others.
- **S2. Enrollment script and source sync (4c).** `782a29e`, `838bcc4`, `7ffab1e` only. Drop `d9e00a4`. Decide the
  per-source error-capture gap against `git_source.py` and add only that, with a test that one failing source skips only its own items.
- **S3. Per-project overlays (4a).** `97d8813`, `efa9bb8`, `f2dc87d`, `3b6a845`. Includes the owner-scoped answers interaction from item 3.
- **S4. Branding (4d), public surface, docs.** `fdc05ec`, `fe96bfd`, `e2e5a45`, example YAML, plus archiving the build plan (`7aa2967`).
- **S5. Retire the branch.** After S4 merges, verify content-equivalence with `git diff origin/staging origin/claude/org-config-phase-4 -- aec docs tests`
  (squash merges make `ahead_by` meaningless), take a bundle (`git bundle create`) as the restore point, then delete the branch.
  Deleting it is destructive, so it stays with the maintainer.

Order: S1, S2, S3 can run in parallel only if their file ownership is split (they all touch `apply.py` and `validator.py`),
so run them in sequence. S4 last.

## Contract change coverage

Every step adds optional keys to the org config schema. `schema_version` stays `"1.0"`; older `aec` readers reject
unknown keys, so an org that uses a Phase 4 key needs members on a Phase 4 `aec`. The step that adds the key states
that in `docs/orgs/authoring-org-configs.md` (the branch already carries the text). Before each step, grep every
writer and reader of the org config: `validate_org_config`, `parse_org_config_text`, `effective_policy`, `apply_org_policy`,
`aec org enroll`, `aec org apply`, `aec doctor`, the examples under `docs/orgs/examples/`, and the tests that enumerate them.

## Done when

- S1 through S4 merged to `staging`, each with tests on Python 3.9 and 3.12, `docs/qa-verification.md` updated where a user-visible flow changed.
- `aec org validate` accepts `docs/orgs/examples/phase4-features.yaml` on `staging` (`tests/docs/test_org_examples.py` pins it).
- No second clone implementation in `aec/lib/org_config/`.
- The branch is retired by the maintainer after S5's check, with the bundle kept.

## Out of scope

Org-to-org inheritance, per-user overrides, telemetry and a central registry stay on the icebox (see `plans/ROADMAP.md`).
