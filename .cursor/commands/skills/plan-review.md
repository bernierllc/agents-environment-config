---
name: "plan-review"
description: "Use when reviewing, auditing, or cleaning up plan files. Discovers plans across the repo and Claude's project directory, correlates them with git branches, performs deep code inspection to determine actual completion state vs. claimed status, and produces a gap analysis report. Also triggered by "review my plans", "what's the state of my plans", "clean up plans", or "status of plan X"."
tags: ["skill"]
---


# Plan Review

## Overview

Plans lie. Code doesn't. This skill reconciles the two.

Inspect plan files across a project, correlate them with git branches, and perform deep code inspection to determine actual completion state versus claimed status. Produce an honest gap analysis with concrete evidence from the codebase. Adaptive — read the room based on what discovery reveals and offer appropriate next steps including cleanup, test execution, agent handoff, or roadmap generation.

This skill does not couple to any specific agent — it produces artifacts that any PM agent or human can consume.

## Checklist

Complete these in order:

1. **Determine entry point and scope** (full review, single plan, cleanup-only)
2. **Discover plan files** (AEC config → conventions → Claude dir → ask user)
3. **Discover and correlate branches** (match plans ↔ branches, categorize)
4. **Checkpoint** (if 6+ items, confirm with user before proceeding)
5. **Deep inspect each plan/branch pair** (extract artifacts, check code, gap analysis)
6. **Ask report destination** (terminal / file / both)
7. **Generate and present report** (using report template)
8. **Ask what next** (cleanup / tests / handoff / roadmap / nothing)
9. **Execute chosen actions** (with per-item confirmation for cleanup)
10. **Optionally save memory** (project-type summary of review state)

## Entry Points

| Trigger | Behavior |
|---------|----------|
| User invokes skill directly | Full cycle: discover → inspect → report → ask next |
| "review my plans" or similar | Same full cycle |
| "review this plan" / "status of plan X" | Single-plan mode: skip discovery, inspect the named plan only |
| "clean up plans" | Discovery + report, then jump straight to cleanup |
| "what's the state of my plans" | Discovery + report only, then ask what's next |

## Plan Discovery

### Source Resolution

Resolve plan file locations in priority order. Stop expanding sources once a sufficient set is found, but always check at least the first two levels:

1. **AEC config** — Read `AGENTINFO.md` for a plans directory setting (e.g., `plans_dir: docs/plans`). If present, use that path as the primary source.
2. **Convention scan** — Scan the repo root for these directories:
   - `plans/`
   - `docs/plans/`
   - `docs/superpowers/specs/`
   - `docs/superpowers/plans/`
3. **Claude's project directory** — Scan `~/.claude/projects/<project-hash>/` for plan-like `.md` files with plan structure (phase tracking, task lists, implementation steps).
4. **Ask the user** — If nothing found, or if the user might have additional locations, ask before proceeding.

### What Qualifies as a Plan File

Detect plan files using concrete signals. At least 2 must match for a file to qualify:

- **Checkboxes** — presence of `- [ ]` or `- [x]` markdown checkboxes
- **Phase/step headings** — headings matching patterns like `## Phase N`, `## Step N`, `### Task`, `## Implementation`
- **Status markers** — text like `[DONE]`, `[IN PROGRESS]`, `[NOT STARTED]`, `[COMPLETE]`, `Status: `
- **File naming** — `.plan.md` suffix, or file located inside a `plans/` directory
- **Implementation references** — mentions of specific file paths, function names, or `create`/`implement`/`build` verbs in headings

**Exclude** these regardless of signal count:
- Pure design specs with no implementation phases (no checkboxes, no phase headings)
- Memory files (`MEMORY.md`, files in `memory/`)
- READMEs and changelogs

### Discovery Output

Present findings as a table before proceeding:

| Plan Name | Source Location | Claimed Status | Associated Branch |
|-----------|----------------|----------------|-------------------|
| `<filename>` | `<path relative to repo root>` | `<extracted status or "unknown">` | `<branch if detectable from plan content or naming, else "—">` |

