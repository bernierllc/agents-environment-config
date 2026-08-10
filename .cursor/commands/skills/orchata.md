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

**Resume check first.** If `<state-dir>/run-state.json` exists on the current branch with a
non-done run (see `references/run-state.md`; state dir per "State files" below): reconcile
it against reality (git log, open PRs, CI/deploy status, the external tracker row if one is
linked), report any drift in one line each, and continue from the first non-done step. Do
NOT re-plan a run that is already in flight. No run-state on the current branch → before
planning fresh, check other branches (`git branch -a --sort=-committerdate`, local and
remote-tracking) for a committed checkpoint via
`git show <branch>:<state-dir>/run-state.json`; only a checkpoint with an in-flight run
counts — one with at least one step whose status is neither `done` nor `skipped` (the
terminal statuses per `references/run-state.md`); a fully terminal run-state is history,
not an in-flight run. A live hit means the run lives on that branch —
switch to it when the tree is clean, otherwise surface the conflict and pause (same rule as
the resume skill).

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

### Task granularity

The plan file is the map; the task brief is all a worker gets. **Every task brief must be
executable from its brief + named file paths alone** — never "read the plan" or "check the
project docs". A runnable brief has: goal, inputs, constraints, and where the output lands.
Size tasks by the tier doing them:

| Tier | Task size |
|---|---|
| Low (haiku / low effort) | Larger mechanical batches — context reload cost dominates, fewer/bigger wins |
| Mid (sonnet) | One commit-able unit, ≤ ~15 tool calls — a usage-limit cut costs at most one unit |
| High (opus/fable reasoning) | Smallest possible brief + pointers; the model pulls threads itself |

**Docs and code never share a stage.** Documentation expansion is cheap and self-contained —
its own stage, tagged low-tier. Implementation stages get the full budget headroom.

**Tracker rows at plan time:** if an external tracker is configured (see "External tracker"
below), every stage gets a row/issue at plan time, linked to the branch when execution
starts on it. The plan seeds the queue.

## Phase 3 — Orchestrate

Author and run Workflow scripts; the orchestrator (you, the session model) plans, judges,
synthesizes, and integrates — it does not do fan-out work itself.

### Orchestration economy

Token cost is an explicit objective, not a side effect. The orchestrator's job is to get as
much of the project completed as possible through orchestration while executing as little of
the actual work as possible:

- Any unit of work a worker can do from a context-minimal brief is delegated — the
  orchestrator never "quickly does it inline" to save a dispatch.
- The orchestrator consumes conclusions and structured returns, never workers' file dumps or
  transcripts.
- Worker tier and effort are set per the tier table; mechanical batches go low-tier.

### Shared-worktree mode

When the user asks for work against a single branch, or the stages are mostly serial, run
the whole fleet against **one worktree branch the orchestrator oversees**: workers propose
patches concurrently, the orchestrator applies and commits them serially in dependency
order (tests before each commit). The orchestrator owns the branch — workers never commit
to it directly. Per-worker worktree isolation remains the fallback for genuinely parallel
file mutation.

Worktree hygiene (either mode):

- Sequence environment moves **before** dispatching background agents: create the worktree
  and complete any `cd` first, then dispatch with worktree-absolute paths. An agent
  dispatched against a checkout that then moves gets its Bash calls refused.
- At worktree creation, exclude the `node_modules` symlink from git's view (worktree
  equivalent of `.git/info/exclude`) — gitignore does not match symlinks, so `git add -A`
  is otherwise a standing hazard.

### Orchestration mechanics

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
- Workflow scripts whose `args` carries structure start with a defensive parse —
  `args = typeof args === 'string' ? JSON.parse(args) : args` — hosts may deliver args as a
  JSON string.
- Log friction as it happens — a wrong default in these instructions, an unnecessary pause, a
  missed case that caused rework → append to the friction register (see Phase 5).

### Checkpoint discipline

A usage-limit cut must cost at most one step, never the run. Read
`references/run-state.md` before the first stage executes, then after **every** completed
step, in this order (each layer is a fallback for the one after it):

