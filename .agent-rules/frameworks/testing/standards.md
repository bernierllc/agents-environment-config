# Testing Standards (No Mocking Internal Systems)

## Core Testing Policy

**If we own it or write it, we test it directly - we do NOT mock it in tests.**

### Critical Rules
- **DO NOT mock the database or the internal API**
- **Use a real database instance and real HTTP calls**
- **Mocks are only allowed for external third-party services**
- **Tables, code, configuration, and definitions that we own and that affect the code we own inside of 3rd party systems should be tested because we own it**

## Principles
- Prefer small, fast tests near the code; grow realism as you move up the test pyramid.
- Test against real systems we own - database, APIs, services, models, repositories
- Mocks are ONLY allowed for external third-party services we do not control
- Avoid global toggles that bypass tests; failures must be fixed or the test adjusted with rationale

## No Mocking Internal Systems Policy

### What NOT to Mock (We Own It)
- **Database**: Never mock Prisma, database queries, or repositories - use real database instances
- **Internal APIs**: Never mock our own API endpoints - make real HTTP calls
- **Internal Services**: Never mock service classes we own and maintain
- **Tables/Models**: Never mock database tables, models, or their relationships
- **Configuration**: Never mock config that we own and control
- **Definitions in 3rd-party systems**: If we define tables/schemas/config in external systems, test the real thing because we own it

### What CAN Be Mocked (External Third-Party Only)
- **External APIs**: Stripe, SendGrid, Twilio, Google APIs (when not testing our own code within them), etc.
- **External services**: OAuth providers (when not testing auth flow)
- **Network conditions**: Simulating timeouts, errors from external services
- **Rate-limited services**: When testing without burning API quota

### Rationale
Mocking internal systems creates tests that pass when the mock is correct but fail in production when the real system behaves differently. Tests against mocks only verify that code works with the mock, not with the real system. If we own it, we must test it directly.

## Test Pyramid and Testing Strategy
1. Unit tests (NO internal mocks) — fast feedback on small units
   - Use real database instances for database operations
   - Call real service methods with real dependencies
   - Make real HTTP calls to internal APIs
   - Only mock external third-party services
2. Integration tests (NO internal mocks)
   - Use real database and make real HTTP calls to our APIs
   - Validate wiring across module boundaries and data contracts
3. End-to-end (NO mocks for internal systems)
   - Exercise the system through public interfaces
   - Use real database and real internal APIs
   - Only mock external third‑party services you do not control

## UI Testing Workflow

**CRITICAL: For creating UI tests, use Playwright MCP with the actual UI to identify how the actual UI works in order to write or validate what is in the Playwright tests. Then run the Playwright tests and make sure they work against the actual UI as it actually works.**

### UI Test Creation Process
1. **Discovery Phase**: Use Playwright MCP to interact with the actual running UI
   - Navigate to the UI and explore its behavior
   - Identify selectors, interactions, and states through actual usage
   - Document how the UI actually responds to user actions
2. **Test Writing**: Write Playwright tests based on actual UI behavior discovered
   - Use selectors and interactions verified against the real UI
   - Ensure tests match the actual UI workflow, not assumptions
3. **Validation**: Run tests against the actual UI and verify they work correctly
   - Tests must pass against the real UI as it actually works
   - Adjust tests if UI behavior differs from assumptions
   - Never write tests without first verifying against the actual UI

## When To Mock
- **NEVER**: Database, Prisma, internal APIs, internal services, repositories, models
- **NEVER**: Any code, tables, configuration, or definitions that we own
- **NEVER**: Tables, code, configuration, or definitions that we own inside of 3rd party systems
- **ALLOWED**: External third-party APIs (Stripe, SendGrid, Twilio, etc.) that we do not control
- **ALLOWED**: External services we don't control (OAuth providers when not testing auth flow)
- **ALLOWED**: Simulating external service failures (timeouts, 5xx from external services)
- **ALLOWED**: Rate-limited external services to avoid burning API quota

