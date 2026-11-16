#!/bin/bash
# Removes linked git worktrees whose branch has a merged PR and whose HEAD is exactly the commit
# GitHub merged, then deletes the local branch. Kept and reported: dirty worktrees, a HEAD past the
# merged commit (unpushed work), a branch name with a newer open PR, ignored .env* files that differ from the primary checkout's.
# Scans $PROJECTS_ROOT (default ~/projects) one and two levels deep. DRY_RUN=1 only prints.
# Idempotent; schedule it daily with cron or launchd.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN:-0}"
NL=$'\n'
command -v gh >/dev/null || { echo "gh not found in PATH=$PATH"; exit 1; }
echo "== $(date '+%F %T') prune-merged-worktrees (DRY_RUN=$DRY_RUN, ROOT=$ROOT)"

pr_heads() { # repo state -> "branch sha" lines; on failure prints why and returns 1
  local out
  out="$(cd "$1" && gh pr list --state "$2" --limit 1000 --json headRefName,headRefOid \
        -q '.[] | "\(.headRefName) \(.headRefOid)"' 2>&1)" \
    || { echo "skip $1: gh pr list --state $2 failed: $out"; return 1; }
  printf '%s\n' "$out"
}

primary_repo() { # <repo>/.git -> 0 when it is a main checkout that has linked worktrees
  local r="${1%/.git}"
  [ -e "$1" ] || return 1
  # only the main checkout: a linked worktree has its own git-dir but shares the common dir
  [ "$(git -C "$r" rev-parse --git-dir)" = "$(git -C "$r" rev-parse --git-common-dir)" ] || return 1
  [ "$(git -C "$r" worktree list | wc -l)" -gt 1 ]
}

resolve_physical() { # path -> sets RESOLVED to it with every symlink followed; non-zero on any failure
  # Pure Bash 3.2: `realpath` is missing and `readlink -f` unsupported on older macOS, so neither is relied on.
  # The result travels in a global and every substitution that carries a path ends in a sentinel `x`: `$(...)`
  # strips trailing newlines, which would turn a link to "config\n" into a link to the tracked `config`.
  local p="$1" n=0 dir base t v
  while :; do
    n=$((n + 1)); [ "$n" -le 40 ] || return 1 # symlink loop or absurd depth
    dir="${p%/*}"; base="${p##*/}"; [ -n "$dir" ] || dir=/
    case "$base" in
      ""|.|..) v="$(cd -P -- "$p" 2>/dev/null && pwd -P && printf x)" || return 1
               p="${v%x}"; RESOLVED="${p%"$NL"}"; return 0 ;;
    esac
    v="$(cd -P -- "$dir" 2>/dev/null && pwd -P && printf x)" || return 1
    dir="${v%x}"; dir="${dir%"$NL"}"
    p="${dir%/}/$base"
    [ -L "$p" ] || break
    v="$(readlink -n -- "$p" && printf x)" || return 1 # -n: the output is exactly the link's bytes, newline or not
    t="${v%x}"; [ -n "$t" ] || return 1
    while [ "${#t}" -gt 1 ] && [ "${t%/}" != "$t" ]; do t="${t%/}"; done
    case "$t" in /*) p="$t" ;; *) p="$dir/$t" ;; esac
  done
  RESOLVED="$p"
}

resolve_proven() { # path -> resolve_physical, and a result containing a newline counts as not resolved (not proven)
  resolve_physical "$1" || return 1
  case "$RESOLVED" in *"$NL"*) return 1 ;; esac
}

survives_removal() { # physical-path repo -> 0 only when the path is proven to outlive this sweep
  # Containment is decided by filesystem identity (-ef), never by comparing path text: a case alias on APFS, a
  # firmlink or a symlinked ancestor names the same directory with different text. Not proven (returns 1): inside
  # any linked worktree of any repo the sweep walks (WORKTREES, built in pass 1: the sweep may remove any of
  # them), or under $ROOT but outside this repo's primary checkout. Anywhere else survives, e.g. a shared env
  # file outside every worktree.
  local anc="$1" repo="$2" w in_root=0 in_repo=0
  while :; do
    while IFS= read -r -d '' w; do
      [ "$anc" -ef "$w" ] && return 1
    done <"$WORKTREES"
    [ "$anc" -ef "$repo" ] && in_repo=1
    [ "$anc" -ef "$ROOT" ] && in_root=1
    [ "$anc" = / ] && break
    anc="${anc%/*}"; [ -n "$anc" ] || anc=/
  done
  [ "$in_root" -eq 0 ] || [ "$in_repo" -eq 1 ]
}

sweep_inventory() { # pass 1: fills WORKTREES (every linked worktree of every repo under $ROOT) and PROTECT
  # Data is shared across worktrees and repos, so the decision to keep one worktree cannot be made from its own
  # contents alone. PROTECT lists every worktree that an .env symlink in a different worktree points into.
  # Anything pass 1 cannot read sets SWEEP_ERR, which keeps every worktree: nothing is proven unreferenced.
  local gitdir repo wts w rel anc p
  for gitdir in "$ROOT"/*/.git "$ROOT"/*/*/.git; do
    primary_repo "$gitdir" || continue
    repo="${gitdir%/.git}"
    wts="$(git -C "$repo" worktree list --porcelain 2>&1)" || { SWEEP_ERR="could not list the worktrees of $repo"; return; }
    while IFS= read -r w; do
      [ -n "$w" ] || continue
      resolve_physical "$w" && [ -d "$RESOLVED" ] || continue # a registered worktree whose directory is gone holds nothing
      printf '%s\0' "$RESOLVED" >>"$WORKTREES"
    done <<<"$(awk '/^worktree /{n++; if (n > 1) print substr($0, 10)}' <<<"$wts")" # the first entry is the primary checkout
  done
  while IFS= read -r -d '' w; do
    (cd "$w" && find . -type l -ipath '*/.env*' -print0) >"$LINKS" \
      || { SWEEP_ERR="could not scan $w for .env symlinks, so no worktree is proven unreferenced"; return; }
    while IFS= read -r -d '' rel; do
      resolve_physical "$w/$rel" && [ -e "$RESOLVED" ] || continue # dangling or looping: it reaches no data
      anc="$RESOLVED"
      while :; do
        while IFS= read -r -d '' p; do
          if [ "$anc" -ef "$p" ] && [ ! "$p" -ef "$w" ]; then printf '%s\0' "$p" >>"$PROTECT"; fi
        done <"$WORKTREES"
        [ "$anc" = / ] && break
        anc="${anc%/*}"; [ -n "$anc" ] || anc=/
      done
    done <"$LINKS"
  done <"$WORKTREES"
}

