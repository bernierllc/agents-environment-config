#!/bin/bash
# Cleanup hung processes and Docker resources.
# Only kills actually hung/unresponsive processes, not active ones.
# Safe to run from Raycast or CLI.


# Run a command with timeout (macOS doesn't have GNU timeout)
# Usage: run_with_timeout SECONDS command [args...]
# The command runs in its own process group and the whole group is killed on
# expiry: killing only the leader leaves children (brew's ruby, pnpm workers)
# holding stdout open, so a `$(...)` caller would still wait for EOF forever.
# Exit status: the command's, or 124 on timeout (same as GNU timeout).
run_with_timeout() {
    local seconds="$1"
    shift
    perl -e '
        my $seconds = shift @ARGV;
        my $pid = fork;
        die "fork: $!" unless defined $pid;
        if ($pid == 0) { setpgrp(0, 0); exec @ARGV; exit 127 }
        setpgrp($pid, $pid);  # also from the parent: closes the race with an early signal
        my $kill_group = sub {
            kill "-TERM", $pid; sleep 2; kill "-KILL", $pid; waitpid $pid, 0;
        };
        $SIG{ALRM} = sub { $kill_group->(); exit 124 };
        # Ctrl-C: kill the group, then die of the same signal so the calling
        # shell sees an interrupt and aborts instead of running the next step.
        $SIG{INT} = $SIG{TERM} = sub {
            my $sig = shift; $kill_group->(); $SIG{$sig} = "DEFAULT"; kill $sig, $$;
        };
        alarm $seconds;
        waitpid $pid, 0;
        exit(($? & 127) ? 128 + ($? & 127) : $? >> 8);
    ' -- "$seconds" "$@"
}

# Clean a package-manager cache without letting it hang the script.
# Usage: clean_pm_cache SECONDS label command [args...]
# - stdin from /dev/null: Corepack shims (node's bundled yarn/pnpm) prompt
#   "Do you want to continue? [Y/n]" on a TTY stdin when the tool isn't
#   downloaded yet; with stderr piped the prompt is invisible and blocks forever.
# - COREPACK_ENABLE_NETWORK=0: a missing tool fails fast instead of being
#   downloaded by a cleanup script.
# - run_with_timeout: same guard the Docker steps already have.
clean_pm_cache() {
    local seconds="$1" label="$2"
    shift 2
    echo "  $label..."
    local out
    if out=$(COREPACK_ENABLE_NETWORK=0 run_with_timeout "$seconds" "$@" </dev/null 2>&1); then
        echo "    $(tail -n1 <<<"$out")"
    else
        echo "    ($label failed or timed out: $(tail -n1 <<<"$out"))"
    fi
}

