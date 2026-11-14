# Seed Data Management

## Core Principle

Not all "data the app needs" is the same thing. Treat data as one of three distinct tiers — reference, seed, or fixture — and route each tier through the correct mechanism. Conflating them is the root cause of broken deploys, flaky tests, and dirty production databases.

## Three Categories of Application Data

### Reference Data (→ Migrations)

Data the application **depends on to function**. If it's missing, the app breaks.

**Examples:** workflow statuses, system roles, permissions, feature flags, lookup tables, enum values stored in DB

**Deployed to:** ALL environments, automatically
**Mechanism:** Database migrations (not seed scripts)

- Must be idempotent (`INSERT ... ON CONFLICT DO NOTHING` or equivalent)
- Versioned alongside schema changes — the migration that adds a `status` column also inserts the valid status values
- Tested: migration tests verify reference data exists after running

**Framework patterns:**

- **Supabase:** Include in migration SQL files under `supabase/migrations/`
  ```sql
  -- supabase/migrations/20260410_add_workflow_statuses.sql
  CREATE TABLE workflow_statuses (id text PRIMARY KEY, label text NOT NULL);
  INSERT INTO workflow_statuses (id, label) VALUES
    ('draft', 'Draft'),
    ('review', 'In Review'),
    ('published', 'Published')
  ON CONFLICT (id) DO NOTHING;
  ```
- **Alembic:** Use `op.bulk_insert()` in migration `upgrade()` functions
  ```python
  def upgrade():
      statuses = op.create_table('workflow_statuses', ...)
      op.bulk_insert(statuses, [
          {'id': 'draft', 'label': 'Draft'},
          {'id': 'review', 'label': 'In Review'},
      ])
  ```
- **Prisma:** Include in migration SQL or use `prisma db seed` with a migration-aware script that guards on existing rows.
- **Django:** Use data migrations (`RunPython` in migration files) — never `loaddata` fixtures at deploy time.

### Seed Data (→ Bootstrap Scripts)

Baseline operational data to bootstrap a usable environment. Not required for the app to function, but required for it to be useful.

**Examples:** first admin user, default organization, initial system settings, welcome content

**Deployed to:** ALL environments, but values vary per environment

- Dev/staging: known credentials, test-friendly config
- Production: secure credentials sourced from env vars, minimal config

**Mechanism:** Explicit seed scripts, run on demand (`make seed`, `npm run seed`)

- Must be idempotent — safe to re-run without duplicating data
- Never auto-run on deploy
- Environment-aware: reads `NODE_ENV` / `APP_ENV` to determine credential source

**Framework patterns:**

- **Supabase:** `supabase/seed.sql` (runs on `supabase db reset`)
- **Alembic:** `scripts/seed.py` invoked via `make seed`
- **Prisma:** `prisma/seed.ts` (runs via `prisma db seed`)
- **Django:** Custom management command (`python manage.py seed`) with env-gated credential lookup

### Fixture Data (→ Test Framework)

Synthetic data for development and testing. Never touches production.

**Examples:** test users, sample content, edge-case data, demo scenarios, performance test datasets

**Deployed to:** Local and staging ONLY, never production

**Mechanism:**

- **Automated tests:** Test factories/builders that create data per-test, rolled back after each test
- **Local dev:** Dev seed scripts for convenience data (idempotent, re-runnable)
- **Staging:** Explicit staging-only seed target, run manually post-deploy

**Key principle:** Tests must never depend on pre-existing data. Each test declares or creates what it needs. If a test breaks when run in isolation, its data setup is wrong.

## Decision Flow

Use this flow to classify any piece of data before you write it down anywhere:

1. **Does the application crash, misbehave, or render an invalid UI if this row is absent in production?**
   - Yes → **Reference data**. Goes in a migration.
   - No → continue.
2. **Does a real human user or operator need this row to exist before they can use the system (e.g. the first admin, the default org)?**
   - Yes → **Seed data**. Goes in a bootstrap script, run on demand.
   - No → continue.
3. **Is this row only needed for tests, demos, local exploration, or staging walkthroughs?**
   - Yes → **Fixture data**. Goes in test factories or a dev/staging-only seed script. Never migrations, never production.

If you cannot answer "yes" to any of the three, you probably do not need the data at all — push back before adding it.

