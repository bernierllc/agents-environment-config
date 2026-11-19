#!/bin/bash
# Removes linked git worktrees whose branch has a merged PR and whose HEAD is exactly the commit GitHub merged,
# then deletes the local branch (only if it still points at that commit). Fails closed on DRY_RUN: only DRY_RUN=0
# (or unset) removes for real; any other value (1, true, yes, empty, ...) only prints. Scans $PROJECTS_ROOT
# (default ~/projects) one and two levels deep. Never runs `git worktree prune`: it cannot tell a moved or
# unmounted worktree from a deleted one. Kept and reported: dirty worktrees, a HEAD past the merged commit
# (unpushed work), commits in the HEAD reflog that no ref reaches, a branch name with a newer open PR, and any
# worktree holding an ignored or untracked path unless it is PROVEN regenerable: every such path must sit under a
# directory named exactly node_modules, .venv, venv, site-packages, __pycache__, dist, build, .next, .turbo,
# coverage, .pytest_cache, .mypy_cache or .ruff_cache (a symlink or another spelling does not count). Secret
# names (.env*, keys, certificates, credentials, ...) keep the worktree even there, and a .env* file is exempt
# only when it is byte-identical to the primary checkout's copy. Anything that cannot be scanned is kept too.
# Idempotent; schedule it daily with cron or launchd.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN-0}" # `-`, not `:-`: DRY_RUN= (set but empty) is not "0"
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

wgit() { # worktree git-args... -> git run in the worktree with a stale core.fsmonitor hook unable to call edits clean
  local w="$1"; shift
  git -C "$w" -c core.fsmonitor=false "$@"
}

same_as_primary() { # worktree primary relpath -> 0 only for a regular file byte-identical to a regular primary copy
  local d="$3"
  [ ! -L "$1/$3" ] && [ -f "$2/$3" ] && [ ! -L "$2/$3" ] || return 1
  # a symlinked parent could lead the "primary copy" back into a worktree that is about to be removed
  while [ "$d" != "${d%/*}" ]; do d="${d%/*}"; [ ! -L "$2/$d" ] || return 1; done
  cmp -s "$1/$3" "$2/$3"
}

regen_ok="" # the last validated regenerable directory prefix ("dir/"): ls-files sorts, so most paths hit it
under_regenerable_dir() { # worktree relpath -> 0 when a leading directory of relpath is a real regenerable one
  [ -z "$regen_ok" ] || case "$2" in "$regen_ok"*) return 0 ;; esac
  local rest="${2%/*}" acc="" comp
  [ "$rest" != "$2" ] || return 1 # no directory part
  rest="$rest/"
  while [ -n "$rest" ]; do
    comp="${rest%%/*}"; rest="${rest#*/}"; acc="$acc$comp/"
    case "$comp" in # whole components, case-sensitive: a spelling it cannot classify is kept
      node_modules|.venv|venv|site-packages|__pycache__|dist|build|.next|.turbo|coverage|.pytest_cache|.mypy_cache|.ruff_cache)
        if [ -d "$1/$acc" ] && [ ! -L "$1/${acc%/}" ]; then regen_ok="$acc"; return 0; fi ;;
    esac
  done
  return 1
}