env_data_scan() { # worktree primary listfile -> returns 0 and prints why when the tree must be kept, 1 when it holds no .env data
  # Fails closed: only a .env that is positively proven to hold no data of its own is skipped; anything else keeps
  # the tree. Proven safe: a regular file byte-identical to a regular (non-symlink) copy in the primary checkout
  # that survives the sweep; a symlink whose target survives the sweep; a symlink to a regular tracked file inside
  # the worktree. Everything else (a symlink to an ignored file, a directory or the root of the worktree; a symlink
  # that cannot be resolved, dangling, unreadable or containing a newline included; a copy or target inside any
  # worktree the sweep may remove) is kept: deleting the worktree would delete the data.
  # The list is NUL-separated (git quotes odd names otherwise) and read from a file: no `grep -q` at the end of a
  # pipeline, whose early exit SIGPIPEs the writer under pipefail and reads as "none".
  local path="$1" repo="$2" list="$3" wt f tgt r rel tag pc n
  git -C "$path" ls-files -z -o -i --exclude-standard >"$list"
  r=$?
  [ "$r" -eq 0 ] || { echo "could not list ignored files (git ls-files exit $r)"; return 0; }
  resolve_proven "$path" || { echo "could not resolve the worktree path"; return 0; }
  wt="$RESOLVED"
  while IFS= read -r -d '' f; do
    # any component of the listed path may carry the name (APFS is case-insensitive), so the name test comes first
    case "/$f" in
      */.[eE][nN][vV]*) case "$f" in */) echo "holds ignored .env files"; return 0 ;; esac ;;
      */) # git lists an ignored nested repo or worktree as one entry and never enumerates its files; any .env* inside
          # (or an error reading it, which find prints and so counts) keeps the tree
          n="$(find "$path/$f" -iname '.env*' 2>&1 | head -n 1)"
          [ -z "$n" ] || { echo "holds ignored .env files"; return 0; }
          continue ;;
      *) continue ;;
    esac
    if [ -L "$path/$f" ]; then
      resolve_proven "$path/$f" && tgt="$RESOLVED" && [ -e "$tgt" ] \
        || { echo "could not resolve a .env symlink target"; return 0; }
      case "$tgt" in
        "$wt"/*) # a tracked file is safe only while it matches the index: assume-unchanged and skip-worktree
                 # hide local edits from `git status` and `git diff`, so any flag keeps the tree
                 rel="${tgt#"$wt"/}"
                 [ -f "$tgt" ] && tag="$(git --literal-pathspecs -C "$path" ls-files -v -- "$rel")" \
                   && case "$tag" in "H "*) true ;; *) false ;; esac \
                   && git --literal-pathspecs -C "$path" diff --quiet -- "$rel" \
                   || { echo "holds ignored .env files"; return 0; } ;;
        *) survives_removal "$tgt" "$repo" || { echo "holds ignored .env files"; return 0; } ;;
      esac
    else
      # the primary copy is resolved first so a symlinked parent cannot point it back into a worktree
      { resolve_proven "$repo/$f" && pc="$RESOLVED" && [ -f "$pc" ] && [ ! -L "$repo/$f" ] && [ ! "$path/$f" -ef "$pc" ] \
          && survives_removal "$pc" "$repo" && cmp -s "$path/$f" "$pc"; } \
        || { echo "holds ignored .env files"; return 0; }
    fi
  done <"$list"
  return 1
}

env_data_reason() { # worktree primary -> returns 0 and prints why when the tree must be kept, 1 when it holds no .env data
  local list rc p
  [ -z "$SWEEP_ERR" ] || { echo "$SWEEP_ERR"; return 0; }
  # a missing list reads as "nothing protected" through a failed redirect, so it is checked; an empty one is fine
  [ -r "$WORKTREES" ] && [ -r "$PROTECT" ] || { echo "could not read the sweep's worktree lists"; return 0; }
  while IFS= read -r -d '' p; do
    [ "$1" -ef "$p" ] && { echo "holds data an .env symlink in another worktree points at"; return 0; }
  done <"$PROTECT"
  list="$(mktemp)" || { echo "could not create a temp file to list ignored files"; return 0; }
  env_data_scan "$1" "$2" "$list"; rc=$?
  rm -f "$list"
  return "$rc"
}

WORKTREES="$(mktemp)" && PROTECT="$(mktemp)" && LINKS="$(mktemp)" || { echo "could not create temp files"; exit 1; }
trap 'rm -f "$WORKTREES" "$PROTECT" "$LINKS"' EXIT
SWEEP_ERR=""
sweep_inventory

for gitdir in "$ROOT"/*/.git "$ROOT"/*/*/.git; do
  primary_repo "$gitdir" || continue
  repo="${gitdir%/.git}"
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
        if why="$(env_data_reason "$path" "$repo")"; then
          echo "keep    $path  ($branch: $why)"; continue
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
