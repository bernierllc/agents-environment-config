# Supabase Development Rules

## Command Usage

### Workspace Commands
- **ALWAYS use `pnpm supa`** instead of global supabase CLI
- **NEVER use `supabase` directly** - always go through pnpm workspace

### Common Supabase Commands
- Start local Supabase: `pnpm supa start`
- Stop local Supabase: `pnpm supa stop`
- Generate types: `pnpm supa:generate` (local) or `pnpm supa:generate:remote`
- Create migration: `pnpm supa migration:new <name>`
- Apply migrations: `pnpm supa migration:up`
- Reset database: `pnpm supa reset`
- Check status: `pnpm supa status`
- Open Studio: `pnpm supa:studio` (http://127.0.0.1:54323)
- Open Mailpit: `pnpm supa:mailpit` (http://127.0.0.1:54324)

## Development Workflow

- **ASSUME Supabase is running** on `http://localhost:54321` unless told otherwise
- **Check `pnpm supa status`** before suggesting database operations
- **Use local types generation** (`pnpm supa:generate`) for development
- **Test API endpoints** using browser extensions or curl, not by starting servers

## File Locations

- Supabase config: `supabase/config.toml`
- Migrations: `supabase/migrations/`
- Types: `supabase/types.ts`
- Seed data: `supabase/seed.sql`

## Database Structure

### Conventions
- All tables use UUIDs for IDs (text-based UUIDs)
- Timestamps use `timestamptz`
- Junction tables follow naming pattern: `table1_table2`
- All tables have `created_at` and `updated_at` fields

### Schema Organization
```
supabase/
├── migrations/          # Database migrations
├── seed.sql            # Seed data
├── config.toml         # Supabase configuration
└── types.ts            # Generated TypeScript types
```

## Row Level Security (RLS)

### Core Principle: NEVER Bypass RLS
Row Level Security (RLS) is your primary security mechanism. The service role should **respect RLS policies**, not bypass them.

### RLS Setup Pattern
```sql
-- Enable RLS
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Grant table access
GRANT SELECT ON jobs TO anon, authenticated;
GRANT ALL ON jobs TO service_role;

-- Create policies
CREATE POLICY jobs_public_read ON jobs
  FOR SELECT TO anon, authenticated
  USING (is_published = true);
```

### Security Layers
1. **Table Grants** - Grant appropriate permissions to roles
2. **RLS Policies** - Fine-grained access control
3. **Service Role Grants** - Explicit grants for service role

## Migration Template

```sql
BEGIN;

-- Create table
CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  is_published BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Grant table access
GRANT SELECT ON jobs TO anon, authenticated;
GRANT ALL ON jobs TO service_role;

-- Create policies
CREATE POLICY jobs_public_read ON jobs
  FOR SELECT TO anon, authenticated
  USING (is_published = true);

COMMIT;
```

## Best Practices

1. **Always enable RLS** on tables with sensitive data
2. **Grant appropriate permissions** to anon/authenticated/service_role
3. **Use context client** in API routers - don't create new clients
4. **Test with different roles** to ensure policies work correctly
5. **Document security assumptions** in migrations
6. **Prefer explicit grants** over broad permissions
7. **Use policies for fine-grained control** over simple grants

## References
- **Database**: See `frameworks/database/sqlalchemy.mdc` for SQLAlchemy patterns
- **Security**: See `general/security.mdc`
- **Architecture**: See `general/architecture.mdc`