env_data_scan() { # worktree primary listfile -> returns 0 and prints why when the tree must be kept, 1 when it may go
  # Blunt on purpose: no target analysis. Every status is captured, never read through a pipe (`grep -q` or
  # `head` would hide a failure or SIGPIPE the writer under pipefail), and every failure keeps the tree.
  local f out rc rel subs=""
  wgit "$1" ls-files -z -s -v >"$3"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read the index (git ls-files exit $rc)"; return 0; }
  while IFS= read -r -d '' f; do # "<tag> <mode> <sha> <stage>TAB<path>"
    # assume-unchanged and skip-worktree make `git status` call a modified file clean
    case "$f" in [hSs]" "*) echo "has files marked assume-unchanged or skip-worktree"; return 0 ;; esac
    case "$f" in ?" 160000 "*) # tracked submodules; the list is newline-joined, so a name with a newline cannot be split
      case "${f#*"$TAB"}" in *"$NL"*) echo "has a file name with a newline"; return 0 ;; esac
      subs="$subs$NL${f#*"$TAB"}" ;;
    esac
    case "$f" in ?" 120000 "*) case "/${f#*"$TAB"}" in */.[eE][nN][vV]*) echo "holds an .env symlink"; return 0 ;; esac ;; esac
  done <"$3"
  # An initialized submodule (it has its own .git) is left to git's refusal to remove it. Under a gitlink path that
  # is NOT initialized here, `git status`, `ls-files -o` and `git worktree remove` all see nothing, so anything
  # in that directory is unproven data.
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    # -e, not -L: a dangling `.git` symlink makes status clean and `worktree remove` succeed, so it is not "initialized"
    { [ -d "$1/$rel" ] && [ ! -e "$1/$rel/.git" ]; } || continue
    out="$(find "$1/$rel" -mindepth 1 -maxdepth 1 -print0 2>&1 >"$3")"; rc=$?
    { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not scan the submodule directory $rel (find exit $rc)"; return 0; }
    [ ! -s "$3" ] || { echo "holds files under an uninitialized submodule"; return 0; }
  done <<<"$subs"
  # untracked and ignored files; an ignored nested repo is one `dir/` entry. git warns and still exits 0 for a
  # directory it cannot read, so any stderr output counts as a failure too.
  out="$(wgit "$1" ls-files -z -o 2>&1 >"$3")"; rc=$?
  { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not list ignored files (git ls-files exit $rc)"; return 0; }
  while IFS= read -r -d '' f; do
    case "$f" in *"$NL"*) echo "has a file name with a newline"; return 0 ;; esac
    case "/$f" in # any path component may carry the name, in any case (APFS is case-insensitive)
      # the one exemption: a regular file byte-identical to the primary's copy
      */.[eE][nN][vV]*) same_as_primary "$1" "$2" "$f" || { echo "holds ignored .env files"; return 0; }; continue ;;
      */) out="$(find "$1/$f" -iname '.env*' 2>&1)"; rc=$? # a nested repo: the scan below keeps it
          [ "$rc" -eq 0 ] || { echo "could not scan $f (find exit $rc)"; return 0; }
          [ -z "$out" ] || { echo "holds ignored .env files"; return 0; }
          continue ;;
      # secret names keep the tree everywhere, node_modules and virtualenvs included
      */.[dD][eE][vV].[vV][aA][rR][sS]*|*/.[nN][pP][mM][rR][cC]|*/.[nN][eE][tT][rR][cC]|*/.[pP][yY][pP][iI][rR][cC]|*/.[gG][iI][tT]-[cC][rR][eE][dD][eE][nN][tT][iI][aA][lL][sS]) echo "holds secret-named files"; return 0 ;;
      */[cC][rR][eE][dD][eE][nN][tT][iI][aA][lL][sS]|*/[cC][rR][eE][dD][eE][nN][tT][iI][aA][lL][sS].*|*/[iI][dD]_*) echo "holds secret-named files"; return 0 ;;
      *.[eE][nN][vV]|*.[eE][nN][vV].*|*.[pP][eE][mM]|*.[kK][eE][yY]|*.[pP]12|*.[pP][fF][xX]|*.[pP]8) echo "holds secret-named files"; return 0 ;;
      *.[jJ][kK][sS]|*.[kK][eE][yY][sS][tT][oO][rR][eE]|*.[tT][fF][vV][aA][rR][sS]|*.[tT][fF][sS][tT][aA][tT][eE]) echo "holds secret-named files"; return 0 ;;
    esac
    # No name list is complete, so anything not proven regenerable is unproven data: keep unless it sits under a
    # regenerable directory (dependency trees, virtualenvs, build output)
    under_regenerable_dir "$1" "$f" || { echo "holds ignored files that are not known regenerable output ($f)"; return 0; }
  done <"$3"
  # Any nested .git, file or directory, in any case (APFS), is unproven pushed history. So is a bare repo, which has
  # no .git at all: a directory `objects` beside a file `HEAD` and a directory `refs`. git lists only a valid nested
  # repo (as `dir/`) and skips a broken one, so find every name. A tracked submodule's own .git is left to git's refusal.
  # `objects` may itself be a symlink to a shared object store, so it is not required to be a plain directory.
  out="$(find "$1" -mindepth 1 \( -iname .git -prune -print0 \) -o \( \( -type d -o -type l \) -iname objects -print0 \) 2>&1 >"$3")"; rc=$?
  { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not scan for nested git repos (find exit $rc)"; return 0; }
  while IFS= read -r -d '' f; do
    rel="${f#"$1"/}"
    case "${rel##*/}" in
      .git) [ "$rel" != .git ] || continue # the worktree's own
            case "$subs$NL" in *"$NL${rel%/.git}$NL"*) continue ;; esac ;;
      .[gG][iI][tT]) ;; # another spelling is never the worktree's own or a submodule's
      *) [ -f "${f%/*}/HEAD" ] && [ -d "${f%/*}/refs" ] || continue ;; # `objects` without a bare layout is just a folder
    esac
    echo "holds a nested git repo"; return 0
  done <"$3"
  return 1
}

