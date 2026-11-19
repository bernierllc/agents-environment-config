#!/bin/bash
# Quarantines, then removes, linked git worktrees whose branch has a merged PR and whose HEAD is exactly the commit
# GitHub merged. A run never deletes a worktree it has just found: it moves it (git worktree move, one rename) to
# $PROJECTS_ROOT/.prune-quarantine/<UTC time>/ (YYYY-MM-DDTHHMMSSZ), rescans the moved tree and moves it back on any hit. A later run purges an
# entry quarantined at least PRUNE_QUARANTINE_DAYS ago (default 7, minimum 1; compared as an instant, so the hold is a true minimum): full guard again, rename aside, no process holding it,
# rescan, git worktree remove, and only when PRUNE_ALLOW_DELETE=1 (deletion is off by default: see holder_scan), then the branch is deleted only if it still points at the checked commit. Fails closed on DRY_RUN: only
# DRY_RUN=0 (or unset) acts for real. Scans $PROJECTS_ROOT (default ~/projects) one and two levels deep. Never runs
# `git worktree prune`. Kept and reported: dirty worktrees, a HEAD past the merged commit, commits in the HEAD, branch
# or ORIG_HEAD reflogs that no ref reaches, anything in the worktree's git directory that git does not create for a
# clean worktree (config.worktree, MERGE_AUTOSTASH, ...), a branch name with a newer open PR, and any ignored or
# untracked path not PROVEN regenerable: a marker proves the tool that wrote it, never every file beneath it. Only two
# things are proven, file by file: under a pyvenv.cfg the venv scaffold and each file an installed package's RECORD lists
# whose sha256 AND size still match the file on disk; a __pycache__ .pyc beside its proven .py. Everything else keeps the
# worktree: an npm lockfile lists packages, not file hashes, and a CACHEDIR.TAG names a tool, not the files a person put
# beside it, so node_modules, caches, yarn and pnpm trees all keep. The index must equal HEAD (staged work keeps). A
# process that has its cwd or a file open inside a tree keeps it, before the first move and again before a removal
# (lsof). Secret names (.env*, keys, credentials, ...) keep the worktree everywhere. Anything that cannot be read or
# scanned keeps the worktree, is logged, and makes the run exit 1.
# A worktree whose real path is not strictly under $PROJECTS_ROOT is reported and never touched. The branch is deleted only
# when it is not main, master, staging, develop or a remote's HEAD branch, and no other worktree has it checked out.
# Worktrees are read with `git worktree list --porcelain -z`, so no path can forge another record. An open-PR list that reaches the limit
# (1000) skips the repo with exit 1: a PR reusing a branch name could be missing from it.
# Idempotent; schedule it daily with cron or another scheduler.
set -uo pipefail
ROOT="${PROJECTS_ROOT:-$HOME/projects}"
DRY_RUN="${DRY_RUN-0}" # `-`, not `:-`: DRY_RUN= (set but empty) is not "0"
DAYS="${PRUNE_QUARANTINE_DAYS-7}"
# Unattended deletion is OFF unless PRUNE_ALLOW_DELETE=1 (exactly). A rename cannot stop a process that already holds
# the tree, and no check closes the last gap (see holder_scan), so by default a purge pass stops at the quarantine.
# Setting it, and re-enabling the scheduled job, is the operator's decision, never an agent's or a CI job's.
ALLOW_DELETE="${PRUNE_ALLOW_DELETE-0}"
QBASE="$ROOT/.prune-quarantine"
RROOT="$(cd "$ROOT" 2>/dev/null && pwd -P)" || RROOT="" # the resolved root: symlinks and .. gone
NL=$'\n'
TAB=$'\t'
command -v gh >/dev/null || { echo "gh not found in PATH=$PATH"; exit 1; }
case "$DAYS" in ''|*[!0-9]*|0|0[0-9]*) echo "PRUNE_QUARANTINE_DAYS must be a whole number of days, 1 or more (got '$DAYS')"; exit 1 ;; esac
case "$ROOT" in /*) ;; *) echo "PROJECTS_ROOT must be an absolute path (got '$ROOT')"; exit 1 ;; esac # a relative root changes meaning with the cwd
FAULTS="$(mktemp)" || { echo "could not create a temp file"; exit 1; } # a fault in a subshell cannot set a variable
trap 'rm -f "$FAULTS"' EXIT
note_fault() { echo x >>"$FAULTS" || echo "note    could not record a fault, the exit status may be wrong"; }
echo "== $(date '+%F %T') prune-merged-worktrees (DRY_RUN=$DRY_RUN, ROOT=$ROOT, quarantine ${DAYS}d)"

PR_LIMIT=1000 # gh pr list truncates silently at --limit
pr_heads() { # repo state -> "branch sha" lines; on failure prints why and returns 1
  local out n
  out="$(cd "$1" && gh pr list --state "$2" --limit "$PR_LIMIT" --json headRefName,headRefOid \
        -q '.[] | "\(.headRefName) \(.headRefOid)"' 2>&1)" \
    || { echo "skip $1: gh pr list --state $2 failed: $out" >&2; return 1; } # stderr: stdout is captured by the caller
  # A full page may be missing the open PR that reuses a branch name, so the repo cannot be verified. A full merged
  # page only hides candidates (a worktree absent from it is kept), so it is not a reason to skip.
  if [ "$2" = open ]; then
    n="$(printf '%s\n' "$out" | awk 'NF{n++} END{print n+0}')"
    [ "$n" -lt "$PR_LIMIT" ] || { echo "skip $1: open PR list reached the limit of $PR_LIMIT, a PR reusing a branch name may be missing" >&2; return 1; }
  fi
  printf '%s\n' "$out"
}

under_root() { # path -> 0 only when its resolved real path lies strictly below the resolved projects root
  local rp
  [ -n "$RROOT" ] || return 1
  rp="$(cd "$1" 2>/dev/null && pwd -P)" || return 1
  case "$rp" in "$RROOT"/?*) return 0 ;; *) return 1 ;; esac # a text prefix alone would accept /projects2 for /projects
}

wgit() { # worktree git-args... -> git run in the worktree with a stale core.fsmonitor hook unable to call edits clean
  local w="$1"; shift
  git -C "$w" -c core.fsmonitor=false "$@"
}

# Return codes of every check below: 0 = keep and say why (policy), 1 = nothing found, 2 = a read or a command failed
# (the tree is kept too, and the run exits 1). Only exactly 1 ever lets a tree go.

same_as_primary() { # worktree primary relpath -> 0 only for a regular file byte-identical to a regular primary copy
  local d="$3"
  [ ! -L "$1/$3" ] && [ -f "$2/$3" ] && [ ! -L "$2/$3" ] || return 1
  # a symlinked parent could lead the "primary copy" back into a worktree that is about to be removed
  while [ "$d" != "${d%/*}" ]; do d="${d%/*}"; [ ! -L "$2/$d" ] || return 1; done
  cmp -s "$1/$3" "$2/$3"
}

# A marker proves WHICH tool made a directory, never that every file beneath it is that tool's, so only a marker that
# comes with a per-file proof is used. pyvenv.cfg marks a venv, whose installed files carry a sha256 and a size in the
# RECORD of the package that installed them (checked against the disk by proof_venv). Two markers are NOT used, because
# neither can say which files are the tool's: node_modules/.package-lock.json lists packages, not file hashes (a
# database or a hand-patched file inside a listed package looks the same); a CACHEDIR.TAG proves the tool that wrote the
# tag, and any person can put one in any directory. A directory NAME proves nothing either, so dist, build, coverage,
# .next, .turbo, node_modules, caches, yarn and pnpm trees all keep the worktree. marker_of finds the outermost venv
# above a file; env_data_scan collects every file under it and unproven() keeps the tree for any file the RECORDs do not
# prove. Marker files and every directory on the way must be real, not symlinks.
m_root="" # the last venv directory prefix ("dir/"): ls-files sorts, so most paths hit it
marker_of() { # worktree relpath -> 0 when the path lies under a venv (sets m_root)
  [ -z "$m_root" ] || case "$2" in "$m_root"*) return 0 ;; esac
  m_root=""
  local rest="${2%/*}" acc="" comp
  [ "$rest" != "$2" ] || return 1 # no directory part
  rest="$rest/"
  while [ -n "$rest" ]; do
    comp="${rest%%/*}"; rest="${rest#*/}"; acc="$acc$comp/"
    [ ! -L "$1/${acc%/}" ] || return 1 # a marker below a non-directory cannot exist, so no -d test is needed
    if [ -f "$1/${acc}pyvenv.cfg" ] && [ ! -L "$1/${acc}pyvenv.cfg" ]; then m_root="$acc"; return 0; fi
  done
  return 1
}

