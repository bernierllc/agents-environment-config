# Per-repo records in a catalog

An org catalog is a git repo. Enrolling it (`aec org enroll`) clones all of it to
`~/.aec/orgs/<org-id>.d/repo/`, not just the config file and the items it lists, and
`aec update` refreshes that clone; `aec org apply` only applies what is already there.
Anything else committed in the catalog is readable by skills and scripts on every enrolled
machine, so a catalog can carry data about *repos*, not only about installable items.

This is a convention today, not an AEC feature: AEC delivers the files but does not read
them. See `plans/2026-11-14-catalog-repo-records.md` for the feature that would make AEC
understand them.

## Example: branch roles and review-setting expectations

One file per repo, `repos/<name>.yaml`:

```yaml
repo: example-org/my-app
default_branch: staging        # what GitHub reports as default
integration_branch: staging    # where PRs land and code deploys
prod_branch: main              # where production deploys from
deploy_flow: staging-then-promote
thread_resolution:
  expected: required           # required | waived
  # waived needs both of these; the check fails once recheck_after has passed
  # waiver_reason: why it is off
  # recheck_after: 2026-12-14
  status: on                   # written by the check: on | off | no-ruleset
  checked_at: 2026-11-14T22:00:00Z
```

Review and merge skills read the record instead of assuming `main` is production. Do not
assume it either: a repo's default branch may be its deploy branch, and `main` may be the
promotion target.

## Read the approved commit, not the working tree

`aec update` refreshes the clone in place: it fetches the catalog's ref and checks out the new
commit into `~/.aec/orgs/<org-id>.d/repo/` *before* any review. For an unsigned or guided org
the new config is then only staged for review, and `aec org apply --decline` discards the
staged config but does not move the clone back. So the files in that directory can be
upstream bytes nobody has approved. A skill or script that reads them is trusting unreviewed
content.

The approved commit is `resolved_commit` in `~/.aec/orgs/<org-id>.state.json`; it changes only
when a change is promoted (a signed managed org promotes at refresh, any other org at
`aec org apply`). Read the record at that commit:

```sh
commit=$(jq -r .resolved_commit ~/.aec/orgs/example-org.state.json)
git -C ~/.aec/orgs/example-org.d/repo show "$commit:repos/my-app.yaml"
```

The commit's objects stay in the clone, so this works even while the working tree is ahead.
Run the catalog's check script the same way: from a checkout of `$commit` (for example
`git worktree add --detach <tmp> "$commit"`), never from the live directory. A skill that
cannot do this should say so and stop rather than read the working tree.

## Checking records against reality

A record is a claim, so it needs a check that compares it with the live system. The catalog
ships a script that calls the GitHub API for each record and reports, per repo:

- the default branch no longer matches the record (ERROR: confirm the setup, update the record);
- the integration or prod branch does not exist (ERROR);
- the setting is off where it is `required` (ERROR), or off under a waiver (WARN until
  `recheck_after`, then ERROR).

The check runs from the approved commit (see above) when a skill operates on a repo, so a
stale record is caught at the moment it matters. Nothing schedules it. A scheduled sweep can be added with cron or launchd, the way
`scripts/prune-merged-worktrees.sh` is scheduled, if you want records refreshed between
operations.

Keep tests for such a script on pure functions fed with real captured API responses; a
hand-written fake of the API proves only that the fake agrees with itself.
