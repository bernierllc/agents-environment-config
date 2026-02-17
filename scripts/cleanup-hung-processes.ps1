# Cleanup hung processes and Docker resources (Windows).
# Only kills actually hung/unresponsive processes, not active ones.
# Requires PowerShell 5.1+ (Windows) or PowerShell Core.

$ErrorActionPreference = "SilentlyContinue"
$killedCount = 0

Write-Host "Checking for hung processes..."
Write-Host "================================="

# 1. Hung vitest processes (>10 min)
Write-Host ""
Write-Host "Checking for hung vitest processes (>10 min)..."
$vitestProcs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like "*vitest*" -and $_.CreationDate }
foreach ($proc in $vitestProcs) {
    try {
        $age = (Get-Date) - $proc.CreationDate
        if ($age.TotalMinutes -gt 10) {
            Write-Host "  Killing hung vitest: PID $($proc.ProcessId) (running $([math]::Floor($age.TotalMinutes)) min)"
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            $killedCount++
        }
    }
    catch { }
}
Write-Host "  Vitest check complete"

# 2. Hung jest processes (>10 min)
Write-Host ""
Write-Host "Checking for hung jest processes (>10 min)..."
$jestProcs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like "*jest*" -and $_.CommandLine -notlike "*majestic*" -and $_.CreationDate }
foreach ($proc in $jestProcs) {
    try {
        $age = (Get-Date) - $proc.CreationDate
        if ($age.TotalMinutes -gt 10) {
            Write-Host "  Killing hung jest: PID $($proc.ProcessId) (running $([math]::Floor($age.TotalMinutes)) min)"
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            $killedCount++
        }
    }
    catch { }
}
Write-Host "  Jest check complete"

# 3. Stale build processes (esbuild, webpack, tsc) - >30 min
Write-Host ""
Write-Host "Checking for stale build processes (>30 min)..."
$buildPatterns = @("esbuild", "webpack", "tsc")
foreach ($pattern in $buildPatterns) {
    $procs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -like "*$pattern*" -and $_.CreationDate }
    foreach ($proc in $procs) {
        try {
            $age = (Get-Date) - $proc.CreationDate
            if ($age.TotalMinutes -gt 30) {
                Write-Host "  Killing stale $pattern : PID $($proc.ProcessId) (running $([math]::Floor($age.TotalMinutes)) min)"
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
                $killedCount++
            }
        }
        catch { }
    }
}
Write-Host "  Stale build check complete"

# 4. Not Responding processes (Windows equivalent of hung)
Write-Host ""
Write-Host "Checking for Not Responding processes..."
$hungProcs = Get-Process | Where-Object { $_.Responding -eq $false -and $_.ProcessName -match "^(node|npm)" }
foreach ($proc in $hungProcs) {
    try {
        Write-Host "  Killing Not Responding: $($proc.ProcessName) PID $($proc.Id)"
        Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        $killedCount++
    }
    catch { }
}
Write-Host "  Not Responding check complete"

Write-Host ""
Write-Host "================================="
Write-Host "Process cleanup complete: $killedCount processes killed"
Write-Host ""

# Docker cleanup
Write-Host "Starting Docker cleanup..."
Write-Host "================================="

try {
    $dockerCheck = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker is not running, skipping cleanup"
    }
    else {
        $timeoutSec = 60

        Write-Host ""
        Write-Host "Current Docker disk usage:"
        $job = Start-Job { docker system df }
        if (Wait-Job $job -Timeout $timeoutSec) {
            Receive-Job $job
        }
        else {
            Write-Host "  (Docker df timed out)"
            Stop-Job $job
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "Cleaning up Docker..."

        # Remove stopped containers
        $stoppedOut = docker ps -aq -f status=exited 2>$null
        $stoppedIds = @($stoppedOut -split "`r?`n" | Where-Object { $_.Trim() })
        if ($stoppedIds.Count -gt 0) {
            Write-Host "  Removing $($stoppedIds.Count) stopped containers..."
            $stoppedIds | ForEach-Object { docker rm $_.Trim() 2>$null }
        }

        Write-Host "  Running docker system prune..."
        $job = Start-Job { docker system prune -f }
        if (-not (Wait-Job $job -Timeout $timeoutSec)) {
            Stop-Job $job
            Write-Host "  (Prune timed out)"
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue

        Write-Host "  Pruning unused volumes..."
        $job = Start-Job { docker volume prune -f }
        if (-not (Wait-Job $job -Timeout 30)) { Stop-Job $job }
        Remove-Job $job -Force -ErrorAction SilentlyContinue

        Write-Host "  Pruning unused images (unused 24h+)..."
        $job = Start-Job { docker image prune -a -f --filter "until=24h" }
        if (-not (Wait-Job $job -Timeout $timeoutSec)) {
            Stop-Job $job
            Write-Host "  (Image prune timed out)"
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "Docker disk usage after cleanup:"
        $job = Start-Job { docker system df }
        if (Wait-Job $job -Timeout $timeoutSec) {
            Receive-Job $job
        }
        Remove-Job $job -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "Docker cleanup complete"
    }
}
catch {
    Write-Host "Docker is not available: $_"
}

Write-Host ""
Write-Host "================================="
Write-Host "All cleanup tasks complete"
Write-Host "================================="