pyc_has_source() { # worktree relpath -> 0 for <dir>/__pycache__/<module>.<tag>.pyc with <dir>/<module>.py beside it
  local d="${2%/*}" b="${2##*/}"
  [ "$d" != "$2" ] && [ "${d##*/}" = __pycache__ ] || return 1
  case "$b" in *.pyc|*.pyo) ;; *) return 1 ;; esac
  local src="${d%__pycache__}" # "" or "dir/"
  [ -f "$1/$src${b%%.*}.py" ]
}

# Runs under `python3 -I` for every RECORD file. RECORD lines are `path,sha256=<urlsafe base64, no padding>,size`, the path
# relative to site-packages (`../../../bin/tool` reaches bin/). A file is printed (relative to the worktree) only when it
# is a regular file, not a symlink, whose sha256 AND size both equal the RECORD's: a missing or other-algorithm hash, a
# missing size, a mismatch or an unreadable file proves nothing, so the file is never printed and the tree is kept. A
# path that leaves the worktree is skipped. The RECORD itself is listed with no hash by design (pip), so it is printed
# as read: a forged RECORD can only vouch for files whose content really matches what it claims.
read -r -d '' VENV_VERIFIER <<'PYEOF'
import base64, csv, hashlib, os, stat, sys
for rec in sys.argv[1:]:
    print(rec)
    site = os.path.dirname(os.path.dirname(rec))
    with open(rec, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if len(row) != 3 or row[0].startswith("/") or "\n" in row[0]:
                continue
            name, digest, size = row
            rel = os.path.normpath(os.path.join(site, name))
            if rel == ".." or rel.startswith("../") or not (digest.startswith("sha256=") and size.isascii() and size.isdigit()):
                continue
            b64 = digest[7:]
            try:
                want = base64.b64decode(b64.replace("-", "+").replace("_", "/") + "=" * (-len(b64) % 4), validate=True)
                fd = os.open(rel, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except (ValueError, OSError):
                continue
            with os.fdopen(fd, "rb") as f:
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_size != int(size):
                    continue
                h = hashlib.sha256()
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            if len(want) == 32 and h.digest() == want:
                print(rel)
PYEOF

proof_venv() { # worktree root outfile -> the files under root whose RECORD hash and size match the disk, one per line
  ( cd "$1" && find "${2%/}" -path '*/site-packages/*.dist-info/RECORD' -type f -exec python3 -I -c "$VENV_VERIFIER" {} + ) >"$3" 2>"$3.e"
}

unproven() { # worktree root claims proof -> prints the first claimed file the venv's RECORDs do not prove (none: all are)
  local rx='^(pyvenv\.cfg|\.gitignore|CACHEDIR\.TAG|lib64|bin/((python|𝜋thon)[0-9.]*t?|[Aa]ctivate([.]csh|[.]fish|[.]nu|[.]bat|[.]ps1)?|deactivate[.]bat|pydoc[.]bat))$'
  proof_venv "$1" "$2" "$4" || { echo "could not read the venv RECORD files under $2 ($(head -c 200 "$4.e" 2>/dev/null | tr '\n' ' '))"; return 2; }
  awk -v root="$2" -v rx="$rx" -v proof="$4" '
    BEGIN { while ((r = getline line < proof) > 0) p[line] = 1
            if (r < 0) { print "could not read " proof; exit 2 }
            close(proof) }
    { n++; c[n] = $0; all[$0] = 1 }
    END {
      for (i = 1; i <= n; i++) {
        f = c[i]
        if (f in p || substr(f, length(root) + 1) ~ rx) continue
        # <dir>/__pycache__/<module>.<tag>.pyc is rebuilt from <dir>/<module>.py, itself one of the claims (so proven itself)
        d = f; sub(/\/[^\/]*$/, "", d); b = f; sub(/^.*\//, "", b)
        if (d ~ /(^|\/)__pycache__$/ && b ~ /\.py[co]$/) {
          sd = d; sub(/__pycache__$/, "", sd); m = b; sub(/\..*$/, "", m)
          if ((sd m ".py") in all) continue
        }
        print f; exit 0
      }
    }' "$3"
}

gitlink_data() { # worktree list subs -> 0 + why when a gitlink directory not initialized here holds files, 1, 2
  # An initialized submodule (it has its own .git) is left to git's refusal to remove it. Under a gitlink path that
  # is NOT initialized here, `git status`, `ls-files -o` and `git worktree remove` all see nothing, so anything in
  # that directory is unproven data. The list is newline-joined; a name with a newline was rejected by the caller.
  local rel out rc IFS="$NL"
  set -f
  for rel in $3; do
    [ -n "$rel" ] || continue
    # -e, not -L: a dangling `.git` symlink makes status clean and `worktree remove` succeed, so it is not "initialized"
    { [ -d "$1/$rel" ] && [ ! -e "$1/$rel/.git" ]; } || continue
    out="$(find "$1/$rel" -mindepth 1 -maxdepth 1 -print0 2>&1 >"$2")"; rc=$?
    { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not scan the submodule directory $rel (find exit $rc)"; return 2; }
    [ -f "$2" ] || { echo "could not read back the scan of the submodule directory $rel"; return 2; }
    [ ! -s "$2" ] || { echo "holds files under an uninitialized submodule"; return 0; }
  done
  return 1
}

flush_claims() { # worktree root claimsfile prooffile -> 0 + why when a claimed file is not proven, 1 when all are, 2 on failure
  local bad rc
  [ -n "$2" ] || return 1
  bad="$(unproven "$1" "$2" "$3" "$4")"; rc=$?
  [ "$rc" -eq 0 ] || { echo "$bad"; return 2; }
  [ -z "$bad" ] || { echo "holds ignored files that are not proven regenerable ($bad)"; return 0; }
  return 1
}

env_data_scan() { # worktree primary listfile -> 0 + why when the tree must be kept, 1 when it may go, 2 on a failed read
  # Blunt on purpose: no target analysis. Every status is captured, never read through a pipe (`grep -q` or
  # `head` would hide a failure or SIGPIPE the writer under pipefail), and every failure keeps the tree. Every list is
  # written to $3 and then opened on fd 3 with the open's status checked: a `done <"$3"` that fails to open reads as an
  # empty list, which would be "nothing found".
  local f out rc rel subs="" cur_root="" claims="$3.c" proof="$3.p"
  wgit "$1" ls-files -z -s -v >"$3"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read the index (git ls-files exit $rc)"; return 2; }
  exec 3<"$3" || { echo "could not read back the index list"; return 2; }
  while IFS= read -r -d '' -u 3 f; do # "<tag> <mode> <sha> <stage>TAB<path>"
    # assume-unchanged and skip-worktree make `git status` call a modified file clean
    case "$f" in [hSs]" "*) echo "has files marked assume-unchanged or skip-worktree"; return 0 ;; esac
    case "$f" in ?" 160000 "*) # tracked submodules; the list is newline-joined, so a name with a newline cannot be split
      case "${f#*"$TAB"}" in *"$NL"*) echo "has a file name with a newline"; return 0 ;; esac
      subs="$subs$NL${f#*"$TAB"}" ;;
    esac
    case "$f" in ?" 120000 "*) case "/${f#*"$TAB"}" in */.[eE][nN][vV]*) echo "holds an .env symlink"; return 0 ;; esac ;; esac
  done
  exec 3<&-
  out="$(gitlink_data "$1" "$3" "$subs")"; rc=$?
  [ "$rc" -eq 1 ] || { echo "$out"; return "$rc"; }
  # Any nested .git, file or directory, in any case (APFS), is unproven pushed history. So is a bare repo, which has
  # no .git at all: a directory `objects` beside a file `HEAD` and a directory `refs`. git lists only a valid nested
  # repo (as `dir/`) and skips a broken one, so find every name. An initialized submodule's git dir sits under modules/, which admin_dir_scan keeps first.
  # `objects` may itself be a symlink to a shared object store, so it is not required to be a plain directory.
  out="$(find "$1" -mindepth 1 \( -iname .git -prune -print0 \) -o \( \( -type d -o -type l \) -iname objects -print0 \) 2>&1 >"$3")"; rc=$?
  { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not scan for nested git repos (find exit $rc)"; return 2; }
  exec 3<"$3" || { echo "could not read back the nested repo scan"; return 2; }
  while IFS= read -r -d '' -u 3 f; do
    rel="${f#"$1"/}"
    case "${rel##*/}" in
      .git) [ "$rel" != .git ] || continue ;; # the worktree's own; a submodule's is caught by the git dir scan
      .[gG][iI][tT]) ;; # another spelling is never the worktree's own
      *) [ -f "${f%/*}/HEAD" ] && [ -d "${f%/*}/refs" ] || continue ;; # `objects` without a bare layout is just a folder
    esac
    echo "holds a nested git repo"; return 0
  done
  exec 3<&-
  # untracked and ignored files; an ignored nested repo is one `dir/` entry. git warns and still exits 0 for a
  # directory it cannot read, so any stderr output counts as a failure too.
  out="$(wgit "$1" ls-files -z -o 2>&1 >"$3")"; rc=$?
  { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not list ignored files (git ls-files exit $rc)"; return 2; }
  exec 3<"$3" || { echo "could not read back the list of ignored files"; return 2; }
  : >"$claims" || { echo "could not create the claims list"; return 2; }
  while IFS= read -r -d '' -u 3 f; do
    case "$f" in *"$NL"*) echo "has a file name with a newline"; return 0 ;; esac
    case "/$f" in # any path component may carry the name, in any case (APFS is case-insensitive)
      # the one exemption: a regular file byte-identical to the primary's copy
      */.[eE][nN][vV]*) same_as_primary "$1" "$2" "$f" || { echo "holds ignored .env files"; return 0; }; continue ;;
      */) echo "holds a nested git repo"; return 0 ;; # git lists a valid nested repo as `dir/`; the scan above already keeps it
      # secret names keep the tree everywhere, node_modules and virtualenvs included
      */.[dD][eE][vV].[vV][aA][rR][sS]*|*/.[nN][pP][mM][rR][cC]|*/.[nN][eE][tT][rR][cC]|*/.[pP][yY][pP][iI][rR][cC]|*/.[gG][iI][tT]-[cC][rR][eE][dD][eE][nN][tT][iI][aA][lL][sS]) echo "holds secret-named files"; return 0 ;;
      */[cC][rR][eE][dD][eE][nN][tT][iI][aA][lL][sS]|*/[cC][rR][eE][dD][eE][nN][tT][iI][aA][lL][sS].*|*/[iI][dD]_*) echo "holds secret-named files"; return 0 ;;
      *.[eE][nN][vV]|*.[eE][nN][vV].*|*.[pP][eE][mM]|*.[kK][eE][yY]|*.[pP]12|*.[pP][fF][xX]|*.[pP]8) echo "holds secret-named files"; return 0 ;;
      *.[jJ][kK][sS]|*.[kK][eE][yY][sS][tT][oO][rR][eE]|*.[tT][fF][vV][aA][rR][sS]|*.[tT][fF][sS][tT][aA][tT][eE]) echo "holds secret-named files"; return 0 ;;
    esac
    # No name list is complete, so anything not proven regenerable is unproven data. A marker only says which tool owns
    # the directory: its files are collected per marked root and each is proven by that tool's own records below.
    if marker_of "$1" "$f"; then
      if [ "$m_root" != "$cur_root" ]; then # ls-files sorts, so a root's files are contiguous
        out="$(flush_claims "$1" "$cur_root" "$claims" "$proof")"; rc=$?
        [ "$rc" -eq 1 ] || { echo "$out"; return "$rc"; }
        cur_root="$m_root"; : >"$claims" || { echo "could not reset the claims list"; return 2; }
      fi
      printf '%s\n' "$f" >>"$claims" || { echo "could not record a marked file"; return 2; }
      continue
    fi
    pyc_has_source "$1" "$f" || { echo "holds ignored files that are not proven regenerable ($f)"; return 0; }
  done
  exec 3<&-
  out="$(flush_claims "$1" "$cur_root" "$claims" "$proof")"; rc=$?
  [ "$rc" -eq 1 ] || { echo "$out"; return "$rc"; }
  return 1
}

