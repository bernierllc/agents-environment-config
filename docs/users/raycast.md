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

- **Colima running:** runs `docker system prune` (stopped containers, unused networks, dangling images, build cache) and removes images unused for 24h+, then recycles the VM (`colima stop`, `colima start`). Containers come back according to their restart policy: `unless-stopped`/`always` ones restart with the daemon, `no` ones stay stopped (for example the byo-* and redis containers). If Colima fails to come back up, the script exits non-zero and says so.
- **Docker Desktop (or another daemon):** prunes only; nothing is stopped.
- **No runtime:** Docker cleanup is skipped.

Volumes are never pruned: an unused volume is often a stopped dev database's data. Compose stacks whose project directory no longer exists (a removed worktree) are reported with the command to stop them, but never stopped automatically.

From the terminal, the `cleanup` shell function runs the script as a subprocess, so the shell stays open when it finishes.
