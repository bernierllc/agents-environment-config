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

# Another worktree, clone or submodule inside this one: `git worktree remove` deletes ignored
# content, which would take that nested checkout and its uncommitted work with it.
holds_nested_checkout() {
  # node_modules is searched too: a git dependency or linked checkout there can hold uncommitted work
  find "$1" -mindepth 2 -name .git -print -quit 2>/dev/null | grep -q .
}

env_data_reason() { # worktree primary -> returns 0 and prints why when the tree must be kept, 1 when it holds no .env data
  # Fails closed: anything that cannot be verified keeps the tree. A .env that is a byte-identical copy of the
  # primary checkout's, a symlink out of the worktree, a symlink to a tracked file or a dangling symlink holds no
  # data of its own; a symlink to an ignored file inside the worktree does (deleting the tree deletes the target).
  # No `grep -q` at the end of a pipeline: under pipefail its early exit SIGPIPEs the writer and reads as "none".
  local path="$1" repo="$2" ign rc wt f tgt
  ign="$(git -C "$path" ls-files -o -i --exclude-standard)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not list ignored files (git ls-files exit $rc)"; return 0; }
  wt="$(cd -P "$path" 2>/dev/null && pwd -P)" || { echo "could not resolve the worktree path"; return 0; }
  while IFS= read -r f; do
    case "/$f" in */.env*) ;; *) continue ;; esac
    if [ -L "$path/$f" ]; then
      [ -e "$path/$f" ] || continue
      tgt="$(realpath "$path/$f" 2>/dev/null || readlink -f "$path/$f" 2>/dev/null)"
      case "$tgt" in
        "") echo "holds ignored .env files"; return 0 ;;
        # exact tracked file only: --literal-pathspecs stops `only-copy[1]` globbing onto a tracked `only-copy1`,
        # and [ -f ] stops a directory target counting as tracked because one file under it is
        "$wt"/*) { [ -f "$tgt" ] && git --literal-pathspecs -C "$path" ls-files --error-unmatch -- "${tgt#"$wt"/}" >/dev/null 2>&1; } \
                   || { echo "holds ignored .env files"; return 0; } ;;
      esac
    else
      cmp -s "$path/$f" "$repo/$f" || { echo "holds ignored .env files"; return 0; }
    fi
  done <<<"$ign"
  return 1
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
    # a repo cloned or linked inside (git dependency, local checkout) can hold uncommitted work or its own .env
    if find "$nm" -name .git -print -quit 2>/dev/null | grep -q .; then echo "keep    $nm  ($2: holds a git checkout)"; continue; fi
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
            if why="$(env_data_reason "$path" "$repo")"; then
              echo "keep    $path  ($label: $why)"
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