1. Update `<state-dir>/run-state.json` (local write — always succeeds)
2. `git add <state-dir>/ && git commit` on the working branch (survives the machine) —
   run `git branch --show-current` immediately before **every** commit; never trust
   intake-phase branch state after compaction, a long run, or an environment move
3. Update the stage's row in the external tracker, if one is configured (visible outside
   the CLI)

Layer 3 is optional, and it failing (tracker down, permission-blocked) never blocks — note
the miss in run-state and move on. Checkpoint **early and after each step**, not at the
end: the whole point is that the tail of the run is the part that gets cut.

### Supervisor resilience

Fan-out runs assume workers die. Rules:

- **Worker contract:** every worker prompt ends with a required structured return —
  `{task_id, status: fixed|failed|blocked, files_changed, tests_passing, evidence, notes}`
  (use Workflow `schema` when available). A worker that returns anything else counts as
  `failed`.
- **Retry budget: 2** per task, then mark `blocked` with the last error as evidence and
  move on — never spin on one worker.
- **Stream results:** append each verdict to `<state-dir>/fleet-results.json` as it
  arrives, not in a final batch. A supervisor cut mid-fleet loses zero completed verdicts.
- **Propose in parallel, merge serially:** workers produce branches/patches concurrently;
  the orchestrator integrates one at a time in dependency order, running tests before each
  merge commit.
- **Context-minimal prompts:** workers get their brief + exact file paths + expected
  return shape — never the conversation, the plan file, or "figure out the context".
- **Name cross-file contracts:** when splitting work by file ownership, the worker prompt
  states any contract its files must honor with files it doesn't own (e.g. "CI assumes a
  `packageManager` field in package.json") — or a smoke stage runs the consumer's setup
  after integration. Ownership splits hide exactly these seams.

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

**Terminal condition — all work blocked.** If every remaining stage is on the punch list
(nothing runnable is left), stop and report the punch list as a needs-from-human list in
priority order: what's needed, why it blocks, what resumes when it lands. This is the only
legitimate mid-run stop. One blocker never stops the run while other work can progress.

## Phase 5 — Retro

1. **Verify with evidence.** Tests actually run, outputs shown, claims match reality. A page
   load is not verification. Deploy verification asserts deployment **identity** (a new
   deployment id/commit visible in the provider's deployment list) plus a response-body
   match — never a bare HTTP status code, which a stale or placeholder deploy also returns.
   Report failures plainly.
2. **Report:** what shipped, what's on the punch list (inline summary + file path), what was
   assumed at intake.
3. **Friction register** — read `references/friction-register.md`. Log this run's friction,
   then evaluate the register: any high-severity entry, ≥3 medium, or ≥5 total since the
   last review → present the compact register verdict from the reference (verdict line, top
   entries with proposed fixes, proposed diffs) and offer the improvement conversation
   (Y / N / Never) exactly as the reference describes. On Y: review entries together, draft
   concrete diffs to this skill's files, and offer a PR back to the skill's source repo —
   PR only with explicit confirmation. Entries addressed by a shipped fix are pruned on
   review — the register is a queue, not an archive.

## State files

All state is user-global at `~/.claude/orchata/`, created lazily on first run (see Phase 1
for defaults). `capabilities.json` per Phase 1; `friction.json` per
`references/friction-register.md` — one register across all projects, so opt-out is a
user-level decision. If `friction.json` has `"opt_out": true`, skip all friction logging and
never offer the improvement conversation.

**Per-run state is different:** it lives in the project at `<state-dir>/` (run-state.json,
fleet-results.json) and is committed to the working branch — see `references/run-state.md`.
Default state dir: **`.orchata/`**; the user's global or project instructions may name a
different directory — honor theirs. Global `~/.claude/orchata/` holds cross-project skill
state only.

## External tracker (optional checkpoint layer 3)

The third checkpoint layer is whatever system the user already tracks work in — an issue
tracker, a project database, a team wiki. Orchata never assumes one exists or names one.
At intake, use whatever the user's global/project instructions configure for work tracking;
if nothing is configured, run with layers 1–2 (local write + git commit are sufficient on
their own), and once — at retro, not mid-run — suggest the user name a tracker in their
global instructions if they want run state visible outside the CLI. Never block any step
on the tracker.
