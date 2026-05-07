# Discovery

When you set up AEC in a repo that already has agents, skills, or rules, `aec discover` scans for local items that match the AEC catalog and offers to bring them under AEC management.

## How it works

1. **Scan** — Compares local files against the AEC catalog using one of three depth levels
2. **Review** — Shows matches grouped by type with match quality indicators
3. **Choose** — Install matches under AEC management, or dismiss them (won't be asked again)

## Scan depth levels

| Level | Name | What it does | Speed |
|-------|------|-------------|-------|
| 1 | Quick | Name matching only | Instant |
| 2 | Normal | Name + content hash comparison (detects exact, modified, renamed) | Sub-second |
| 3 | Deep | Full content similarity scan (finds renamed/similar files, 70%+ threshold) | <1 min for ~500 items |

## Commands

```bash
# Scan current repo for items matching AEC catalog
aec discover

# Scan with specific depth
aec discover --depth 3

# Scan global ~/.claude/ directory
aec discover -g

# Preview what would be found (no changes)
aec discover --dry-run

# Re-surface previously dismissed items
aec discover --rediscover

# Non-interactive: install exact matches, skip the rest
aec discover --yes
```

## Integration with setup

During `aec setup`, you're offered a Normal-depth scan automatically:

```
Scan for files that match items in the AEC catalog? [Y/n]:
```

No depth prompt during setup — it defaults to Normal for a smooth onboarding experience.

## Integration with install/update

When you run `aec install` or `aec update` in global scope, a Quick-level name scan runs in the background. If untracked items matching AEC catalog names are found, you'll see:

```
ℹ Found 2 untracked items matching AEC catalog names. Run `aec discover -g` to review.
```

## Match types

| Type | Meaning |
|------|---------|
| **Exact** | Same name, identical content |
| **Modified** | Same name, different content |
| **Renamed** | Different name, identical content |
| **Similar** | Different name, 70%+ content overlap (Deep scan only) |

## Dismissals

When you skip an item during discovery, it's marked as "dismissed" — AEC won't ask about it again. Dismissals are stored per-repo in `.aec.json` and globally in `~/.agents-environment-config/dismissed-*.json`.

If a dismissed item changes (either your local copy or the AEC catalog version), AEC can automatically re-surface it depending on your preference:

```
If a skill, agent, or rule you previously dismissed changes or gets updated,
should we compare it to AEC tracked items again?
  1) Yes, re-compare automatically
  2) No, keep dismissed until I run aec discover --rediscover
```

## Backup before replace

When replacing a local file with an AEC-managed version, you're asked whether to back up the original. Backups go to `.aec-backup/` with timestamped filenames:

```
.aec-backup/
  engineering-backend-architect.2026-04-10T18-00-00.md
  webapp-testing.2026-04-10T18-00-00/
```

## Contributing dismissed items

When you dismiss items, AEC reminds you that contributions are welcome:

```
You skipped 2 items. If any would be useful to others, consider contributing:
  https://github.com/bernierllc/agency-agents/blob/main/CONTRIBUTING.md
```

## Discovering existing repos from Raycast scripts

If you have existing Raycast scripts from before tracking was added, use `aec discover-repos` to retroactively populate the tracking log:

```bash
aec discover-repos              # Interactive - shows what was found, asks to add
aec discover-repos --dry-run    # Preview without making changes
aec discover-repos --auto       # Auto-add all discovered paths
```
