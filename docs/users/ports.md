# Port registry

When you manage multiple projects on one machine, port collisions are inevitable. Project A claims port 3000, project B also claims 3000, and you discover the conflict at runtime when a dev server fails to bind.

The port registry solves this with a central registry at `~/.agents-environment-config/ports-registry.json`. Ports are assigned first-come-first-served based on registration timestamp.

## How it works

1. Each project declares its ports in `.aec.json` (see [.aec.json schema](aec-json.md))
2. During `aec setup`, ports are registered against the central registry
3. Conflicts are surfaced as warnings -- they do not block setup
4. You fix the `.aec.json` and re-register

## Commands

| Command | Description |
|---------|-------------|
| `aec ports list` | Show all registered ports across all projects, grouped by project |
| `aec ports check [path]` | Check for conflicts without registering (defaults to current directory) |
| `aec ports register [path]` | Register ports from `.aec.json` into the central registry |
| `aec ports unregister [path]` | Remove all port registrations for a project |
| `aec ports validate` | Find stale entries (project directories that no longer exist) |

## Conflict resolution

Port conflicts warn but do not block. When a conflict is detected, AEC shows which project registered the port first and when:

```
⚠ Port conflict: port 3000 is already registered to "my-portfolio"
  (registered 2026-03-15T10:00:00Z)
  Your .aec.json assigns 3000 to "dev-server"
  → Update your .aec.json to use a different port, or run
    aec ports list to see all registered ports
```

Stale entries (from deleted project directories) are cleaned up automatically by `aec prune`.
