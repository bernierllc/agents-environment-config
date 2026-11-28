---
name: "feature-map-review"
description: "Map every feature of a software project, find its gaps, re-cut plans and backlog by feature, then map the work and the code's boundaries. Builds a feature registry with links, tags plans and tracker rows by feature, records every gap under a permanent id, reviews each feature against its plans, groups gaps into workstreams, writes a plan review, applies what the user accepts and makes one tracker row per workstream. Then types workstream dependencies (critical paths, linchpins, what waits on people, delivery data) and maps the code into contexts (owned files and tables, declared interfaces, imports reaching past them) to show which work can safely run in parallel. Use whenever someone wants a feature map, a gap audit of code against plans, unowned, stale or conflicting plans, a prioritised roadmap, the critical path, what to start next, what can run in parallel, or bounded contexts and interface boundaries, even if they only say \"what are we missing\", \"audit our plans\" or \"map this project\"."
tags: ["skill"]
---

# Feature map and plan review

This skill runs a project-wide review in stages. Each stage leaves files in the repo that the next stage
reads, and each stage ends at a checkpoint where the user decides what happens next. The aim is to give
the user six things:
1. a true picture of the product: every feature and how they depend on each other;
2. every known hole, each with a permanent id;
3. the plans re-cut by feature, so overlaps, conflicts, stale plans and unowned work show up;
4. a backlog that traces every row back to the gaps it closes;
5. the work graph: what each workstream needs first, the critical path to each milestone, and what waits
   on a person, a vendor or a decision;
6. the context map: the product's independent pieces, what each owns and offers, and where the code
   crosses them, so the user knows which work can run side by side safely.

Why the cut by feature matters: plans are written one initiative at a time, and gaps are found one at a
time. Neither view shows that three plans define the same thing three ways, that a done plan still claims
open work, or that a high-severity hole has no owner. Looking at one feature with all of its plans and gaps
together does.

You will orchestrate many parallel agents. Your own job is the decisions and the merges, so keep file dumps
out of your context: agents write JSON files, and you read them with scripts.

## The stages

| # | Stage | Output | Checkpoint |
|---|---|---|---|
| 0 | Set up | `docs/feature-map/config.json`, branch, scratchpad layout | Confirm conventions with the user |
| 1 | Registry and tagging | `features.json`, `features:` in every plan, the map page | Show the map |
| 2 | Gap table | `gaps.json` (permanent ids), `gaps:` in plans, closed plans | Show counts and learnings |
| 3 | Feature reviews | `reviews.json`: per feature, workstreams `WS-NNN` | (none, goes straight to 4) |
| 4 | Synthesis and report | `plan-review-<date>.md`, consolidated workstreams | **User accepts or edits** |
| 5 | Apply | edited, new and archived plans; synced frontmatter | Checks green, commit |
| 6 | Tracker rows | one row per workstream, linked to its plan's row | Row URLs written back |
| 7 | Ship | one or more PRs, sized for review | PR open, reviews requested |
| 8 | Work view | `work.json` (edges, waits, who, delivery data), `work-review-<date>.md` | **User reads the review** |
| 9 | Context map | `contexts.json`, the Contexts tab | **User reviews the boundaries** |

A user can stop after any stage, and each stage is useful by itself. Stage 1 alone gives a feature map;
stages 1 and 2 give a gap audit. Stage 8 needs the workstreams of stage 3; stage 9 needs only the
registry, so a user who asks "what can run in parallel" can get a context map right after stage 1. When a
project already has `docs/feature-map/`, run in **refresh mode**
(see the end of this file) instead of starting over.

Read `references/data-model.md` before writing any data file. It defines every file, field and id rule,
and the scripts enforce it.

## Bundled tools

