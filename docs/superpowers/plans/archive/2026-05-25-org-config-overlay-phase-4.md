# Org Config Overlay — Phase 4 (policy expressiveness) Implementation Plan

> Status: build-ready (2026-05-25). Branch: `claude/manifest-features-launch-joqf5` is merged/under review as PR #54 (Phases 1–3); start Phase 4 on a fresh branch off `main` after #54 lands.

> **For agentic workers:** REQUIRED SUB-SKILL: implement task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax. Test first → watch it fail → implement the minimum → watch it pass → run the full suite → commit. Do not batch tasks.

**Goal:** Extend the shipped overlay applier with the deferred *policy-expressiveness* features from the design spec — per-project overlays, time-bounded rules, declarative `enrollment_script` actions, and branding — without breaking the closed-schema / signed-trust / P7-conflict guarantees from Phases 1–3.

## Scope (locked 2026-05-25)

**In scope (4a–4d):**
- **4a** — Per-project overlays (`projects[]`): `match` on `git_remote`/`directory` → a profile delta layered on org policy, applied at **repo scope** (first match wins).
- **4b** — Time-bounded rules: per-item `required_after` / `expires_at`, evaluated against `now`.
- **4c** — `enrollment_script`: the closed declarative action set (`add_source`, `install_items`, `set_hooks`, `run_doctor`, `set_pref`) — no shell escape hatch.
- **4d** — Branding: `display_name` / `welcome_message` / `doctor_footer`.

**Iceboxed (P5+, by decision):** org-to-org inheritance/delegation; per-user overrides inside one config; telemetry; central org registry; MDM-driven auto key rotation. Each is additive in a later schema version — do not design for them now.

**Parent spec:** `docs/superpowers/specs/2026-05-04-org-config-overlay-design.md` — see the annotated example (`projects:`, `enrollment_script:`, `branding:`), "Schema design notes", and the `enrollment_script` Actions Reference appendix.

## What already shipped (reuse, do not rebuild)

- Schema/parse/validate: `schema.py` (`OrgConfig`, `ItemPolicy`, `Stance`, `CustomSource`), `parser.py` (`parse_org_config_text`), `validator.py` (`validate_org_config`; **already rejects** `projects` at validator.py:82 and `enrollment_script` at :88 — those are the seams to open).
- Effective policy + applier: `effective.py` (`effective_policy`, `EffectivePolicy`), `apply.py` (`apply_org_policy`, `apply_preferences`, `apply_prompts`, `apply_items`, `compile_desired_items`, `blocked_item_keys`).
- Multi-org + trust + propagation: `conflicts.py`, `resolutions.py`, `reconcile.py`, `rotation.py`, `propagation.py`, `discovery.py`, `paths.py`, `trust.py`, `fetch.py`.
- Custom-source machinery: `aec/lib/sources.py` (clone/register), `apply_core.py` (`DesiredItem` → `plan_apply`/`execute_apply`).
- Prefs/hooks: `aec/lib/preferences.py` (`set_setting`/`set_preference`/`set_instruction_config`, `OPTIONAL_FEATURES`, `KNOWN_PREFERENCE_KEYS`), hook lifecycle.

## Conventions

- TDD, `pytest` from repo root; `tmp_path` + injected `home_dir`/`now`/fetchers — never hit the network.
- **Python 3.9 compatibility is enforced by CI (matrix 3.9 + 3.12).** Lessons from Phase 3:
  - Test on 3.9 locally before pushing: `uv python install 3.9 && uv run -p 3.9 …` or a 3.9 venv.
  - `datetime.fromisoformat` on 3.9 can't parse a `Z` suffix → always `value.replace("Z", "+00:00")` first.
  - In `CliRunner` tests, assert on `result.output` (not `result.stderr`; click < 8.2 raises "stderr not separately captured").
- `schema_version` stays `"1.0"` — every new block is **optional**, so old configs keep validating and new configs keep loading on Phase-1 readers that ignore unknown optional keys is NOT assumed; instead these readers reject unknown keys, so authors using P4 features must require users on a P4-capable `aec`. (Document this; do not bump schema_version unless a field is mandatory.)
- Conventional commits (`feat(org-config):`, `test(org-config):`, `docs(org-config):`). Full suite green with `--cov-fail-under=65` before every commit.

