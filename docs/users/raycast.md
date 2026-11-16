# Raycast integration

During project setup (`aec setup` or `scripts/setup-repo.sh`), users are prompted to generate [Raycast](https://raycast.com/) launcher scripts. These scripts provide one-keystroke access to open a project in any detected agent.

Scripts are generated per-agent based on what is installed on the machine. The setup detects all supported agents (Claude, Cursor, Gemini, Qwen, Codex) and generates scripts for each one found.

| Script pattern | Example | Purpose |
|----------------|---------|---------|
| `{agent}-{project}.sh` | `cursor-my-app.sh` | Open project in the agent |
| `claude-{project}-resume.sh` | `claude-my-app-resume.sh` | Resume last Claude session |

The generated scripts include Raycast metadata (`@raycast.schemaVersion`, `@raycast.title`, etc.) so they appear in the Raycast command palette automatically.

To skip Raycast script generation during setup, pass `--skip-raycast` (Python CLI) or answer "N" at the prompt (shell script).

## Discovering existing repos from scripts

If you have existing Raycast scripts from before tracking was added, use `aec discover-repos` to retroactively populate the tracking log:

```bash
aec discover-repos              # Interactive - shows what was found, asks to add
aec discover-repos --dry-run    # Preview without making changes
aec discover-repos --auto       # Auto-add all discovered paths
```

## Cleanup hung processes

The `scripts/` and `raycast_scripts/` directories ship with cleanup helpers that kill hung development processes (vitest, jest, stale build tools) and run Docker cleanup. They only terminate processes that are actually hung (e.g., running >10 min for test runners, >30 min for build tools), not active ones.

| Platform | Script | Notes |
|----------|--------|-------|
| macOS / Linux | `scripts/cleanup-hung-processes.sh` | Also at `raycast_scripts/cleanup-hung-processes.sh` |
| Windows | `scripts/cleanup-hung-processes.ps1` | Run in PowerShell: `pwsh -File scripts/cleanup-hung-processes.ps1` |

Both scripts include timeouts on Docker commands to prevent hangs when the Docker daemon is slow or unresponsive.

### Docker runtime and Colima

The macOS/Linux script detects which runtime backs the `docker` CLI:

- **Colima running and the CLI targets its socket:** runs `docker system prune` (stopped containers, unused networks, dangling images, build cache) and removes images unused for 24h+. The VM is recycled (`colima stop`, `colima start`) only when `CLEANUP_RECYCLE_COLIMA=1` is set, because the stop interrupts every running container. When it runs, containers come back according to their restart policy: `unless-stopped`/`always` ones restart with the daemon, `no` ones stay stopped (for example the byo-* and redis containers). If Colima fails to come back up, the script exits non-zero and says so.
- **Docker Desktop (or another daemon):** prunes only; nothing is stopped. This includes a Colima VM that runs while the CLI targets another daemon.
- **No runtime:** Docker cleanup is skipped.

Anonymous volumes are pruned, including those of containers the cleanup just removed: a stopped database whose data sits in an anonymous volume loses that data. Keep dev data in named volumes, which are kept: they often hold a stopped dev database's data. Set `CLEANUP_PRUNE_NAMED_VOLUMES=1` to prune them too. Compose stacks whose project directory no longer exists (a removed worktree) are reported with the command to stop them, but never stopped automatically.

From the terminal, the `cleanup` shell function runs the script as a subprocess, so the shell stays open when it finishes.

### Disk reclaim

Beyond processes and Docker, the macOS/Linux script frees disk that builds up silently:

- **Colima disk:** before any recycle it runs `colima ssh -- sudo fstrim -a`. The VM disk is sparse and only grows; trimming returns blocks freed by `docker system prune` to macOS.
- **App updater staging** (macOS only: Sparkle `Installation` and `*.ShipIt` directories under `~/Library/Caches`): keeps the newest entry, which may be waiting to install on quit, and removes older entries untouched for 7 days that no process has open.
- Package-manager caches (npm, pnpm, yarn, uv, pip, Homebrew) are cleaned only when that tool is installed.

### Worktree pruning

`scripts/prune-merged-worktrees.sh` reclaims disk from linked git worktrees under `$PROJECTS_ROOT` (default `~/projects`). It removes a clean worktree (and its local branch) when its PR merged at exactly its HEAD, or when HEAD is already pushed, no open PR uses the branch, no process has its cwd inside it, and git has not touched it for `PRUNE_IDLE_HOURS` (default 24). Worktrees it keeps get their `node_modules` stripped after `STRIP_IDLE_DAYS` (default 3) idle; the next install restores them. Dirty worktrees, unpushed commits, worktrees with their own ignored `.env*` files and worktrees holding a nested worktree, clone or submodule are never removed. Only ignored `node_modules` directories with no tracked files inside are stripped.

Below `LOW_DISK_GB` free (default 30) it uses 2-hour / 1-day thresholds and posts a notification (macOS). Set `LOW_DISK_CLEANUP=1` to also run `cleanup-hung-processes.sh` at that point; it is opt-in because that script kills hung processes and prunes Docker, including anonymous volumes.

It runs on macOS and Linux. Without `gh` it removes nothing and only strips idle `node_modules`; without `lsof` (or `/proc` on Linux) it cannot tell which worktrees are in use and leaves them all alone. `DRY_RUN=1` prints what it would do. It is idempotent, so schedule it hourly (launchd `StartInterval 3600` or cron).
