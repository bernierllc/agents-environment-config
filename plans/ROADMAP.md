# AEC Roadmap

**Last reviewed:** 2026-08-18 — Matt (headless prompts added to Tier 1)
**Current shipped version:** v2.38.1

## What AEC is

`agents-environment-config` (AEC, `aec` on pip) is a zero-runtime-dependency
Python CLI that installs and manages agents, skills, rules, MCP servers, and
hooks across user projects. Solo maintainer, pre-customer / early-adopter
stage: we optimize for shipping quickly, breaking things on purpose when the
underlying design improves, and keeping the public CLI surface
self-documenting. The roadmap below is the prioritized bet on where the next
unit of impact lives — not a contract.

---

## Review follow-ups awaiting prioritization

- [Remove `installed` from `.aec.json`](2026-11-27-aecjson-installed-section-removal.md): `aec repo setup/sync` copies the GLOBAL
  manifest into each repo's `.aec.json` `installed` section, so it shows another scope's versions, while the v2 manifest already
  records installs per repo. Repoint `aec discover` at the manifest's repo scope, delete the copy writer, drop the schema key,
  migrate existing files, point readers at the manifest (aec export or aec list). Scheduling pending.
- [Skill install scan](2026-11-24-skill-install-scan.md): `aec` places third-party skills into full-access agents with no
  content check, and `aec skills install/update` bypass the one write chokepoint. Run NVIDIA/SkillSpector in `--no-llm`
  static mode as a blocking, fail-closed check inside `place_installed_item`, route the bypass through it, record the verdict
  in the manifest, and certify the catalog in CI. Scheduling pending: Tracker placement row `PLACE: Skill install scan`.
- [Review-gate doctor: `Review Gate` required without a default-branch workflow](2026-11-24-doctor-required-check-workflow-exists.md): a ruleset can
  require `Review Gate` when the default branch has no workflow that publishes it (it loads from the default branch), which
  deadlocks ordinary merges. The doctor should fail on that one contract where it can read rulesets; general producer
  inference is a separate plan. The installer seed flag and templates were dropped because an org's
  repo-create script already seeds before rulesets. Scheduling pending.
- [prune-merged-worktrees ignored-.env guard fails open](2026-11-16-prune-env-guard-fail-open.md): `grep -q`
  under pipefail read 2+ unique `.env` files as none, and any `.env` symlink was exempt; both deleted unique
  data. P1 data loss; fix shipped with the plan.

- [prune-merged-worktrees guard hardening](2026-11-22-prune-env-guard-hardening.md): follow-up to the fail-open
  fix. `assume-unchanged`/`skip-worktree` targets, C-quoted names (`ls-files -z`) and macOS `readlink -f`
  portability still read as "nothing to keep". P1 data loss; planned.

- [Trusted replay for merge-with-main promote slices](2026-11-21-mvs-trusted-slice-replay.md): a
  downstream slice-aware mid guard fails closed for a slice head that merges main into its staging cut. The
  guard should run the base ref's script and generator over fetched head objects; consuming the
  `Promote slice` check result is rejected (it runs from the PR head, so a forged check passes).
  Scheduling pending.

- [Land org-config Phase 4 from the parked branch](2026-11-19-org-config-phase-4-landing.md): time-bound
  rules, per-project overlays, `enrollment_script` and branding are built, tested and documented on
  `claude/org-config-phase-4` (tip `7aa2967`, 15 commits, never a PR) and exist nowhere else. `staging` moved
  on (208 commits, two conflicting files, and its own custom-source clone). Four rebased PRs, then retire the
  branch. Scheduling pending.

- [Unforgeable required checks (SEC-MVS-01)](2026-11-16-unforgeable-required-checks.md): required checks
  match name + Actions app id, so a PR workflow can publish a protected name (as a job or through the Checks
  API). Interim detector covers the job case; the permanent fix is an org required workflow or our own App.
  Awaiting the maintainer's A/B choice.