admin_dir_scan() { # worktree listfile -> 0 + why when the git admin dir holds a file git does not create for a clean worktree
  # `git worktree remove` deletes the whole admin dir: config.worktree (extensions.worktreeConfig), MERGE_AUTOSTASH,
  # MERGE_HEAD, rebase state and the like go with it, and a clean `git status` hides most of them. Directories alone
  # hold nothing; every other entry must be one of the files below.
  local gd f rel out rc
  gd="$(git -C "$1" rev-parse --absolute-git-dir)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not locate the git dir (git rev-parse exit $rc)"; return 2; }
  out="$(find "$gd" ! -type d -print0 2>&1 >"$2")"; rc=$?
  { [ "$rc" -eq 0 ] && [ -z "$out" ]; } || { echo "could not scan the git dir (find exit $rc)"; return 2; }
  exec 3<"$2" || { echo "could not read back the git dir scan"; return 2; }
  while IFS= read -r -d '' -u 3 f; do
    rel="${f#"$gd"/}"
    case "$rel" in
      HEAD|ORIG_HEAD|FETCH_HEAD|AUTO_MERGE|COMMIT_EDITMSG|commondir|gitdir|index|logs/HEAD) ;; # what git writes for a clean worktree
      *) echo "its git directory holds $rel, which git does not create for a clean worktree"; return 0 ;;
    esac
  done
  exec 3<&-
  return 1
}