## File structure

### New files
```
aec/lib/org_config/
├── projects.py        # ProjectOverlay matcher: git_remote normalization + glob, directory glob, first-match-wins
├── timebound.py       # pure date-gating helpers (active_at(now, required_after, expires_at) -> effective stance)
└── enrollment.py      # declarative enrollment_script runner (closed action set, idempotent, sandboxed)

tests/lib/org_config/
├── test_projects.py
├── test_timebound.py
├── test_enrollment.py
├── test_effective_projects.py     # repo-scoped effective policy with project overlays
└── test_branding.py
tests/commands/
└── test_org_apply_repo.py         # `aec org apply` inside a matching repo
```

### Modified files
- `schema.py` — add `projects: list[ProjectOverlay]`, `ProjectOverlay`, `ProjectMatch`, `ProjectProfile`; `ItemPolicy` gains `required_after`/`expires_at`; `OrgConfig` gains `enrollment_script: list[dict]` and `branding: Optional[Branding]`.
- `validator.py` — open the `projects` and `enrollment_script` rejection seams; validate the new structures (reuse item/pref/prompt validation); reject unknown `enrollment_script` actions (escape-hatch test from the spec appendix).
- `effective.py` — thread `now` through `effective_policy` for 4b; add `effective_policy_for_repo(paths, *, repo_path, git_remote, now)` for 4a.
- `apply.py` — `apply_org_policy` detects the current repo (via `get_repo_root` + git remote) and additionally applies the repo-scoped project policy; run `enrollment_script` on enroll/apply; surface branding.
- `commands/org.py` — `enroll` runs `enrollment_script`; `apply` does repo-scoped apply; surface `welcome_message` on enroll.
- `commands/doctor.py` — append `doctor_footer` / `display_name` to the org section.
- `commands/install_cmd.py` / `sources.py` — `add_source` enrollment action reuses existing clone/register.
- `__init__.py` — export `match_project`, `effective_policy_for_repo`, enrollment entry point.
- `docs/orgs/authoring-org-configs.md`, `docs/users/org-configs.md`, `docs/orgs/examples/` — document + example each feature.

---

# Sub-phase 4b — Time-bounded rules (do first; smallest, unblocks `now` threading)

## Task 4b.1: `timebound.py` — pure date-gating
**Files:** create `timebound.py`, `test_timebound.py`.
- [ ] Step 1 — failing tests: `active_at(now, required_after=None, expires_at=None) -> bool` true when `required_after <= now < expires_at`; before `required_after` → False; at/after `expires_at` → False; bad/`Z`-suffixed ISO parsed via `.replace("Z","+00:00")`; naive vs aware handled.
- [ ] Step 2 — implement pure function over ISO strings. Module constant for parse helper.
- [ ] Step 3 — commit `feat(org-config): add time-bound rule date gating`.

## Task 4b.2: schema + validator for `required_after`/`expires_at`
**Files:** `schema.py`, `validator.py`, extend `test_schema.py`/`test_validator.py`.
- [ ] Step 1 — failing tests: `ItemPolicy` carries the two optional ISO fields; validator accepts them, rejects non-ISO and `expires_at <= required_after` (`field_path="items.<type>.<name>.expires_at"`).
- [ ] Step 2 — implement; sweep `ItemPolicy` constructors in tests/fixtures (contract change).
- [ ] Step 3 — commit `feat(org-config): validate required_after/expires_at on items`.

## Task 4b.3: apply time gating in effective policy
**Files:** `effective.py`, extend `test_effective.py`.
- [ ] Step 1 — failing tests: `effective_policy(paths, now=…)` omits/keeps install-intent items by `active_at`; an expired `blocked` no longer removes; default `now` = current UTC.
- [ ] Step 2 — implement: thread `now` (default `datetime.now(timezone.utc)` ISO) through `effective_policy`; when an item is outside its window, drop it from install-intent (and from blocked-removal). `apply_org_policy` already has `now`; pass it down.
- [ ] Step 3 — full suite + commit `feat(org-config): enforce time-bounded item stances on apply`.

---

# Sub-phase 4a — Per-project overlays (`projects[]`)

