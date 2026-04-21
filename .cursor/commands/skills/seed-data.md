---
name: "seed-data"
description: "Use when creating, modifying, or auditing application data that must exist in databases across environments — classifies data as reference/seed/fixture, picks the right framework workflow, and enforces idempotency and environment targeting."
tags: ["skill"]
---


# Seed Data Classification & Generation

Use this skill whenever data has to live in a database across environments — new lookup tables, enum rows, roles, statuses, baseline accounts, demo content, or test inputs. It walks the agent through classifying the data, picking the correct framework workflow, and producing idempotent, environment-aware artifacts.

Triggers:

- Creating a new table that ships with default rows
- Adding status fields, roles, permissions, plan tiers, or any enum-like data stored in the DB
- A feature that only works once baseline data is loaded
- Writing tests that depend on specific data being present
- Modifying existing reference data (adding a new status, renaming a role)

## Workflow

### 1. Classify every piece of data

For each new or modified row, run the checklist top to bottom. Stop at the first match.

| Question | Yes → | No → |
|---|---|---|
| 1. Does the application break (500s, missing joins, failing queries) without this data? | **Reference data** — ships via migration to every environment | Continue |
| 2. Is this data required for the app to be *useful* out of the box (first admin, default org, starter workspace)? | **Seed data** — ships via seed script; value may vary per environment | Continue |
| 3. Is this data needed only for development convenience, demos, or test scenarios? | **Fixture data** — lives in test infrastructure or a dev-only seed target; never production | — |

Decision summary:

- **Reference data** — migration. Versioned, idempotent, runs everywhere automatically. Example: `workflow_statuses` rows the app queries on every request.
- **Seed data** — seed script. Idempotent, runs per environment, values may differ (dev admin password ≠ prod admin password). Example: the first admin user, a default "System" organization.
- **Fixture data** — test factories or dev-only seed. Example: `alice@test.com`, sample blog posts, dummy invoices. Never deploys to production.

### 2. Pick the framework workflow

#### Supabase

1. **Reference data:** new migration file `supabase/migrations/YYYYMMDDHHMMSS_add_<name>.sql`. Use idempotent `INSERT ... ON CONFLICT DO NOTHING` (or `DO UPDATE` when fields may change).
2. **Seed data:** append to `supabase/seed.sql`. This file runs on `supabase db reset` and when a project is first provisioned.
3. **Fixtures:** leave out of `seed.sql` in production pipelines; either add dev-only rows behind a guard or create per-test in the test suite.
4. **Verify:**
   ```bash
   supabase db reset
   supabase db reset   # second run proves idempotency
   psql "$SUPABASE_DB_URL" -c "select count(*) from workflow_statuses;"
   ```

Example reference migration:

```sql
insert into workflow_statuses (slug, label, sort_order) values
  ('draft',     'Draft',     10),
  ('active',    'Active',    20),
  ('archived',  'Archived',  30)
on conflict (slug) do update
  set label = excluded.label,
      sort_order = excluded.sort_order;
```

#### Alembic (Python / SQLAlchemy)

1. **Reference data:** inside the migration's `upgrade()`, use `op.bulk_insert()` against a lightweight table object. Provide a matching delete in `downgrade()`.
2. **Seed data:** `scripts/seed.py` (or a `make seed` / CLI management command). Use `session.merge()` or `INSERT ... ON CONFLICT` via the dialect.
3. **Fixtures:** `pytest` fixtures that build rows via factory functions and roll back in a per-test transaction.
4. **Verify:**
   ```bash
   alembic upgrade head
   alembic upgrade head   # second run must be a no-op
   python scripts/seed.py
   python scripts/seed.py # second run must be a no-op
   ```

Example reference insert:

```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    statuses = sa.table(
        "workflow_statuses",
        sa.column("slug", sa.String),
        sa.column("label", sa.String),
    )
    op.bulk_insert(statuses, [
        {"slug": "draft",    "label": "Draft"},
        {"slug": "active",   "label": "Active"},
        {"slug": "archived", "label": "Archived"},
    ])
```

Example idempotent seed:

```python
obj, created = Role.objects_get_or_create(
    slug="admin",
    defaults={"label": "Administrator"},
)
```

#### Prisma (TypeScript)

1. **Reference data:** raw SQL inside a Prisma migration under `prisma/migrations/<ts>_<name>/migration.sql`, using `ON CONFLICT DO NOTHING` / `DO UPDATE`.
2. **Seed data:** `prisma/seed.ts`, wired up in `package.json`:
   ```json
   {
     "prisma": { "seed": "tsx prisma/seed.ts" }
   }
   ```
   Use `prisma.<model>.upsert()` so the script is safe to re-run.
3. **Fixtures:** test helpers that build rows with the Prisma client, cleaned up with truncation or a wrapping transaction.
4. **Verify:**
   ```bash
   npx prisma migrate deploy
   npx prisma db seed
   npx prisma db seed   # second run must be a no-op
   ```

Example `prisma/seed.ts`:

```ts
import { PrismaClient } from "@prisma/client";
const prisma = new PrismaClient();

async function main() {
  await prisma.workflowStatus.upsert({
    where: { slug: "active" },
    update: { label: "Active" },
    create: { slug: "active", label: "Active", sortOrder: 20 },
  });
}

main().finally(() => prisma.$disconnect());
```