reflog_orphans() { # worktree primary branch -> 0 + why when a commit named in a log no ref reaches, 1 when none, 2 on failure
  # The worktree's HEAD reflog and ORIG_HEAD go with it on removal, and deleting the branch deletes the BRANCH reflog
  # (<common dir>/logs/refs/heads/<branch>), which can hold a commit the HEAD reflog never saw. A commit named there
  # (before a reset, an amend or a rebase) that no branch, tag, remote ref or HEAD reaches would then be lost. The test:
  # every sha in those logs that is a commit in this repo must be excluded by `git rev-list <shas> --not --all`.
  # A sha that is not a commit here (all-zero, a tree, or pruned already) is dropped: there is nothing left to lose.
  local gd cd log ids lost rc
  gd="$(git -C "$1" rev-parse --absolute-git-dir)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not locate the git dir (git rev-parse exit $rc)"; return 2; }
  cd="$(git -C "$2" rev-parse --absolute-git-dir)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not locate the primary git dir (git rev-parse exit $rc)"; return 2; }
  [ ! -e "$cd/reftable" ] || { echo "a reftable repository: its reflogs cannot be read here"; return 0; }
  ids="$(
    {
    for log in "$gd/logs/HEAD" "$gd/ORIG_HEAD" "$cd/logs/refs/heads/$3"; do
      { [ -e "$log" ] || [ -L "$log" ]; } || continue # no log: nothing to lose
      awk '{print $1; print $2}' "$log" || exit 2
    done
    # FETCH_HEAD (one line per fetched ref: "<sha>TAB..."), kept by admin_dir_scan as harmless, is the only reference
    # to history fetched by URL or by a refspec that stores no ref; removal deletes it
    if [ -e "$gd/FETCH_HEAD" ] || [ -L "$gd/FETCH_HEAD" ]; then awk '{print $1}' "$gd/FETCH_HEAD" || exit 2; fi
    } | sort -u | wgit "$1" cat-file --batch-check='%(objecttype) %(objectname)' | awk '$1=="commit"{print $2}')"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read the reflogs (exit $rc)"; return 2; }
  [ -n "$ids" ] || return 1
  lost="$(printf '%s\n' "$ids" | wgit "$1" rev-list --stdin --max-count=1 --not --all)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not check the reflogs against the refs (git rev-list exit $rc)"; return 2; }
  [ -z "$lost" ] || { echo "a reflog holds commits no ref reaches (reflogs, ORIG_HEAD or FETCH_HEAD)"; return 0; }
  return 1
}

