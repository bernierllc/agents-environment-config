#!/bin/bash
# Removes linked git worktrees whose branch has a merged PR and whose HEAD is exactly the commit
# GitHub merged, then deletes the local branch. Kept and reported: dirty worktrees, a HEAD past the
# merged commit (unpushed work), a branch name with a newer open PR, ignored .env* files that differ from the primary checkout's.
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

resolve_physical() { # path -> prints it with every symlink followed; non-zero on any failure
  # Pure Bash 3.2: `realpath` is missing and `readlink -f` unsupported on older macOS, so neither is relied on.
  local p="$1" n=0 dir base t
  while :; do
    n=$((n + 1)); [ "$n" -le 40 ] || return 1 # symlink loop or absurd depth
    dir="${p%/*}"; base="${p##*/}"; [ -n "$dir" ] || dir=/
    case "$base" in
      ""|.|..) p="$(cd -P -- "$p" 2>/dev/null && pwd -P)" || return 1; break ;;
    esac
    dir="$(cd -P -- "$dir" 2>/dev/null && pwd -P)" || return 1
    p="${dir%/}/$base"
    [ -L "$p" ] || break
    t="$(readlink -- "$p")" && [ -n "$t" ] || return 1
    while [ "${#t}" -gt 1 ] && [ "${t%/}" != "$t" ]; do t="${t%/}"; done
    case "$t" in /*) p="$t" ;; *) p="$dir/$t" ;; esac
  done
  printf '%s\n' "$p"
}

env_data_scan() { # worktree primary listfile -> returns 0 and prints why when the tree must be kept, 1 when it holds no .env data
  # Fails closed: only a .env that is positively proven to hold no data of its own is skipped; anything else keeps
  # the tree. Proven safe: a regular file byte-identical to a regular (non-symlink) copy in the primary checkout;
  # a symlink that resolves outside the worktree; a symlink that resolves to a regular tracked file inside it.
  # Everything else (a symlink to an ignored file, a directory or the root of the worktree; a symlink that cannot
  # be resolved, dangling or unreadable included) is kept: deleting the worktree would delete the target.
  # The list is NUL-separated (git quotes odd names otherwise) and read from a file: no `grep -q` at the end of a
  # pipeline, whose early exit SIGPIPEs the writer under pipefail and reads as "none".
  local path="$1" repo="$2" list="$3" wt f tgt r rel tag
  git -C "$path" ls-files -z -o -i --exclude-standard >"$list"
  r=$?
  [ "$r" -eq 0 ] || { echo "could not list ignored files (git ls-files exit $r)"; return 0; }
  wt="$(cd -P "$path" 2>/dev/null && pwd -P)" || { echo "could not resolve the worktree path"; return 0; }
  while IFS= read -r -d '' f; do
    case "/$f" in */.env*) ;; *) continue ;; esac
    if [ -L "$path/$f" ]; then
      tgt="$(resolve_physical "$path/$f")" && [ -n "$tgt" ] && [ -e "$tgt" ] \
        || { echo "could not resolve a .env symlink target"; return 0; }
      case "$tgt" in
        "$wt"/*) # a tracked file is safe only while it matches the index: assume-unchanged and skip-worktree
                 # hide local edits from `git status` and `git diff`, so any flag keeps the tree
                 rel="${tgt#"$wt"/}"
                 [ -f "$tgt" ] && tag="$(git --literal-pathspecs -C "$path" ls-files -v -- "$rel")" \
                   && case "$tag" in "H "*) true ;; *) false ;; esac \
                   && git --literal-pathspecs -C "$path" diff --quiet -- "$rel" \
                   || { echo "holds ignored .env files"; return 0; } ;;
        "$wt") echo "holds ignored .env files"; return 0 ;;
      esac
    else
      { [ -f "$repo/$f" ] && [ ! -L "$repo/$f" ] && [ ! "$path/$f" -ef "$repo/$f" ] && cmp -s "$path/$f" "$repo/$f"; } \
        || { echo "holds ignored .env files"; return 0; }
    fi
  done <"$list"
  return 1
}

env_data_reason() { # worktree primary -> returns 0 and prints why when the tree must be kept, 1 when it holds no .env data
  local list rc
  list="$(mktemp)" || { echo "could not create a temp file to list ignored files"; return 0; }
  env_data_scan "$1" "$2" "$list"; rc=$?
  rm -f "$list"
  return "$rc"
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