## Branch Correlation

### Matching Strategy

Match plans to branches using four methods, applied in order:

1. **Explicit references** — Scan plan content for branch names (e.g., `branch: feat/cleanup-hung-processes-script`). Direct match.
2. **Naming convention** — Match branch names against plan identifiers: REQ IDs, feature names, plan file slugs. Example: plan `gdocs-table-manipulation.plan.md` matches branch `feat/gdocs-table-manipulation`.
3. **Commit message scanning** (opt-in) — For branches still unmatched after naming convention, scan up to 5 recent commits per branch for references to plan names or IDs. Only perform this step when unmatched branches remain.
4. **Main branch** — For plans describing already-merged work, check if plan artifacts exist on `main`.

### Git Commands

```bash
# List all local and remote branches
git branch -a

# Last commit date on a branch
git log -1 --format=%ci <branch>

# Recent commits for message scanning (max 5)
git log -5 --oneline <branch>
```

### Correlation Categories

| Category | Meaning |
|----------|---------|
| **Matched** | Plan has a corresponding branch (or artifacts confirmed on main) |
| **Orphan plan** | Plan exists but no branch found — work never started, branch deleted, or already merged |
| **Orphan branch** | Branch exists but no plan references it — untracked or ad-hoc work |
| **Stale match** | Plan + branch both exist but branch has no commits in 30+ days |

### Checkpoint — Adaptive Behavior

After building the correlation table, adapt based on total item count (plans + branches combined):

| Discovery Size | Behavior |
|----------------|----------|
| 1-5 items | No checkpoint. Proceed directly to deep inspection. |
| 6-11 items | Display the correlation table. Ask: "Proceed with full inspection?" Wait for confirmation. |
| 12+ items | Display the correlation table. Prepare a task list for parallel inspection. Suggest the user invoke `superpowers:dispatching-parallel-agents` with the prepared task list. Do not proceed with serial inspection unless explicitly requested. |

## Deep Inspection

### From the Plan Side

For each plan file:

- Extract all phases, tasks, and steps with their claimed status (checkbox state, status markers, heading labels).
- Extract all referenced artifacts — files, modules, functions, routes, configs, tests. Look for file paths, function/class names, route definitions, and config keys.
- Extract dependencies between phases — identify what blocks what based on ordering, explicit dependency markers, or references from one phase to another's outputs.

### From the Code Side

> **CRITICAL — Technical Constraints for Cross-Branch Inspection:**
>
> Normal file reads and grep only work on the currently checked-out branch. For all other branches, use these git commands:
>
> ```bash
> # Read a file on another branch
> git show <branch>:<path>
>
> # Read a file on a remote-only branch
> git show origin/<branch>:<path>
>
> # List files in a directory on another branch
> git ls-tree -r --name-only <branch> -- <directory>
>
> # Search for a pattern in a file on another branch
> git show <branch>:<path> | grep <pattern>
>
> # Check last commit date (staleness)
> git log -1 --format=%ci <branch>
> ```
>
> Do not attempt to checkout other branches during inspection. All cross-branch reads go through `git show` or `git ls-tree`.

For each matched branch:

- Check existence of every referenced artifact via `git ls-tree -r --name-only <branch>` or `git show <branch>:<path>`.
- For files that exist, pipe `git show <branch>:<path>` through grep for referenced functions, classes, methods, and routes.
- Check for test files related to the plan's deliverables (existence = evidence of progress).
- If tests found, note them and flag as available-to-run. Do not run tests automatically.
- Check last commit date via `git log -1 --format=%ci <branch>` to assess staleness.

### Multi-Branch Plans

Some plans span multiple branches (e.g., Phase 1 on `feat/phase-1`, Phase 2 on `feat/phase-2`). When a plan matches multiple branches, inspect each matched branch separately and merge findings into one report section per plan. The correlation table shows all matched branches for such plans.

### Gap Analysis Per Phase/Task

Assign each phase or task one of these statuses based on artifact inspection:

