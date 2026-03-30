---
name: "commit"
description: "Use when the user wants to commit and optionally push their changes. Standardizes the commit workflow with commitlint validation, gitignore checks, and safe push procedures."
tags: ["skill"]
---


# Commit Skill

Handles the full commit workflow: review changes, validate, commit with conventional commits, and optionally push.

## Workflow

### 1. Review current state

Run these in parallel:
- `git status` (never use `-uall`)
- `git diff --staged` and `git diff` to see all changes
- `git log --oneline -5` to match existing commit message style

### 2. Validate before staging

For any new files or directories being added:
- Run `git check-ignore <path>` to verify they are not gitignored
- If gitignored, stop and tell the user — do not attempt the commit

### 3. Stage files

- Stage specific files by name — do not use `git add -A` or `git add .`
- Never stage `.env` files, credentials, or secrets

### 4. Write the commit message

Format: `type(scope): lowercase description`

Rules:
- **type**: feat, fix, refactor, test, docs, chore, ci, style, perf, build
- **scope**: lowercase, describes the area (e.g., auth, api, ui, db)
- **subject**: lowercase first letter, no period at end, imperative mood
- Keep the first line under 72 characters
- Add a body (separated by blank line) only if the "why" isn't obvious from the subject
- Always end with: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

Use a HEREDOC for the message:
```bash
git commit -m "$(cat <<'EOF'
type(scope): description here

Optional body explaining why.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### 5. Handle hook failures

If a pre-commit hook fails:
- Read the error output
- Fix the issue (lint errors, type errors, test failures)
- Re-stage the fixed files
- Create a NEW commit — never use `--amend` after a hook failure since the commit didn't happen
- Never use `--no-verify` to bypass hooks

### 6. Push (only if requested)

If the user asked to push:
- `git fetch` first
- Check if remote has diverged: `git log --oneline HEAD..origin/$(git branch --show-current)`
- If diverged, rebase before pushing (ask user first)
- Push with `-u` flag to set upstream if needed
- Never force push to main/master without explicit user confirmation

### 7. Verify

Run `git status` after commit to confirm clean state.

## What NOT to do

- Do not use `git add -A` or `git add .`
- Do not use `--no-verify` or `--no-gpg-sign`
- Do not amend previous commits unless explicitly asked
- Do not push unless the user specifically asked to push
- Do not capitalize the commit subject
- Do not read or explore code beyond what git commands show — this is a commit skill, not a code review