# Check if process has been running longer than N minutes based on ps etime
# etime formats: MM:SS, HH:MM:SS, D-HH:MM:SS
# Returns 0 (true) if old enough, 1 (false) otherwise
is_process_older_than_minutes() {
    local pid="$1"
    local min_minutes="$2"
    local etime
    etime=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
    [ -z "$etime" ] && return 1

    # Has days (e.g. 1-02:30:00) -> definitely old
    [[ "$etime" =~ ^[0-9]+- ]] && return 0

    # HH:MM:SS format - parse hours
    if [[ "$etime" =~ ^([0-9]+):([0-9]{2}):([0-9]{2})$ ]]; then
        local hours="${BASH_REMATCH[1]}"
        local mins="${BASH_REMATCH[2]}"
        local total_mins=$((10#$hours * 60 + 10#$mins))
        [ "$total_mins" -ge "$min_minutes" ] && return 0
        return 1
    fi

    # MM:SS format
    if [[ "$etime" =~ ^([0-9]+):([0-9]{2})$ ]]; then
        local mins="${BASH_REMATCH[1]}"
        [ "$mins" -ge "$min_minutes" ] && return 0
    fi

    return 1
}

KILLED_COUNT=0

echo "Checking for hung processes..."
echo "================================="

# 1. Zombie processes (state Z) - kill parent to reap
echo ""
echo "Checking for zombie processes..."
ZOMBIES=$(ps aux | awk '$8=="Z" || $8~/^Z/ {print $2}')
if [ -n "$ZOMBIES" ]; then
    for pid in $ZOMBIES; do
        PARENT_PID=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        if [ -n "$PARENT_PID" ] && [ "$PARENT_PID" != "1" ]; then
            echo "  Killing parent $PARENT_PID of zombie $pid"
            if kill -9 "$PARENT_PID" 2>/dev/null; then
                ((KILLED_COUNT++)) || true
            fi
        fi
    done
else
    echo "  No zombie processes found"
fi

# 2. Vitest - only kill if running > 10 minutes (likely hung)
echo ""
echo "Checking for hung vitest processes (>10 min)..."
while read -r pid; do
    if is_process_older_than_minutes "$pid" 10; then
        echo "  Killing hung vitest: PID $pid"
        kill -9 "$pid" 2>/dev/null && ((KILLED_COUNT++)) || true
    fi
done < <(pgrep -f "vitest" 2>/dev/null || true)
echo "  Vitest check complete"

# 3. Jest - only kill if running > 10 minutes (likely hung)
echo ""
echo "Checking for hung jest processes (>10 min)..."
while read -r pid; do
    [[ -z "$pid" ]] && continue
    if is_process_older_than_minutes "$pid" 10; then
        echo "  Killing hung jest: PID $pid"
        kill -9 "$pid" 2>/dev/null && ((KILLED_COUNT++)) || true
    fi
done < <(pgrep -f "jest" 2>/dev/null | grep -v "majestic" || true)
echo "  Jest check complete"

# 4. Stuck I/O (D state) - node/npm only
echo ""
echo "Checking for stuck I/O processes (node/npm)..."
STUCK_IO=$(ps aux | awk '$8~/^D/ && ($11~/node/ || $11~/npm/) {print $2}')
if [ -n "$STUCK_IO" ]; then
    for pid in $STUCK_IO; do
        PROC_NAME=$(ps -o comm= -p "$pid" 2>/dev/null)
        echo "  Killing stuck I/O: $pid ($PROC_NAME)"
        kill -9 "$pid" 2>/dev/null && ((KILLED_COUNT++)) || true
    done
else
    echo "  No stuck I/O processes found"
fi

# 5. High CPU node - report only, do not kill
echo ""
echo "Checking for runaway node processes (>80% CPU)..."
HIGH_CPU=$(ps aux | awk '$3>80 && $11~/node/ && $1!="root" {print $2, $3, $11}')
if [ -n "$HIGH_CPU" ]; then
    echo "$HIGH_CPU" | while read -r pid cpu cmd; do
        echo "  [REPORT] High CPU node: PID $pid at ${cpu}% (not killing - may be legitimate)"
    done
else
    echo "  No runaway node processes found"
fi

# 6. Stale build processes (esbuild, webpack, tsc) - only if > 30 min
echo ""
echo "Checking for stale build processes (>30 min)..."
for proc in "esbuild" "webpack" "tsc"; do
    while read -r pid; do
        [[ -z "$pid" ]] && continue
        if is_process_older_than_minutes "$pid" 30; then
            ELAPSED=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ')
            echo "  Killing stale $proc: PID $pid (running $ELAPSED)"
            kill -9 "$pid" 2>/dev/null && ((KILLED_COUNT++)) || true
        fi
    done < <(pgrep -f "$proc" 2>/dev/null || true)
done
echo "  Stale build check complete"

echo ""
echo "================================="
echo "Process cleanup complete: $KILLED_COUNT processes killed"
echo ""

# Docker cleanup (with timeouts to prevent hangs)
echo "Starting Docker cleanup..."
echo "================================="

if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running, skipping cleanup"
else
    DOCKER_TIMEOUT=60

    echo ""
    echo "Current Docker disk usage:"
    run_with_timeout "$DOCKER_TIMEOUT" docker system df 2>&1 || echo "  (Docker df timed out or failed)"

    echo ""
    echo "Cleaning up Docker..."

    STOPPED=$(run_with_timeout 10 docker ps -aq -f status=exited 2>/dev/null || true)
    if [ -n "$STOPPED" ]; then
        STOPPED_COUNT=$(echo "$STOPPED" | wc -l | tr -d ' ')
        echo "  Removing $STOPPED_COUNT stopped containers..."
        echo "$STOPPED" | xargs docker rm 2>/dev/null || true
    fi

    echo "  Running docker system prune..."
    run_with_timeout "$DOCKER_TIMEOUT" docker system prune -f 2>&1 || echo "  (Prune timed out)"

    echo "  Pruning unused volumes..."
    run_with_timeout 30 docker volume prune -f 2>/dev/null || echo "  (Volume prune timed out)"

    echo "  Pruning unused images (unused 24h+)..."
    run_with_timeout "$DOCKER_TIMEOUT" docker image prune -a -f --filter "until=24h" 2>/dev/null || echo "  (Image prune timed out)"

    echo ""
    echo "Docker disk usage after cleanup:"
    run_with_timeout "$DOCKER_TIMEOUT" docker system df 2>&1 || echo "  (Docker df timed out)"

    echo ""
    echo "Docker cleanup complete"
fi

# Cache directory cleanup (>.next, node_modules/.cache, etc. older than 48h)
echo ""
echo "Starting cache directory cleanup..."
echo "================================="

PROJECTS_DIR="$HOME/projects"
CACHE_DIRS_DELETED=0
CACHE_BYTES_FREED=0

if [ -d "$PROJECTS_DIR" ]; then
    # Known cache directory patterns to clean
    CACHE_PATTERNS=(".next" ".nuxt" ".turbo" ".parcel-cache" ".cache" "dist" ".output" ".svelte-kit")

    for pattern in "${CACHE_PATTERNS[@]}"; do
        while IFS= read -r cache_dir; do
            [[ -z "$cache_dir" ]] && continue
            # Check if directory is older than 48 hours (modified time)
            if find "$cache_dir" -maxdepth 0 -mmin +2880 -print -quit 2>/dev/null | grep -q .; then
                DIR_SIZE=$(du -sk "$cache_dir" 2>/dev/null | awk '{print $1}')
                DIR_SIZE=${DIR_SIZE:-0}
                echo "  Removing $cache_dir ($(( DIR_SIZE / 1024 ))MB, >48h old)"
                rm -rf "$cache_dir" 2>/dev/null && {
                    ((CACHE_DIRS_DELETED++)) || true
                    CACHE_BYTES_FREED=$((CACHE_BYTES_FREED + DIR_SIZE))
                }
            fi
        done < <(find "$PROJECTS_DIR" -maxdepth 3 -type d -name "$pattern" 2>/dev/null)
    done

    # Also clean node_modules/.cache directories (webpack/babel/eslint caches)
    while IFS= read -r cache_dir; do
        [[ -z "$cache_dir" ]] && continue
        if find "$cache_dir" -maxdepth 0 -mmin +2880 -print -quit 2>/dev/null | grep -q .; then
            DIR_SIZE=$(du -sk "$cache_dir" 2>/dev/null | awk '{print $1}')
            DIR_SIZE=${DIR_SIZE:-0}
            echo "  Removing $cache_dir ($(( DIR_SIZE / 1024 ))MB, >48h old)"
            rm -rf "$cache_dir" 2>/dev/null && {
                ((CACHE_DIRS_DELETED++)) || true
                CACHE_BYTES_FREED=$((CACHE_BYTES_FREED + DIR_SIZE))
            }
        fi
    done < <(find "$PROJECTS_DIR" -maxdepth 4 -type d -path "*/node_modules/.cache" 2>/dev/null)

    echo ""
    echo "  Cache cleanup: $CACHE_DIRS_DELETED directories removed (~$(( CACHE_BYTES_FREED / 1024 ))MB freed)"
else
    echo "  Projects directory not found at $PROJECTS_DIR, skipping"
fi

# Claude temp file cleanup
echo ""
echo "Starting Claude temp file cleanup..."
echo "================================="

CLAUDE_CLEANED=0

# 1. /tmp/claude and /tmp/claude-* directories (session temp files, safe to clean if >48h)
for tmp_dir in /tmp/claude /tmp/claude-*; do
    [ -d "$tmp_dir" ] || continue
    while IFS= read -r subdir; do
        [[ -z "$subdir" ]] && continue
        if find "$subdir" -maxdepth 0 -mmin +2880 -print -quit 2>/dev/null | grep -q .; then
            echo "  Removing $subdir"
            rm -rf "$subdir" 2>/dev/null && ((CLAUDE_CLEANED++)) || true
        fi
    done < <(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)
done

# 2. macOS temp dir claude files (var/folders)
MACOS_TMP="${TMPDIR:-/tmp}"
for tmp_item in "$MACOS_TMP"/claude-*; do
    [ -e "$tmp_item" ] || continue
    if find "$tmp_item" -maxdepth 0 -mmin +2880 -print -quit 2>/dev/null | grep -q .; then
        echo "  Removing $tmp_item"
        rm -rf "$tmp_item" 2>/dev/null && ((CLAUDE_CLEANED++)) || true
    fi
done

# 3. ~/.claude/projects - clean JSONL conversation logs older than 7 days
#    (These are the biggest space consumers - conversation histories)
if [ -d "$HOME/.claude/projects" ]; then
    JSONL_FREED=0
    while IFS= read -r jsonl_file; do
        [[ -z "$jsonl_file" ]] && continue
        FILE_SIZE=$(du -sk "$jsonl_file" 2>/dev/null | awk '{print $1}')
        FILE_SIZE=${FILE_SIZE:-0}
        # Only clean files > 1MB and older than 7 days
        if [ "$FILE_SIZE" -gt 1024 ]; then
            echo "  Removing old conversation log: $(basename "$(dirname "$jsonl_file")")/$(basename "$jsonl_file") ($(( FILE_SIZE / 1024 ))MB)"
            rm -f "$jsonl_file" 2>/dev/null && {
                ((CLAUDE_CLEANED++)) || true
                JSONL_FREED=$((JSONL_FREED + FILE_SIZE))
            }
        fi
    done < <(find "$HOME/.claude/projects" -name "*.jsonl" -mtime +7 2>/dev/null)
    [ "$JSONL_FREED" -gt 0 ] && echo "  Freed ~$(( JSONL_FREED / 1024 ))MB from old conversation logs"
fi

# 4. ~/Library/Caches/claude-cli-nodejs - safe to clean entirely if >48h old
CLAUDE_CACHE="$HOME/Library/Caches/claude-cli-nodejs"
if [ -d "$CLAUDE_CACHE" ]; then
    if find "$CLAUDE_CACHE" -maxdepth 0 -mmin +2880 -print -quit 2>/dev/null | grep -q .; then
        CACHE_SIZE=$(du -sh "$CLAUDE_CACHE" 2>/dev/null | awk '{print $1}')
        echo "  Clearing Claude CLI cache ($CACHE_SIZE)"
        rm -rf "$CLAUDE_CACHE" 2>/dev/null && ((CLAUDE_CLEANED++)) || true
    fi
fi

echo ""
echo "  Claude cleanup: $CLAUDE_CLEANED items cleaned"

# Package manager and system cache cleanup
echo ""
echo "Starting package manager cache cleanup..."
echo "================================="

if command -v pnpm >/dev/null 2>&1; then
    clean_pm_cache 120 "Pruning pnpm store" pnpm store prune
else
    echo "  pnpm not found, skipping"
fi

if command -v yarn >/dev/null 2>&1; then
    clean_pm_cache 120 "Cleaning yarn cache" yarn cache clean
else
    echo "  yarn not found, skipping"
fi

if command -v brew >/dev/null 2>&1; then
    clean_pm_cache 300 "Running brew cleanup" brew cleanup
else
    echo "  brew not found, skipping"
fi

if command -v pip >/dev/null 2>&1; then
    clean_pm_cache 120 "Purging pip cache" pip cache purge
elif command -v pip3 >/dev/null 2>&1; then
    clean_pm_cache 120 "Purging pip3 cache" pip3 cache purge
else
    echo "  pip not found, skipping"
fi

echo ""
echo "Package manager cache cleanup complete"

echo ""
echo "================================="
echo "All cleanup tasks complete"
echo "================================="
