#!/usr/bin/env bash
# Provenance of a merge-with-main promote slice (plan 2026-11-21-mvs-trusted-slice-replay, step 3).
#
#   HEAD_SHA=<event head sha> BASE_SHA=<event base sha> HEAD_REF=<head branch> [GIT_REMOTE=<url>] \
#     [SLICE_FETCH_TOKEN=<contents:read token>] [SLICE_SCRATCH=<new dir>] bash scripts/check-slice-provenance.sh
#
# SLICE_FETCH_TOKEN authenticates an https fetch (a private repo: the scratch repo reads no config and the checkout
# keeps no credentials). It is sent as an http.extraHeader from env config, never on argv, and never printed.
# SLICE_SCRATCH keeps the scratch repo at that path, which must not exist yet (nothing can be pre-seeded into it),
# for replay-promote-slice.py; the caller removes it.
#
# Exit 0 means only "these parents may feed the trusted replay". It is NOT a pass for the slice: the replay
# (replay-promote-slice.py) decides that, and check-main-source.sh admits a slice only on the replay's exit 0.
# Exit 1 is a rejection, including every input, fetch or object error (fail closed).
#
# Inputs are the event's immutable SHAs, fetched as git objects only, into a fresh scratch repo, from GIT_REMOTE
# (default $GITHUB_SERVER_URL/$GITHUB_REPOSITORY): the checkout is never read or written, nothing the head carries
# is run, and no system, global, checkout or env git config applies. The head ref name is read only to detect
# that it moved after the event; staging is resolved to one SHA, reported as part of the replay tuple.
#
# The slice head must be exactly the merge: two parents, the first on staging's first-parent history, the
# second EQUAL to BASE_SHA (an older main is stale: rebuild the slice, never re-evaluate it into a pass).
set -euo pipefail
: "${HEAD_SHA:?HEAD_SHA is required (github.event.pull_request.head.sha)}"
: "${BASE_SHA:?BASE_SHA is required (github.event.pull_request.base.sha)}"
: "${HEAD_REF:?HEAD_REF is required}"
reject() { echo "::error::slice provenance: $*" >&2; exit 1; }

# No git env but ours, before the first git call (git init included): system, global, checkout-local and
# env-injected config (GIT_CONFIG_PARAMETERS, GIT_CONFIG_COUNT/KEY_n/VALUE_n) could redirect the fetch
# (url.insteadOf) to a forged remote, and GIT_SSH_COMMAND, GIT_PROXY_COMMAND, GIT_ASKPASS, GIT_EXEC_PATH,
# GIT_TEMPLATE_DIR and the like could run or swap code, so every GIT_* variable except the GIT_REMOTE input goes.
# HTTP proxy and TLS variables (https_proxy, SSL_CERT_FILE, ...) stay: they are the runner's own environment, which
# the pull_request_target job and the base workflow control, never the PR head.
while IFS= read -r v; do
  case "$v" in GIT_REMOTE) ;; GIT_*) unset "$v" ;; esac
done < <(compgen -e)
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 GIT_ALLOW_PROTOCOL=https:file
# The remote is an input, never read from the checkout: GIT_REMOTE taken literally, else this run's repo on the
# runner's server (under pull_request_target that is the base repo, which holds staging and the same-repo slice).
if [ -n "${GIT_REMOTE:-}" ]; then
  url="$GIT_REMOTE"
