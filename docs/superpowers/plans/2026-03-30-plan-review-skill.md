# Plan Review Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Claude Code skill that discovers plan files, correlates them with git branches, performs deep code inspection to determine actual completion state, and produces a gap analysis report with optional cleanup and handoff actions.

**Architecture:** Single skill (`plan-review/`) with SKILL.md and a report template reference file. The skill is procedural — it walks through discovery, correlation, inspection, reporting, and action phases in sequence. No scripts or external dependencies; all logic is expressed as Claude instructions using git commands, file reads, and grep.

**Tech Stack:** Markdown (SKILL.md), git CLI commands, Claude Code tools (Read, Grep, Glob, Bash)

**Spec:** `docs/superpowers/specs/2026-03-30-plan-review-skill-design.md`

---

### Task 1: Initialize the Skill Directory

**Files:**
- Create: `.claude/skills/plan-review/SKILL.md`
- Create: `.claude/skills/plan-review/references/report-template.md`

- [ ] **Step 1: Run the skill-creator init script**

```bash
python3 /Users/mattbernier/projects/agents-environment-config/.claude/skills/skill-creator/scripts/init_skill.py plan-review --path /Users/mattbernier/projects/agents-environment-config/.claude/skills/plan-review
```

Expected: Directory created with template SKILL.md and example subdirectories.

- [ ] **Step 2: Clean up generated scaffolding**

Delete the example files in `scripts/` and `assets/` directories that the init script creates — this skill only needs `references/`. Remove the `scripts/` and `assets/` directories entirely if empty after cleanup.

- [ ] **Step 3: Verify directory structure**

```bash
find /Users/mattbernier/projects/agents-environment-config/.claude/skills/plan-review -type f
```

Expected:
```
.claude/skills/plan-review/SKILL.md
.claude/skills/plan-review/references/report-template.md
```

(The references dir may have an example file from init — that gets replaced in Task 3.)

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/plan-review/
git commit -m "feat(skills): initialize plan-review skill scaffold"
```

---

### Task 2: Write SKILL.md — Frontmatter and Overview

**Files:**
- Modify: `.claude/skills/plan-review/SKILL.md`

- [ ] **Step 1: Write the frontmatter**

Replace the generated frontmatter with:

```yaml
---
name: plan-review
description: Use when reviewing, auditing, or cleaning up plan files. Discovers plans across the repo and Claude's project directory, correlates them with git branches, performs deep code inspection to determine actual completion state vs. claimed status, and produces a gap analysis report. Also triggered by "review my plans", "what's the state of my plans", "clean up plans", or "status of plan X".
metadata:
  filePattern:
    - "**/plans/**/*.md"
    - "**/specs/**/*.md"
    - "**/plan*.md"
    - "**/docs/**/*.plan.md"
  bashPattern:
    - "git branch"
    - "git log.*plan"
---
```

Note: The `metadata.filePattern` and `metadata.bashPattern` fields are used by the pretooluse-skill-inject hook to auto-inject this skill when Claude reads/edits plan files or runs plan-related git commands.

- [ ] **Step 2: Write the overview section**

After the frontmatter, write the Overview section. This should include:

- The core principle: "Plans lie. Code doesn't. This skill reconciles the two."
- A 2-3 sentence explanation of what the skill does
- The relationship between this skill and other skills (it can suggest PM agents for handoff, but doesn't couple to any)

Reference the spec Section "Overview" for exact wording. Keep it concise — under 150 words.

- [ ] **Step 3: Write the entry points table**

Add the Entry Points section with this table (from spec Section "Entry Points"):

| Trigger | Behavior |
|---------|----------|
| User invokes skill directly | Full cycle: discover → inspect → report → ask next |
| "review my plans" or similar | Same full cycle |
| "review this plan" / "status of plan X" | Single-plan mode: skip discovery, inspect the named plan only |
| "clean up plans" | Discovery + report, then jump straight to cleanup |
| "what's the state of my plans" | Discovery + report only, then ask what's next |

- [ ] **Step 4: Verify the file reads correctly**

Read `.claude/skills/plan-review/SKILL.md` and verify frontmatter parses correctly, overview is present, entry points table renders properly.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/plan-review/SKILL.md
git commit -m "feat(skills): add plan-review frontmatter, overview, and entry points"
```