| Status | Criteria |
|--------|----------|
| **Complete** | All referenced artifacts exist, expected functions/methods present |
| **Partial** | Some artifacts exist, others missing |
| **Not started** | No referenced artifacts found on the branch |
| **Overclaimed** | Plan says "done" but artifacts missing or incomplete |
| **Underclaimed** | Plan says "not started" but artifacts exist |
| **Diverged** | File exists but expected symbols not found — e.g., plan references `createTable()` but grep finds no match in the file, or plan references `table_manager.py` but only `table_ops.py` exists. Detection: file exists + expected function/class/export names absent. This is a mechanical check, not a semantic comparison. |

### Orphan Handling

**Orphan branches** (branch with no matching plan):
- Summarize changed files, commit messages, and scope of work on the branch.
- Flag whether the branch looks like completed work that could be merged, or abandoned work that could be deleted.

**Orphan plans** (plan with no matching branch):
- Check whether the plan's referenced artifacts exist on `main` (already merged).
- If artifacts found on main, mark as "likely merged — plan not cleaned up."
- If not on main either, mark as "unstarted."

## Report

### Generating the Report

Read `references/report-template.md` for the report skeleton. Fill all `{{placeholder}}` variables with actual data collected during discovery, correlation, and deep inspection. Every section of the template must be populated — leave no placeholders in the final output.

### Report Destination

Ask the user each time before generating:

- **Terminal only** — print the report to the conversation
- **Written file** — write to the plans directory (or a user-specified path)
- **Both** — print and write

Default file location: the plans directory identified during discovery, or a user-specified path. Do not assume a location without asking.

## Next Steps

After presenting the report, ask: **"What would you like to do next?"**

Options:
- **Clean up plans** — archive completed, update statuses, remove dead plans
- **Run discovered tests** — execute test files found during inspection
- **Hand off to an agent** — prepare a structured handoff artifact
- **Generate a roadmap artifact** — structured summary of remaining work across all plans
- **Nothing** — just needed the report

The user can pick one, multiple, or none.

## Cleanup Actions

When the user chooses cleanup, present a proposed action list. Each action requires individual user approval.

| Action | When Proposed | What It Does |
|--------|---------------|--------------|
| **Archive plan** | All phases complete, artifacts verified on main | Move to `plans/archive/` (or configured archive dir) |
| **Update plan status** | Actual status differs from claimed status | Rewrite status markers in the plan file to match reality |
| **Flag for deletion** | No branch, no artifacts on main, no commits referencing it | Suggest deletion, require explicit confirmation |
| **Create branch reminder** | Orphan plan with no work started | Note in report, suggest user create a branch |
| **Flag orphan branch** | Branch with no plan | Suggest: write a plan, merge it, or delete it |

### Presentation Format

Present each proposed action with a `[y/n]` confirmation:

```
Proposed cleanup actions:

1. [ARCHIVE] some-plan.md — all phases verified complete
   → Move to plans/archive/  [y/n]

2. [UPDATE STATUS] other-plan.md — Phase 1-2 complete, plan says "not started"
   → Update phase statuses in file  [y/n]

3. [FLAG DEAD] old-plan.md — no branch, no artifacts on main
   → Delete file  [y/n]

4. [ORPHAN BRANCH] feat/some-branch — no matching plan
   → Suggest: merge, plan, or delete  [y/n to see details]
```

Execute each action only after explicit user approval. Never batch-execute without per-item confirmation.

## Agent Handoff

When the user chooses agent handoff:

- Prepare a structured handoff artifact containing the full report plus a remaining-work summary (incomplete phases, orphan items, next priorities).
- List available PM-type agents the user could invoke (e.g., project management skills, dispatching agents).
- Do NOT invoke any agent automatically — present the options and let the user choose.

## Memory Integration

After completing a review, optionally save a project memory summarizing the state:

```
Plan review YYYY-MM-DD: X plans (N complete, M partial, K not started), Y orphan branches, Z stale. Report at <path-if-written>.
```

Save as type: `project`.