#### Django

1. **Reference data:** data migration using `RunPython` with a forward and reverse function.
2. **Seed data:** custom management command (`python manage.py seed`) that uses `get_or_create` / `update_or_create`. Prefer this over `loaddata` for environment-specific values.
3. **Fixtures:** `fixtures/*.json` loaded via `loaddata` for deterministic test data, or `pytest-django` + `factory_boy` with per-test transaction rollback.
4. **Verify:**
   ```bash
   python manage.py migrate
   python manage.py seed
   python manage.py seed            # second run must be a no-op
   python manage.py loaddata fixtures/dev.json   # dev / test only
   ```

Example data migration:

```python
from django.db import migrations

def forwards(apps, schema_editor):
    Status = apps.get_model("workflows", "WorkflowStatus")
    for slug, label in [("draft", "Draft"), ("active", "Active")]:
        Status.objects.update_or_create(slug=slug, defaults={"label": label})

def backwards(apps, schema_editor):
    Status = apps.get_model("workflows", "WorkflowStatus")
    Status.objects.filter(slug__in=["draft", "active"]).delete()

class Migration(migrations.Migration):
    dependencies = [("workflows", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
```

### 3. Pick the right environments

| Data class | prod | staging | dev | test |
|---|---|---|---|---|
| Reference | yes | yes | yes | yes |
| Seed | yes (real values) | yes (real or sanitized) | yes (safe defaults) | yes, when required for boot |
| Fixture | **no** | optional demo set | yes | yes, created per test |

Rules of thumb:

- Production credentials must come from env vars, never hard-coded in seed files.
- Staging seeds should be close to prod shape but never contain real user PII.
- Test data is owned by the test suite; never rely on dev seeds being present in CI.

### 4. Enforce idempotency

Every seed and reference insert must be safe to run twice. Patterns:

- **Postgres / Supabase / Prisma raw SQL:** `INSERT ... ON CONFLICT (unique_col) DO NOTHING` or `DO UPDATE SET ...`.
- **Prisma:** `prisma.model.upsert({ where, update, create })`.
- **Django / SQLAlchemy ORM:** `get_or_create`, `update_or_create`, `session.merge()`.
- **Alembic raw SQL:** gate with `SELECT 1 FROM ... WHERE ...` or use `ON CONFLICT`.
- **MySQL:** `INSERT ... ON DUPLICATE KEY UPDATE`.

Anti-patterns to refuse:

- Plain `INSERT` without a unique constraint or conflict handler.
- Seeds that assume an empty database.
- Migrations that skip the `downgrade()` path for reference data.

### 5. Verification checklist

After running the seed/migration, confirm all of:

- [ ] Row counts match expectation — `select count(*) from <table>` for each touched table.
- [ ] Spot-check representative rows (slug, label, foreign keys look correct).
- [ ] Re-run the seed/migration — the second run completes cleanly with zero inserts/updates (or logs "already present").
- [ ] Unique constraints exist on the natural keys used by the idempotent upsert.
- [ ] App boots and exercises the data (smoke a route or query that depends on it).
- [ ] No fixture/test data leaked into migrations or the production seed target.
- [ ] No production credentials or PII committed — only env-var references.

### 6. Plan writing integration

When a plan introduces new models or data:

1. Add a **Data Requirements** section.
2. List every data item and classify it using the table above.
3. Add explicit tasks:
   - Reference → migration file + migration test + idempotency check.
   - Seed → seed script update + re-run verification.
   - Fixture → factory / builder in test infra, plus any dev-only seed entry.
4. Note environment targeting for each item (prod / staging / dev / test).

### 7. Pre-commit check

Before committing changes that introduce new models, enums, or lookup data:

- [ ] All reference data has corresponding migrations.
- [ ] Migrations are idempotent (a second `upgrade` / `migrate` is a no-op).
- [ ] Seed scripts updated if new bootstrap data is needed, and are idempotent.
- [ ] Tests build their own data — no reliance on seeds or cross-test leftovers.
- [ ] No fixture/test data in migration files.
- [ ] No production credentials in seed files — only env-var reads.
- [ ] Downgrade / reverse path exists for every data migration.

## When NOT to use this skill

- Generating inputs for an individual test case — that belongs to the test framework / test-runner skill via factories, builders, or pytest fixtures. This skill only covers *shared* data that belongs in a migration or seed script.
- One-off manual data corrections in a live environment — use a runbook or a targeted operational script with an audit trail, not the seed pipeline.
- Content-management data that end users edit through the app UI — that is application state, not seed data.
- Large demo datasets used only for screenshots or sales — keep those in a demo-only loader outside the normal seed path.

## Related references

- Companion rule: `~/.agent-tools/rules/agents-environment-config/frameworks/database/seed-data.md` — authoritative written rules this skill operationalizes.
- Connection management: `~/.agent-tools/rules/agents-environment-config/frameworks/database/connection-management.md` — pool lifecycle, migration ordering, and env-var expectations that seed scripts must respect.
- Testing standards: `~/.agent-tools/rules/agents-environment-config/frameworks/testing/standards.md` — owns fixture / factory patterns that this skill defers to.
