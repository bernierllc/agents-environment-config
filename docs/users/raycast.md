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
