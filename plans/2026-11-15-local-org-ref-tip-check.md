# Ref-only tip check for locally enrolled orgs

**Source:** Codex P2 r4579980336 on PR #132. Status: not started.

## Root cause

The moved-ref check for ref-only custom sources (a branch tip that advanced since
the approved commit) lives inside `_refresh_one` in `aec/commands/org.py`, and
`refresh_remote_orgs` skips every org whose `source_of_record` is `local`. A
locally enrolled, unsigned config with a ref-only source therefore never sees its
branch move: `aec update` reports no pending review and later applies keep
resolving the previously approved commit.

`git+` and url enrollments are not affected: they go through `_refresh_one`.

## Correct fix

1. Split the tip check out of `_refresh_one` into its own function
   (`_check_source_tips(paths, st, cfg)`) that reads the org's enrolled config,
   resolves each ref-only source's tip, and sets the `review` pending when a tip
   moved.
2. Call it from `_refresh_one` (unchanged behavior) and from `refresh_remote_orgs`
   for local orgs, without refetching their config file.
3. Cover it with tests: local org + moved branch reports "pending review" and a
   later `aec org apply` approves it; local org + unmoved branch stays "unchanged".

## Affected surfaces

`aec/commands/org.py` (`refresh_remote_orgs`, `_refresh_one`), `aec update`'s org
refresh, `tests/commands/test_org_custom_sources.py`, `docs/orgs/` update-flow text.

## Done when

`aec update` on a locally enrolled org with a ref-only source reports pending
review after the branch advances, and `aec org apply` converges, both under test.
