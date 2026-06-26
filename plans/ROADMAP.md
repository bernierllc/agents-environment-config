# AEC Roadmap

**Last reviewed:** 2026-06-25 — Matt (plugin-management Phase 1 in flight)
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

## Tier 1 — Now (active this cycle)

Work that is in flight or unblocked and at the front of the queue.

| Initiative | Why now | Plan file | Status |
|---|---|---|---|
| Hook management completion (Task 13/14/16 + `aec run-script`) | Library shipped in v2.32.0 but no caller invokes it — installed skills that ship hooks today do nothing. Closing the gap unlocks every downstream package that depends on hooks. | `docs/superpowers/plans/2026-04-21-aec-hook-management.md` *(active worktree — do not edit)* | In-flight (parallel agent) |
| Plugin management + loadout schema (Phase 1) | Adds a fifth item type (plugins) installed via a portable `plugin.json` loadout manifest, with three install types (marketplace / per-tool / external) and a never-auto-install guarantee. Lets AEC install plugins and seeds the loadout manifest format. | `docs/superpowers/plans/2026-06-25-aec-plugin-management-loadout.md` | In-flight (`feature/plugin-management-loadout-schema`) |

**Exit criteria for Tier 1:** `aec install <item-with-hooks>` actually wires
hooks into Claude/Gemini/Cursor/Git; `aec uninstall` removes them cleanly;
`aec hooks` CLI exposes at least `validate`, `list`, `install`, `remove`.

---

## Tier 2 — Next (1–2 cycles out)

Directionally committed; spec or scope-skeleton exists; needs one resolution
pass before tasks are picked up.

| Initiative | Hypothesis / expected outcome | Plan file | Confidence |
|---|---|---|---|
| Org-config Phase 2 — signing, multi-org, propagation | Phase 1 made org configs work for a single unsigned org. Phase 2 makes them safe (signed), multi-org-aware, and refresh-aware — the bar for any real org adoption. | `docs/superpowers/plans/2026-05-19-org-config-overlay-phase-2.md` *(skeleton — open questions inside)* | Med — 6 open Qs to resolve before tasks |
| Org-config plugin governance | `ITEM_TYPES` omits `plugins`, so an `items.plugins` org policy is silently dropped today and would `KeyError`-crash `aec org apply` once exercised. Closes the gap left when plugin management shipped (PR #55) — wires plugins through the org-config apply pass via the loadout `install_plugin` engine. | `docs/superpowers/plans/2026-06-25-org-config-plugin-governance.md` *(full plan — correct fix + affected surfaces inside)* | High — root cause + fix scoped; no open Qs |
| Loadout open-standard extraction (Phase 2) | Move the `loadout` / `plugin.json` schema + docs out of AEC into the open repo `github.com/mbernier/loadout` so any AI tool — not just AEC — can publish and consume loadout manifests, making loadout a tool-neutral standard. | `docs/superpowers/specs/2026-06-25-aec-plugin-management-and-loadout-schema-design.md` (Phase 2; repo cloned at `~/projects/loadout`) | Med — gated on Phase 1 shipping + intent to publish |

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
| Legacy `plans/` cleanup | Decide fate of `gdocs-table-manipulation*.plan.md` and `ui-audit-skill-command.plan.md` — both target other repos. Move out of AEC or delete. | `plans/` (legacy dir) |
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
- **`plans/` is gitignored.** This file is force-tracked
  (`git add -f plans/ROADMAP.md`). Don't add other tracked files to `plans/`.
