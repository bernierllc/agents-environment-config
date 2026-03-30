# Plan Review Skill — Design Spec

**Date:** 2026-03-30
**Status:** Draft
**Skill Location:** `.claude/skills/plan-review/`

## Overview

A skill that inspects plan files across a project, correlates them with git branches, performs deep code inspection to determine actual completion state, and produces an honest gap analysis. The skill is adaptive — it reads the room based on what it discovers and offers appropriate next steps including cleanup, test execution, agent handoff, or roadmap generation.

Core principle: Plans lie. Code doesn't. This skill reconciles the two.

## Plan Discovery

### Source Resolution (priority order)

1. **AEC config** — check `AGENTINFO.md` or AEC config files for a plans directory setting
2. **Convention scan** — look for `plans/`, `docs/plans/`, `docs/superpowers/specs/` in the repo root
3. **Claude's project directory** — scan `~/.claude/projects/<project-hash>/` for plan-like `.md` files with plan structure (phase tracking, task lists, implementation steps)
4. **Ask the user** — if nothing found, or if the user might have additional locations

### What Qualifies as a Plan File

Detect plan files using these concrete signals (at least 2 must match):

- **Checkboxes:** presence of `- [ ]` or `- [x]` markdown checkboxes
- **Phase/step headings:** headings matching patterns like `## Phase N`, `## Step N`, `### Task`, `## Implementation`
- **Status markers:** text like `[DONE]`, `[IN PROGRESS]`, `[NOT STARTED]`, `[COMPLETE]`, `Status: `
- **File naming:** `.plan.md` suffix, or file located inside a `plans/` directory
- **Implementation references:** mentions of specific file paths, function names, or `create`/`implement`/`build` verbs in headings

**Excludes:** pure design specs with no implementation phases (no checkboxes, no phase headings), memory files, READMEs, changelog files

### Discovery Output

A table showing each plan found, its source location, claimed status (if any), and associated branch (if detectable from plan content or naming conventions).

## Branch Correlation

### Matching Strategy

1. **Explicit references** — plan file mentions a branch name directly (e.g., `branch: feat/cleanup-hung-processes-script`)
2. **Naming convention** — branch name contains plan identifiers (REQ IDs, feature names, plan file slugs). e.g., plan `gdocs-table-manipulation.plan.md` matches branch `feat/gdocs-table-manipulation`
3. **Commit message scanning** (opt-in, max 5 recent commits per branch) — check recent commits on unmatched branches for references to plan names or IDs. Only performed if naming convention matching leaves unmatched branches, and limited to 5 most recent commits per branch to avoid expense
4. **Main branch** — for plans that describe work already merged, check if artifacts exist on `main`

### Correlation Categories

| Category | Meaning |
|----------|---------|
| **Matched** | Plan has a corresponding branch (or is on main) |
| **Orphan plan** | Plan exists but no branch found — work never started, branch deleted, or already merged |
| **Orphan branch** | Branch exists but no plan references it — untracked/ad-hoc work |
| **Stale match** | Plan + branch exist but branch has no commits in 30+ days |

### Checkpoint

After correlation, display the correlation table and ask "proceed with full inspection?" If 12+ items found, suggest the user invoke the `superpowers:dispatching-parallel-agents` skill with a prepared task list for parallel inspection (see Adaptive Behavior section).

## Deep Inspection

### From the Plan Side

- Extract all phases/tasks/steps with their claimed status
- Extract all referenced artifacts — files, modules, functions, routes, configs, tests
- Extract dependencies between phases (what blocks what)

### From the Code Side (on the relevant branch)

**Technical constraint:** For branches other than the currently checked-out branch, all file inspection must use `git show <branch>:<path>` (or `git show origin/<branch>:<path>` for remote-only branches). Normal file reads and grep only work on the current checkout. Cross-branch grepping requires piping: `git show <branch>:<path> | grep <pattern>`. File listing on another branch uses `git ls-tree -r --name-only <branch> -- <directory>`.

- Check existence of every referenced artifact via `git ls-tree` or `git show`
- For files that exist, pipe `git show <branch>:<path>` through grep for referenced functions/classes/methods/routes
- Check for test files related to the plan's deliverables (existence = evidence of progress)
- If tests found, note them and flag as available-to-run (do not run automatically)
- Check last commit date on the branch via `git log -1 --format=%ci <branch>`

**Multi-branch plans:** Some plans span multiple branches (e.g., Phase 1 on `feat/phase-1`, Phase 2 on `feat/phase-2`). When a plan matches multiple branches, inspect each matched branch separately and merge findings into a single per-plan report section. The correlation table shows all matched branches for such plans.

### Gap Analysis Per Phase/Task

| Status | Criteria |
|--------|----------|
| **Complete** | All referenced artifacts exist, functions/methods present |
| **Partial** | Some artifacts exist, others missing |
| **Not started** | No referenced artifacts found on the branch |
| **Overclaimed** | Plan says "done" but artifacts are missing or incomplete |
| **Underclaimed** | Plan says "not started" but artifacts exist |
| **Diverged** | File exists but expected symbols not found — e.g., plan says `createTable()` but grep finds no match in the file, or plan references `table_manager.py` but only `table_ops.py` exists in the same directory. Detection: file exists + expected function/class/export names absent. This is a mechanical check, not a semantic comparison. |

### Orphan Handling

**Orphan branches (no plan):**
- Summarize what's on the branch: changed files, commit messages, scope of work
- Flag whether it looks like completed work that could be merged or abandoned work

