#!/bin/bash
# Reclaims disk from linked git worktrees under $PROJECTS_ROOT (default ~/projects), one and two levels deep.
#
# Removes a worktree (and its local branch) when it is clean, holds no ignored .env* that differs
# from the primary checkout's, and either:
#   - merged: its branch has a merged PR and HEAD is exactly the commit GitHub merged, or
#   - pushed: HEAD is already on a remote branch, no open PR uses the branch name, no process has
#     its cwd inside it, and git has not touched it for PRUNE_IDLE_HOURS (default 24). This covers
#     review/detached worktrees, closed PRs and branches that never got a PR.
# Strips node_modules from any remaining worktree idle for STRIP_IDLE_DAYS (default 3) with no
# process inside it; the next install (or an APFS clone from the primary checkout) restores it.
#
# Below LOW_DISK_GB free (default 30) it switches to aggressive thresholds (2h / 1 day) and posts a
# notification on macOS. With LOW_DISK_CLEANUP=1 it also runs cleanup-hung-processes.sh from this
# directory (kills hung processes and prunes Docker, including anonymous volumes), so that is opt-in.
# Works on macOS and Linux. Needs gh to remove worktrees (without it, only node_modules is stripped)
# and lsof or /proc to see busy worktrees (without either, nothing is touched).
# Kept and reported: dirty worktrees, unpushed commits, open-PR branches, busy or recent worktrees.
# DRY_RUN=1 only prints. Idempotent; schedule it hourly with launchd or cron.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN:-0}"
PRUNE_IDLE_HOURS="${PRUNE_IDLE_HOURS:-24}"
STRIP_IDLE_DAYS="${STRIP_IDLE_DAYS:-3}"
LOW_DISK_GB="${LOW_DISK_GB:-30}"
LOW_DISK_CLEANUP="${LOW_DISK_CLEANUP:-0}"
# git status must not rewrite the index: its mtime is how idleness is measured
export GIT_OPTIONAL_LOCKS=0
HAVE_GH=1
command -v gh >/dev/null || { HAVE_GH=0; echo "gh not found in PATH=$PATH: no worktree is removed, idle node_modules are still stripped"; }

free_gb() { df -Pk "$HOME" | awk 'NR==2 {print int($4/1048576)}'; }
FREE_BEFORE="$(free_gb)"
LOW=0
if [ "$FREE_BEFORE" -lt "$LOW_DISK_GB" ]; then
  LOW=1; PRUNE_IDLE_HOURS=2; STRIP_IDLE_DAYS=1
fi
echo "== $(date '+%F %T') prune-merged-worktrees (DRY_RUN=$DRY_RUN, ROOT=$ROOT, free=${FREE_BEFORE}G, low_disk=$LOW, idle=${PRUNE_IDLE_HOURS}h, strip=${STRIP_IDLE_DAYS}d)"

pr_heads() { # repo state -> "branch sha" lines; on failure prints why and returns 1
  local out
  out="$(cd "$1" && gh pr list --state "$2" --limit 1000 --json headRefName,headRefOid \
        -q '.[] | "\(.headRefName) \(.headRefOid)"' 2>&1)" \
    || { echo "skip $1: gh pr list --state $2 failed: $out"; return 1; }
  printf '%s\n' "$out"
}

# Every process cwd, once per run: a worktree with a shell, agent or dev server inside is in use.
CAN_SEE_BUSY=1
if command -v lsof >/dev/null; then
  BUSY_CWDS="$(lsof -a -d cwd -u "$(id -u)" -Fn 2>/dev/null | sed -n 's/^n//p' | sort -u)"
elif [ -d /proc/self ]; then
  BUSY_CWDS="$(for c in /proc/[0-9]*/cwd; do readlink "$c"; done 2>/dev/null | sort -u)"
else
  BUSY_CWDS=""
fi
# this script's own process always has a cwd, so an empty list means collection failed
if [ -z "$BUSY_CWDS" ]; then
  CAN_SEE_BUSY=0; echo "could not list process cwds (lsof or /proc): cannot tell which worktrees are in use, leaving all of them alone"
fi
is_busy() { [ "$CAN_SEE_BUSY" = 1 ] || return 0; awk -v p="$1" '$0==p || index($0, p"/")==1 {f=1; exit} END{exit !f}' <<<"$BUSY_CWDS"; }

# Hours since git last touched the worktree (checkout, commit, add, status with a refresh).
idle_hours() {
  local gd newest=0 f m
  gd="$(git -C "$1" rev-parse --absolute-git-dir 2>/dev/null)" || { echo 0; return; }
  for f in "$gd/index" "$gd/HEAD" "$gd/logs/HEAD"; do
    [ -e "$f" ] || continue
    # GNU stat first: on Linux `stat -f` means filesystem status and would not fail
    m="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f")"
    [ "$m" -gt "$newest" ] && newest="$m"
  done
  echo $(( ($(date +%s) - newest) / 3600 ))
}

# An ignored .env that is a symlink to, or a byte-identical copy of, the primary checkout's holds no
# data of its own: only a .env that differs keeps the tree.
# Another worktree, clone or submodule inside this one: `git worktree remove` deletes ignored
# content, which would take that nested checkout and its uncommitted work with it.
holds_nested_checkout() {
  find "$1" -mindepth 2 -name node_modules -prune -o -name .git -print -quit 2>/dev/null | grep -q .
}

holds_own_env() {
  git -C "$1" ls-files -o -i --exclude-standard | grep -E '(^|/)\.env' \
    | while IFS= read -r f; do [ -L "$1/$f" ] || cmp -s "$1/$f" "$2/$f" || echo "$f"; done | grep -q .
}

