# Make hook consent durable across all lifecycle transitions

Status: deferred P2 follow-up from PR #131; scheduling pending.

## Root causes and scope

Declarative `execute_apply(..., install_hooks=False)` reaches
`_install_single_item`, which bypasses hook lifecycle completely. No durable
negative consent is recorded, so a later unattended upgrade accepts the default
of enabling hooks. Writing a false flag in this caller alone would preserve the
bypass of declared-directory setup and removal of already installed hooks.

Playwright's legacy pipeline lifecycle retracts marked Git blocks when consent
is disabled but does not restore them when consent becomes enabled. Upgrades do
not execute the separate pipeline-copy post-install action. Blindly wiring on
true would create references to absent scripts for users who never installed
the optional pipeline, and could revive stale scripts after an upgrade.

Affected surfaces: apply_core.execute_apply; install_cmd._install_single_item
and _post_install_playwright_pipeline; hooks.lifecycle, setup, state and
legacy_pipeline; upgrade, catalog refresh, drift repair; legacy copied scripts
and raw Git/custom hooksPath/Husky blocks.

## S1 — Complete consent transition ownership

1. Extend the existing hook lifecycle/setup interface to accept an explicit
   hook policy from declarative apply without bypassing resource configuration.
   Define precedence: explicit false suppresses hooks for that operation and
   persists false; normal install/upgrade reuses saved consent unless explicitly
   changed. Do not mutate global prompt answers or write consent in callers.
2. Route false through the existing installer removal/recording transaction:
   preserve resources, remove recorded hooks, save disabled consent, and only
   then record item installation success. Keep global installs' existing
   no-repository-hook behavior. Propagate setup failures for retry.
3. Make the existing legacy pipeline owner reconcile both disabled and enabled
   states. Establish durable provenance for optional pipeline installation;
   do not treat hook consent as consent to copy an optional pipeline. For an
   opted-in pipeline, reconcile required template scripts before restoring
   marked blocks, using existing destination resolution and block ownership.
   Preserve user content and avoid duplicating generic hook installation.
4. Define failure/retry behavior: missing or failed pipeline preparation must
   be reported, not silently mark active wiring successful. Repeated repair
   must be idempotent. Sweep all callers listed above for the same policy.

## Acceptance tests

- Real apply with hooks false creates declared directories, records disabled
  consent, and installs no hooks. A later version upgrade with yes retains
  disabled consent and does not execute hook commands.
- Apply false over a previously enabled item removes only owned hooks; user
  commands and other items' hooks survive. Explicit later true enables them.
- Playwright optional pipeline enabled install -> disable -> version upgrade
  with explicit true restores executable pre-commit and pre-push pipeline
  commands while preserving user commands. Cover raw Git, custom hooksPath and
  Husky, including optional pipeline never installed, missing scripts, and
  preparation failure/retry. No dangling blocks for an absent pipeline.
- Verify recorded state and drift after each transition, and repeat transitions
  to prove idempotence. Use real repository/filesystem/subprocess behavior.

## Known limitations until S1 ships

Declarative hook suppression is not durable through a later unattended upgrade.
Re-enabling Playwright hook consent during upgrade restores declarative hooks
but does not restore legacy pipeline blocks removed by an earlier opt-out.

Findings:
- https://github.com/bernierllc/agents-environment-config/pull/131#discussion_r4530503124
- https://github.com/bernierllc/agents-environment-config/pull/131#discussion_r4530503136