---

### Task 3: Write the Ordered Checklist

**Files:**
- Modify: `.claude/skills/plan-review/SKILL.md`

Writing the checklist early establishes the procedural backbone — all subsequent sections conform to it rather than retrofitting.

- [ ] **Step 1: Add a Checklist section after the Overview**

Following the pattern from verification-writer and browser-verification, add a numbered checklist that Claude MUST follow in order:

```markdown
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
```

- [ ] **Step 2: Verify the checklist matches the flow diagram from the spec**

Compare the checklist against the spec's flow diagram at `docs/superpowers/specs/2026-03-30-plan-review-skill-design.md`. Every step in the flow should appear in the checklist.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/plan-review/SKILL.md
git commit -m "feat(skills): add plan-review ordered checklist"
```

---

### Task 4: Write the Report Template Reference

**Files:**
- Create/Replace: `.claude/skills/plan-review/references/report-template.md`

- [ ] **Step 1: Write the report template**

Create `references/report-template.md` containing the report skeleton from the spec Section "Report Structure". Use placeholder variables wrapped in `{{double_braces}}` that the skill fills during report generation:

```markdown
# Plan Review Report — {{date}}

## Summary
- {{plan_count}} plans found across {{source_count}} sources
- {{correlated_count}} branches correlated
- {{orphan_plan_count}} orphan plans, {{orphan_branch_count}} orphan branches

## Correlation Map

| Plan | Source | Branch | Category | Last Commit |
|------|--------|--------|----------|-------------|
| {{plan_name}} | {{source_path}} | {{branch_name}} | {{category}} | {{last_commit}} |

## Per-Plan Deep Inspection

### {{plan_name}}
- **Source:** {{source_path}}
- **Branch:** {{branch_name}} (last commit: {{last_commit_date}})
- **Overall:** {{completed_phases}}/{{total_phases}} phases complete

| Phase | Plan Status | Actual Status | Evidence |
|-------|-------------|---------------|----------|
| {{phase_name}} | {{claimed_status}} | {{actual_status}} | {{evidence}} |

- **Tests available:** {{test_count}} test files found (not run)
- **Staleness:** Last commit {{days_since_commit}} days ago

### Orphan Branch: {{branch_name}}
- **Changed files:** {{changed_file_count}} files, {{additions}} additions
- **Commit summary:** "{{commit_summary}}"
- **Assessment:** {{assessment}}

### Orphan Plan: {{plan_name}}
- **Artifacts on main?** {{on_main}}
- **Assessment:** {{assessment}}

## Runnable Tests
{{test_files_grouped_by_plan}}
```

- [ ] **Step 2: Verify the template**

Read the file back and confirm all placeholder variables are present and the markdown structure is valid.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/plan-review/references/report-template.md
git commit -m "feat(skills): add plan-review report template reference"
```

---

### Task 5: Write SKILL.md — Plan Discovery Section

**Files:**
- Modify: `.claude/skills/plan-review/SKILL.md`

- [ ] **Step 1: Write the Plan Discovery section**

Add the complete Plan Discovery section after the Entry Points. This section must include all three subsections from the spec:

**Source Resolution** — the priority-ordered list:
1. AEC config — check `AGENTINFO.md` for plans directory setting
2. Convention scan — `plans/`, `docs/plans/`, `docs/superpowers/specs/`
3. Claude's project directory — `~/.claude/projects/<project-hash>/` scanning for plan-like `.md` files
4. Ask the user — fallback

**What Qualifies as a Plan File** — the concrete signals (at least 2 must match):
- Checkboxes (`- [ ]`, `- [x]`)
- Phase/step headings (`## Phase N`, `## Step N`, `### Task`)
- Status markers (`[DONE]`, `[IN PROGRESS]`, etc.)
- File naming (`.plan.md` suffix, files in `plans/` directory)
- Implementation references (file paths, function names, create/implement/build verbs)