- [Stale skills fail loudly](2026-11-21-stale-skills-fail-loudly.md): `aec update` reports stale skills and exits 0,
  `aec upgrade` always exits 0, `run-script` silently runs an older repo copy, `doctor` ignores vendored versions, and
  re-vendoring from a stale source ships old checkers. Exit-code contract (14 = work remains), `run-script` and `doctor`
  warnings, re-vendor refusal in claude-skills. Extends the vendored-copies plan below. Scheduling pending.

- [`aec upgrade` detects vendored skill copies](2026-11-16-upgrade-detects-vendored-skills.md): "(up to date)"
  is computed from the manifest only, so stale vendored skill copies in a repo are never reported or upgraded.
  Scheduling pending.

- [Idempotent hook install from a git worktree](2026-11-16-install-from-worktree-idempotent-hooks.md):
  installing from a linked worktree appends a duplicate gemini hook with the worktree's absolute path and
  repoints `.aec/installed-hooks`. Scheduling pending.

- [Honor the AGENTINFO.md layout everywhere](2026-11-15-agentinfo-layout-honored.md): `aec migrate
  agents-md` (and its `--all` / maintenance-prompt path) ignores `instructions_layout=agentinfo`, and
  `aec generate files` writes AEC's own `templates/`. One owner for the layout decision. Scheduling pending.

- [Owner-scoped overlay answers](2026-11-15-owner-scoped-overlay-answers.md): org overlay answers
  are machine-global, so a repo-shaped answer (license kind) reaches repos outside the org. Scheduling pending.

- [Catalog support for per-repo records](2026-11-14-catalog-repo-records.md): catalogs can already
  carry per-repo data; AEC should validate, expose and check it. Scheduling pending.

- [Release pushes vs PR-only rules](2026-11-14-release-pushes-vs-pr-only-rules.md): the release
  workflow pushes to `main` directly, which blocks PR-required rules and a `staging` branch.
  Scheduling pending.

- [Recover an interrupted custom-source publication](2026-11-14-org-source-publish-crash-recovery.md):
  P2 from PR #132; a kill between the source rename and the state write loses the known-good
  checkout. S1 makes publication crash-safe. Scheduling pending.

- [Confine the remaining setup writers](2026-11-14-confine-remaining-setup-writers.md):
  writer sweep from PR #136; `.gitignore`, git-essentials templates and the
  plans migration still follow symlinks. S1 routes them through
  `aec.lib.confine`. Scheduling pending.

- [Deterministic directory prefix rendering](2026-11-10-directory-prefix-rendering.md):
  P2 from PR #131; S1 replaces cascading rewrites with original-path matching
  and validates overlapping defaults. Scheduling pending.

- [Hook consent transitions](2026-11-10-hook-consent-transitions.md): two P2
  findings from PR #131; S1 owns durable declarative opt-out and optional
  pipeline re-enablement through the existing lifecycle. Scheduling pending.

- [Shared directory transactions](2026-11-10-shared-directory-transactions.md):
  P2 concurrency finding from PR #131; S1 owns serialization and multiprocess
  validation. Scheduling pending.

- [AGENTS.md layout and `aec rollback`](2026-11-14-agents-md-layout-and-rollback.md):
  opt-in AGENTINFO.md → AGENTS.md migration recorded as reversible changesets.
  In progress on `feat/agents-md-migration`.

- [Custom-source validation hardening](2026-11-15-custom-source-validation-hardening.md): two
  P2s from PR #132; a non-UTF-8 source file crashes apply instead of failing the source, and a
  numeric YAML `version` passes validation then never matches. Scheduling pending.

## Tier 1 — Now (active this cycle)

Work that is in flight or unblocked and at the front of the queue.

