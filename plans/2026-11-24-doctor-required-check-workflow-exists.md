# Review-gate doctor fails when a ruleset requires `Review Gate` and the default branch cannot publish it

**Status:** planned. Scheduling pending.
**Priority:** medium. Cheap to build; it turns a silent merge deadlock into a named failure.

**Incumbent (checked 2026-11-24):**

- Seeding a new repo before its rulesets exist is already owned by an org's repo-create script (a platform-ops repo's
  `scripts/repo_create.py`, merged 2026-11-23). It writes the gate workflows to the integration branch, then applies rulesets, and
  stops at its step 4 when a workflow behind a required check is missing. The same ordering is written into the operator
  reference for that flow. So the **installer seed flag and the `main-via-staging.yml` / `notion-sync.yml` templates are dropped
  from this plan**: those two workflows are one org's conventions, not a generic `review-gate` product surface, and a second copy
  would drift from the reference repo the script copies byte-for-byte.
- `review-gate/scripts/doctor-review-gate.py` (claude-skills) has `remote_checks`, which lists rulesets and only *warns*, and
  returns nothing, so `main()` cannot turn a remote finding into an exit code. It has no check that the gate can report at all.
  That gap is what remains.

## Problem

Rulesets applied before any workflow exists require checks that cannot report. `Review Gate` runs on `pull_request_target`; the
shipped `review-gate.yml` records (in its header, with a live run as evidence) that GitHub takes that workflow file from the
repository **default branch**, whatever the PR base, and a PR cannot supply it. So the workflow must already be merged to the
default branch before any PR can pass. A new repo whose default branch has no gate deadlocks the first PR and the first promotion
for every ordinary (non-bypass) merge (seen on two new repos on 2026-11-23). The create-time script now prevents the order mistake
for repos it creates. Nothing detects the same state afterwards: a workflow renamed or deleted, a ruleset added by hand, a repo
created some other way. A bypass list does not make the required check satisfiable, so the check runs on those rulesets too.

## Root cause

A required status check is a name in a ruleset; whether anything can produce that name is a separate fact nobody compares.

## Scope decision: the known contract only

A general "can any workflow publish context X" analyzer is not part of this plan. Producers can be job names, reusable-workflow
calls, matrices, expressions, PR-supplied workflows (`pull_request` runs from the PR's merge commit, so a baseline branch
inventory proves neither presence nor absence) or Checks API calls with an explicit name. Getting that wrong yields false FAILs
and false assurance, so it is a separate plan. GitHub also binds a requirement to a context name and an optional integration, not
to a workflow path or event, so a ruleset alone never proves which producer a repo intends. This plan therefore hard-fails only
when the **caller asserts** the contract the review-gate skill itself ships: `Review Gate` is produced by the skill's
`review-gate.yml`, a `pull_request_target` workflow read from the default branch only. The assertion is an explicit doctor option
(step 3); an operator or an org's post-create step passes it. Without it the same finding is a WARN. Under the assertion the
default-branch inventory is sufficient evidence, because nothing else can supply that workflow.

## Where it can run

`review-gate-doctor.yml` (the optional CI job) states it has no token that can read rulesets, so its ruleset checks are warnings
there. This check therefore runs where `gh` can read rulesets and repository contents (an operator's shell, or a post-create step
in an org's repo-create flow); in the CI job it stays a warning that says why it was skipped. Opting the CI job into a token is a
separate decision for the repo owner. Minimum permissions: ruleset reads need Metadata read, workflow reads need Contents read.

## Correct fix (claude-skills PR, normal gates)

1. `remote_checks` returns a result and `main()` exits 1 on a confirmed remote failure (it returns nothing today).
2. For every **enforcing** ruleset (paginate the listing) that covers one of the doctor's `MERGE_BRANCHES` (`main`, `staging`, via
   `ruleset_covered_branches`), read its `required_status_checks`. Other branches are out of scope and the output says so.