Include the exclusions list.

**Discovery Output** — describe the table format shown to the user.

Use imperative/infinitive form throughout (per skill-creator guidelines).

- [ ] **Step 2: Read the file and verify**

Verify the section reads coherently and all spec details are present.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/plan-review/SKILL.md
git commit -m "feat(skills): add plan-review discovery section"
```

---

### Task 6: Write SKILL.md — Branch Correlation Section

**Files:**
- Modify: `.claude/skills/plan-review/SKILL.md`

- [ ] **Step 1: Write the Branch Correlation section**

Add the Branch Correlation section with all subsections from the spec:

**Matching Strategy** — the four methods in order:
1. Explicit references in plan files
2. Naming convention matching (plan slug ↔ branch name)
3. Commit message scanning (opt-in, max 5 recent commits per branch, only for unmatched branches)
4. Main branch artifact check

**Correlation Categories** — the table with Matched, Orphan plan, Orphan branch, Stale match.

**Checkpoint** — the adaptive behavior (from spec's Adaptive Behavior table, which is the authoritative source for these thresholds):
- 1-5 items: no checkpoint, proceed directly
- 6-11 items: show correlation table, ask "proceed with full inspection?"
- 12+ items: show table, prepare task list, suggest `superpowers:dispatching-parallel-agents`

Include a concrete naming convention example: plan `gdocs-table-manipulation.plan.md` matches branch `feat/gdocs-table-manipulation`.

Include the exact git commands to use:
- `git branch -a` for listing all branches
- `git log -1 --format=%ci <branch>` for last commit date
- `git log -5 --oneline <branch>` for commit message scanning

- [ ] **Step 2: Read and verify**

Check that the section covers all four matching strategies and the adaptive checkpoint behavior.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/plan-review/SKILL.md
git commit -m "feat(skills): add plan-review branch correlation section"
```

---

### Task 7: Write SKILL.md — Deep Inspection Section

**Files:**
- Modify: `.claude/skills/plan-review/SKILL.md`

- [ ] **Step 1: Write the Deep Inspection section**

This is the most technically detailed section. Include all subsections from the spec:

**From the Plan Side:**
- Extract phases/tasks/steps with claimed status
- Extract referenced artifacts (files, modules, functions, routes, configs, tests)
- Extract dependencies between phases

**From the Code Side — Technical Constraints:**
Include the explicit technical constraint block about cross-branch inspection:
- `git show <branch>:<path>` for reading files on other branches
- `git show origin/<branch>:<path>` for remote-only branches
- `git ls-tree -r --name-only <branch> -- <directory>` for listing files
- `git show <branch>:<path> | grep <pattern>` for cross-branch grepping
- `git log -1 --format=%ci <branch>` for staleness

**Multi-branch Plans:**
Include the paragraph about plans spanning multiple branches — inspect each separately, merge into one report section.

**Gap Analysis Per Phase/Task** — the status table:
- Complete, Partial, Not started, Overclaimed, Underclaimed, Diverged
- Include the mechanical definition for Diverged (file exists + expected symbols absent)

**Orphan Handling:**
- Orphan branches: summarize changes, flag merge/abandon candidates
- Orphan plans: check main for artifacts, mark as merged or unstarted

- [ ] **Step 2: Read and verify**