## Mock Verification (For External Services Only)

**CRITICAL: All mocks for external third-party services MUST be tested to match the ACTUAL thing they are mocking, otherwise the mocks are useless and only cause problems.**

Use one or more techniques so mocks do not drift from the real world:
- Contract tests: Assert provider/consumer agree on request/response shapes.
- Golden files/snapshots: Record real responses and reuse as fixtures; refresh on schema changes.
- Schema/type guards: Validate fixtures against JSON Schema or TypeScript types at test load.
- Parity runs: Periodically hit real services in CI nightly jobs to detect drift.

## Quality Bars
- Unit: fast (<100ms), isolated, deterministic. High branch/path coverage.
- Integration: validate cross‑module contracts and realistic data flows.
- E2E: validate critical paths; focus on user‑visible correctness.

## Test Isolation

### Core Principle
**Tests must be isolated by default** — data from one test suite should not affect another, and tests within a suite should not depend on each other unless explicitly necessary.

### Isolation Requirements
- **Between test suites**: Each test suite must clean up its own state and not rely on data created by other suites.
- **Between tests**: Each test must set up and tear down its own data. Tests should be able to run in any order.
- **Shared state**: Only share data between tests when explicitly necessary and documented with clear rationale.
- **Database/state**: Use transactions, test databases, or fixtures that are reset between tests. Never rely on shared mutable state.

### Implementation Guidelines
- **Setup/teardown**: Use `beforeEach`/`afterEach` or `beforeAll`/`afterAll` hooks to establish and clean up test state.
- **Transaction rollback**: Wrap database-dependent tests in transactions that roll back after each test.
- **Isolated test databases**: Use separate test databases or schemas per test suite when possible.
- **Fixtures**: Create fresh test data per test rather than reusing data across tests.
- **Global state**: Avoid global variables, singletons, or shared caches that persist between tests.
- **Concurrent execution**: Tests should be safe to run in parallel without interference.

### Exceptions and Documentation
- **Shared fixtures**: When sharing data is necessary (e.g., expensive setup, read-only reference data), document the rationale and ensure the shared state is immutable or reset between uses.
- **Integration test dependencies**: Integration tests may share a database schema, but each test must still clean up its own modifications.
- **E2E scenarios**: E2E tests may require shared state to simulate real user workflows; document these dependencies clearly.

## Database and Service Testing

### Core Principle
**Tests must set up services at test run time and tear them down when tests are done.** Running services at test time is purposefully part of our testing strategy because:
- Setting up services helps us test our environment variables
- Tests our infrastructure setup, connection, and communication
- Tests our database migrations on every test run
- Ensures infrastructure works correctly as part of the test suite

### Database Connection Management in Tests

> **General Principles**: See `frameworks/database/connection-management.mdc` for ORM-agnostic guidance.
> **Prisma-Specific**: See `frameworks/database/prisma.mdc` for Prisma patterns.

**Core Rule: Never create standalone database clients in tests. Always use shared/pooled connections.**

#### Rules
- **NEVER** use `new PrismaClient()` (or equivalent) directly in test files
- **ALWAYS** use shared test clients from test utilities (e.g., `getSharedPrismaClient()`)
- **NEVER** call disconnect methods on shared clients (test infrastructure manages lifecycle)
- **Exception**: E2E tests in separate processes may need isolated clients with explicit cleanup

#### Correct Pattern
```typescript
// BAD - creates new connection per file/test
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

// GOOD - uses shared pooled connection
import { getSharedPrismaClient } from '@/tests/utils/shared-database';
const prisma = getSharedPrismaClient();
```

#### Test Cleanup
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

#### Symptoms of Connection Pool Exhaustion
- Error: "Too many clients already" or "Too many database connections"
- Tests passing individually but failing when run together
- Intermittent connection timeouts

