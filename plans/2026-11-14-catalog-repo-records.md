# Catalog support for per-repo records

Status: planned; scheduling pending.

## Root cause and affected surfaces

A catalog can already hold per-repo data (branch roles, review-setting expectations) because
enrollment (`aec org enroll`) clones the whole catalog repo and `aec update` refreshes that
clone; `aec org apply` only promotes the staged config (`docs/orgs/catalog-repo-records.md`).
AEC does not know the data exists. Consequences today: each skill must locate the clone path
itself, and must know to read at the approved commit (`resolved_commit`) because the refresh
moves the working tree ahead of approval for unsigned and guided orgs, and a re-clone drops the
old `resolved_commit` object; the signature covers the config only, so records and check
scripts in the same commit are unauthenticated; nothing validates the
record schema, `aec org status` cannot report a stale record, and the live check is a script
the catalog author wrote and each skill has to know to run.

Surfaces: `aec/lib/org_config` (schema, fetch, state), `aec org apply|status|doctor`,
`docs/orgs/authoring-org-configs.md`, and every skill that reads branch roles.

## S1 — Declare record types in the org config

1. Add an optional top-level `records:` block to the org config schema: a record type
   (`repos`), a directory in the catalog, a JSON Schema for each record, and an optional
   `check` command path inside the catalog.
2. Validate records at `aec org apply`, against the commit being approved, and report failures
   the way item conflicts are reported.
3. Authenticate what AEC reads: extend the signature to cover the record files and the check
   script (a manifest of their hashes inside the signed config, or a signed tree hash), and
   refuse records and checks the signature does not cover. Until then `aec org record` and
   `aec org check` must say the records are unauthenticated.
4. Keep a durable ref for the promoted commit (for example `refs/aec/approved`, updated at
   promotion) and make the broken-clone recovery in `_fetch_remote` preserve it, so reading at
   `resolved_commit` cannot hit a missing object.
5. Tests with a local bare git repo catalog and example-org records, including a re-clone
   after a broken clone and a record changed in a commit whose config is unchanged.

## S2 — Read access for skills

1. `aec org record <type> <name>` prints the record as JSON for the enrolled org that owns it,
   read from `resolved_commit` (`git show`), never from the refreshed working tree. Skills
   call it instead of building the clone path.
2. Conflicting records across enrolled orgs are surfaced, not silently picked.

## S3 — Run the catalog's check

1. `aec org check [<type>] [--name <name>]` runs the declared `check` from a checkout of
   `resolved_commit` and exits non-zero on error. Output is the check's own.
2. Decide whether `aec doctor` includes it. Do not add a scheduler: lazy checking at
   operation time is enough, and an optional cron/launchd recipe belongs in the docs.

## Done when

An enrolled machine can ask AEC for a repo's record, `aec org apply` rejects a malformed
record, and `aec org check` reports drift, with tests for each.