Confirm all git commands are correct syntax and the Diverged detection method is clearly specified.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/plan-review/SKILL.md
git commit -m "feat(skills): add plan-review deep inspection section"
```

---

### Task 8: Write SKILL.md — Report, Cleanup, and Next Steps Sections

**Files:**
- Modify: `.claude/skills/plan-review/SKILL.md`

- [ ] **Step 1: Write the Report section**

Include:
- Reference to `references/report-template.md` — instruct Claude to read it and fill in the template
- Report destination question (terminal only / file / both) — ask each time
- Default file location: plans directory or user-specified

- [ ] **Step 2: Write the "After the Report" section**

The skill asks "What would you like to do next?" with these options:
- Clean up plans
- Run discovered tests
- Hand off to an agent
- Generate a roadmap artifact
- Nothing

The user can pick one, multiple, or none.

- [ ] **Step 3: Write the Cleanup Actions section**

Include:
- The action types table (Archive, Update status, Flag for deletion, Create branch reminder, Flag orphan branch)
- The presentation format with `[y/n]` per item
- The rule: each action only executes after explicit user approval

- [ ] **Step 4: Write the Agent Handoff section**

When the user chooses handoff, the skill:
- Prepares a structured handoff artifact (the report + remaining work summary)
- Lists available PM-type agents the user could invoke
- Does NOT invoke any agent itself — presents options and lets the user choose

- [ ] **Step 5: Write the Memory Integration section**

After a review, optionally save a project memory. Format:
```
"Plan review YYYY-MM-DD: X plans (N complete, M partial, K not started), Y orphan branches, Z stale. Report at <path-if-written>."
```
Type: `project`

- [ ] **Step 6: Read the complete SKILL.md and verify end-to-end**

Read the entire file. Verify:
- Frontmatter is valid YAML
- All sections flow logically
- No contradictions between sections
- All spec requirements are covered
- Total length is reasonable (aim for under 400 lines — verification-writer is 359, browser-verification is 534)

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/plan-review/SKILL.md
git commit -m "feat(skills): add plan-review report, cleanup, and next steps sections"
```

---

### Task 9: Validate and Package the Skill

**Files:**
- Read: `.claude/skills/plan-review/SKILL.md` (full file)
- Read: `.claude/skills/plan-review/references/report-template.md`

- [ ] **Step 1: Run the skill-creator validation script**

```bash
python3 /Users/mattbernier/projects/agents-environment-config/.claude/skills/skill-creator/scripts/quick_validate.py /Users/mattbernier/projects/agents-environment-config/.claude/skills/plan-review
```

Expected: Validation passes. If it reports errors, fix them before proceeding.

- [ ] **Step 2: Read the complete SKILL.md one final time**

Full read of the file. Check:
- Imperative/infinitive voice throughout (not "you should" — use "To X, do Y")
- No contradictions between checklist order and section details
- All git commands have correct syntax
- The adaptive behavior thresholds (1-5, 6-11, 12+) are consistent everywhere they appear
- Report template reference is correctly pointed to
- Entry points table covers all triggers from the spec

- [ ] **Step 3: Read the report template**

Verify all placeholder variables are present and the markdown renders correctly.

- [ ] **Step 4: Run the package script**

```bash
python3 /Users/mattbernier/projects/agents-environment-config/.claude/skills/skill-creator/scripts/package_skill.py /Users/mattbernier/projects/agents-environment-config/.claude/skills/plan-review
```

Expected: Validation passes and a `plan-review.zip` is created.

- [ ] **Step 5: Commit the final state**

```bash
git add .claude/skills/plan-review/
git commit -m "feat(skills): finalize plan-review skill — validated and packaged"
```

---

### Task 10: Update Skill Registration

**Files:**
- Check: `.claude/skills/CLAUDE.md` (if it lists skills, add plan-review)
- Check: Any skill index or registry files in the repo

- [ ] **Step 1: Check if skills are registered anywhere**

Read `.claude/skills/CLAUDE.md` and check if there's a list of available skills that needs updating.

- [ ] **Step 2: Add plan-review to any skill registries found**

If there's a skills index, add plan-review with its description.

- [ ] **Step 3: Verify the skill shows up in the skills list**

The skill should appear in the available skills list shown in system reminders. This may require a session restart to verify — note this for the user.

- [ ] **Step 4: Commit if changes were made**

```bash
git add .claude/skills/CLAUDE.md
git commit -m "docs(skills): register plan-review skill in skill index"
```

(Adjust the `git add` path to match whichever file(s) were actually modified.)