Node 18+, no dependencies. Run them from the target repo root (`<skill>` is this skill's directory):

- `node <skill>/scripts/build-map.mjs [--check]`: validates all the map data and renders
  `docs/feature-map/dist/index.html` (an interactive map: areas, features, links, gaps, plans on a timeline
  by phase, per-feature review, learnings, and when their files exist the Work view and the Contexts view).
  `--check` only validates; wire it into the project's lint so the data can never drift from the plans
  or the code. The graph and context compute live in `scripts/lib/work.mjs` and `scripts/lib/contexts.mjs`.
- `node <skill>/scripts/check-plans.mjs`: every live plan has valid `features:` and `gaps:` frontmatter.
- `node <skill>/scripts/gaps.mjs next-id | add | close | sync-plan-gaps | learnings | stats`: the gap table.
  It hands out permanent ids and keeps one record per line.
- `assets/templates/`: starter files for a new project. `assets/feature-map.html` is the page template the
  build fills.

See `scripts/README.md` for flags. Prefer these over hand-editing JSON: they keep ids permanent and diffs
small.

## Stage 0: set up

Learn the project's conventions before you touch anything. Read its agent instruction files (`AGENTS.md`,
`CLAUDE.md`, `CONTRIBUTING`), its plans directory and any roadmap file. Then decide each of these, and
ask the user only about the ones you cannot find out:

- **Plans:** where they live, what frontmatter they carry, the status values, and the archive convention.
  If plans have no frontmatter, propose adding the minimal block in `assets/templates/plan-template.md`.
- **Phases:** how the project orders work (a roadmap file, milestones, Phase 1/2/3). Workstreams and new
  plans are placed in these.
- **External plans:** plans kept outside the repo, for example Notion pages. They go into
  `external-plans.json` and appear on the timeline with a dashed outline.
- **Tracker:** where backlog rows live (Notion, GitHub Issues, Linear, or nowhere). Read
  `references/trackers.md` for the one you find. Learn the tracker's own rules before writing to it; some
  workspaces keep backlog and in-flight work in different databases.
- **Principles:** the product principles, review rules, branch rules and CI cost rules. Reviewers check
  plans against the principles, so pass the file to every reviewer brief.
- **Scale:** count plans, tracker rows and top-level source areas. Size the agent fan-outs from that
  (guide: about 10 plans or 70 tracker rows or 10 features per agent; stay inside any agent-count guideline
  the session gives you).

Then:
1. Branch off the project's integration branch, following its rules.
2. Copy `assets/templates/*` into `docs/feature-map/`, except `work.json` and `contexts.json` (they come
   in at stages 8 and 9; the build reads them as soon as they exist), and fill in `config.json`.
3. Make a scratchpad layout for agent inputs and outputs, with one folder per stage (`tag/`, `gapwork/`,
   `review/`, `apply/`, `rows/`). Agent outputs are working files and never get committed.

## Stage 1: registry and tagging

1. **Seed the registry yourself** from a code read: routes, pages, API, jobs, integrations, admin tools.
   Group the features into 8 to 15 **areas**, and add the **links** between them. Link kinds are `needs`,
   `gate`, `trigger`, `data` and `exposes`, with `partial` for half-built links. A feature is something a
   customer, operator or integrator would recognise as its own capability, not a module. Engineering and
   process capabilities (CI, deploys, review gates, plan sync) get their own area.
2. **Fan out** with the briefs in `references/briefs.md`:
   - plan taggers over all live plans;
   - tracker taggers over open rows that have no plan;
   - external-plan readers (for example over a Notion tree, read-only);
   - one debt harvester over the repo's own lists of known debt (TODO markers, baselines, exclusion lists,
     feature flags, ungated route lists);
   - one surface-parity auditor (UI vs API vs CLI/MCP vs SDK vs docs, per feature);
   - one hunter for built capabilities the registry is missing.

   Each tagger returns the features a plan touches, proposed new features, and gaps. Deferred and
   out-of-scope items count as gaps, and they are the most valuable, because nobody owns them.
3. **Merge by hand.** Dedupe proposed features, since several agents will invent the same one under
   different ids. Then write `features:` into every plan's frontmatter, along with `annotations.json`
   (a summary per plan and how much of it is built) and `tracker-features.json`.
4. Run `build-map.mjs --check`, then build, and open the page in a browser to confirm it renders, with no
   console errors and no horizontal scroll at phone width.

**Checkpoint:** show the map. Publish it as an artifact if the session can, and give the counts:
features, links, plans tagged, gaps found. Ask whether the areas and features look right before building on them.

## Stage 2: gap table

1. Move every gap into `gaps.json` with a permanent id (`gaps.mjs add`). Ids are never reused or
   renumbered, because tracker rows, plans and commit messages will cite them.
