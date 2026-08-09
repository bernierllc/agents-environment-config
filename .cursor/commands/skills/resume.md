---
name: "resume"
description: "Use at the start of a session in a repo with prior work in flight, or when the user says "resume", "/resume", "where were we", "pick up where we left off". Reads checkpointed run state, the activity log, and the external tracker, reconciles them against git reality, and continues from the recorded next action instead of re-planning."
tags: ["skill"]
---

# Resume

Recover an interrupted session from its checkpoints. The goal is to **continue, not
re-plan** — a run that is already mapped gets picked up at its first non-done step.

## 1. Gather state (all three layers, cheap reads first)

- **State dir:** user/project instructions may name one; default `.orchata/`. Read
  `run-state.json` if present (schema: a run has `steps[]` with `status`, plus
  `next_action`). Read the last ~10 lines of `activity.jsonl` if present.
- **Git:** `git branch --show-current`, `git log --oneline -10`, `git status --short`,
  `git branch --sort=-committerdate | head` for other recent branches. No run-state on
  the current branch → check the most recent branches for a committed checkpoint
  (`git show <branch>:<state-dir>/run-state.json`) before concluding no run is in
  flight; a hit means the run lives on that branch — switch to it, or reconcile from
  where you are.
- **External tracker:** if the user's instructions configure one, query its open
  (non-done) rows whose source link matches this repo — match on `org/repo` from
  `git remote get-url origin`, never the repo name alone. Tracker unavailable → proceed
  on layers 1–2 and say so.

## 2. Reconcile — trust reality over records

For each claim in run-state / tracker rows, check it against git and the world before
acting on it. One line per drift found:

- run-state names a different branch than the checkout → the checkout wins; say which
  run the state file belongs to.
- A step marked done with no matching commit/PR/evidence → treat as not done.
- A step marked pending that git shows already happened → mark it done with the
  evidence.
- A tracker row with no branch, a branch with no row, or notes older than the branch's
  last commit → list it; these are the first things to resolve.

## 3. Continue

- **In-flight run found:** state the run's objective in one line, then execute from the
  first non-done step / `next_action`. Do not re-derive the plan. Keep the existing
  checkpoint discipline: update run-state (and tracker, when configured) after every
  completed step.
- **No run in flight:** report clean state in ≤5 lines — current branch, last commit,
  any open tracker rows for this repo — and ask nothing; wait for direction unless the
  open rows make the next task obvious.
- **Conflicting states** (two runs, or state contradicting git in a way you can't
  resolve): present the conflict in a few lines and let the user pick. This is the only
  case where resume pauses.