keep_reason() { # worktree primary merged-sha branch -> 0 + why when the tree must be kept, 1 when it may go, 2 on a failure
  # one scratch file per check: the scan's list, its .c/.p claim files and the throwaway index all hang off it
  local list out rc
  list="$(mktemp)" || { echo "could not create a temp file"; return 2; }
  out="$(keep_reason_scan "$1" "$2" "$3" "$4" "$list")"; rc=$?
  rm -f "$list" "$list.c" "$list.p" "$list.p.e" "$list.idx" "$list.idx.lock"
  [ "$rc" -eq 1 ] || echo "$out"
  return "$rc"
}

keep_reason_scan() { # worktree primary merged-sha branch list -> as keep_reason
  local out list="$5" rc
  # A stat cache is not evidence about content: core.trustctime=false + core.checkStat=minimal, or a restored mtime,
  # let git call a same-size edit clean. Status runs against a throwaway index built from HEAD, which carries no stat
  # data at all, so git has to read and compare every file's content (and still sees staged changes as differences).
  GIT_INDEX_FILE="$list.idx" wgit "$1" read-tree HEAD >/dev/null 2>&1; rc=$?
  if [ "$rc" -eq 0 ]; then
    out="$(GIT_INDEX_FILE="$list.idx" wgit "$1" status --porcelain -uall 2>&1)"; rc=$? # -uall: ignores status.showUntrackedFiles
  fi
  [ "$rc" -eq 0 ] || { echo "could not read git status"; return 2; }
  [ -z "$out" ] || { echo "PR merged but worktree dirty"; return 0; }
  # The throwaway index above replaces the real one, so it cannot see staged-only work: stage new content, restore the
  # file to HEAD's, and status against a fresh index is clean while the real index still holds the only copy. Git's own
  # index-versus-HEAD comparison (exit 1 = differences) covers it; it reads no file, so no stat cache is involved.
  wgit "$1" diff-index --cached --quiet HEAD -- >/dev/null 2>&1; rc=$?
  case "$rc" in
    0) ;;
    1) echo "the index holds staged changes"; return 0 ;;
    *) echo "could not compare the index with HEAD (git diff-index exit $rc)"; return 2 ;;
  esac
  [ "$(git -C "$1" rev-parse HEAD 2>/dev/null)" = "$3" ] \
    || { echo "HEAD is not the merged commit, may hold unpushed commits"; return 0; }
  # refs/worktree, refs/bisect and refs/rewritten belong to this worktree alone and go with it on removal
  out="$(wgit "$1" for-each-ref refs/worktree refs/bisect refs/rewritten 2>&1)"; rc=$?
  [ "$rc" -eq 0 ] || { echo "could not read per-worktree refs (git for-each-ref exit $rc)"; return 2; }
  [ -z "$out" ] || { echo "holds per-worktree refs"; return 0; }
  out="$(reflog_orphans "$1" "$2" "$4")"; rc=$?
  [ "$rc" -eq 1 ] || { echo "${out:-reflog check failed, exit $rc}"; [ "$rc" -eq 0 ] && return 0; return 2; }
  out="$(admin_dir_scan "$1" "$list")"; rc=$?
  if [ "$rc" -eq 1 ]; then out="$(env_data_scan "$1" "$2" "$list")"; rc=$?; fi
  [ "$rc" -eq 1 ] || echo "$out"
  return "$rc"
}

