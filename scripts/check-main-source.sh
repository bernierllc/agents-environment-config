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
# branch protection that requires the published Check Run named exactly
# "PRs into main must come from staging" (not the Actions job name); see the
# `main promotion gate` ruleset. Only an allowed source publishes that check
# (success); a rejected one publishes nothing, so the required context stays
# absent and blocks the merge. The check is commit-scoped: a PR from another
# branch at the very same SHA as staging delivers the identical commit, and a
# rejected PR can never overwrite staging's success at that SHA.
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
echo "::error::PRs into main must come from 'staging' (got '$HEAD_REF')."
echo ""
echo "main is promotion-only. Merge this into staging first, verify there,"
echo "then promote staging -> main."
echo ""
echo "There is no hotfix/* or revert-* bypass. Land the fix on staging,"
echo "then open staging -> main."
exit 1