reflog_orphans() { # worktree -> returns 0 and prints why when its HEAD reflog names a commit no ref reaches, 1 when none
  # The reflog is private to the worktree and goes with it on removal. A commit that was checked out here (before a
  # reset, an amend or a rebase) and that no branch, tag, remote ref or HEAD reaches would then be lost. The test:
  # every sha in logs/HEAD that is a commit in this repo must be excluded by `git rev-list <shas> --not --all`.
  # A sha that is not a commit here (all-zero, or pruned already) is dropped: there is nothing left to lose.
  local gd log ids lost rc
  gd="$(git -C "$1" rev-parse --absolute-git-dir)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not locate the git dir (git rev-parse exit $rc)"; return 0; }
  log="$gd/logs/HEAD"
  [ -e "$log" ] || [ -L "$log" ] || return 1 # no HEAD reflog: nothing to lose
  ids="$(awk '{print $1; print $2}' "$log" | sort -u \
        | wgit "$1" cat-file --batch-check='%(objecttype) %(objectname)' | awk '$1=="commit"{print $2}')"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read the HEAD reflog (exit $rc)"; return 0; }
  [ -n "$ids" ] || return 1
  lost="$(printf '%s\n' "$ids" | wgit "$1" rev-list --stdin --max-count=1 --not --all)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not check the HEAD reflog against the refs (git rev-list exit $rc)"; return 0; }
  [ -z "$lost" ] || { echo "HEAD reflog holds commits no ref reaches"; return 0; }
  return 1
}

