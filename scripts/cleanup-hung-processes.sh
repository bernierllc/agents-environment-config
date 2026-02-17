#!/bin/bash
# Cleanup hung processes and Docker resources.
# Only kills actually hung/unresponsive processes, not active ones.
# Safe to run from Raycast or CLI.


# Run a command with timeout (macOS doesn't have GNU timeout)
# Usage: run_with_timeout SECONDS command [args...]
run_with_timeout() {
    local seconds="$1"
    shift
    perl -e "alarm $seconds; exec @ARGV" -- "$@"
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

echo ""
echo "================================="
echo "All cleanup tasks complete"
echo "================================="