2. **Enrich** with the gap-enrichment brief. Agents receive disjoint slices of gaps, and for each gap they:
   - mark duplicates;
   - name **every** feature the fix touches (`related`), because a fix and its plan have to span all of
     them;
   - write a detail a stranger could act on;
   - attach evidence they actually opened;
   - verify against the code that the gap is still open;
   - assign a `cause` (the taxonomy is in the data model);
   - match an existing tracker row;
   - propose an owning plan only where the plan's scope clearly fits.
3. Merge: apply duplicates, close fixed gaps with the evidence, and write `gaps:` into the frontmatter of
   each owning plan.
4. **Close what is built.** A plan whose work is all in the code should be closed (status done, with its
   PRs) and its tracker row updated. Do this only with evidence, such as merged PRs or the code path.
5. Build and check again. The page shows each gap on its home feature and on every related feature, with
   `#GAP-0123` deep links, and a Learnings view (gaps by cause, by how found, by area).

**Checkpoint:** report open gaps, how many no plan or row covers, and the top causes. Do not offer one
tracker row per gap. Hundreds of rows is noise. Offer the per-feature review instead (stages 3 to 5). It
groups gaps into a few hundred workstreams at most, and it usually finds plan problems no single gap shows.

## Stage 3: feature reviews

Give each reviewer a slice of features (the feature-review brief). Each feature's input comes from the
data, built with a script:
- the feature;
- its open home gaps (full records);
- related gaps homed elsewhere;
- every plan naming it, with verb, status, phase and summary;
- tracker rows without a plan;
- its links.

Each reviewer returns, per feature:
- a summary;
- health (`solid`, `gaps` or `at-risk`);
- each plan's role (`owns`, `touches`, `stale`, `conflicts`);
- **workstreams**: every home gap in exactly one, each with title, why, gaps, features, owner plan or
  `new`, phase, size and depends_on;
- conflicts, plan changes and proposed new plans.

Merge with a script that:
- gives workstreams permanent `WS-NNN` ids;
- checks that every open gap sits in exactly one workstream;
- normalises plan keys, dropping plans that are not live and plans without frontmatter;
- writes `reviews.json` one feature per line.

## Stage 4: synthesis and report

The reviewers each saw a slice. Now take the cross-feature view with the synthesis brief: one agent, or
a few split by concern (structure, changes, phase 1). The synthesis has six parts:

1. **New plans:** the smallest set of coherent outcomes for the unowned workstreams. Prefer folding a
   workstream into a live plan whose scope fits.
2. **Final owner per workstream.**
3. **Plan changes, ranked:** merges, splits, closes, re-scopes and phase moves. Flag **catch-all plans**
   that carry work for many unrelated features.
4. **Conflicts, deduplicated:** mark each one as needing a product call from the user or as mechanical.
5. **The phase 1 critical path:** what must land for the nearest milestone, in order.
6. **Consolidation:** merge workstreams that share an owner and phase and would ship together. Aim for
   roughly a third of the original count, and never merge across phases or unrelated outcomes.

Then write `docs/feature-map/plan-review-<date>.md` from `references/report-template.md`. Lead with:
- what to do now, outside any plan (live risks);
- the critical path;
- the decisions only the user can make, each with a recommended answer.

Link every plan, workstream and gap by id. The build copies the report next to the map, and the page links
to it.

**Checkpoint:** present the report (as an artifact or document if the session can publish one) and ask
one question with options: accept all recommendations, accept with edits, or walk through the decisions.
Nothing in the plans changes before this answer, because the report is a proposal.

## Stage 5: apply

Apply only what was accepted. Fan out so every plan file has exactly one editing agent (the apply-edits
brief), plus new-plan writers (the new-plan brief), plus one agent for external plans.

- **Decisions:** rewrite the conflicting text so the plan states the decision, and add a dated line
  recording that the user decided it.
- **Re-scopes:** move the scope, steps and acceptance criteria, and leave a pointer to wherever content
  went.
- **Splits:** the new plan writer lifts the section out; the source keeps a one-line pointer.
- **Closes and merges:** set the project's valid status, then archive with the project's convention. That
  means moving the file, renaming its manifest key, removing roadmap lines and repointing every citation,
  code comments included. A status the checker rejects (such as "superseded" when only "archived"
  exists) is a sign to archive, not to invent a status.