long_lived() { # repo branch -> 0 for a branch that is never deleted: main, master, staging, develop, a remote's HEAD
  local heads
  case "$2" in main|master|staging|develop) return 0 ;; esac
  heads="$(git -C "$1" for-each-ref --format='%(symref)' 'refs/remotes/*/HEAD')" || return 0 # unreadable: keep the branch
  printf '%s\n' "$heads" | sed 's|^refs/remotes/[^/]*/||' | grep -qxF -- "$2"
}

checked_out_at() { # repo branch -> 0 + prints a worktree path with refs/heads/<branch> checked out, 1 when none, 2 on failure
  # `git worktree list --porcelain -z` ends every field with a NUL, so no path can forge a `branch` field: a path is
  # always the text of a `worktree ` field and never equals one that starts with `branch `.
  local tmp f wt="" rc
  tmp="$(mktemp)" || return 2
  git -C "$1" worktree list --porcelain -z >"$tmp" 2>/dev/null; rc=$?
  if [ "$rc" -ne 0 ] || ! exec 5<"$tmp"; then rm -f "$tmp"; return 2; fi
  while IFS= read -r -d '' -u 5 f; do
    case "$f" in
      "worktree "*) wt="${f#worktree }" ;;
      "branch refs/heads/$2") exec 5<&-; rm -f "$tmp"; printf '%s\n' "$wt"; return 0 ;;
    esac
  done
  exec 5<&-; rm -f "$tmp"
  return 1
}

delete_branch() { # repo branch sha -> delete the branch only while it still points at the checked commit
  # `branch -D` would drop a branch somebody moved after the scan. update-ref -d keeps a moved branch; it also leaves
  # the branch.<name>.* config section behind, which `branch -D` would have removed. It also lacks `branch -D`'s refusal
  # to delete a branch another worktree has checked out (that worktree would be left on an unborn branch), so that
  # refusal is made here, after the removed worktree is gone from the list. A checkout made between this list and the
  # update-ref is a race this cannot close; update-ref has no such check to lean on.
  local repo="$1" branch="$2" sha="$3" cfg cur rc other
  # a worktree on staging whose HEAD equals a merged promotion PR head may go; the integration branch itself never does
  if long_lived "$repo" "$branch"; then echo "kept    branch $branch of $repo  (long-lived branch, never deleted)"; return; fi
  other="$(checked_out_at "$repo" "$branch")"; rc=$?
  case "$rc" in
    0) echo "kept    branch $branch of $repo  (checked out in another worktree: $other)"; return ;;
    1) ;;
    *) echo "kept    branch $branch of $repo  (could not list the worktrees to see whether it is checked out elsewhere)"; note_fault; return ;;
  esac
  if git -C "$repo" update-ref -d "refs/heads/$branch" "$sha"; then
    cfg="$(git -C "$repo" config --remove-section "branch.$branch" 2>&1)"; rc=$?
    # a branch with no upstream has no section: git says so with exit 128 and this message
    { [ "$rc" -eq 0 ] || case "$cfg" in *"no such section"*) true ;; *) false ;; esac; } \
      || echo "note    $repo: could not remove the branch.$branch config section: $cfg"
  else
    cur="$(git -C "$repo" rev-parse --verify --quiet "refs/heads/$branch")"
    if [ "$cur" = "$sha" ]; then echo "kept    branch $branch of $repo  (git update-ref -d failed)"; note_fault
    else echo "kept    branch $branch of $repo  (not deleted: it is now ${cur:-absent}, not the checked $sha)"; fi
  fi
}

move_wt() { # repo from to -> git worktree move; prints the failure with context
  local out
  out="$(git -C "$1" worktree move "$2" "$3" 2>&1)" || { echo "could not move $2 to $3: $out"; return 1; }
}

# A quarantine directory is named for the UTC instant it was made (fixed width, so string order is time order). The hold
# is compared as an instant, never as a calendar day, so PRUNE_QUARANTINE_DAYS is a true minimum.
STAMP='%Y-%m-%dT%H%M%SZ'
is_stamp() { case "$1" in [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z) true ;; *) false ;; esac; }
cutoff=""
if cutoff="$(date -u -v-"$DAYS"d +"$STAMP" 2>/dev/null || date -u -d "$DAYS days ago" +"$STAMP" 2>/dev/null)" && is_stamp "$cutoff"; then :
else
  cutoff=""; echo "note    cannot compute the quarantine cutoff time: nothing will be purged"; note_fault
fi

