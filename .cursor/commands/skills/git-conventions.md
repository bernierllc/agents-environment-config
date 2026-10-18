---
name: "git-conventions"
description: "Use when committing in any Bernier LLC repo, or when a commit is rejected with "commit-msg: subject must be". Enforces conventional commits with a lowercase subject (`type(scope): description`) through a git commit-msg hook that aec installs into the repo's active hooks directory. Replaces the commitlint that the global rules used to name but no repo ever had."
tags: ["skill"]
---


# Git conventions

One rule, enforced where the commit happens: the first line of every commit is
`type(scope): lowercase description`.

- **types:** `feat fix docs chore test refactor perf ci build revert release style`
- **scope:** optional, `[a-z0-9._/,-]+` (`fix(senders,campaigns):` is fine), `!` before the colon for breaking changes
- **description:** starts with a lowercase letter or a digit; anything after that is free, so GitHub's squash suffix `(#815)` passes
- **passthrough:** `Merge …`, `Revert "…"`, `fixup! …`, `squash! …`, `amend! …` are git's own subjects and are not checked

## Install

```
aec install skill git-conventions
```

`hooks.json` carries a `git` override for `commit-msg`. aec writes it as a delimited block into
the repo's active hooks directory (`.husky/` if present, else `core.hooksPath`, else `.git/hooks`),
so it runs in every worktree of that repo. The block runs in a subshell, so a passing subject falls through to whatever else the hook file runs (husky lines, other aec blocks). The check is inline in the hook, so it works in
worktrees where `.claude/skills/` is gitignored and absent.

## Verify

```
sh "$(aec info skill git-conventions --path 2>/dev/null || echo .claude/skills/git-conventions)/scripts/selftest.sh"
```

or by hand: `git commit --allow-empty -m 'Bad Subject'` is rejected, `git commit --allow-empty -m 'chore(hooks): check the hook (#1)'` passes (then `git reset --hard HEAD~1`).

## Why a hook, not commitlint

The global rules said "Commitlint enforces it." Nothing did: no repo had commitlint, husky or a
`commit-msg` hook. A dependency-free hook that aec installs is the smallest thing that is true
in every repo, including ones with no `package.json`.