- **Every new plan opens with a provenance line:** created by the feature-map review on `<date>` (link the
  report), carrying `WS-…`, closing `GAP-…`. Tracker rows made from it repeat that line. This is how
  anyone later learns where a plan or row came from.

Then do the lead's merge work yourself:
- set each workstream's final owner;
- `gaps.mjs sync-plan-gaps --apply`, so each plan lists its fixed gaps plus the open gaps of the
  workstreams it owns;
- add the features new plans introduce, and repoint `introduced_by`;
- drop references to archived plans from the review data;
- write the section for any workstream an agent moved into a plan but did not describe there.

Before the checks, scan every plan, live and archived, for each workstream id and confirm the paragraph that mentions it names its current owner. Split any plan whose workstreams span phases so the earliest slice shows in its own phase. Grep the whole repo (configs, `.env.example`, migrations) for paths of archived plans.

Run `check-plans.mjs`, `build-map.mjs --check`, and the project's own lint, type check and tests. **Commit
as soon as checks pass.** Long sessions restart, and uncommitted work is the work you lose.

## Stage 6: tracker rows

Read `references/trackers.md`. The steps:
- one row per open workstream (never one per gap), built by a script from the data;
- each row carries the provenance line, the workstream's why, its gaps with deep links and evidence, its
  features, its owner plan, its phase and its size;
- properties carry the workstream id and the gap ids, so the tracker can be queried by either;
- rows are linked under their owner plan's row where the tracker supports parent/child.

Agents create the rows from ready-made payloads, split by owner plan so no two agents edit the same parent
row. They query before creating, so a rerun never duplicates rows, and write their output file after every
batch. Write the row URLs back into `reviews.json` (`row`), so the map links each workstream to its row.

Adding a property to a tracker database shared by other projects changes it for all of them. Say so when
you do it, and touch only the rows you create and the parent rows you link.

## Stage 7: ship

- Respect the project's PR rules: base branch, who merges, review order and CI cost.
- **Size the PRs for review.** If the project caps the size of a review or a promotion, split the work:
  the map and data in one PR, and the applied review in a second PR stacked on it. Say in each PR how they
  relate.
- The PR body says how the data was made (which agents, how many, what was merged by hand), what the
  checks show, and what is generated and needs no line-by-line review.
- Before every push, run the checks locally; CI minutes cost money. After pushing, follow the session's
  PR-watching rules.

## Stage 8: Work view

The plan review says what to do; the work graph says in what order, and what is really in the way.

1. **Edges.** Copy `assets/templates/work.json` into the map directory. Fan out the workstream-dependencies brief over slices of workstreams (about 65 each). Each
   agent records, per workstream, what it `needs` first (`blocks` or `enables`, each with a concrete why),
   what it `waits` on outside the graph (`human`, `external`, `date`, `decision`) and `who` can do it
   (`agent`, `agent+human`, `human`). Merge into `work.json` with a script; every workstream gets a
   record. Fix every `--check` problem; a `blocks` cycle means two agents disagreed, so keep the edge
   with the stronger why.
2. **Delivery data.** One agent runs the delivery brief over git, PRs and CI: rework and follow-up fixes
   per feature, PR and CI churn, promotion lag, plan lead times. Put it in `work.json`'s `git`, and set
   `size_days` from plan lead times (PR durations are hours at every size and cannot size work).
3. **Milestones.** Add one per nearest goal (for example launch = phase 1; scale = phases 1 and 2). The
   build computes each milestone's critical path, every workstream's slack and classes (long pole,
   linchpin, convergence, waits, phase inversion, agent-ready, leaf).
4. **Sync back.** Write each workstream's needs into its owner plan's section (`Needs: WS-…`) and its
   tracker row, so the order is visible where people work.
