# Testing Tools & Commands

## Runners & Libraries
- Unit/Integration: Vitest / Jest + Testing Library
- E2E: Playwright (preferred) or Cypress
- Contract tests: Pact, OpenAPI validators, Zod/JSON Schema

## UI Testing with Playwright MCP

**CRITICAL: For creating UI tests, use Playwright MCP with the actual UI to identify how the actual UI works in order to write or validate what is in the Playwright tests. Then run the Playwright tests and make sure they work against the actual UI as it actually works.**

### UI Test Workflow
1. **Discovery**: Use Playwright MCP to interact with the actual running UI
   - Navigate and explore the UI behavior
   - Identify selectors, interactions, and states
   - Document actual UI responses
2. **Write Tests**: Create Playwright tests based on discovered UI behavior
   - Use verified selectors and interactions
   - Match actual UI workflows, not assumptions
3. **Validate**: Run tests against the actual UI and verify they work
   - Tests must pass against the real UI
   - Adjust if UI behavior differs from assumptions
   - Never write tests without verifying against the actual UI first

## Suggested Commands
```bash
# Run fast unit/integration tests
pnpm test:run

# Run with coverage
pnpm test:coverage

# E2E suite
pnpm test:e2e

# Contract tests (example)
pnpm test:contracts
```

## Guardrails
- Lint/typecheck pre-commit; full suite pre-push
- Keep test output deterministic; avoid real clocks unless essential
