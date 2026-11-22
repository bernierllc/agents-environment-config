#!/usr/bin/env bash
# Provenance of a merge-with-main promote slice (plan 2026-11-21-mvs-trusted-slice-replay, step 3).
#
#   HEAD_SHA=<event head sha> BASE_SHA=<event base sha> HEAD_REF=<head branch> \
#     bash scripts/check-slice-provenance.sh
#
# Exit 0 means only "these parents may feed the trusted replay". It is NOT a pass for the slice: the replay
# (R2) and its hosted evidence (R3) decide that, and until they land check-main-source.sh rejects every slice
# whatever this returns. Exit 1 is a rejection, including every input, fetch or object error (fail closed).
#
# Inputs are the event's immutable SHAs, fetched from GIT_REMOTE (default origin) as git objects only: no
# checkout into the working tree, nothing the head carries is run. The head ref name is read only to detect
# that it moved after the event; staging is resolved to one SHA, reported as part of the replay tuple.
#
# The slice head must be exactly the merge: two parents, the first on staging's first-parent history, the
# second EQUAL to BASE_SHA (an older main is stale: rebuild the slice, never re-evaluate it into a pass).
set -euo pipefail
: "${HEAD_SHA:?HEAD_SHA is required (github.event.pull_request.head.sha)}"
: "${BASE_SHA:?BASE_SHA is required (github.event.pull_request.base.sha)}"
: "${HEAD_REF:?HEAD_REF is required}"
remote="${GIT_REMOTE:-origin}"
# Walk the immutable objects, never a locally rewritten graph: no replacement refs, no grafts.
export GIT_NO_REPLACE_OBJECTS=1

reject() { echo "::error::slice provenance: $*" >&2; exit 1; }

for v in HEAD_SHA BASE_SHA; do
  [[ "${!v}" =~ ^[0-9a-f]{40}$ ]] || reject "$v must be a 40-hex commit SHA (got '${!v}')"
done

ls_tip() {
  local out sha
  out=$(git ls-remote "$remote" "refs/heads/$1") || reject "could not list '$1' on $remote"
  # ls-remote matches by suffix; keep only the exact ref.
  sha=$(awk -v r="refs/heads/$1" '$2 == r { print $1 }' <<<"$out")
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || reject "could not resolve '$1' on $remote"
  printf '%s' "$sha"
}

staging_sha=$(ls_tip staging)
ref_sha=$(ls_tip "$HEAD_REF")
[ "$ref_sha" = "$HEAD_SHA" ] || reject "head ref '$HEAD_REF' moved after the event ($HEAD_SHA -> $ref_sha); a new event must evaluate it"

unshallow=()
[ "$(git rev-parse --is-shallow-repository)" = "true" ] && unshallow=(--unshallow)
git fetch --quiet --no-tags --no-write-fetch-head ${unshallow[@]+"${unshallow[@]}"} "$remote" \
  "$HEAD_SHA" "$BASE_SHA" "$staging_sha" || reject "fetch of the event objects from $remote failed"
[ ! -e "$(git rev-parse --git-path info/grafts)" ] || reject "this checkout has info/grafts, which rewrites ancestry"
[ "$(git rev-parse --is-shallow-repository)" = "false" ] || reject "this checkout is still shallow after the fetch"
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