elif [ -n "${GITHUB_SERVER_URL:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
  url="$GITHUB_SERVER_URL/$GITHUB_REPOSITORY"
else
  reject "GIT_REMOTE or GITHUB_SERVER_URL and GITHUB_REPOSITORY are required to know which remote to fetch from"
fi
# The walk runs in a fresh empty repo that holds only the fetched event objects, so nothing local to the checkout
# (replace refs, grafts, shallow file, commit-graph, alternates, config, hooks) can rewrite ancestry. The flags below
# are defense in depth inside that repo.
if [ -n "${SLICE_SCRATCH:-}" ]; then
  work="$SLICE_SCRATCH"
  mkdir "$work" || reject "SLICE_SCRATCH '$work' must be a new directory"
else
  work=$(mktemp -d) || reject "could not create a scratch repo"
  trap 'rm -rf "$work"' EXIT
fi
git init -q --bare --template= "$work/walk.git" || reject "could not create a scratch repo"
export GIT_DIR="$work/walk.git"
export GIT_NO_REPLACE_OBJECTS=1 GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false
if [ -n "${SLICE_FETCH_TOKEN:-}" ]; then
  [[ "$url" == https://* ]] || reject "SLICE_FETCH_TOKEN is only sent to an https remote"
  auth=$(printf 'x-access-token:%s' "$SLICE_FETCH_TOKEN" | base64 | tr -d '\n') || reject "could not encode the fetch token"
  export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_1=http.extraHeader GIT_CONFIG_VALUE_1="Authorization: Basic $auth"
  unset auth SLICE_FETCH_TOKEN
fi

for v in HEAD_SHA BASE_SHA; do
  [[ "${!v}" =~ ^[0-9a-f]{40}$ ]] || reject "$v must be a 40-hex commit SHA (got '${!v}')"
done

ls_tip() {
  local out sha
  out=$(git ls-remote "$url" "refs/heads/$1") || reject "could not list '$1' on $url"
  # ls-remote matches by suffix; keep only the exact ref.
  sha=$(awk -v r="refs/heads/$1" '$2 == r { print $1 }' <<<"$out")
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || reject "could not resolve '$1' on $url"
  printf '%s' "$sha"
}

staging_sha=$(ls_tip staging)
ref_sha=$(ls_tip "$HEAD_REF")
[ "$ref_sha" = "$HEAD_SHA" ] || reject "head ref '$HEAD_REF' moved after the event ($HEAD_SHA -> $ref_sha); a new event must evaluate it"

git fetch --quiet --no-tags --no-write-fetch-head "$url" "$HEAD_SHA" "$BASE_SHA" "$staging_sha" \
  || reject "fetch of the event objects from $url failed"
[ ! -e "$(git rev-parse --git-path info/grafts)" ] || reject "the scratch repo has info/grafts, which rewrites ancestry"
[ "$(git rev-parse --is-shallow-repository)" = "false" ] || reject "the scratch repo is shallow after the fetch"
for sha in "$HEAD_SHA" "$BASE_SHA" "$staging_sha"; do
  git cat-file -e "$sha^{commit}" 2>/dev/null || reject "commit $sha is missing after fetch"
done

line=$(git rev-list --parents -n 1 "$HEAD_SHA") || reject "cannot read parents of $HEAD_SHA"
read -r -a parents <<<"$line"
parents=("${parents[@]:1}")
if [ "${#parents[@]}" -eq 1 ] && [ "$(git rev-list --parents -n 1 "${parents[0]}" | wc -w)" -ge 3 ]; then
  reject "commit $HEAD_SHA is appended after the merge; the slice head must be the merge itself"
fi
[ "${#parents[@]}" -eq 2 ] || reject "slice head must have exactly two parents (has ${#parents[@]})"
first="${parents[0]}" second="${parents[1]}"

if [ "$second" != "$BASE_SHA" ]; then
  if git merge-base --is-ancestor "$second" "$BASE_SHA"; then
    reject "second parent $second is an older main than base $BASE_SHA: stale, rebuild the slice from its staging cut on the current main"
  fi
  reject "second parent $second is not the event base $BASE_SHA"
fi

fp=$(git rev-list --first-parent "$staging_sha") || reject "cannot walk staging's first-parent history"
grep -qx "$first" <<<"$fp" || reject "first parent $first is not on staging's first-parent history (staging $staging_sha)"

echo "slice provenance holds: head=$HEAD_SHA staging=$staging_sha base=$BASE_SHA (feeds the replay only; not a pass)"