| Initiative | Why now | Plan file | Status |
|---|---|---|---|
| Hook management completion (Task 13/14/16 + `aec run-script`) | Library shipped in v2.32.0 but no caller invokes it — installed skills that ship hooks today do nothing. Closing the gap unlocks every downstream package that depends on hooks. | `docs/superpowers/plans/2026-04-21-aec-hook-management.md` *(active worktree — do not edit)* | In-flight (parallel agent) |
| Plugin management + loadout schema (Phase 1) | Adds a fifth item type (plugins) installed via a portable `plugin.json` loadout manifest, with three install types (marketplace / per-tool / external) and a never-auto-install guarantee. Lets AEC install plugins and seeds the loadout manifest format. | `docs/superpowers/plans/2026-06-25-aec-plugin-management-loadout.md` | In-flight (`feature/plugin-management-loadout-schema`) |
| Headless prompts (agent-answerable CLI) | 75 interactive callsites across 19 files have no non-interactive path and no way for an agent to discover what will be asked. Gating dependency for the Tier-3 agent-native onboarding bet, and today `aec test schedule -g` under a closed stdin silently registers an OS job. Finishes the `prompts.py` seam org-config Phase 1 left at 4 of 75 callsites. | `docs/superpowers/plans/2026-08-18-headless-prompts.md` | In-flight (`feat/headless-prompts`) |

**Exit criteria for Tier 1:** `aec install <item-with-hooks>` actually wires
hooks into Claude/Gemini/Cursor/Git; `aec uninstall` removes them cleanly;
`aec hooks` CLI exposes at least `validate`, `list`, `install`, `remove`; every
interactive prompt is answerable via `--answers` and discoverable via `aec prompts`.

---

## Tier 2 — Next (1–2 cycles out)

Directionally committed; spec or scope-skeleton exists; needs one resolution
pass before tasks are picked up.

