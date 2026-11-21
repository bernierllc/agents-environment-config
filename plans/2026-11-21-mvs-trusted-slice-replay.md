# Trusted replay for merge-with-main promote slices (main-via-staging guard)

> Status: plan, not started.
> Owner of the follow-up: aec (the canonical `main-via-staging.yml` and `scripts/check-main-source.sh`).

## Problem

A downstream repo (a staging-default repo that cuts `promote/*` slices) lands a mid guard for `promote/<YYYY-MM-DD>-<n>` heads. The guard
(`main-via-staging.yml`, `pull_request_target`, a privileged job) cannot run the PR head's code, so
for a promote slice it runs an inline, metadata-only GitHub compare check. It enforces: same-repo
head, a `promote/<date>-<n>` ref, a head SHA on staging's first-parent history, and fail closed on a
truncated compare, an API error, an empty `HEAD_REPO` or a head that merges a staging cut with main.

That last rule is the gap. A slice head that merges main into its staging cut (a merge-with-main
slice) fails closed. Today's escape hatches are both manual: back-merge main into staging with a
merge commit and cut a plain slice, or use a `hotfix/*` branch.

## Correct fix: a trusted replay

The guard runs the BASE ref's script and generator over fetched head objects. It never runs the
head's generator.

1. The trusted-base checkout (already in the guard) supplies the script and the generator from the
   PR base.
2. The job fetches the head's git objects only (no checkout of head files into the working tree, no
   execution of anything the head carries).
3. The base script replays the slice: it recomputes the expected merge result and the regenerated
   manifest from the fetched objects and compares them to the head's tree by object id.
4. A merge-with-main slice passes only when the replayed result equals the head's tree. Any
   difference, a missing object, a truncated fetch or an API error fails closed.

## Rejected: consuming the `Promote slice` check result

Do not make the guard pass because a `Promote slice` check run succeeded. `promote-slice.yml` is an
unprivileged `pull_request` workflow that runs from the PR head, so the head controls its
definition. A forged same-name check run (or a head that edits the workflow) would pass the guard.
The guard must derive its verdict from code and data the base controls. `promote-slice.yml` stays
read-only and gates nothing.

## Surfaces to change (grep every one before coding)

- aec `.github/workflows/main-via-staging.yml` (canonical blob at tag v2.53.1 is `00c2a594`).
- aec `scripts/check-main-source.sh` and its tests.
- The forged-check detector pins in `scripts/check-forged-gate-names.py` (the guard name and the
  `Promote slice` name must stay distinct; no new job may take a protected name).
- Any downstream repo's slice-aware mid guard, its `promote-slice.yml` and the tests that pin them.
- Every repo carrying the mid guard or the canonical guard re-vendors after this lands.

## Acceptance

- A merge-with-main promote slice whose replayed tree equals the head passes the guard.
- A tampered slice, a fork head, a deleted fork, a truncated fetch and an API error each fail closed
  (one test per case, a real git graph, stubbed `gh` only at the network boundary).
- A forged `Promote slice` check run changes nothing (test).
- Compare pagination beyond 124 commits and the live truncation path are exercised on a throwaway PR
  (the downstream repo's throwaway-PR checklist) before any promotion relies on the guard.
- The detector (`check-forged-gate-names.py`) returns rc 0 on the head.

## Open questions

- Fetch cost for large slices: fetch the compare range only, or the whole head?
- Does the replay live in the canonical guard (aec) with downstream repos adopting it, or stay a
  downstream script until a second repo needs it? Recommendation: canonical, because every
  staging-default repo with slices needs the same rule.
