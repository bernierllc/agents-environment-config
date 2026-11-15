# Confine the remaining setup writers to the repo

**Source:** review of PR #136 (Codex P1 r4576120153 and the writer sweep the
reviewer asked for). Status: not started.

## Root cause

PR #136 added `aec/lib/confine.py` (`escapes(root, paths)`): a path is only
written when it sits under the repo root with no symlink in any component.
Every writer of agent instruction files (migrate, tidy, setup's agent files,
the Port Registry section, the old rules-path updater, rollback) goes through
it, and `test_every_writer_refuses_paths_that_leave_the_repo` runs each one.

Older setup writers that PR #136 did not touch still follow symlinks, so a
linked file or directory in a repo can send their write to a shared location
outside it:

| Writer | Location | Writes |
|---|---|---|
| gitignore patterns | `aec/commands/repo.py` (`open(gitignore_path, "a")`) | `.gitignore` |
| git essentials `.gitignore` | `aec/commands/repo.py` `_create_git_essentials` | `.gitignore` |
| git essentials templates | `aec/lib/git_setup.py` `write_git_essential` / `_write_rendered` | `.github/…`, PR/issue templates, etc. |
| plans migration | `aec/commands/repo.py` (`shutil.move` into the plans dir) | plan files |

Raycast scripts (`repo.py`, `raycast_scripts/`) are written into AEC's own
checkout, not a user repo, so they are out of scope.

## Correct fix

1. Call `escapes(project_dir, [dest])` before each write above; on a problem,
   warn and skip that file (same shape as `_copy_agent_files`).
2. Add each writer to `CALLERS` in
   `tests/test_migrate_rollback_cmd.py::test_every_writer_refuses_paths_that_leave_the_repo`
   with a symlinked-file and a symlinked-directory case.
3. Sweep again with
   `grep -nE "write_text|write_bytes|open\(.*['\"][wa]|shutil\.(move|copy)|os\.replace" aec/`
   and list any writer that is intentionally outside a repo.

## Priority

P2: needs a symlink a user (or a cloned repo) placed on purpose; it is the
same class as the P1 fixed in PR #136, so do it before the next setup change.