3. Only the context `Review Gate` is analyzed. If it is pinned to an `integration_id` other than 15368 (GitHub Actions), skip it
   (an installed app reports it). Pinned to 15368, or with no `integration_id`, it is analyzed. Every other required context is
   listed once as "producer not verified (generic producer analysis is out of scope)": a WARN, never a FAIL. A new doctor option
   (`--expect-default-branch-gate`) asserts that this repo uses the skill's `review-gate.yml` as the producer; only with it can the
   analysis FAIL. A source-less context never FAILs without the option (an external publisher or a PR-supplied `pull_request`
   workflow could satisfy it).
4. List `.github/workflows/` on the **default branch** once and read the files. The listing is complete only below the Contents API
   cap of 1,000 entries; at the cap, after a partial fetch failure, or on a rate limit, the result is a WARN.
5. The default branch has the producer when `.github/workflows/review-gate.yml` (or `.yaml`, the path the installer writes) exists
   there and declares a `pull_request_target` trigger. No other file counts: a substring match would let the companion
   `review-gate-doctor.yml` (which mentions "Review Gate" in a comment and its own name but publishes no such check) mask a deleted
   gate. A file at another path that the repo wants to use as the producer is the unverified case, so it WARNs.
6. With the assertion (step 3), **FAIL** (exit 1, naming the context, the default branch and the fix: "merge review-gate.yml to
   <default branch> before requiring the check") when the default-branch inventory is complete and readable and step 5 finds no
   producer. That holds even when the workflow exists only on `staging` or another covered branch: it will not load until it
   reaches the default branch, and the message says so. Without the assertion the same state is a WARN that names the option.
7. Absence of `.github/workflows/` (a 404 on the listing) counts as the empty inventory only when the repository and the default
   branch are already known readable; the helper keeps the HTTP status. Denied access, a missing ref and a transient failure are
   each a WARN that names the status.
8. `install-workflow.py`'s closing hint orders the steps: merge the workflow to the default branch first, then require the check.
9. Contract tests (fixtures, no network). With the option: a ruleset requiring `Review Gate` with `review-gate.yml` on the default
   branch (pass), without it (fail), on a covered branch only (fail, default branch named), with the real companion
   `review-gate-doctor.yml` present and the gate absent (fail), an absent workflows directory on a readable repo (fail), a
   `review-gate.yml` without `pull_request_target` (fail). Without the option: the same missing-gate states (warn naming the
   option), a PR-supplied `pull_request` workflow named `Review Gate` (warn, never fail), a source-less context with no workflow
   (warn). Either way: a non-Actions integration id (skip), another required context (warn, not verified), more than one page
   of rulesets, the 1,000-entry cap, denied access, missing ref and transient failure (each warn), and `main()` exiting 1 on a
   confirmed failure and 0 on warnings only.
10. Versioning: update the version in every file the doctor's parity check and the repo's manifest consistency check name
    (`review-gate/SKILL.md`, `review-gate/hooks.json`, `skills-manifest.json`), and add a note under the doctor section of
    `review-gate/SKILL.md`.

## Rollout

Author delegate opens the claude-skills PR into `main` with the `review:high` label (squash). aec picks up the new version through
the normal catalog sync; no fleet upgrade is requested, and no broad `aec upgrade` runs. Repos get the check when they next
re-vendor. Passing `--expect-default-branch-gate` from an org's repo-create post-create step is that org's own change, filed with
its owner once the doctor ships.

## Out of scope

Installer seed flag and workflow templates (dropped above). General producer inference for arbitrary required contexts, including
reusable-workflow traversal, matrix and expression names, event eligibility, merge queues and PR-supplied workflows (a separate
plan; those contexts WARN today). Applying or repairing rulesets (the org's repo-create script and its operators own that).
Branches other than `main` and `staging`. Branch protection rules that predate rulesets. Deciding whether the doctor's CI job gets
a ruleset-reading token.