| Initiative | Hypothesis / expected outcome | Plan file | Confidence |
|---|---|---|---|
| Org-config Phase 2 — signing, multi-org, propagation | Phase 1 made org configs work for a single unsigned org. Phase 2 makes them safe (signed), multi-org-aware, and refresh-aware — the bar for any real org adoption. | `docs/superpowers/plans/2026-05-19-org-config-overlay-phase-2.md` *(skeleton — open questions inside)* | Med — 6 open Qs to resolve before tasks |
| Org-config plugin governance | `ITEM_TYPES` omits `plugins`, so an `items.plugins` org policy is silently dropped today and would `KeyError`-crash `aec org apply` once exercised. Closes the gap left when plugin management shipped (PR #55) — wires plugins through the org-config apply pass via the loadout `install_plugin` engine. | `docs/superpowers/plans/2026-06-25-org-config-plugin-governance.md` *(revised 2026-10-06 for Claude-owned plugin versions; shipped in #110, v2.47.0)* | High — root cause + fix scoped; `pinned`/`version` rejected for plugins |
| Org-config settings & file delivery | Org configs can carry skills/rules but not agent settings or files, custom git sources are declared but never cloned, and private catalogs can't refresh — so org-wide `autoMode`, global `AGENTS.md` and references are hand-synced per machine. Git-sourced org configs + `agent_settings` (owned-key merge into user settings) + `files`, with drift refusal, delivered by `aec org apply` / `aec update`. | `docs/superpowers/plans/2026-10-06-org-config-settings-delivery.md` | High — root cause + design scoped; no blocking Qs; follows plugin governance (both touch `aec org apply`) |
| Plugin parity for other agents | AEC manages Claude Code plugins end to end (install, detect, update, uninstall, org policy). Codex, Gemini, Qwen and Cursor only get a one-time command and a stale catalog version. Generalize the Claude manager into per-agent adapters, as far as each agent's CLI allows. | `docs/superpowers/plans/2026-10-06-plugin-parity-other-agents.md` | Med — verify each CLI first (several facts UNVERIFIED) |
| Managed symlink ownership by record | `is_our_symlink` recognises AEC links by a path-name substring, so checkouts cloned under another name leave dangling, never-repaired links after a move or reclone. Record link ownership at creation instead. | `docs/superpowers/plans/2026-09-25-managed-symlink-ownership.md` | High — root cause + fix scoped |
| Hook lifecycle transactions | `aec upgrade` removes an item's hooks and then reinstalls them, so a failed reinstall leaves it hookless and drops custom_check consent. #99 made install/remove all-or-nothing; this finishes the job for every entry point (upgrade, org apply, drift repair), makes restore report every path it could not restore, and names the fix when a state file is corrupt. | `docs/superpowers/plans/2026-09-30-hook-lifecycle-transactions.md` | High — root cause + fix scoped; item 1 is a small deletion |
| Adopt prewired hooks | A committed hook entry (PR #101's pr-merge-flow guard) has no aec state on a fresh clone, so catalog refresh never re-renders it and uninstall leaves it active. Adopt entries listed in an explicit committed registry of hooks aec prewires (item, agent, event, fingerprint), kept fresh by a CI test. | `docs/superpowers/plans/2026-10-01-prewired-hook-adoption.md` | High — root cause + fix scoped |
| Render agent rules per user | `.agent-rules/` is tracked **and** is every user's installed rule set (symlinked from `~/.agent-tools`), so `aec install` renders personal settings into tracked files: every non-default user gets a permanently dirty checkout. Keep the repo copy default-rendered and exact-validated; render a per-user installed copy. | `docs/superpowers/plans/2026-09-26-agent-rules-per-user-render.md` | High — root cause + fix scoped; pairs with managed symlink ownership |
| Loadout open-standard extraction (Phase 2) | Move the `loadout` / `plugin.json` schema + docs out of AEC into the open repo `github.com/mbernier/loadout` so any AI tool — not just AEC — can publish and consume loadout manifests, making loadout a tool-neutral standard. | `docs/superpowers/specs/2026-06-25-aec-plugin-management-and-loadout-schema-design.md` (Phase 2; repo cloned at `~/projects/loadout`) | Med — gated on Phase 1 shipping + intent to publish |
| API and MCP verification skills + access manifest | The UI verification chain (verification-writer → browser-verification → playwright-*) has no API or MCP counterpart, so nothing tells docs agents what is customer-facing, role-gated, tier-gated or unreleased. Adds `api-verification-writer`, `api-verification` (role/scope matrix runner) and a generated access manifest, and wires feedback between the docs and verification agents. | `plans/api-mcp-verification-skills.md` | Medium (open questions in plan) |
| Org-config version constraints | One evaluator (`version_satisfies`, beside `parse_version`) now gates every source, default catalog included: mismatch or malformed pin is unsatisfiable, the validator accepts exactly what it parses, and a constraint gates but never selects an older version. | `plans/2026-11-14-custom-source-version-ranges.md` | In review — Tracker AEC-VERSION-RANGES-1 |
| Org-config ref-tip check for local enrollments | A locally enrolled org with a ref-only custom source never notices its branch moved: the tip check lives in `_refresh_one`, which `refresh_remote_orgs` skips for local orgs. `git+`/url enrollments are unaffected. Split the check out and run it for local orgs too. | `plans/2026-11-15-local-org-ref-tip-check.md` | Medium — root cause + fix scoped |

**Gate to advance to Now:** answer the 6 open questions in the Phase-2 skeleton
(esp. crypto library, conflict-UX shape, managed-mode propagation timing) and
break Phase 2 into the four 2a–2d sub-phases described in the plan.

---

## Tier 3 — Later (3–6 months / strategic)

Scope is known; not ready to build; needs the Tier-2 work to land first or
needs a stronger user signal before we commit engineering time.

| Initiative | Strategic hypothesis | Plan file | Signal to advance |
|---|---|---|---|
| AEC packages + agent-native onboarding | Today users (and their agents) drive AEC by remembering commands. A package + template system would let an agent reason about the project and `aec install` the right bundle. Natural successor to org-config. | `docs/superpowers/plans/2026-04-10-aec-packages-agent-onboarding.md` | Phase 2 of org-config shipped + first real external user asking for bundled setup |
| Loadout adoption PRs (Phase 3) | Add `plugin.json` loadout files to the items and plugins we ship, and open PRs to the upstream plugins we depend on — seeding real-world loadout adoption beyond AEC itself. | `docs/superpowers/specs/2026-06-25-aec-plugin-management-and-loadout-schema-design.md` (Phase 3) | Phase 2 extraction landed + a second tool or plugin author consuming loadout |

---

## Tier 4 — Backlog

Small, well-understood items waiting for a verification or cleanup pass.

| Item | What's left | Source |
|---|---|---|
| Skill versioning verification + archive | Code is shipped (`aec/lib/skills_manifest.py`, `aec/commands/skills.py`, doctor checks). Need to confirm legacy-symlink cleanup is wired into `aec install` and run a real install/update/uninstall smoke. ~1h. | `docs/superpowers/plans/2026-03-30-skill-versioning-implementation.md` |
| Physical archive of shipped plans | Five plans have shipping-status headers but still live in `docs/superpowers/plans/`. Run the `git mv` block in `docs/superpowers/plans/archive/README.md`. | `docs/superpowers/plans/archive/README.md` |

---

## Not building (and why)

Saying no in public prevents the same idea coming back six times.

| Request | Source | Reason | Revisit when |
|---|---|---|---|
| Public registry of well-known orgs for org-config | Org-config design spec | Adds central infra + trust questions that don't pay off for the current single-maintainer scale. | A second external org adopts AEC and asks for it |
| Telemetry from user machines back to orgs | Org-config design spec | Surveillance attack surface > value. Users explicitly do not want this. | Never (unless privacy-preserving model emerges) |
| Org-to-org config inheritance | Org-config design spec | YAML composition without inheritance is already explicit and debuggable. | A real org hits a duplication ceiling |
| Executable shell in `enrollment_script` | Org-config design spec | Would gut the signing trust model. Use declarative actions instead. | Never |

---

## What was archived 2026-05-19

These plans shipped and have `> Status: shipped …` headers prepended in-place.
Physical relocation to `docs/superpowers/plans/archive/` is pending — see
`docs/superpowers/plans/archive/README.md` for the `git mv` block.

- `2026-03-30-plan-review-skill.md` (skill in catalog)
- `2026-04-04-brew-aligned-cli-redesign.md` (flat-commands live)
- `2026-05-02-git-setup-phase.md` (PR #39)
- `2026-05-04-org-config-overlay-phase-1.md` (PR #47 + #48)
- `2026-05-12-aec-agent-blurb.md` (PR #50)

Legacy `plans/` files marked shipped or superseded in-place:

- `2026-03-04-version-check-design.md` + `-implementation.md` — shipped
- `2026-04-21-aec-hooks-foundation-and-lifecycle.md` — superseded by current
  hook-management plan

---

## How this roadmap is maintained

- **One owner (Matt).** No formal review cadence; re-level whenever a tier-1
  item ships or a new initiative arrives.
- **Plans are the source of truth for scope.** This file is the index; per-plan
  files hold the details. Now/Next plans get full task breakdowns; Later/Backlog
  plans get scope + open questions only.
- **Promotion gates are written, not implicit.** Every tier-down item lists what
  has to be true to advance — answer those before moving the row up.
- **Shipped → archived within a week.** Prepend `> Status: shipped via PR #N
  on YYYY-MM-DD`, run `git mv` into `docs/superpowers/plans/archive/`,
  remove from the active table here.
- **`plans/` is gitignored.** Durable implementation and deferral plans are
  explicitly tracked with `git add -f` and linked here so worktree cleanup does
  not discard outstanding work.
