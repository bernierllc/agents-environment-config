---
name: "pr-merge-flow"
description: "Use after opening or pushing to a pull request, while waiting on CI, or before merging the base branch (staging/main) into a feature branch. Keeps parallel PRs from restarting each other's CI and review — hand the merge to GitHub auto-merge, wait on checks in the background, and sync the base only on a real conflict. Ships a PreToolUse guard that enforces it."
tags: ["skill"]
---

# PR merge flow

Several agents land PRs into the same base branch. Each merge to the base moves it. If
every other agent then merges the base into its own branch, each of those PRs rebuilds CI
and restarts review. Nothing merges, and every agent keeps paying to watch its own
rebuild. This skill stops that.

## Rules

1. **Don't sync the base into a mergeable PR.** Check first:
   `gh pr view <n> --json mergeStateStatus --jq .mergeStateStatus`
   - `DIRTY` → a real conflict: merge the base in, resolve, push.
   - `BEHIND` → the base's ruleset requires up-to-date branches: update (`gh pr update-branch <n>`).
   - `CLEAN` / `UNSTABLE` / `BLOCKED` / `HAS_HOOKS` → **leave the branch alone.** GitHub
     can already merge it. Pull requests are tested as the branch merged into the current
     base, and the base's own push CI catches anything that breaks once changes combine.
   - A base change to CI config or `.gitignore` is **not** a reason to sync: the PR picks
     up the new workflow on its next push anyway.
2. **Hand the merge to GitHub.** When the review loop is done:
   `gh pr merge <n> --auto --squash` (use `--merge` for long-lived-branch promotions, e.g.
   staging → main), then stop. GitHub merges it once the required checks pass. Nobody
   watches. If the repo has auto-merge disabled, enable it:
   `gh api -X PATCH repos/<owner>/<repo> -F allow_auto_merge=true`.
3. **Wait for free.** Watch checks with `gh pr checks <n> --watch --fail-fast` run in the
   background (Claude Code: `run_in_background`). It costs nothing until it exits, and the
   harness wakes you. Never write a `sleep`/poll loop.
4. **Never sync worktrees in a loop.** `for w in …; do git -C $w merge origin/staging` is
   the exact pattern that rebuilt every open PR at once. Handle one PR at a time, by rule 1.
5. **PRs open ready for review, never as drafts,** and on the right repo: in a fork, run
   `gh repo set-default <owner>/<repo>` once or pass `-R`.

## The guard

`hooks.json` wires `scripts/pr-guard.py` as a Claude Code PreToolUse hook into each repo
this skill is installed in (`aec install skill pr-merge-flow`; a global install leaves
hooks dormant). It blocks:

- `git merge|pull|rebase <base>` when the current branch's open PR into `<base>` is mergeable;
- the same command in a directory it can't resolve (`$w` in a loop);
- `gh pr create --draft` and `gh pr ready --undo`;
- `gh pr create` without `-R` in a fork that has no `gh repo set-default` (it would open
  the PR on the upstream repo).

It fails open when there's no open PR, `gh` is unavailable, or GitHub reports `UNKNOWN`.

**Scope:** the guard catches the commands agents habitually run, not a determined
evasion; it is a speed bump, not a Bash sandbox. Parsing errs toward checking more:
comments and heredoc bodies are dropped, `( … )` scopes `cd`, and input `shlex` can't
parse is split on every operator character. Exotic Bash that still slips past is out of
scope unless an agent actually ran it.

**Override:** when you genuinely need a specific commit from the base (a fix your tests
depend on), append `# sync-base: <reason>` to the command. Say which commit and why.
The reason stays in the transcript.

Self-check: `python3 pr-merge-flow/tests/test_pr_guard.py`.
