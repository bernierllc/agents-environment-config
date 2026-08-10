---
name: "ship"
description: "Use when work on the current branch is ready to land — "ship this", "/ship", "wrap this up and open the PR", or the end of any implementation session. Runs the closing ritual as one command: verify (typecheck + tests), conventional commit, push, draft PR, external-tracker sync, and a five-line report."
tags: ["skill"]
---

# Ship

Land the current branch's work with evidence. One pass, no skipped gates. If any gate
fails, stop there, report plainly, and fix or hand back — never ship red.

## 0. Preflight

- `git status` + `git branch --show-current`. Nothing to ship (clean tree, no unpushed
  commits) → say so and stop.
- Resolve the repo's actual default branch to a bare local name: run
  `git symbolic-ref --short refs/remotes/origin/HEAD` first, and only if it succeeded
  strip the remote prefix from its output (`sed 's|^origin/||'`). If the command failed
  **or** produced empty output, fall back to
  `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name` — never pipe the
  two steps blindly (the pipeline masks a symbolic-ref failure and yields an empty
  name), never assume `main`/`master`, and never compare a remote-qualified name like
  `origin/main` against `git branch --show-current`. On that branch with anything to ship — uncommitted work
  **or** unpushed local commits → move it to a feature branch first: create one named
  for the work at HEAD (unpushed commits ride along), then point the local default
  branch back at its upstream — from the feature branch, `git branch -f <default>
  origin/<default>`. Never commit to or push the default branch directly.
- Check nothing staged is gitignored or secret-shaped (`.env*`, keys, tokens). Never
  force-add ignored files.

## 1. Verify

- Run the repo's typecheck and full test suite (from repo scripts/config — never
  `--watch`). No typechecker/tests → note that in the report rather than inventing one.
- Any failure → **stop**. Report the failing output. Fixing is a separate decision from
  shipping; do not "fix the test to pass" here.

## 2. Commit

- Stage only the files this work touched — review `git status` file-by-file, not
  `git add -A`.
- Conventional commit message from the actual diff, following the repo's conventions
  (check recent `git log` for style; commitlint rules win).
- Pre-commit hooks run; never bypass them (`--no-verify` is forbidden). Hook failure
  unrelated to your files → report it, don't work around it.

## 3. Push + draft PR

- `git push -u origin <branch>`.
- If `gh` is available and the remote is a GitHub repo: open a **draft** PR against the
  repo's integration branch (an existing `staging`/`develop` branch, else the default
  branch). Body: what changed, why, test evidence (suite name + pass count), and any
  follow-ups. Respect user/project rules that gate PRs into the default branch — when
  gated, push only and put "open PR" in the report's next step.
- PR already open for this branch → push updates it; skip creation.

## 4. Tracker sync

- If the user's global or project instructions configure an external work tracker,
  update this branch's row in the same turn: swap the source link to the PR URL once one
  exists, refresh notes/status. No row yet → create it.
- Tracker unavailable or permission-blocked → append the same record as one JSON line to
  the state dir's activity log (state dir per user config; default `.orchata/`,
  `activity.jsonl`) and note the fallback in the report. Never block the ship on the
  tracker.

## 5. Report (exactly this shape)

```
branch:  <name>
commit:  <hash> <subject>
PR:      <url | "not opened — <why>">
tests:   <suite result | "none configured">
tracker: <synced | fallback | none configured>
next:    <one concrete step>
```
