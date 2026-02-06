# Prisma Patterns

> **Connection Management**: See `frameworks/database/connection-management.mdc` for general principles.

## Connection Management

### Core Rules

- **NEVER** use `new PrismaClient()` directly in services, handlers, or test files
- **ALWAYS** use the singleton pattern for production code
- **ALWAYS** use shared test clients for test code
- **NEVER** call `prisma.$disconnect()` on shared clients

### Singleton Pattern (Production)

This is THE ONLY place `new PrismaClient()` should be instantiated in production code:

```typescript
// lib/prisma.ts - Single source of truth
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma = globalForPrisma.prisma ?? new PrismaClient({
  log: process.env.NODE_ENV === 'development' ? ['query', 'error', 'warn'] : ['error'],
});

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

export default prisma;
```

### Service Usage

```typescript
// BAD - creates new client per service instantiation
class UserService {
  private prisma = new PrismaClient();
}

// GOOD - imports singleton
import { prisma } from '@/lib/prisma';

class UserService {
  async getUser(id: string) {
    return prisma.user.findUnique({ where: { id } });
  }
}

// ALSO GOOD - dependency injection for testability
class UserService {
  constructor(private prisma: PrismaClient) {}
}
```

### Connection Pool Configuration

```prisma
// In schema.prisma or connection string
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  // Connection pool settings via URL params:
  // ?connection_limit=10&pool_timeout=30
}
```

### Serverless Configuration (Vercel, AWS Lambda, etc.)

```bash
# Use Prisma Accelerate or PgBouncer for serverless
DATABASE_URL="prisma://accelerate.prisma-data.net/?api_key=..."
DIRECT_URL="postgresql://..."  # For migrations only
```

```prisma
datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  directUrl = env("DIRECT_URL")
}
```

### Graceful Shutdown

For long-running processes (not serverless):

```typescript
// Graceful shutdown handler
process.on('beforeExit', async () => {
  await prisma.$disconnect();
});
```

## Test Connection Management

### Rules for Test Files

- **NEVER** use `new PrismaClient()` directly in test files
- **ALWAYS** use `getSharedPrismaClient()` from `tests/utils/shared-database.ts`
- **NEVER** call `prisma.$disconnect()` on shared clients (test infrastructure manages lifecycle)
- **Exception**: E2E tests running in separate processes may need their own clients

### Pattern Recognition

When you see these patterns in test files, they need fixing:

```typescript
// BAD - creates new connection per file/test
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

// GOOD - uses shared pooled connection
import { getSharedPrismaClient } from '@/tests/utils/shared-database';
const prisma = getSharedPrismaClient();
```

### Test Cleanup

```typescript
// BAD - disconnecting shared client breaks other tests
afterAll(async () => {
  await prisma.$disconnect();
});

// GOOD - clean up data only, let infrastructure manage connection
afterAll(async () => {
  await prisma.someTable.deleteMany({
    where: { id: { startsWith: testFactory.prefix } }
  });
});
```

### Test Isolation with Transactions

If a test needs isolation, use transactions not separate clients:

```typescript
await prisma.$transaction(async (tx) => {
  // isolated operations that auto-rollback on failure
});
```

## Debugging Connection Issues

```typescript
// Add to prisma client for debugging
const prisma = new PrismaClient({
  log: [
    { level: 'query', emit: 'event' },
    { level: 'error', emit: 'stdout' },
  ],
});

prisma.$on('query', (e) => {
  console.log(`Query: ${e.query}`);
  console.log(`Duration: ${e.duration}ms`);
});
```

### Symptoms of Connection Pool Exhaustion

- Error: "Too many clients already" or "Too many database connections"
- Tests passing individually but failing when run together
- Intermittent connection timeouts

### Fixing Connection Issues

1. Search for `new PrismaClient()` in test files
2. Replace with `getSharedPrismaClient()`
3. Remove any `$disconnect()` calls on the shared client
4. Verify tests still pass with `--runInBand`

## Database Operations

### Type Safety
- Use Prisma-generated types consistently
- Leverage TypeScript types from `@prisma/client`
- Use `Prisma.*` utility types for operations

```typescript
import { Prisma } from '@prisma/client';

async function createUser(data: Prisma.UserCreateInput): Promise<User> {
  return await prisma.user.create({ data });
}
```

### Query Patterns
```typescript
// Find unique
const user = await prisma.user.findUnique({
  where: { id: userId }
});

// Find many with filters
const users = await prisma.user.findMany({
  where: { status: 'active' },
  include: { profile: true }
});

// Update
const updated = await prisma.user.update({
  where: { id: userId },
  data: { status: 'active' }
});

// Delete
await prisma.user.delete({
  where: { id: userId }
});
```

## Migration Management

### Schema Changes
- All schema changes require migrations
- Use `npx prisma migrate dev` for development
- Use `npx prisma migrate deploy` for production
- Never edit migration files after creation

### Schema Validation
```bash
# Validate schema
npx prisma validate

# Generate client
npx prisma generate

# Create migration
npx prisma migrate dev --name migration_name

# Apply migrations
npx prisma migrate deploy
```

## Best Practices

### Transactions
Use transactions for complex operations:

```typescript
await prisma.$transaction(async (tx) => {
  await tx.user.create({ data: userData });
  await tx.profile.create({ data: profileData });
});
```

### Error Handling
```typescript
try {
  const user = await prisma.user.findUnique({
    where: { id: userId }
  });
  
  if (!user) {
    throw new Error('User not found');
  }
  
  return user;
} catch (error) {
  if (error instanceof Prisma.PrismaClientKnownRequestError) {
    // Handle Prisma-specific errors
  }
  throw error;
}
```

### Soft Delete Pattern
```typescript
// Add deleted_at field to schema
model User {
  id        String    @id @default(uuid())
  deletedAt DateTime? @map("deleted_at")
}

// Query with soft delete
const users = await prisma.user.findMany({
  where: {
    deletedAt: null
  }
});
```

## References
- **Database**: See `frameworks/database/supabase.mdc` for Supabase patterns
- **SQLAlchemy**: See `frameworks/database/sqlalchemy.mdc` for Python patterns
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