quarantine_one() { # repo path branch sha mb -> move to the quarantine, rescan, move back on any hit
  local repo="$1" path="$2" branch="$3" sha="$4" mb="$5" dir q n why rc why2
  # A process whose cwd or open file is in the tree is moved out from under it by the rename, and the rescan below cannot
  # see a process that has not written yet. Same check as before a removal; a process that starts after it is the
  # residual race (see holder_scan).
  why="$(holder_scan "$path")"; rc=$?
  if [ "$rc" -ne 1 ]; then
    [ "$rc" -eq 0 ] || note_fault
    echo "keep    $path  ($branch: ${why:-holder check failed, exit $rc}; nothing was moved)"
    return
  fi
  dir="$QBASE/$(date -u +"$STAMP")"
  # check the quarantine base before creating anything in it: a .prune-quarantine symlink would otherwise get a directory made outside the root
  mkdir -p "$QBASE" || { echo "FAILED  $path  ($branch: could not create $QBASE)"; note_fault; return; }
  under_root "$QBASE" || { echo "FAILED  $path  ($branch: $QBASE resolves outside $ROOT, nothing was moved)"; note_fault; return; }
  mkdir -p "$dir" || { echo "FAILED  $path  ($branch: could not create $dir)"; note_fault; return; }
  under_root "$dir" || { echo "FAILED  $path  ($branch: $dir resolves outside $ROOT, nothing was moved)"; note_fault; return; }
  q="$dir/$(basename "$repo")--$(basename "$path")"; n=1
  while [ -e "$q" ] || [ -L "$q" ]; do n=$((n + 1)); q="$dir/$(basename "$repo")--$(basename "$path")-$n"; done
  if ! why="$(move_wt "$repo" "$path" "$q")"; then echo "FAILED  $path  ($branch: $why)"; note_fault; return; fi
  # the rescan of the moved tree: a file written between the first scan and the move travels with it and is seen here
  why="$(keep_reason "$q" "$repo" "$sha" "$branch")"; rc=$?
  if [ "$rc" -ne 1 ]; then
    [ "$rc" -eq 0 ] || note_fault
    if why2="$(move_wt "$repo" "$q" "$path")"; then echo "keep    $path  ($branch: ${why:-rescan failed, exit $rc}; moved back after the move)"
    else echo "FAILED  $path  ($branch: ${why:-rescan failed, exit $rc}; $why2; it stays at $q)"; note_fault; fi
    return
  fi
  echo "quarantined $path  ($branch, ${mb}M) -> $q  (restore: git -C $repo worktree move $q $path)"
}

holder_scan() { # tree -> 0 + why when a process has its cwd or a file open inside it, 1 when none, 2 when lsof could not say
  # Renaming a tree does not stop a process that already holds it: its cwd and open files follow the inode, so it can
  # still write after the last rescan. lsof +D lists every cwd, open file and mapped file under the directory. This
  # closes the window for every process lsof can see (the pruner's own user). It does NOT close it for a process of
  # another user (lsof cannot list those), a holder that starts in the milliseconds between this check and the remove
  # by finding the renamed path itself, or a platform whose lsof hides some processes; that is why deletion is opt-in.
  local real out err rc
  command -v lsof >/dev/null 2>&1 || { echo "could not list open files (lsof not found)"; return 2; }
  real="$(cd "$1" 2>/dev/null && pwd -P)" || { echo "could not list open files (cannot enter $1)"; return 2; }
  err="$(mktemp)" || { echo "could not create a temp file"; return 2; }
  out="$(lsof -n -P -w -F pc +D "$real" 2>"$err")"; rc=$?
  if [ -n "$out" ]; then # lsof exits 1 as well when it listed holders but could not stat something: any output is a holder
    rm -f "$err"; echo "a process holds files inside it ($(printf '%s\n' "$out" | awk '/^c/{print substr($0,2); exit}'))"; return 0
  fi
  if [ "$rc" -eq 1 ] && [ -z "$out" ] && [ ! -s "$err" ]; then rm -f "$err"; return 1; fi # no holder, nothing said
  echo "could not list open files (lsof exit $rc: $(head -c 200 "$err" | tr '\n' ' '))"; rm -f "$err"; return 2
}

purge_one() { # repo path branch sha mb -> after the hold: full guard, rename aside, rescan, remove, delete the branch
  local repo="$1" path="$2" branch="$3" sha="$4" mb="$5" d aside why rc why2
  d="$(basename "$(dirname "$path")")"
  is_stamp "$d" || { echo "keep    $path  ($branch: quarantine directory '$d' is not a UTC timestamp like 2026-01-31T235959Z; rename it to the time it was quarantined)"; note_fault; return; }
  [ -n "$cutoff" ] || { echo "keep    $path  ($branch: quarantined, no cutoff date)"; return; }
  if [[ "$d" > "$cutoff" ]]; then echo "keep    $path  ($branch: quarantined $d, purge after $cutoff)"; return; fi
  why="$(keep_reason "$path" "$repo" "$sha" "$branch")"; rc=$?
  if [ "$rc" -ne 1 ]; then [ "$rc" -eq 0 ] || note_fault; echo "keep    $path  ($branch: quarantined, ${why:-scan failed, exit $rc})"; return; fi
  [ "$ALLOW_DELETE" = 1 ] || { echo "keep    $path  ($branch: quarantined, past the hold; unattended deletion is off, set PRUNE_ALLOW_DELETE=1 to enable)"; return; }
  if [ "$DRY_RUN" != 0 ]; then echo "would   purge $path  ($branch, ${mb}M)"; return; fi
  # rename aside first: nothing that opens the old path can write into the tree any more; then rescan the renamed tree
  case "$path" in *.purge) aside="$path" ;; *) aside="$path.purge" ;; esac
  if [ "$aside" != "$path" ]; then
    { [ ! -e "$aside" ] && [ ! -L "$aside" ]; } || { echo "FAILED  $path  ($branch: $aside already exists)"; note_fault; return; }
    if ! why2="$(move_wt "$repo" "$path" "$aside")"; then echo "FAILED  $path  ($branch: $why2)"; note_fault; return; fi
    why="$(keep_reason "$aside" "$repo" "$sha" "$branch")"; rc=$?
    if [ "$rc" -ne 1 ]; then
      [ "$rc" -eq 0 ] || note_fault
      if why2="$(move_wt "$repo" "$aside" "$path")"; then echo "keep    $path  ($branch: ${why:-rescan failed, exit $rc}; moved back after the rescan)"
      else echo "FAILED  $path  ($branch: ${why:-rescan failed, exit $rc}; $why2; it stays at $aside)"; note_fault; fi
      return
    fi
  fi
  # last check before the delete, so the window it leaves is the shortest: a holder keeps the tree and it goes back
  why="$(holder_scan "$aside")"; rc=$?
  if [ "$rc" -ne 1 ]; then
    [ "$rc" -eq 0 ] || note_fault
    if [ "$aside" = "$path" ]; then echo "keep    $path  ($branch: ${why:-holder check failed, exit $rc}; it stays set aside)"
    elif why2="$(move_wt "$repo" "$aside" "$path")"; then echo "keep    $path  ($branch: ${why:-holder check failed, exit $rc}; moved back before the remove)"
    else echo "FAILED  $path  ($branch: ${why:-holder check failed, exit $rc}; $why2; it stays at $aside)"; note_fault; fi
    return
  fi
  if git -C "$repo" worktree remove "$aside"; then
    echo "removed $path  ($branch, ${mb}M)"
    delete_branch "$repo" "$branch" "$sha"
  else
    echo "FAILED  $aside  ($branch)"; note_fault
  fi
}

