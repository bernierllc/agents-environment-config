# Catalog support for per-repo records

Status: planned; scheduling pending.

## Root cause and affected surfaces

A catalog can already hold per-repo data (branch roles, review-setting expectations) because
`aec org apply` clones the whole catalog repo (`docs/orgs/catalog-repo-records.md`). AEC does
not know the data exists. Consequences today: each skill must locate the clone path itself,
nothing validates the record schema, `aec org status` cannot report a stale record, and the
live check is a script the catalog author wrote and each skill has to know to run.

Surfaces: `aec/lib/org_config` (schema, fetch, state), `aec org apply|status|doctor`,
`docs/orgs/authoring-org-configs.md`, and every skill that reads branch roles.

## S1 — Declare record types in the org config

1. Add an optional top-level `records:` block to the org config schema: a record type
   (`repos`), a directory in the catalog, a JSON Schema for each record, and an optional
   `check` command path inside the catalog.
2. Validate records at `aec org apply` and report failures the way item conflicts are reported.
3. Tests with a local bare git repo catalog and example-org records.

## S2 — Read access for skills

1. `aec org record <type> <name>` prints the record as JSON for the enrolled org that owns it.
   Skills call it instead of building the clone path.
2. Conflicting records across enrolled orgs are surfaced, not silently picked.

## S3 — Run the catalog's check

1. `aec org check [<type>] [--name <name>]` runs the declared `check` and exits non-zero on
   error. Output is the check's own.
2. Decide whether `aec doctor` includes it. Do not add a scheduler: lazy checking at
   operation time is enough, and an optional cron/launchd recipe belongs in the docs.

## Done when

An enrolled machine can ask AEC for a repo's record, `aec org apply` rejects a malformed
record, and `aec org check` reports drift, with tests for each.
