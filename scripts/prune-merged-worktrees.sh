#!/bin/bash
# Removes linked git worktrees whose branch has a merged PR and whose HEAD is exactly the commit
# GitHub merged, then deletes the local branch. Kept and reported: dirty worktrees, a HEAD past the
# merged commit (unpushed work), a branch name with a newer open PR, ignored .env* files in the tree.
# Scans $PROJECTS_ROOT (default ~/projects) one and two levels deep. DRY_RUN=1 only prints.
# Idempotent; schedule it daily with cron or launchd.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN:-0}"
command -v gh >/dev/null || { echo "gh not found in PATH=$PATH"; exit 1; }
echo "== $(date '+%F %T') prune-merged-worktrees (DRY_RUN=$DRY_RUN, ROOT=$ROOT)"

pr_heads() { # repo state -> "branch sha" lines; on failure prints why and returns 1
  local out
  out="$(cd "$1" && gh pr list --state "$2" --limit 1000 --json headRefName,headRefOid \
        -q '.[] | "\(.headRefName) \(.headRefOid)"' 2>&1)" \
    || { echo "skip $1: gh pr list --state $2 failed: $out"; return 1; }
  printf '%s\n' "$out"
}

for gitdir in "$ROOT"/*/.git "$ROOT"/*/*/.git; do
  [ -e "$gitdir" ] || continue
  repo="${gitdir%/.git}"
  # only the main checkout: a linked worktree has its own git-dir but shares the common dir
  [ "$(git -C "$repo" rev-parse --git-dir)" = "$(git -C "$repo" rev-parse --git-common-dir)" ] || continue
  [ "$(git -C "$repo" worktree list | wc -l)" -gt 1 ] || continue
  merged="$(pr_heads "$repo" merged)" || continue
  open="$(pr_heads "$repo" open)" || continue

  git -C "$repo" worktree list --porcelain \
    | awk '/^worktree /{w=substr($0,10)} /^branch /{b=substr($0,8); sub("^refs/heads/","",b); print w "\t" b}' \
    | while IFS=$'\t' read -r path branch; do
        [ "$path" = "$repo" ] && continue
        sha="$(awk -v b="$branch" '$1==b{print $2; exit}' <<<"$merged")"
        [ -n "$sha" ] || continue
        if awk -v b="$branch" '$1==b{f=1} END{exit !f}' <<<"$open"; then
          echo "keep    $path  ($branch: name reused by an open PR)"; continue
        fi
        if [ -n "$(git -C "$path" status --porcelain 2>/dev/null)" ]; then
          echo "keep    $path  ($branch: PR merged but worktree dirty)"; continue
        fi
        if [ "$(git -C "$path" rev-parse HEAD)" != "$sha" ]; then
          echo "keep    $path  ($branch: HEAD is not the merged commit, may hold unpushed commits)"; continue
        fi
        if git -C "$path" ls-files -o -i --exclude-standard | grep -q -E '(^|/)\.env'; then
          echo "keep    $path  ($branch: holds ignored .env files)"; continue
        fi
        kb="$(du -sk "$path" 2>/dev/null | cut -f1)"; mb=$(( ${kb:-0} / 1024 ))
        if [ "$DRY_RUN" = 1 ]; then echo "would   $path  ($branch, ${mb}M)"; continue; fi
        if git -C "$repo" worktree remove "$path"; then
          git -C "$repo" branch -D "$branch" >/dev/null 2>&1 || true
          echo "removed $path  ($branch, ${mb}M)"
        else
          echo "FAILED  $path  ($branch)"
        fi
      done
  git -C "$repo" worktree prune
done
df -h "$HOME" | tail -1
