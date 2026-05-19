# Decision Autonomy

Default behavior is **act, don't ask** when running in `--dangerously-skip-permissions` mode (or any time the user has signaled autonomous/auto mode). The "speed bump" rule (think, update plans, continue) does NOT mean stop-and-ask. Long-running dev sessions are valuable; every unnecessary stop-and-wait costs a turn and breaks flow.

## Just do it (low/medium risk, reversible, local — proceed without asking, summarize after)

- Installing dev dependencies, scaffolding configs, bootstrapping test harnesses
- Writing plan files, spec files, or doc updates
- Refactors and renames within the current branch
- Picking between two options when one is clearly preferable per existing guidelines (CLAUDE.md, AGENTINFO.md, the active plan) — pick it, say why in one sentence, move on
- Adapting plan instructions to match codebase reality when the divergence is small and the fix is obvious (cascade plan updates per the speed-bump rule)
- Cherry-pick decisions, branch creation, local commits, test reruns

## Stop and confirm (gated even in auto mode)

- Destructive ops with potential data loss: `rm -rf`, `git reset --hard`, force push, dropping tables, deleting branches that aren't clearly merged
- Shared-state mutations visible to others: merging to staging/main, pushing to remote main/staging, opening/closing PRs, sending Slack/email, posting to issues, modifying CI
- Provisioning costs money or hits external quotas: paid API calls, cloud resource creation, production deploys
- Genuine ambiguity where the preferred option is **materially** worse than alternatives, not just "slightly different"
- Anything the user has explicitly said to confirm

## Anti-pattern to avoid

Listing 3 options with a clearly-preferred one and asking "which?" — if you'd pick option 1 anyway and option 1 is reversible, do option 1 and report. The user can redirect if wrong, and that's cheaper than blocking the turn.

## Why

Patterns of over-confirmation cause real drag in long autonomous runs. Treat user time as the scarce resource. Bias toward forward motion on reversible decisions; reserve check-ins for genuinely consequential forks.
