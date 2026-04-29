# No Patch Fixes — Always Fix the Root Cause

When a bug, broken consumer, drifted contract, or stale test is discovered, the only acceptable resolutions are:

1. **Fix it correctly now** as part of the current work, OR
2. **Write a plan file** in `plans/` that captures the root cause, the correct fix, the affected surfaces, and the priority — and link it from `plans/ROADMAP.md` for scheduling.

## Never Acceptable

- Adding fallback shims, default-value `.get(..., {})` masks, or backward-compat aliases to keep two diverged shapes alive.
- Updating tests to match drifted code without first checking whether the code or the test reflects the intended contract.
- "Comment out the assert and move on" or "ignore the failing test for now."
- Logging the issue verbally in chat as "I'll come back to it" — if it isn't in code or in a plan file, it doesn't exist.

## Required Workflow When a Root Cause is Discovered Mid-Task

1. **State the root cause explicitly to the user**, including which surfaces are affected and which behavior is currently broken.
2. **Discuss the trade-off:** fix-now (extra blast radius, but no debt accrued) vs. plan-and-defer (focused commit, but you must write the plan file before continuing).
3. **Whichever path is chosen, the resolution must be the correct fix** — not a patch, not a workaround, not a silenced symptom.
4. If deferring, the plan file is a hard prerequisite. Do not move on until it exists and is referenced from `ROADMAP.md`.

## Why

Patch fixes accumulate as silent tech debt. They make the codebase progressively harder to reason about, mask real production bugs (e.g. stale `.get()` keys silently zeroing out a UI for months), and erode trust in the test suite. A failing test is a gift — it points at exactly the thing that needs fixing. Patching it over throws that signal away.

## This Rule Overrides Time Pressure

"We need to ship today" is not a justification for a patch fix. Either pay the cost of fixing it correctly, or pay the cost of writing the plan that ensures it gets fixed correctly later. There is no third option.