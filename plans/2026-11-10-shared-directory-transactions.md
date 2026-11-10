# Serialize shared directory configuration

Status: deferred follow-up from PR #131; review severity P2, scheduling pending.

## Root cause and affected surfaces

`aec/lib/hooks/setup.py:configure_directories` reads a repository-wide mapping,
collects answers, and atomically replaces the file. Atomic replacement prevents
partial JSON, but does not serialize read/merge/write. Concurrent installs can
lose different keys or accept competing first choices for the same key. Runtime
readers and installed commands then disagree. All generic hook installs,
upgrades, catalog refreshes, and Playwright post-install use this writer.

Readers include `configured_hooks` and drift repair, verification-writer's
`verification_paths.py`, Playwright's `directories.js`, browser and runner
preflights, and the API verification matrix.

## S1 — Implement a serialized configuration commit

1. Inspect the existing portable locking implementation in
   `aec/lib/managed_symlinks.py` and the locks in `org_config/state.py` and
   `org_config/resolutions.py`. Reuse or extract the portable primitive rather
   than adding another platform-specific implementation.
2. Collect prompt answers outside the lock. Acquire a repository-scoped stable
   lock file (not the atomically replaced JSON inode), reread and validate the
   latest mapping, reject conflicting saved keys, and merge distinct keys.
3. Create requested resource directories and atomically write the merged mapping
   while holding the lock. Return the committed choices for hook rendering.
   Never hold a lock while waiting for interactive input. Report lock and write
   failures; do not silently substitute defaults or success.
4. Keep the lock file stable across processes, including process termination;
   document supported-platform behavior and bounded failure diagnostics.

## Acceptance criteria

Use real subprocesses and deterministic synchronization, not timing sleeps or
mocked writes. Concurrent different-key selections must both survive. Same-key
same-value selections must agree; conflicting selections must yield one winner
and one explicit failure before the loser installs inconsistent hooks. Test
interrupted writers and lock release. Run installed commands and drift checks
after each scenario, and verify runtime readers use the committed custom paths.

Until this ships, concurrent setup against the same repository remains a known
limitation; sequential installs preserve shared choices.

Review: https://github.com/bernierllc/agents-environment-config/pull/131#discussion_r4529380336
