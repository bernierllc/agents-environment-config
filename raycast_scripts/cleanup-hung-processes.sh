#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Cleanup Hung Processes
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🧹
# @raycast.packageName System Cleanup

# Documentation:
# @raycast.description Kills hung/unresponsive processes and runs Docker cleanup
# @raycast.author Matt Bernier

echo "🔍 Checking for hung processes..."
echo "================================="

KILLED_COUNT=0

# 1. Kill zombie processes (state Z)
echo ""
echo "📍 Checking for zombie processes..."
ZOMBIES=$(ps aux | awk '$8=="Z" || $8~/Z/ {print $2}')
if [ -n "$ZOMBIES" ]; then
    echo "Found zombie processes: $ZOMBIES"
    for pid in $ZOMBIES; do
        # Get parent and kill it (zombies can only be cleaned by parent)
        PPID=$(ps -o ppid= -p $pid 2>/dev/null | tr -d ' ')
        if [ -n "$PPID" ] && [ "$PPID" != "1" ]; then
            echo "  Killing parent $PPID of zombie $pid"
            kill -9 $PPID 2>/dev/null && ((KILLED_COUNT++))
        fi
    done
else
    echo "  No zombie processes found ✓"
fi

# 2. Kill hung vitest processes (common issue)
echo ""
echo "📍 Checking for vitest processes..."
VITEST_PIDS=$(pgrep -f "vitest" 2>/dev/null)
if [ -n "$VITEST_PIDS" ]; then
    VITEST_COUNT=$(echo "$VITEST_PIDS" | wc -l | tr -d ' ')
    echo "  Found $VITEST_COUNT vitest processes - killing..."
    pkill -9 -f "vitest" 2>/dev/null
    KILLED_COUNT=$((KILLED_COUNT + VITEST_COUNT))
    echo "  Killed $VITEST_COUNT vitest processes ✓"
else
    echo "  No vitest processes found ✓"
fi

# 3. Kill hung jest processes
echo ""
echo "📍 Checking for jest processes..."
JEST_PIDS=$(pgrep -f "jest" 2>/dev/null | grep -v "majestic")
if [ -n "$JEST_PIDS" ]; then
    JEST_COUNT=$(echo "$JEST_PIDS" | wc -l | tr -d ' ')
    echo "  Found $JEST_COUNT jest processes - killing..."
    pkill -9 -f "jest" 2>/dev/null
    KILLED_COUNT=$((KILLED_COUNT + JEST_COUNT))
    echo "  Killed $JEST_COUNT jest processes ✓"
else
    echo "  No jest processes found ✓"
fi

# 4. Kill processes in uninterruptible sleep (D state) for too long
# These are usually stuck on I/O - be careful, some are legitimate
echo ""
echo "📍 Checking for stuck I/O processes..."
# Only kill node/npm processes stuck in D state, not system processes
STUCK_IO=$(ps aux | awk '$8~/D/ && ($11~/node/ || $11~/npm/) {print $2}')
if [ -n "$STUCK_IO" ]; then
    for pid in $STUCK_IO; do
        PROC_NAME=$(ps -o comm= -p $pid 2>/dev/null)
        echo "  Killing stuck I/O process: $pid ($PROC_NAME)"
        kill -9 $pid 2>/dev/null && ((KILLED_COUNT++))
    done
else
    echo "  No stuck I/O processes found ✓"
fi

# 5. Kill orphaned node processes consuming high CPU (>80%) for user processes
echo ""
echo "📍 Checking for runaway node processes..."
HIGH_CPU=$(ps aux | awk '$3>80 && $11~/node/ && $1!="root" {print $2, $3, $11}')
if [ -n "$HIGH_CPU" ]; then
    echo "$HIGH_CPU" | while read pid cpu cmd; do
        # Check if it's been running hot for a while (crude check - process exists)
        echo "  Found high CPU node process: PID $pid at ${cpu}% CPU"
        # Don't auto-kill these, just report - they might be legitimate builds
    done
else
    echo "  No runaway node processes found ✓"
fi

# 6. Kill orphaned esbuild/webpack/tsc processes older than 30 minutes
echo ""
echo "📍 Checking for stale build processes..."
for proc in "esbuild" "webpack" "tsc"; do
    STALE=$(pgrep -f "$proc" 2>/dev/null)
    if [ -n "$STALE" ]; then
        for pid in $STALE; do
            # Get process elapsed time
            ELAPSED=$(ps -o etime= -p $pid 2>/dev/null | tr -d ' ')
            if [[ "$ELAPSED" =~ ^[0-9]+-.*$ ]] || [[ "$ELAPSED" =~ ^[0-9]{2,}:[0-9]{2}:[0-9]{2}$ ]]; then
                # Process is older than 1 hour (has days or hours:min:sec format)
                PROC_NAME=$(ps -o comm= -p $pid 2>/dev/null)
                echo "  Killing stale $proc process: $pid (running for $ELAPSED)"
                kill -9 $pid 2>/dev/null && ((KILLED_COUNT++))
            fi
        done
    fi
done
echo "  Stale build process check complete ✓"

echo ""
echo "================================="
echo "🧹 Process cleanup complete: $KILLED_COUNT processes killed"
echo ""

# Docker Cleanup
echo "🐳 Starting Docker cleanup..."
echo "================================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "⚠️  Docker is not running, skipping cleanup"
else
    # Show current usage
    echo ""
    echo "Current Docker disk usage:"
    docker system df
    
    echo ""
    echo "Cleaning up Docker..."
    
    # Remove stopped containers
    STOPPED=$(docker ps -aq -f status=exited 2>/dev/null)
    if [ -n "$STOPPED" ]; then
        STOPPED_COUNT=$(echo "$STOPPED" | wc -l | tr -d ' ')
        echo "  Removing $STOPPED_COUNT stopped containers..."
        docker rm $STOPPED >/dev/null 2>&1
    fi
    
    # Prune system (containers, networks, dangling images, build cache)
    echo "  Running docker system prune..."
    PRUNE_OUTPUT=$(docker system prune -f 2>&1)
    
    # Prune unused volumes
    echo "  Pruning unused volumes..."
    docker volume prune -f >/dev/null 2>&1
    
    # Prune unused images (not just dangling)
    echo "  Pruning unused images..."
    docker image prune -a -f --filter "until=24h" >/dev/null 2>&1
    
    echo ""
    echo "Docker disk usage after cleanup:"
    docker system df
    
    echo ""
    echo "🐳 Docker cleanup complete ✓"
fi

echo ""
echo "================================="
echo "✅ All cleanup tasks complete!"
echo "================================="