## Task 4a.1: `projects.py` — matcher
**Files:** create `projects.py`, `test_projects.py`.
- [ ] Step 1 — failing tests: `normalize_git_remote("git@github.com:acme/backend.git") == "github.com:acme/backend"` (and the https form normalizes identically); `match_project(projects, repo_path, git_remote)` returns the first entry whose `git_remote` glob (over normalized remote) or `directory` glob (over `expanduser(abspath)`) matches; no match → None; `git_remote` preferred when both present.
- [ ] Step 2 — implement normalization (strip scheme/`.git`, unify `git@host:owner/repo` ↔ `https://host/owner/repo` → `host:owner/repo`) + `fnmatch` globs; first-match-wins.
- [ ] Step 3 — commit `feat(org-config): match per-project overlays by git remote/directory`.

## Task 4a.2: schema + validator for `projects[]`
**Files:** `schema.py`, `validator.py`, `test_validator.py`.
- [ ] Step 1 — failing tests: parse `projects: [{match:{git_remote|directory}, profile:{items, preferences, prompts}}]`; reject an entry whose `match` has neither key; profile items reuse the source-required + allow-list checks; **remove** the Phase-1 `projects` rejection (validator.py:82).
- [ ] Step 2 — implement `ProjectOverlay`/`ProjectMatch`/`ProjectProfile`; profile is a partial delta (only declared keys).
- [ ] Step 3 — full suite + commit `feat(org-config): accept projects[] overlays in schema`.

## Task 4a.3: repo-scoped effective policy
**Files:** `effective.py`, `test_effective_projects.py`.
- [ ] Step 1 — failing tests: `effective_policy_for_repo(paths, repo_path, git_remote, now)` = base global effective policy with each enrolled org's matching `profile` layered on top (profile items override that org's base items for the same subject); cross-org project conflicts reuse the existing subject conflict/held machinery (P7); no matching project → identical to `effective_policy`.
- [ ] Step 2 — implement by extending each org's `items`/`preferences`/`prompts` with its matched profile delta **before** the cross-org merge, so conflict detection and resolutions still key on the same subjects.
- [ ] **DECISION TO RESOLVE:** project-profile **preferences** — prefs.json is global, not repo-scoped. Options: (a) apply profile prefs only while operating in the matching repo (transient, last-write-wins), or (b) restrict profiles to `items`+`prompts` in v1 and defer profile prefs. Recommend (b) for a clean first cut; revisit if authors need it.
- [ ] Step 3 — full suite + commit `feat(org-config): compute repo-scoped effective policy from project overlays`.

## Task 4a.4: apply project policy at repo scope
**Files:** `apply.py`, `commands/org.py`, `test_org_apply_repo.py`.
- [ ] Step 1 — failing tests (seeded catalog like `test_apply_integration.py`): inside a repo whose remote matches a profile, `aec org apply` installs the profile's `required` items at **repo scope** (manifest repo entry + repo `.claude/...` dir); outside any match, behaves as today; held project conflicts surface in the summary.
- [ ] Step 2 — implement: `apply_org_policy` resolves the current repo (`get_repo_root`) + normalized remote; when present, computes `effective_policy_for_repo` and runs `apply_items(..., scope=<repo-path>)` in addition to the global apply. Keep global-only behavior when not in a repo.
- [ ] Step 3 — full suite (run on 3.9 too) + commit `feat(org-config): apply per-project overlays at repo scope`.

---

# Sub-phase 4c — `enrollment_script` declarative actions

## Task 4c.1: schema + validator (closed action set, escape-hatch blocked)
**Files:** `schema.py`, `validator.py`, `test_validator.py`.
- [ ] Step 1 — failing tests: accept the five actions with their params (per appendix); reject unknown action with the exact spec message (`enrollment_script[3].action 'run' is not a recognized action; allowed: add_source, install_items, set_hooks, run_doctor, set_pref`); `add_source.source_id` must exist in `sources.custom`; `set_pref.key` must be allow-listed; **remove** the Phase-1 rejection (validator.py:88).
- [ ] Step 2 — implement validation; keep actions as validated dicts (typed accessors optional).
- [ ] Step 3 — commit `feat(org-config): validate enrollment_script closed action set`.

