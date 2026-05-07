# `.aec.json` — per-project configuration

Each project can have an `.aec.json` file at its root that stores project-specific AEC configuration: port assignments, test suites, and installed tooling metadata. This file is created automatically during `aec setup`.

## Schema overview

```json
{
  "$schema": "https://aec.bernier.dev/schema/aec.json",
  "version": "1.0.0",
  "project": {
    "name": "my-project",
    "description": "My project description"
  },
  "ports": {
    "dev-server": {
      "port": 3333,
      "protocol": "http",
      "description": "Next.js dev server"
    },
    "test-database": {
      "port": 5433,
      "protocol": "postgresql",
      "description": "Docker test DB"
    }
  },
  "test": {
    "suites": {
      "unit": { "command": "npm run test:unit", "cleanup": null },
      "integration": {
        "command": "npm run test:integration",
        "cleanup": "docker compose -f docker-compose.test.yml down"
      }
    },
    "prerequisites": ["docker"],
    "scheduled": ["unit", "integration"]
  },
  "installed": {
    "skills": {},
    "rules": {},
    "agents": {}
  },
  "dismissed": {
    "agents": {},
    "skills": {},
    "rules": {}
  }
}
```

The `dismissed` section tracks items the user has reviewed via `aec discover` and chosen not to install. See [Discovery](discovery.md) for details.

## How it's created

`aec setup` creates `.aec.json` automatically. It detects test frameworks, prompts for port assignments, and populates the `installed` section from the central manifest. You can also edit it manually.

## Gitignore behavior

`.aec.json` is committed to git by default so all contributors benefit from the metadata. To gitignore it instead:

```bash
aec config set aec_json_gitignored true
```

When `aec_json_gitignored` is `true`, `aec setup` adds `.aec.json` to `.gitignore`. When `false`, it removes that entry if present.

## Sections

| Section | Purpose |
|---------|---------|
| `project` | Name and description (name defaults to directory name) |
| `ports` | Port assignments with protocol and description |
| `test` | Test suites, prerequisites, and scheduled run whitelist |
| `installed` | Local copy of installed skills/rules/agents (synced from central manifest) |
| `dismissed` | Items reviewed via `aec discover` that the user chose not to install |