remove_worktree() { # repo path branch reason
  local kb mb; kb="$(du -sk "$2" 2>/dev/null | cut -f1)"; mb=$(( ${kb:-0} / 1024 ))
  if [ "$DRY_RUN" = 1 ]; then echo "would   $2  ($3, $4, ${mb}M)"; return; fi
  if git -C "$1" worktree remove "$2"; then
    [ -n "$3" ] && git -C "$1" branch -D "$3" >/dev/null 2>&1
    echo "removed $2  ($3, $4, ${mb}M)"
  else
    echo "FAILED  $2  ($3)"
  fi
}

strip_node_modules() { # path label
  local nm kb
  while IFS= read -r nm; do
    # only an ignored directory with nothing tracked inside it is regenerable
    git -C "$1" check-ignore -q "$nm" 2>/dev/null || continue
    [ -z "$(git -C "$1" ls-files -- "$nm" 2>/dev/null | head -n1)" ] || continue
    kb="$(du -sk "$nm" 2>/dev/null | cut -f1)"
    if [ "$DRY_RUN" = 1 ]; then echo "would strip $nm  ($2, $(( ${kb:-0} / 1024 ))M)"; continue; fi
    rm -rf "$nm" && echo "stripped $nm  ($2, $(( ${kb:-0} / 1024 ))M)"
  done < <(find "$1" -maxdepth 3 -name node_modules -type d -prune 2>/dev/null)
}

for gitdir in "$ROOT"/*/.git "$ROOT"/*/*/.git; do
  [ -e "$gitdir" ] || continue
  repo="${gitdir%/.git}"
  git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || { echo "skip $repo: .git is not a valid repository"; continue; }
  # only the main checkout: a linked worktree has its own git-dir but shares the common dir
  [ "$(git -C "$repo" rev-parse --git-dir)" = "$(git -C "$repo" rev-parse --git-common-dir)" ] || continue
  [ "$(git -C "$repo" worktree list | wc -l)" -gt 1 ] || continue
  # without PR state nothing is removed from this repo, but idle node_modules are still stripped
  can_remove="$HAVE_GH"; merged=""; open=""
  if [ "$HAVE_GH" = 1 ]; then
    merged="$(pr_heads "$repo" merged)" || can_remove=0
    open="$(pr_heads "$repo" open)" || can_remove=0
  fi

  # one "path<TAB>branch" line per linked worktree (the first record, the main checkout, is skipped:
  # its path is the physical one and may not equal $repo when $ROOT is reached through a symlink); branch is empty when HEAD is detached
  git -C "$repo" worktree list --porcelain \
    | awk '/^worktree /{w=substr($0,10); b=""} /^branch /{b=substr($0,8); sub("^refs/heads/","",b)}
           /^$/{if (w!="" && n++) print w "\t" b; w=""} END{if (w!="" && n) print w "\t" b}' \
    | while IFS=$'\t' read -r path branch; do
        [ -d "$path" ] || continue
        label="${branch:-detached}"
        if is_busy "$path"; then echo "keep    $path  ($label: a process is running inside it)"; continue; fi
        idle="$(idle_hours "$path")"
        removed=0
        if [ "$can_remove" = 1 ] && [ -z "$(git -C "$path" status --porcelain 2>/dev/null)" ]; then
          head="$(git -C "$path" rev-parse HEAD)"
          sha=""; [ -n "$branch" ] && sha="$(awk -v b="$branch" '$1==b{print $2; exit}' <<<"$merged")"
          has_open=0; [ -n "$branch" ] && awk -v b="$branch" '$1==b{f=1} END{exit !f}' <<<"$open" && has_open=1
          reason=""
          if [ "$has_open" = 1 ]; then
            :
          elif [ -n "$sha" ] && [ "$head" = "$sha" ]; then
            reason="merged"
          elif [ "$idle" -ge "$PRUNE_IDLE_HOURS" ] && [ -n "$(git -C "$path" branch -r --contains "$head" 2>/dev/null)" ]; then
            reason="pushed, idle ${idle}h"
          fi
          if [ -n "$reason" ]; then
            if holds_own_env "$path" "$repo"; then
              echo "keep    $path  ($label: holds ignored .env files)"
            elif holds_nested_checkout "$path"; then
              echo "keep    $path  ($label: holds a nested worktree, clone or submodule)"
            else
              remove_worktree "$repo" "$path" "$branch" "$reason"; removed=1
            fi
          fi
        fi
        [ "$removed" = 1 ] && continue
        if [ "$idle" -ge $(( STRIP_IDLE_DAYS * 24 )) ]; then
          strip_node_modules "$path" "$label, idle ${idle}h"
        fi
      done
  git -C "$repo" worktree prune
done

rc=0
if [ "$LOW" = 1 ] && [ "$DRY_RUN" != 1 ]; then
  cleanup="$(dirname "$0")/cleanup-hung-processes.sh"
  if [ "$LOW_DISK_CLEANUP" = 1 ] && [ -x "$cleanup" ]; then echo "== low disk: running $cleanup"; "$cleanup" || { rc=$?; echo "cleanup failed (exit $rc)"; }; fi
  msg="Free space was ${FREE_BEFORE}G (< ${LOW_DISK_GB}G); now $(free_gb)G after pruning worktrees"
  command -v osascript >/dev/null && osascript -e "display notification \"$msg\" with title \"Low disk space\"" 2>/dev/null
  echo "$msg"
fi
df -h "$HOME" | tail -1
exit "$rc"