for gitdir in "$ROOT"/*/.git "$ROOT"/*/*/.git; do
  [ -e "$gitdir" ] || continue
  repo="${gitdir%/.git}"
  # only a main checkout prints `.git` here (a linked worktree prints its own git dir)
  gd="$(git -C "$repo" rev-parse --git-dir)" || { echo "skip $repo: git rev-parse failed"; note_fault; continue; }
  [ "$gd" = .git ] || continue
  # -z ends every field with a NUL, so a path (any byte but NUL: a newline, a TAB, a lookalike `branch ` line) is exactly
  # one `worktree ` field and can never be read as another field or split into columns.
  wtl="$(mktemp)" || { echo "skip $repo: could not create a temp file"; note_fault; continue; }
  git -C "$repo" worktree list --porcelain -z >"$wtl"; rc=$?
  if [ "$rc" -ne 0 ] || ! exec 4<"$wtl"; then rm -f "$wtl"; echo "skip $repo: could not list worktrees"; note_fault; continue; fi
  wpaths=(); wbranches=() # one entry per worktree, "" for a detached or bare one
  while IFS= read -r -d '' -u 4 f; do
    case "$f" in
      "worktree "*) wpaths+=("${f#worktree }"); wbranches+=("") ;;
      "branch refs/heads/"*) [ "${#wbranches[@]}" -eq 0 ] || wbranches[${#wbranches[@]}-1]="${f#branch refs/heads/}" ;;
    esac
  done
  exec 4<&-; rm -f "$wtl"
  [ "${#wpaths[@]}" -gt 1 ] || continue
  merged="$(pr_heads "$repo" merged)" || { note_fault; continue; }
  open="$(pr_heads "$repo" open)" || { note_fault; continue; }

  i=0
  while [ "$i" -lt "${#wpaths[@]}" ]; do
    path="${wpaths[$i]}"; branch="${wbranches[$i]}"; i=$((i + 1))
    [ -n "$branch" ] || continue
    [ "$path" -ef "$repo" ] && continue # same directory, even when $ROOT reaches it through a symlink
    inq=0; [ "$(dirname "$(dirname "$path")")" -ef "$QBASE" ] && inq=1
    sha="$(awk -v b="$branch" '$1==b{print $2; exit}' <<<"$merged")"
    if [ -z "$sha" ]; then [ "$inq" -eq 0 ] || echo "keep    $path  ($branch: quarantined, no longer in the merged PR list)"; continue; fi
    awk -v b="$branch" '$1==b{f=1} END{exit !f}' <<<"$open"; rc=$?
    if [ "$rc" -eq 0 ]; then echo "keep    $path  ($branch: name reused by an open PR)"; continue; fi
    [ "$rc" -eq 1 ] || { echo "keep    $path  ($branch: could not read the open PR list, awk exit $rc)"; note_fault; continue; }
    if [ -d "$path" ] && ! under_root "$path"; then echo "keep    $path  ($branch: outside $ROOT, only worktrees under the projects root are touched)"; continue; fi
    kb="$(du -sk "$path" 2>/dev/null | awk 'NR==1{print $1}')"; mb=$(( ${kb:-0} / 1024 ))
    if [ "$inq" -eq 1 ]; then purge_one "$repo" "$path" "$branch" "$sha" "$mb"; continue; fi
    why="$(keep_reason "$path" "$repo" "$sha" "$branch")"; rc=$?
    # exactly 1 means "may go"; a scan that was killed or failed some other way keeps the tree
    if [ "$rc" -ne 1 ]; then [ "$rc" -eq 0 ] || note_fault; echo "keep    $path  ($branch: ${why:-scan failed, exit $rc})"; continue; fi
    if [ "$DRY_RUN" != 0 ]; then echo "would   quarantine $path  ($branch, ${mb}M)"; continue; fi
    quarantine_one "$repo" "$path" "$branch" "$sha" "$mb"
  done
  # no `git worktree prune` here: `worktree remove` cleans its own admin dir, and a missing directory is also a
  # moved folder or an unmounted volume whose detached HEAD may hold the only copy of unpushed commits. git's own
  # gc prunes stale entries after gc.worktreePruneExpire (3 months).
done
df -h "$HOME" | tail -1
if [ -s "$FAULTS" ]; then echo "exit 1: at least one check could not complete (see the lines above); every affected worktree was kept"; exit 1; fi
