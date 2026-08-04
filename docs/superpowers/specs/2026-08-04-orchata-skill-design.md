# Orchata Skill — Design Spec

**Date:** 2026-08-04
**Status:** Approved (brainstormed with Matt, this session)
**Item type:** AEC skill (`.claude/skills/orchata/`), installable via `aec install skill orchata`

## Problem

Running a project with full orchestration currently requires retyping a long incantation
("plan this out using ultracode, using appropriate models for the tasks, accounting for token
efficiency, only bringing me in when needed..."). The process — intake, planning, multi-agent
orchestration with model tiering, escalation rules, and honest verification — should be encoded
once, generically, and improve as it is used.

## Decisions (from brainstorm)

- **Name:** `orchata`
- **Workers:** Workflow subagents only (v1). No CLI workers (`claude -p`, `codex exec`) — those
  lose prompt-cache sharing, structured output, progress tracking, resume, and budget visibility.
  Per-stage `model` and `effort` overrides provide the tiering. Non-Claude models deferred.
- **Structure:** Approach B — lean `SKILL.md` + on-demand `references/` files (house style,
  token-frugal, clean PR targets for the improvement loop).
- **Never pause just to pause:** the run never stops for approvals. Questions are batched once
  at intake; escalation items go to a punch list and work routes around them.
- **Skill composition:** delegate to installed skills per phase instead of improvising.
- **AEC awareness:** detect `aec` + installed agents/skills, cache in user-global state. Offer
  installs from the catalog; never auto-install.
- **Self-improvement:** friction register in user-global state; retro offers a review-and-PR-back
  conversation with Y / N / Never semantics.

## Pipeline

`/orchata <task>` runs five phases:

1. **Intake** — read before asking: project `CLAUDE.md`/`AGENTINFO.md`, project memory, git
   state, `.aec.json`. Refresh the capabilities cache if stale. Ask at most ONE batched
   `AskUserQuestion` covering only genuine unknowns that materially change the plan; if
   everything is answerable, ask nothing and state assumptions (one line each).
2. **Plan** — spec + implementation plan, delegating to `superpowers:brainstorming` /
   `superpowers:writing-plans` when installed. Decompose into stages tagged with: model tier,
   effort, dependencies, covering agent/skill (if installed), and escalation-contract flags.
   Plan file lands in `plans/` (or wherever a project override directs).
3. **Orchestrate** — via the Workflow tool where the host provides it (per-call `model` and
   `effort` overrides); fall back to parallel Agent-tool dispatch (model override only) when it
   doesn't, noting the degradation in the retro. Orchestrator = session model:
   implement → verify per stage via `pipeline()`, adversarial verification on risky stages
   (money/auth/data/contract changes), `model`/`effort` overrides per the tier table,
   worktree isolation only when workers mutate files in parallel. Stage prompts name the
   skill the worker should invoke (e.g. TDD, systematic-debugging) when installed.
4. **Escalate** — stages hitting the stop-and-confirm contract are parked on the punch list;
   the workflow routes around them and continues everything unblocked.
5. **Retro** — verify with evidence (tests run, outputs shown), report results + punch list,
   log friction, offer the improvement conversation when warranted.

## Escalation contract

The canonical list is embedded verbatim in SKILL.md (works in bare environments); a user's
global/project instructions may extend it and their additions win. Canonical: destructive ops, prod-visible shared state
(main pushes, PR merges, external messages, CI changes), money/external quota, genuinely
material ambiguity. Everything else proceeds without asking.

**Punch list:** each entry = what's blocked, why, exactly what's needed from the human,
priority. Written to `plans/<task>-punchlist.md` — unless a project/global instruction names a
task-tracking location (checked at intake) — AND summarized in the end-of-turn chat message.
The run never blocks on a punch-list item.

## Model-tier table (references/model-tiers.md)

| Tier | Use for |
|------|---------|
| haiku + low effort | renames, sweeps, formatting, extraction, doc regen |
| sonnet + default | standard implementation, test writing, straightforward fixes |
| opus/inherit + high effort | hard design, gnarly debugging, adversarial verify |
| session model (orchestrator) | planning, judging, synthesis, integration — not fan-out work |

Rule: omit the override unless a tier clearly fits; never pay top-tier prices for mechanical
work; never trust a single pass on risky work.

## State location (spec-review fix)

All runtime state lives user-globally at `~/.claude/orchata/` — never inside the skill
directory. AEC installs skills by copying, so skill-dir state would fragment per project and
leak into fresh installs. `friction.json` is one register across all projects (opt-out is a
user-level decision); `capabilities.json` is keyed by absolute project path. First run
bootstraps the directory with `capabilities.json = {}` and
`friction.json = {"opt_out": false, "last_review": null, "source_repo": null, "entries": []}`.

## AEC awareness (~/.claude/orchata/capabilities.json, keyed by project path)

```json
{
  "detected_at": "2026-08-04",
  "aec": true,
  "aec_version": "2.41.2",
  "installed_agents": ["..."],
  "relevant_skills": ["..."]
}
```

Detection: `command -v aec`, then `aec list`. Refresh when >7 days old, when `aec` errors, or
on a lookup miss. No `aec` → skip silently, use generic workers. Catalog has a better-fitting
agent/skill than what's installed → suggest `aec install ...` once, proceed generically if
declined. **Never auto-install.**

## Friction register (~/.claude/orchata/friction.json)

```json
{
  "opt_out": false,
  "last_review": null,
  "source_repo": null,
  "entries": [
    {"date": "2026-08-04", "level": "medium", "phase": "orchestrate",
     "project": "/abs/path", "what_happened": "..."}
  ]
}
```

- Log during any run when the skill's instructions caused rework, a wrong default, a missed
  case, or an unnecessary pause. Levels: high / medium / low.
- **Retro threshold:** counting only entries dated after `last_review` (all clauses):
  any high, or ≥3 medium, or ≥5 total → offer:
  "Friction has been noted in previous runs — review together and suggest PR(s) back to the
  skill?" with **Y / N / Never**.
  - **Y:** review entries together, draft concrete diffs to the skill files, offer a PR to the
    skill's source repo (PR only with explicit confirmation — proposals, never auto-merge).
    Set `last_review` to today. Source repo resolved in order: cwd is the source repo →
    `aec info skill orchata` → ask once; cached in `source_repo`.
  - **N:** set `last_review` to today; keep logging; re-offer only when new entries re-hit
    the threshold.
  - **Never:** confirm once; set `opt_out: true`; stop logging and stop asking.

## File layout

```
.claude/skills/orchata/
├── SKILL.md                      # flow, decision rules, escalation contract (~120 lines)
├── references/
│   ├── model-tiers.md            # tier table + effort rules + Workflow shape rules
│   ├── workflow-patterns.md      # canonical plan→execute→verify script shapes
│   └── friction-register.md      # register schema, retro protocol, Y/N/Never
└── (no state in the skill dir — runtime state is user-global at ~/.claude/orchata/)
```

## Out of scope (v1)

- CLI workers / non-Claude models (codex) — revisit if a stage genuinely needs another vendor.
- Plugin packaging (hooks, commands) — the skill can graduate later without breaking installs.
- Automatic PR creation — always a confirmed offer.

## Success criteria

- `/orchata <task>` in any repo runs intake→retro without a single mid-run approval request.
- Registered in `skills-manifest.json`; `aec list` shows it; installable like other skills.
- Friction register round-trips: log → threshold → offer → opt-out semantics all honored.