keep_reason() { # worktree primary merged-sha -> returns 0 and prints why when the tree must be kept, 1 when it may go
  local out list rc
  out="$(wgit "$1" status --porcelain -uall 2>&1)" || { echo "could not read git status"; return 0; } # -uall: ignores status.showUntrackedFiles
  [ -z "$out" ] || { echo "PR merged but worktree dirty"; return 0; }
  [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" = "$3" ] \
    || { echo "HEAD is not the merged commit, may hold unpushed commits"; return 0; }
  # refs/worktree, refs/bisect and refs/rewritten belong to this worktree alone and go with it on removal
  out="$(wgit "$1" for-each-ref refs/worktree refs/bisect refs/rewritten 2>&1)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read per-worktree refs (git for-each-ref exit $rc)"; return 0; }
  [ -z "$out" ] || { echo "holds per-worktree refs"; return 0; }
  out="$(reflog_orphans "$1")"; rc=$?
  [ "$rc" -eq 1 ] || { echo "${out:-reflog check failed, exit $rc}"; return 0; } # exactly 1 means "nothing to lose"
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
  # porcelain prints a path with a newline verbatim, so a line that is no known key means the paths below cannot be
  # trusted: keep every worktree of this repo
  bad="$(awk '!/^(worktree |HEAD |branch |detached$|bare$|locked( |$)|prunable( |$)|$)/ {print; exit}' <<<"$wl")"; rc=$?
  [ "$rc" -eq 0 ] || { echo "keep    $repo  (could not check the worktree list, awk exit $rc)"; continue; }
  [ -z "$bad" ] || { echo "keep    $repo  (unrecognised line in the worktree list, a path with a newline? every worktree here is kept)"; continue; }
  [ "$(grep -c '^worktree ' <<<"$wl")" -gt 1 ] || continue
  merged="$(pr_heads "$repo" merged)" || continue
  open="$(pr_heads "$repo" open)" || continue

  awk '/^worktree /{w=substr($0,10)} /^branch /{b=substr($0,8); sub("^refs/heads/","",b); print w "\t" b}' <<<"$wl" \
    | while IFS=$'\t' read -r path branch; do
        [ "$path" -ef "$repo" ] && continue # same directory, even when $ROOT reaches it through a symlink
        sha="$(awk -v b="$branch" '$1==b{print $2; exit}' <<<"$merged")"
        [ -n "$sha" ] || continue
        if awk -v b="$branch" '$1==b{f=1} END{exit !f}' <<<"$open"; then
          echo "keep    $path  ($branch: name reused by an open PR)"; continue
        fi
        # du first, so the scan is the last step before the removal. Nothing locks the worktree: `git worktree
        # remove` makes its own status pass before it deletes (measured gap 1.19 s with 100k ignored files), and a
        # file created in that gap is lost (plans/2026-11-16-prune-env-guard-fail-open.md).
        kb="$(du -sk "$path" 2>/dev/null | cut -f1)"; mb=$(( ${kb:-0} / 1024 ))
        why="$(keep_reason "$path" "$repo" "$sha")"; rc=$?
        # exactly 1 means "may go"; a scan that was killed or failed some other way keeps the tree
        if [ "$rc" -ne 1 ]; then echo "keep    $path  ($branch: ${why:-scan failed, exit $rc})"; continue; fi
        if [ "$DRY_RUN" != 0 ]; then echo "would   $path  ($branch, ${mb}M)"; continue; fi
        if git -C "$repo" worktree remove "$path"; then
          echo "removed $path  ($branch, ${mb}M)"
          # Delete the branch only while it still points at the commit that was checked: `branch -D` would drop a
          # branch somebody moved after the scan. update-ref -d keeps a moved branch; it also leaves the
          # branch.<name>.* config section behind, which `branch -D` would have removed.
          if git -C "$repo" update-ref -d "refs/heads/$branch" "$sha"; then
            cfg="$(git -C "$repo" config --remove-section "branch.$branch" 2>&1)"; rc=$?
            # a branch with no upstream has no section: git says so with exit 128 and this message
            { [ "$rc" -eq 0 ] || case "$cfg" in *"no such section"*) true ;; *) false ;; esac; } \
              || echo "note    $repo: could not remove the branch.$branch config section: $cfg"
          else
            cur="$(git -C "$repo" rev-parse --verify --quiet "refs/heads/$branch")"
            if [ "$cur" = "$sha" ]; then echo "kept    branch $branch of $repo  (git update-ref -d failed)"
            else echo "kept    branch $branch of $repo  (not deleted: it is now ${cur:-absent}, not the checked $sha)"; fi
          fi
        else
          echo "FAILED  $path  ($branch)"
        fi
      done
  # no `git worktree prune` here: `worktree remove` cleans its own admin dir, and a missing directory is also a
  # moved folder or an unmounted volume whose detached HEAD may hold the only copy of unpushed commits. git's own
  # gc prunes stale entries after gc.worktreePruneExpire (3 months).
done
df -h "$HOME" | tail -1
