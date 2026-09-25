# Managed symlink ownership by record, not by path name

**Status:** Proposed (found in PR #86 review, Codex round 8)
**Priority:** Tier 2 — proposed; placement awaiting Matt's confirmation

## Root cause

`aec.lib.filesystem.is_our_symlink()` decides whether AEC owns a symlink by
substring-matching the link's raw target for `agents-environment-config` or
`.agent-tools`. That is a naming heuristic, not a record of ownership:

- A checkout cloned under another name (`git clone … aec`) produces links
  AEC does not recognise as its own. Once that checkout moves or is
  recloned, the dangling links are treated as foreign and never repaired.
- Any unrelated link whose target happens to contain either substring is
  treated as AEC's and may be replaced.

## Correct fix

Record every symlink AEC creates (link path → source path) in AEC's own
state under `~/.agents-environment-config/`, written by `create_symlink`
callers at link time. `is_our_symlink(path)` becomes a lookup: the link is
ours iff `path` is recorded. Moving or recloning the repo then repairs
cleanly, because ownership no longer depends on the target path.

Migration: on first run, adopt existing links that match the old heuristic
into the record, once, then drop the heuristic.

## Affected surfaces

- `aec/lib/filesystem.py` — `is_our_symlink`, `create_symlink`
- `aec/commands/agent_tools.py` — agent directory links
- `aec/commands/install.py` — `_prompt_claude_statusline` stale-link repair
- Any `aec uninstall` / `prune` path that removes links it believes it owns
- Tests: a checkout under a non-`agents-environment-config` name, moved,
  then re-installed, must repair every link.