5. **Write `work-review-<date>.md`** from the template in `references/report-template.md`: the constraint
   (usually the owner's queue, not agent capacity), the critical paths, the linchpins, what is ready now,
   what waits on people, graph defects, the delivery numbers, and the next iteration. Every number comes
   from the build output.

**Checkpoint:** publish the map and the review, and ask the user for the one decision the review puts
first. Typical: clear the owner's queue on the critical path, then dispatch the ready lanes.

## Stage 9: Context map

The work graph says what order work goes in; the context map says which work can safely run at the same
time. Two workstreams that change different contexts, with no imports reaching between them, can run in
parallel; two that share a context or a reach-in will collide.

1. **Draft `contexts.json`** from `assets/templates/contexts.json` (the lead, or the context-boundaries
   brief on a large repo). Usually one
   context per area, a `shared` kernel (database client, env, logging, UI kit) and a `none` context for
   tooling. Set `scope`, `aliases` and `schema` for the codebase. Every file under `scope` and every
   schema table must end up with exactly one owner; `--check` lists the ones that do not.
2. **Declare interfaces.** Start with the entry points the principles name (for example "every export goes
   through exportProject()") and each module's public index. Add `missing` interfaces where a plan must build one,
   with `ref` pointing at that plan.
3. **Read the first build.** Look at the reach-in matrix and at `implicit` (files other contexts import
   that nobody declared). Declare the ones the code already treats as public; leave real leaks as
   reach-ins. Check the kernel imports no context; if it does, something domain-specific lives in the
   kernel and should move.
4. **Lanes.** The Contexts tab lists agent-ready workstreams that change disjoint contexts, with the
   reach-ins that still couple them. These are the candidates for parallel agents; the coupling says
   which interface to build first so they stay apart.
5. **Write a plan** for the context map itself (boundaries to confirm, interfaces to declare, reach-ins to
   untangle, and a lint ratchet so new reach-ins fail), with a tracker row for the user's review.

**Checkpoint:** the user reviews the boundaries and the declared interfaces; those are product decisions,
not code facts. Until they do, say which numbers rest on the draft.

## Running the agents

Every brief follows the same shape. Use the templates in `references/briefs.md` and fill them in for the
project:

- **Why:** the user's goal in a paragraph, and where this agent fits ("one of 12; you own only…").
- **Inputs:** exact paths, read-only unless stated. Never pass a hypothesis to confirm.
- **Decide:** the fields, each with its rule and a size limit.
- **Output:** one JSON file at a given path, with a schema example. Validate it before finishing.
- **Final message:** at most 4 to 6 lines. The file is the deliverable.

More rules:
- **Disjoint ownership.** Every file and every tracker row has exactly one agent that may write it.
- **Restart safety.** Agents rewrite their output file after each step and skip done work on resume.
  Tracker writers query before they create. Resume a stopped agent from its transcript instead of
  starting a new one.
- **Verify.** Agents cite evidence they actually opened. Treat an agent's claim that something is fixed or
  built as a lead to check, not a fact.
- **Plain words.** No marketing tone; follow the project's style rules (some forbid em-dashes).
- **Large JSON:** one record per line, so diffs stay one line per feature, gap or row. Read it with
  scripts; never paste it into your context.

`references/lessons.md` lists what went wrong the first time this was run (over a thousand gaps, well over a
hundred plans and several hundred tracker rows), plus a second run that added the Work view and the context map. Read it before
stage 2 and again before stage 8.

## Refresh mode

When `docs/feature-map/` already exists:
1. Run `build-map.mjs --check` and `check-plans.mjs`, and fix what they report: new plans without tags,
   archived plans still referenced.
2. Tag only plans and rows changed since the registry's `generated_from` note.
3. Append new gaps with `gaps.mjs add`. Never renumber. Close the fixed ones with `gaps.mjs close`, giving
   the PR or plan that fixed them.
4. Re-review only the features whose gaps or plans changed, keeping their existing `WS-NNN` ids. New
   workstreams take the next ids.
5. Report what moved since last time: gaps opened and closed, by cause, and workstreams done.
6. Give every new workstream a `work.json` record (its needs, waits and who), and drop records of
   workstreams that closed. Re-run the delivery brief when the last `git.taken_at` is more than a month old.
7. Add globs and table owners for new code until `--check` passes, and say in the report how the
   reach-in count and the independent pairs moved since the last build.

<!-- feedback-loop:begin -->
## Feedback

If the `feedback-loop` skill is installed, use it to improve this skill over time:

- When this skill's own instructions cause rework, a wrong default, a missed case or a needless
  pause, log it as it happens: subject `skill:feature-map-review`, with the phase or section at fault and the
  concrete fix to these instructions.
- At the end of a run, check `skill:feature-map-review`; if a review is due, make the feedback-loop offer.

If `feedback-loop` is not installed, ignore this section.
<!-- feedback-loop:end -->