## Environment Strategy

| Environment     | Reference Data             | Seed Data               | Fixture Data         |
| --------------- | -------------------------- | ----------------------- | -------------------- |
| Automated tests | Via migrations (fresh DB)  | Not used                | Per-test factories   |
| Local dev       | Via migrations             | `make seed` on demand   | Dev seed script      |
| Staging         | Via deploy migrations      | Explicit post-deploy    | Staging seed script  |
| Production      | Via deploy migrations      | Bootstrap once          | Never                |

### Test Environment

- **Fresh database per test run.** Spin up a clean instance (Docker), apply migrations (which include reference data), run tests.
- **Test isolation:** Each test gets a transaction that rolls back, or truncate-and-reseed between tests.
- **No dirty environments.** Tests must not depend on what ran before them.

### Local Development

- After `make db:reset` or equivalent, run `make seed` to populate convenience data.
- Seeds are idempotent — re-running is safe and expected.
- Reference data is already present from migrations; seed scripts add operational and convenience data.

### Staging

- Migrations deploy automatically (same pipeline as production), bringing reference data with them.
- Staging-specific data (test accounts, demo content) applied via a separate, explicitly-run target.
- Never automatic on deploy — prevents accidental test data leakage if the pipeline is misconfigured.

### Production

- Migrations only. Reference data arrives with schema changes.
- Bootstrap seed (first admin user) runs once during initial setup.
- No fixture data, ever.

## Idempotency & Re-runnability

Every seed and reference-data insert MUST be safe to run more than once. The rules:

- **Guard every insert.** Use `ON CONFLICT DO NOTHING`, `INSERT ... WHERE NOT EXISTS`, `upsert`, or an explicit existence check before inserting.
- **Prefer stable natural keys** (slugs, enum strings) over auto-generated UUIDs so re-runs converge on the same row.
- **Updates must be explicit.** If a seed needs to change an existing row, use `upsert` / `ON CONFLICT DO UPDATE` — never a blind insert that silently no-ops.
- **No order-dependent side effects.** A seed script must produce the same end state whether run once or ten times.
- **Deletes are a smell.** If a seed script deletes data, it probably should be a migration instead.
- **Fail loud on drift.** If a required reference row is missing at boot time, the app should crash with a clear message — do not paper over it with lazy inserts in application code.

## Anti-Patterns

Do NOT do any of the following:

- **Do not commit fixture data (test users, demo orgs) into migrations.** It will end up in production.
- **Do not put reference data in seed scripts.** Seeds are opt-in; migrations are not. Reference data must ride with the schema.
- **Do not let seed scripts run automatically on deploy.** An accidental re-run can clobber env-specific credentials or re-introduce deleted rows.
- **Do not hardcode production credentials** in a seed script. Read them from env vars; fail hard if missing in production.
- **Do not depend on test-order** for fixture state. Each test must create its own data.
- **Do not use `loaddata`, `db seed`, or fixture loaders as a substitute for migrations** when the data is actually reference data.
- **Do not insert without a conflict clause.** A non-idempotent seed is a broken seed.
- **Do not mix all three tiers in one script.** Split reference (migrations), seed (bootstrap), and fixture (test/dev) into separate files with separate entry points.
- **Do not silently mutate production reference data from application code.** Changes ship via new migrations with a clear audit trail.

## When This Rule Applies

If you are doing ANY of the following, you must consider seed data implications:

1. **Creating a new database table** — Does it need default rows? → Reference data migration
2. **Adding a status/enum/role field** — What are the valid values? → Reference data migration
3. **Adding a feature that requires data to exist** — First user? Default org? → Seed data script
4. **Writing tests** — Don't assume data exists. Create what you need per-test.
5. **Modifying existing reference data** — New status value? New role? → New migration that adds it
6. **Setting up a new environment** — Which of the three tiers does it need, and in what order?

**When in doubt, invoke the `seed-data` skill for a guided walkthrough.**

## Related

- **Skill:** `.claude/skills/seed-data/` — interactive walkthrough for classifying and wiring up a new piece of data.
- **Connections:** See `frameworks/database/connection-management.mdc` for how seed scripts should acquire (and release) database clients.
- **Testing:** See `frameworks/testing/standards.mdc` for per-test fixture patterns and test isolation rules.