# Troubleshooting

Common issues and recovery steps. Run `aec doctor` first to identify problems -- it checks all of the items below automatically.

## Prerequisites Not Met

**Symptom:** Commands fail or `aec doctor` reports missing directories.

**Fix:** Run the full installation:

```bash
aec install
```

This creates `~/.agents-environment-config/`, `~/.agent-tools/`, and all required subdirectories.

## Broken Symlinks in ~/.agent-tools/

**Symptom:** `aec doctor` shows agent-tools subdirectories exist but symlinks are missing or broken.

**Diagnosis:** Check symlink targets:

```bash
ls -la ~/.agent-tools/rules/agents-environment-config
```

**Fix:** Re-run agent-tools setup:

```bash
python -m aec agent-tools setup
```

This recreates the symlinks from `~/.agent-tools/{rules,agents,skills,commands}/agents-environment-config` to the correct repo paths.

## Rule Parity Failures

**Symptom:** `aec rules validate` reports mismatches between `.cursor/rules/` and `.agent-rules/`.

**Cause:** Rules were edited in `.cursor/rules/` without regenerating `.agent-rules/`, or `.agent-rules/` was edited directly (it's auto-generated).

**Fix:**

```bash
aec rules generate
aec rules validate
```

Never edit `.agent-rules/` directly -- always edit in `.cursor/rules/` and regenerate.

## Git Hook Failures

**Symptom:** Pre-push or post-merge hooks fail with sync errors.

**Common causes:**
- Submodules not initialized
- Submodule on detached HEAD
- Uncommitted changes in submodules

**Fix submodule state:**

```bash
git submodule update --init --recursive

# If detached HEAD:
cd .claude/agents && git checkout main && cd ../..
cd .claude/skills && git checkout main && cd ../..
```

**Skip hooks temporarily:**

```bash
SKIP_SYNC=1 git push
```

## Missing .aec-managed Marker

**Symptom:** `aec doctor` warns that `~/.agent-tools/` exists but isn't marked as AEC-managed.

**Fix:**

```bash
aec install
```

The marker file prevents AEC from accidentally modifying a manually-managed `~/.agent-tools/` directory.

## Agent Directory Issues

**Symptom:** `aec doctor` shows `~/.claude/` or `~/.cursor/` subdirectories not linked.

**Note:** These are only relevant if the corresponding agent is installed. Missing directories for agents you don't use are not a problem.

**Fix:** Re-run installation to recreate links:

```bash
aec install
```

## Platform-Specific Issues

### macOS: Raycast Scripts

Raycast launcher scripts are macOS-only. They won't be generated on Linux or Windows. This is expected behavior, not an error.

### Windows: Junctions vs Symlinks

On Windows, AEC uses directory junctions instead of symlinks (junctions don't require admin privileges). If you see permission errors during symlink creation, ensure you're running from a normal (non-elevated) terminal.

## Recovery Checklist

When in doubt, this sequence fixes most problems:

```bash
aec install              # Recreate all directories and symlinks
aec rules generate       # Regenerate .agent-rules/ from .cursor/rules/
aec rules validate       # Verify parity
aec doctor               # Confirm everything is healthy
```
