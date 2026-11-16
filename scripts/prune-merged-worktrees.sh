#!/bin/bash
# Removes linked git worktrees whose branch has a merged PR and whose HEAD is exactly the commit
# GitHub merged, then deletes the local branch. Kept and reported: dirty worktrees, a HEAD past the
# merged commit (unpushed work), a branch name with a newer open PR, and any worktree holding an ignored
# or untracked .env* file or any .env* symlink, unless that file is a regular file byte-identical to the
# primary checkout's copy. Anything that cannot be scanned is kept too.
# Scans $PROJECTS_ROOT (default ~/projects) one and two levels deep. DRY_RUN=1 only prints.
# Idempotent; schedule it daily with cron or launchd.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN:-0}"
NL=$'\n'
TAB=$'\t'
command -v gh >/dev/null || { echo "gh not found in PATH=$PATH"; exit 1; }
echo "== $(date '+%F %T') prune-merged-worktrees (DRY_RUN=$DRY_RUN, ROOT=$ROOT)"

pr_heads() { # repo state -> "branch sha" lines; on failure prints why and returns 1
  local out
  out="$(cd "$1" && gh pr list --state "$2" --limit 1000 --json headRefName,headRefOid \
        -q '.[] | "\(.headRefName) \(.headRefOid)"' 2>&1)" \
    || { echo "skip $1: gh pr list --state $2 failed: $out" >&2; return 1; } # stderr: stdout is captured by the caller
  printf '%s\n' "$out"
}

same_as_primary() { # worktree primary relpath -> 0 only for a regular file byte-identical to a regular primary copy
  local d="$3"
  [ ! -L "$1/$3" ] && [ -f "$2/$3" ] && [ ! -L "$2/$3" ] || return 1
  # a symlinked parent could lead the "primary copy" back into a worktree that is about to be removed
  while [ "$d" != "${d%/*}" ]; do d="${d%/*}"; [ ! -L "$2/$d" ] || return 1; done
  cmp -s "$1/$3" "$2/$3"
}

env_data_scan() { # worktree primary listfile -> returns 0 and prints why when the tree must be kept, 1 when it may go
  # Blunt on purpose: no target analysis. Every status is captured, never read through a pipe (`grep -q` or
  # `head` would hide a failure or SIGPIPE the writer under pipefail), and every failure keeps the tree.
  local f out rc
  git -C "$1" ls-files -z -s -v >"$3"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read the index (git ls-files exit $rc)"; return 0; }
  while IFS= read -r -d '' f; do # "<tag> <mode> <sha> <stage>TAB<path>"
    # assume-unchanged and skip-worktree make `git status` call a modified file clean
    case "$f" in [hSs]" "*) echo "has files marked assume-unchanged or skip-worktree"; return 0 ;; esac
    case "$f" in ?" 120000 "*) case "/${f#*"$TAB"}" in */.[eE][nN][vV]*) echo "holds an .env symlink"; return 0 ;; esac ;; esac
  done <"$3"
  # untracked and ignored files; an ignored nested repo is one `dir/` entry. git warns and still exits 0 for a
  # directory it cannot read, so any stderr output counts as a failure too.
  out="$(git -C "$1" ls-files -z -o 2>&1 >"$3")"; rc=$?
  { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not list ignored files (git ls-files exit $rc)"; return 0; }
  while IFS= read -r -d '' f; do
    case "$f" in *"$NL"*) echo "has a file name with a newline"; return 0 ;; esac
    case "/$f" in # any path component may carry the name, in any case (APFS is case-insensitive)
      */.[eE][nN][vV]*) same_as_primary "$1" "$2" "$f" || { echo "holds ignored .env files"; return 0; } ;;
      */) out="$(find "$1/$f" -iname '.env*' 2>&1)"; rc=$?
          [ "$rc" -eq 0 ] || { echo "could not scan $f (find exit $rc)"; return 0; }
          [ -z "$out" ] || { echo "holds ignored .env files"; return 0; } ;;
    esac
  done <"$3"
  return 1
}

keep_reason() { # worktree primary merged-sha -> returns 0 and prints why when the tree must be kept, 1 when it may go
  local out list rc
  out="$(git -C "$1" status --porcelain -uall 2>&1)" || { echo "could not read git status"; return 0; } # -uall: ignores status.showUntrackedFiles
  [ -z "$out" ] || { echo "PR merged but worktree dirty"; return 0; }
  [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" = "$3" ] \
    || { echo "HEAD is not the merged commit, may hold unpushed commits"; return 0; }
  list="$(mktemp)" || { echo "could not create a temp file"; return 0; }
  env_data_scan "$1" "$2" "$list"; rc=$?
  rm -f "$list"
  return "$rc"
}

for gitdir in "$ROOT"/*/.git "$ROOT"/*/*/.git; do
  [ -e "$gitdir" ] || continue
  repo="${gitdir%/.git}"
  # only a main checkout prints `.git` here (a linked worktree prints its own git dir)
  gd="$(git -C "$repo" rev-parse --git-dir)" || { echo "skip $repo: git rev-parse failed"; continue; }
  [ "$gd" = .git ] || continue
  wl="$(git -C "$repo" worktree list --porcelain)" || { echo "skip $repo: could not list worktrees"; continue; }
  [ "$(grep -c '^worktree ' <<<"$wl")" -gt 1 ] || continue
  merged="$(pr_heads "$repo" merged)" || continue
  open="$(pr_heads "$repo" open)" || continue

  awk '/^worktree /{w=substr($0,10)} /^branch /{b=substr($0,8); sub("^refs/heads/","",b); print w "\t" b}' <<<"$wl" \
    | while IFS=$'\t' read -r path branch; do
        [ "$path" = "$repo" ] && continue
        sha="$(awk -v b="$branch" '$1==b{print $2; exit}' <<<"$merged")"
        [ -n "$sha" ] || continue
        if awk -v b="$branch" '$1==b{f=1} END{exit !f}' <<<"$open"; then
          echo "keep    $path  ($branch: name reused by an open PR)"; continue
        fi
        # du first, and nothing slow between the final scan and the removal. Nothing locks the worktree, so a
        # file created in that last instant is still lost (plans/2026-11-16-prune-env-guard-fail-open.md).
        kb="$(du -sk "$path" 2>/dev/null | cut -f1)"; mb=$(( ${kb:-0} / 1024 ))
        why="$(keep_reason "$path" "$repo" "$sha")"; rc=$?
        # exactly 1 means "may go"; a scan that was killed or failed some other way keeps the tree
        if [ "$rc" -ne 1 ]; then echo "keep    $path  ($branch: ${why:-scan failed, exit $rc})"; continue; fi
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