## Task 4c.2: `enrollment.py` — idempotent, sandboxed runner
**Files:** create `enrollment.py`, `test_enrollment.py`.
- [ ] Step 1 — failing tests (inject appliers/catalog): actions run in declared order; `install_items` filters by `types`/`sources` and reuses `apply_items`; `set_pref` honors `if_unset` (+ managed/guided default) via `preferences`; `add_source` reuses `sources.py` clone/register (idempotent); `run_doctor` non-fatal on warnings, fatal on errors; an action failure halts and is reported; **no shell/network/path-escape** (assert it never writes outside `~/.aec`/`~/.agent-tools`/AEC-managed paths).
- [ ] Step 2 — implement `run_enrollment_script(config, paths, *, mode, …)` mapping each action to existing primitives; halt-on-failure with a structured result.
- [ ] Step 3 — full suite + commit `feat(org-config): run declarative enrollment_script actions`.

## Task 4c.3: wire into enroll/apply
**Files:** `commands/org.py`, `apply.py`, extend command tests.
- [ ] Step 1 — failing tests: `aec org enroll` (and `aec install --org-config`) runs the script after a successful verify+persist; failures surface and set non-zero exit; re-enroll is idempotent.
- [ ] Step 2 — implement: call `run_enrollment_script` from `perform_enroll`; respect `install.mode`.
- [ ] Step 3 — full suite + commit `feat(org-config): execute enrollment_script on enroll`.

---

# Sub-phase 4d — Branding

## Task 4d.1: schema + surface
**Files:** `schema.py`, `validator.py`, `commands/org.py`, `commands/doctor.py`, `test_branding.py`.
- [ ] Step 1 — failing tests: `branding.{display_name,welcome_message,doctor_footer}` parse; `aec org enroll` prints `welcome_message`; `aec doctor` org section shows `display_name` + `doctor_footer`.
- [ ] Step 2 — implement (string fields, all optional); surface in enroll output + doctor footer.
- [ ] Step 3 — full suite + commit `feat(org-config): surface org branding on enroll and doctor`.

---

# Cross-cutting

## Task X1: docs + examples
- [ ] Update `docs/orgs/authoring-org-configs.md` (projects[], time-bound rules, enrollment_script reference, branding) and `docs/users/org-configs.md` (repo-scoped apply, what enrollment_script may do).
- [ ] Add `docs/orgs/examples/projects-overlay.yaml` and an `enrollment_script` example; validate all examples through the real parser+validator (as in Phase 3).
- [ ] Commit `docs(org-config): document phase-4 expressiveness features`.

## Task X2: exports + plan archive
- [ ] Export new public surfaces from `__init__.py`; smoke-test imports.
- [ ] On completion, move this plan to `docs/superpowers/plans/archive/` and index it. Commit `docs(plans): archive org-config phase 4`.

---

## Decisions to resolve during build
1. **Project-profile preferences** (4a.3) — recommend items+prompts only in v1; defer profile prefs.
2. **Repo-scope vs global apply ordering** (4a.4) — apply global first, then repo overlay; ensure idempotence on re-run.
3. **`required_after` semantics** (4b.3) — before the date, drop install-intent entirely vs downgrade to `recommended`. Recommend: drop (simplest, matches "takes effect after").
4. **enrollment_script vs the always-on applier** (4c) — `install_items`/`set_pref` overlap `apply_org_policy`. Keep enrollment_script as an explicit, ordered, enroll-time runner; document that managed-mode apply still happens on every invocation regardless.

## Definition of done
- An org can scope policy to repos via `projects[]` (git_remote/directory, first-match-wins), applied at repo scope with P7 conflicts still held.
- `required_after`/`expires_at` gate item stances against `now`.
- `enrollment_script` runs the closed action set idempotently on enroll, with the shell escape hatch rejected at validation.
- Branding surfaces on enroll + doctor.
- All new configs validate; suite green on **3.9 and 3.12** with coverage ≥ 65%.

## Suggested execution order
`4b.1 → 4b.2 → 4b.3` (time-bound; threads `now`) → `4a.1 → 4a.2 → 4a.3 → 4a.4` (projects) → `4c.1 → 4c.2 → 4c.3` (enrollment_script) → `4d.1` (branding) → `X1 → X2`.
