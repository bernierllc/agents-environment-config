#!/usr/bin/env bash
# Which branches may open a PR into main (main-via-staging.yml).
#
# main is promotion-only. The only allowed head is `staging`.
# Hotfix/reverts land on staging first, then promote — a branch name alone
# never authorizes bypassing staging review.
#
#   HEAD_REF=<branch> HEAD_REPO=<owner/repo> REPO=<owner/repo> \
#     bash scripts/check-main-source.sh
#
# Every allowed head must live in this repo: a fork's branch named 'staging'
# is not our staging. HEAD_REPO and REPO are required: an empty HEAD_REPO
# (e.g. a deleted fork) must fail, never skip the fork check.
#
# Bootstrap: this check runs for PRs targeting main. It does not move the
# GitHub default branch; activating it as a merge gate requires a ruleset /
# branch protection that requires the check named exactly
# "PRs into main must come from staging", which is the main-via-staging.yml
# job itself: this script's exit code fails that job. The check is
# commit-scoped: a PR from another branch at the very same SHA as staging
# delivers the identical commit.
# Forged same-name jobs are scripts/check-forged-gate-names.py's concern.
set -euo pipefail
: "${HEAD_REF:?HEAD_REF is required}"
: "${HEAD_REPO:?HEAD_REPO is required (empty means the head repo is gone; treat as a fork)}"
: "${REPO:?REPO is required}"

if [ "$HEAD_REPO" != "$REPO" ]; then
  echo "::error::PRs into main must come from a branch of $REPO, not a fork ('$HEAD_REPO')."
  exit 1
fi

case "$HEAD_REF" in
  staging)
    echo "::notice::'$HEAD_REF' is an allowed source for main."
    exit 0
    ;;
esac
# A merge-with-main promote slice is still rejected, exactly as before this branch existed: provenance may only
# add a reason. Acceptance needs the trusted replay (plan 2026-11-21-mvs-trusted-slice-replay, R2) and its
# hosted evidence (R3); until both land no exit path here is 0. Provenance output feeds that later work.
if [[ "$HEAD_REF" =~ ^promote/[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]+$ ]]; then
  if bash "$(dirname "${BASH_SOURCE[0]}")/check-slice-provenance.sh"; then
    echo "::notice::slice provenance holds for '$HEAD_REF'; that alone never admits a slice."
  fi
  echo "::error::promote slice '$HEAD_REF' rejected: this guard has no trusted replay yet, so no slice is accepted."
  echo "Promote 'staging' -> main instead."
  exit 1
fi
echo "::error::PRs into main must come from 'staging' (got '$HEAD_REF')."
echo ""
echo "main is promotion-only. Merge this into staging first, verify there,"
echo "then promote staging -> main."
echo ""
echo "There is no hotfix/* or revert-* bypass. Land the fix on staging,"
echo "then open staging -> main."
exit 1