#### When Writing New Tests
1. Import from shared test utilities, not ORM client directly
2. Use the shared client for all database operations
3. Clean up test data in `afterAll`/`afterEach`, but don't disconnect
4. If a test needs isolation, use transactions not separate clients

#### When Fixing Connection Issues
1. Search for direct client instantiation in test files (e.g., `new PrismaClient()`)
2. Replace with shared test client utilities
3. Remove any disconnect calls on shared clients
4. Verify tests still pass with `--runInBand`

### Docker-Based Test Services

**MANDATORY: Use Docker for all test services (databases, caches, message queues, etc.)**

- **Container Lifecycle**: 
  - Containers **MUST** spin up at the start of test execution
  - Containers **MUST** spin down at the end of test execution
  - Use test lifecycle hooks (`beforeAll`/`afterAll` or test framework equivalents) to manage container lifecycle
  - Never leave containers running after tests complete

- **Resource Management**:
  - **CRITICAL**: The testing process **MUST** be killed at the end of testing to protect local systems from resource overload
  - Test runners like Vitest can consume 2-3GB per service in memory
  - Without proper cleanup, this quickly makes systems unusable
  - On third-party CI services, this becomes very expensive
  - Implement proper cleanup hooks that ensure all containers and test processes are terminated

- **Implementation Requirements**:
  - Use Docker Compose or container orchestration tools for multi-service test environments
  - Ensure containers are isolated per test run (no shared state between runs)
  - Use unique container names/IDs to avoid conflicts
  - Implement timeout mechanisms to prevent hung containers
  - Log container startup/shutdown for debugging

### Test Suite Execution

**When running the full test suite:**
- **Stop after first 3 failures**: Configure test runner to stop after the first 3 failures
- This speeds up the test-fix loop by allowing developers to:
  - Stop and fix failures immediately
  - Re-run tests without waiting for the entire suite
  - Iterate quickly on fixing issues

- **Implementation**:
  - Vitest: Use `bail: 3` configuration option
  - Jest: Use `bail: 3` configuration option
  - Other runners: Configure equivalent "bail after N failures" option

### Best Practices

- **Service Health Checks**: Wait for services to be healthy before running tests
- **Port Management**: Use dynamic port allocation or port ranges to avoid conflicts
- **Data Cleanup**: Ensure test data is cleaned up between test runs
- **Migration Testing**: Run database migrations as part of test setup to verify they work
- **Environment Variables**: Test that environment variables are correctly loaded and used
- **Connection Testing**: Verify that services can connect to each other correctly

## Fixture Hygiene
- Keep fixtures small and representative; remove unused fields.
- Co-locate fixtures with tests; document provenance (e.g., captured on 2025‑10‑29).
- Validate fixtures against schemas/types on load.

## Tooling Hints
- TypeScript: use `zod`/`io-ts` or JSON Schema to validate test data and API responses.
- API: maintain OpenAPI and generate client/server types; use them in tests.
- UI: prefer Testing Library; avoid implementation‑coupled selectors.
- **UI Testing**: Use Playwright MCP with the actual UI to discover behavior before writing tests. Always verify tests work against the actual UI.
- **Database**: Use Docker containers for test databases - containers must spin up at test start and spin down at test end
- **HTTP**: Use real HTTP clients to call internal APIs in tests
- **Test Runners**: Configure bail after 3 failures for full test suite runs (e.g., Vitest: `bail: 3`, Jest: `bail: 3`)
- **Resource Cleanup**: Ensure test processes and containers are killed after test completion to prevent resource exhaustion

## Documentation and Ownership
- For external service mocks: Each mocked interface must have a short README describing its real contract, how fixtures were captured, and how to refresh them.
- Add a scheduled job or checklist to refresh golden files after external API/schema changes.

## References
- Martin Fowler — “Mocks Aren’t Stubs”
- Google Testing Blog — Testing on the Toilet (test doubles, hermetic tests)
- Thoughtworks Tech Radar — Testing strategies and contract testing

