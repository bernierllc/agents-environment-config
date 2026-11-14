# Test Organization

## Structure (example)
```
src/
├── app/
│   ├── api/[route]/__tests__/route.test.ts
│   └── [page]/__tests__/page.test.tsx
├── components/[component]/__tests__/[component].test.tsx
└── lib/__tests__/utils.test.ts
```

## Naming
- `*.test.ts[x]` for unit/integration
- E2E naming aligns with the chosen runner (e.g., Playwright)

## Coverage Targets
- Unit/integration: >= 80% for new/changed code; 100% for critical paths
- E2E: focus on mission‑critical flows (smoke + regression)

## Scope
- Keep unit tests close to implementation
- Place integration tests near the composing boundary
