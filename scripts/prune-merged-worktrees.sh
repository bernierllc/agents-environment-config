#!/bin/bash
# Removes git worktrees under ~/projects/**/.worktrees whose branch's PR has merged
# (and nothing new is open on it), deletes the local branch, then prunes the pnpm store.
# Dirty worktrees are kept and reported. DRY_RUN=1 only prints.
# Runs daily via launchd/com.mattbernier.prune-merged-worktrees.plist; safe to re-run.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN:-0}"
echo "== $(date '+%F %T') prune-merged-worktrees (DRY_RUN=$DRY_RUN)"

for wtdir in "$ROOT"/*/.worktrees "$ROOT"/*/*/.worktrees; do
  [ -d "$wtdir" ] || continue
  repo="$(dirname "$wtdir")"
  # "branch sha" per merged PR; sha is the commit GitHub merged, so a worktree HEAD past it holds unpushed work
  merged="$(cd "$repo" && gh pr list --state merged --limit 1000 --json headRefName,headRefOid -q '.[] | "\(.headRefName) \(.headRefOid)"' 2>/dev/null)" \
    || { echo "skip $repo: gh pr list failed"; continue; }
  open="$(cd "$repo" && gh pr list --state open --limit 1000 --json headRefName -q '.[].headRefName' 2>/dev/null)"
  [ -n "$merged" ] || continue

  git -C "$repo" worktree list --porcelain \
    | awk '/^worktree /{w=$2} /^branch /{b=$2; sub("refs/heads/","",b); print w" "b}' \
    | while read -r path branch; do
        case "$path" in "$wtdir"/*) ;; *) continue ;; esac
        sha="$(awk -v b="$branch" '$1==b{print $2; exit}' <<<"$merged")"
        [ -n "$sha" ] || continue
        grep -qxF "$branch" <<<"$open" && continue   # branch name reused by a newer open PR
        if [ -n "$(git -C "$path" status --porcelain 2>/dev/null)" ]; then
          echo "keep    $path  ($branch: PR merged but worktree dirty)"; continue
        fi
        if [ "$(git -C "$path" rev-parse HEAD)" != "$sha" ]; then
          echo "keep    $path  ($branch: HEAD is not the merged commit, may hold unpushed commits)"; continue
        fi
        mb=$(( $(du -sk "$path" | cut -f1) / 1024 ))
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

if command -v pnpm >/dev/null; then
  [ "$DRY_RUN" = 1 ] || pnpm store prune 2>&1 | tail -1
fi
df -h "$HOME" | tail -1
