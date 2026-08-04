---
name: "orchata"
description: "Use when the user wants a task or project planned and executed end-to-end with multi-agent orchestration — "orchestrate this", "/orchata", "plan and build this", "run this with subagents", or any request to take a feature/project from intake through planning, parallel implementation, and verification while only involving the human for items that genuinely need their hands. Encodes intake questions, model-tier selection, escalation punch lists, and a self-improvement friction loop."
tags: ["skill"]
---


# Orchata

Plan and execute a task end-to-end: intake → plan → orchestrate → escalate → retro.
The human is brought in exactly twice by default: one batched question set at intake (only if
the repo can't answer), and the end-of-turn report. Everything else runs.

**Prime directive: never pause just to pause.** No mid-run approval requests. Reversible
actions proceed. Items matching the escalation contract go on the punch list and work routes
around them. If you are about to ask the user something mid-run, you are doing it wrong —
either proceed, or punch-list it.

## Phase 1 — Intake

Read before asking, in order:

1. Project `CLAUDE.md` / `AGENTINFO.md` / `AGENTS.md`, and any project profile in memory
2. Git state (branch, recent commits, cleanliness)
3. `.aec.json` if present; note any project override for where tasks/punch lists live
4. Capabilities cache — see "AEC awareness" below; refresh if stale

Then ask **at most one batched `AskUserQuestion`** covering only genuine unknowns that would
materially change the plan (e.g., prod posture when no profile exists, a real fork in scope).
If everything is answerable from the repo, ask nothing — state each assumption in one line and
proceed. Do not ask again until the retro.

### AEC awareness

All orchata state lives in `~/.claude/orchata/` — **never** in the skill's own directory
(skills are installed by copying; state in the skill dir would fragment and leak between
installs). First run: create the directory and write `capabilities.json` (`{}`) and
`friction.json` (`{"opt_out": false, "last_review": null, "source_repo": null, "entries": []}`).

`capabilities.json` is keyed by absolute project path (installed agents/skills differ per
project). Refresh this project's entry when missing, older than 7 days, `aec` errors, or a
lookup misses:

```bash
command -v aec && aec list
```

Record per project: `detected_at`, `aec` (bool), `aec_version`, `installed_agents`,
`relevant_skills`.
No `aec` → skip silently and use generic workers. If the AEC catalog has an agent or skill
that fits a stage better than anything installed, **suggest** `aec install <type> <name>` once
in the plan or retro — proceed generically if not taken up. **Never auto-install anything.**

## Phase 2 — Plan

- Delegate to installed planning skills instead of improvising: `superpowers:brainstorming`
  for unshaped ideas, `superpowers:writing-plans` for specced work. Missing → plan inline.
- Decompose into stages. Tag each stage with:
  - **model tier + effort** — read `references/model-tiers.md`
  - **dependencies** (what blocks what)
  - **covering agent/skill** — an installed agent type or skill that owns this kind of work
    (e.g., Code Reviewer for review stages, TDD skill named in implementation prompts)
  - **escalation flags** — does this stage touch the escalation contract? (see Phase 4)
- Write the plan to `plans/` (or the project's overriding location) per repo conventions.

## Phase 3 — Orchestrate

Author and run Workflow scripts; the orchestrator (you, the session model) plans, judges,
synthesizes, and integrates — it does not do fan-out work itself.

- Use the **Workflow tool** where the host provides it (`agent()` accepts per-call `model`
  and `effort` overrides). If unavailable, fall back to the **Agent tool**: dispatch
  independent workers in parallel, `model` override only (no per-call effort), and note the
  degradation in the retro.
- Read `references/workflow-patterns.md` before writing the script.
- `pipeline()` by default; barriers only when a stage genuinely needs all prior results.
- Per-stage `model`/`effort` overrides per the tier table; omit when no tier clearly fits.
- Adversarial verification on risky stages: anything touching money, auth, data integrity, or
  a contract change gets independent verify agents prompted to refute.
- Worktree isolation only when workers mutate files in parallel.
- Every worker prompt names the skill it should invoke when installed (e.g.
  `superpowers:test-driven-development` for implementation,
  `superpowers:systematic-debugging` when a worker hits a bug).
- Log friction as it happens — a wrong default in these instructions, an unnecessary pause, a
  missed case that caused rework → append to the friction register (see Phase 5).

## Phase 4 — Escalate

The escalation contract. This list is canonical and applies even when no global instructions
exist; a user's global/project instructions may extend it, and their additions win:

- Destructive: `rm -rf`, `git reset --hard`, force push, drop table, delete unmerged branches
- Prod-visible shared state: pushing/merging to `main`, prod deploys, sending Slack/email,
  posting to issues, modifying CI
- Costs money or external quota
- Genuinely material ambiguity where the wrong branch wastes the run

When a stage hits the contract: **park it, don't ask.** Add a punch-list entry — what's
blocked, why, exactly what's needed from the human, priority — and route the workflow around
it. Punch list goes to `plans/<task>-punchlist.md`, unless a project or global instruction
names a task-tracking location (checked at intake), AND is summarized in the end-of-turn
report. The run never blocks on a punch-list item.

## Phase 5 — Retro

1. **Verify with evidence.** Tests actually run, outputs shown, claims match reality. A page
   load is not verification. Report failures plainly.
2. **Report:** what shipped, what's on the punch list (inline summary + file path), what was
   assumed at intake.
3. **Friction register** — read `references/friction-register.md`. Log this run's friction,
   then evaluate the register: any high-level entry, ≥3 medium, or ≥5 total since the last
   review → offer the improvement conversation (Y / N / Never) exactly as the reference
   describes. On Y: review entries together, draft concrete diffs to this skill's files, and
   offer a PR back to the skill's source repo — PR only with explicit confirmation.

## State files

All state is user-global at `~/.claude/orchata/`, created lazily on first run (see Phase 1
for defaults). `capabilities.json` per Phase 1; `friction.json` per
`references/friction-register.md` — one register across all projects, so opt-out is a
user-level decision. If `friction.json` has `"opt_out": true`, skip all friction logging and
never offer the improvement conversation.