**Orphan plans (no branch):**
- Check whether the artifacts exist on `main` (already merged)
- If not on main either, mark as "unstarted"

## Report & Next Steps

### Report Structure

```markdown
# Plan Review Report — YYYY-MM-DD

## Summary
- X plans found across Y sources
- Z branches correlated
- N orphan plans, M orphan branches

## Correlation Map
[Table with plan name, source, branch, category, staleness]

## Per-Plan Deep Inspection
### [Plan Name]
- **Source:** plans/some-plan.md
- **Branch:** feat/some-branch (last commit: YYYY-MM-DD)
- **Overall:** N/M phases complete

| Phase | Plan Status | Actual Status | Evidence |
|-------|-------------|---------------|----------|
| Phase 1 | Complete | Complete | file.py exists, 3 tests found |
| Phase 2 | Complete | Overclaimed | bar.py missing, tests absent |
...

- **Tests available:** N test files found (not run)
- **Staleness:** Last commit X days ago

### [Orphan Branch: branch-name]
- **Changed files:** N files, M additions
- **Commit summary:** "description"
- **Assessment:** candidate for merge/archive/deletion

### [Orphan Plan: plan-name.md]
- **Artifacts on main?** Yes/No/Partial
- **Assessment:** status description

## Runnable Tests
[Test files found during inspection, grouped by plan]
```

### Report Destination

The skill asks the user each time:
- Terminal output only
- Written report file (to plans dir or user-specified location)
- Both

### After the Report

The skill asks: "What would you like to do next?"

- **Clean up plans** — archive completed, update statuses, remove dead plans (each action confirmed individually)
- **Run discovered tests** — execute test files found during inspection
- **Hand off to an agent** — prepare a handoff artifact and suggest available PM agents
- **Generate a roadmap artifact** — structured summary of remaining work across all plans
- **Nothing** — just needed the report

The user can pick one, multiple, or none.

## Cleanup Actions

When the user chooses cleanup, the skill presents a proposed action list. Each action requires individual user approval.

| Action | When Proposed | What It Does |
|--------|---------------|--------------|
| **Archive plan** | All phases complete, artifacts verified on main | Move to `plans/archive/` (or configured archive dir) |
| **Update plan status** | Actual status differs from claimed status | Rewrite status markers in the plan file to match reality |
| **Flag for deletion** | No branch, no artifacts on main, no commits referencing it | Suggest deletion, require explicit confirmation |
| **Create branch reminder** | Orphan plan with no work started | Note in report, suggest user create a branch |
| **Flag orphan branch** | Branch with no plan | Suggest: write a plan, merge it, or delete it |

### Presentation Format

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

## Skill Structure

```
plan-review/
├── SKILL.md
└── references/
    └── report-template.md    # Contains the markdown template from the Report Structure
                               # section — the report skeleton with placeholder variables
                               # that the skill fills during report generation
```

### Frontmatter

- **File patterns:** `**/plans/**/*.md`, `**/specs/**/*.md`, `**/plan*.md`, `**/docs/**/*.plan.md`
- **Bash patterns:** plan-related commands

### Entry Points

| Trigger | Behavior |
|---------|----------|
| User invokes skill directly | Full cycle: discover → inspect → report → ask next |
| "review my plans" or similar | Same full cycle |
| "review this plan" / "status of plan X" | Single-plan mode: skip discovery, inspect the named plan only |
| "clean up plans" | Discovery + report, then jump straight to cleanup |
| "what's the state of my plans" | Discovery + report only, then ask what's next |

### AEC Awareness

- Read `AGENTINFO.md` for plans directory config
- Check for AEC preferences that might specify plan locations
- Fall back to convention scan + user prompt

### Integration Points

- **Memory:** After a review, optionally save a project memory summarizing the state. Format: `"Plan review YYYY-MM-DD: X plans (N complete, M partial, K not started), Y orphan branches, Z stale. Report at <path-if-written>."` Saved as a `project` type memory.
- **Git:** Uses `git show branch:path`, `git ls-tree`, `git log`, `git branch -a` for cross-branch inspection. Remote-only branches use `origin/<branch>` prefix.
- **Parallel inspection:** For 12+ items, the skill prepares a task list and suggests the user invoke `superpowers:dispatching-parallel-agents`. The skill does not dispatch subagents itself — it produces the task definitions for the user to hand off.

### Dependencies

None — the skill uses only git, file reads, and grep. No special tooling required.

## Adaptive Behavior

| Discovery Size | Behavior |
|----------------|----------|
| 1-5 plans/branches | Run single-pass, no checkpoint needed |
| 6-11 plans/branches | Show correlation table, ask to proceed before deep inspection |
| 12+ items | Show correlation table, prepare task list, suggest `superpowers:dispatching-parallel-agents` for parallel inspection |

## Flow Diagram

```
discover plans (AEC config → conventions → Claude dir → ask user)
    ↓
discover branches (all local + remote, including remote-only via origin/)
    ↓
correlate (match plans ↔ branches, categorize orphans)
    ↓
[if 6+ items: checkpoint — "found X plans, Y branches — proceed?"]
    ↓
[if 12+: prepare task list, suggest dispatching-parallel-agents skill]
    ↓
deep inspect each pair (plan artifacts vs. code on branch via git show)
    ↓
produce gap analysis per phase/task
    ↓
ask: terminal only, file, or both?
    ↓
present report
    ↓
ask: what next? (cleanup / run tests / agent handoff / roadmap / nothing)
    ↓
execute chosen action(s) with per-item confirmation where needed
```
