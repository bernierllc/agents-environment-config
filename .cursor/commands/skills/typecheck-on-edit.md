---
name: "typecheck-on-edit"
description: "Use in any TypeScript repo where Claude Code edits files. Installs a PostToolUse hook that type-checks the project after every Edit or Write of a .ts/.tsx file (tsgo if installed, else the repo's tsc) and surfaces the first errors to the model as a blocking error, plus a SessionStart check that warns when the lockfile is newer than node_modules. Replaces hand-written `npx tsc --noEmit | head -20` hooks that ran on every edit of every file and whose output the model never saw."
tags: ["skill"]
---

# Type-check on edit

## What it installs

`hooks.json` carries two Claude Code overrides, written verbatim into the repo's `.claude/settings.json`:

1. **PostToolUse, `Edit|Write`, filtered with `if`** to `Edit(*.ts*)` and `Write(*.ts*)` (Claude Code's
   native per-path filter: an `Edit(...)` rule never matches Write, so both entries exist). Runs
   `node_modules/.bin/tsgo --noEmit` when present, else `node_modules/.bin/tsc --noEmit`, and exits 0 silently
   when neither exists or the repo has no root `tsconfig.json` (monorepos without one are not checked).
   The root is always checked with `-p .`; when it lists `"references"` (a solution-style root with
   `"files": []`, as Vite scaffolds, or a root with its own sources too), each referenced project is
   also checked with `-p <path>`. References are read with a line grep, so a reference commented out
   with `//` on its own line is skipped, but one inside a `/* */` block is not. Only `node_modules` installs
   (npm, pnpm) are supported: a Yarn Plug'n'Play repo has no `node_modules/.bin` and is skipped. On errors it prints the first 20 lines to stderr and exits 2, which is the only
   way a PostToolUse hook's output reaches the model. Exit-0 stdout is never shown to it.
2. **SessionStart** lockfile freshness: when `pnpm-lock.yaml` is newer than `node_modules/.modules.yaml`
   (or `package-lock.json` newer than `node_modules/.package-lock.json`, or `node_modules` is missing),
   it says so, naming the install command. When `node_modules` is a symlink into another checkout (the
   usual worktree shortcut), it compares the two lockfiles instead, since a fresh worktree's lockfile is
   always newer by mtime. A stale or mislinked `node_modules` otherwise type-checks against the wrong
   packages and nobody notices.

## Install

```
aec install skill typecheck-on-edit
```

Per-agent overrides carry no `when` condition, so install it only in TypeScript repos, one at a time,
and delete any hand-written type-check hook from `.claude/settings.json` in the same commit.

For speed, pin tsgo: `npm i -D @typescript/native-preview` (sub-second warm runs on a Next.js app
where tsc takes 10+ s). CI keeps `tsc`; this hook is a tripwire, not the gate. It checks the whole project, so a pre-existing error anywhere blocks every edit until fixed, and a run past the 60 s timeout is silently unchecked. In a composite monorepo where one referenced project imports another, each project is checked on its own, so a dependent sees its dependency's last-built `.d.ts`, not the edited source: a breaking change across projects passes until `tsc -b` runs. Build mode cannot fix this in a hook, because `tsc -b --noEmit` (and tsgo's) fails with TS6310 on composite references, and an emitting `tsc -b` would write build output on every edit.

## Verify

In a fresh Claude Code session in the repo, have the model write `export const x: number = "s";` into a
`.ts` file. The tool result carries a `PostToolUse:Write hook blocking error` block with the TS2322 line.
Edit a `.md` file: nothing runs.

`bash scripts/selftest.sh` (from this skill's directory) runs both hook commands from `hooks.json` against scratch repos with a stub compiler: clean, diagnostic, no compiler, no tsconfig, references (root plus each reference, `//` lines skipped), and the lockfile check's fresh, stale, missing and symlinked cases. CI runs it through `scripts/test_skill_selftests.py`.
