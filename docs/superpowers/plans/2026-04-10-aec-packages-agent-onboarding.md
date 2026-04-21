# AEC Packages, Agent-Native Onboarding & Seed Data

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform AEC from a CLI-driven configuration tool into a package-aware, agent-native platform where the agent does the reasoning and the CLI does the coordination — with seed data management as the first proof-of-concept package.

**Architecture:** AEC gains a package system (bundles of rules + skills + handlebars templates for cross-item coordination), a tracked file writer with hash-based modification detection, an agent-friendly CLI output mode (JSON, non-interactive), and a redesigned onboarding flow where agents drive setup while humans answer policy questions. The CLI becomes the package manager; the agent becomes the intelligence layer.

**Tech Stack:** Python 3.9+, Typer CLI, JSON manifests, YAML package descriptors, existing AEC infrastructure

**Branch strategy:** All work is done in a git worktree on branch `feature/aec-packages`, created 2026-04-12. Worktree location: `.claude/worktrees/aec-packages/`. Plan and spec files live in the worktree — main branch is clean. The worktree isolates package system work from the stable CLI while allowing parallel development on main.

---

## North Star Vision

```
Human installs AEC → tells agent "set up AEC in this repo" → agent scans the repo,
queries the AEC catalog, reasons about what fits, asks the human 3-5 policy questions,
runs `aec install` commands, and hands back a summary with links to logs and configs.

Adding a second project: agent notices commonalities with project 1, suggests promoting
shared rules/skills to global scope.

Established user: AEC detects existing setup, offers to bring items under management
without clobbering anything, with rollback available.
```

---

## Phased Approach

### Phase 0: Seed Data Rule + Skill (Foundation Content)
*Ship the seed data rule and skill immediately — no CLI changes needed. Cross-rule enhancements deferred to Phase 1 when the template system exists.*

### Phase 1: Package System (Bundle, Install, Template)
*AEC learns what a "package" is — template-based coordination over existing install commands, with tracked file writes and hash-based modification detection.*

### Phase 2: Agent-Friendly CLI (JSON Output, Non-Interactive Mode)
*Every AEC command gains `--format json` output and `--non-interactive` mode so agents can drive the CLI programmatically.*

### Phase 3: Agent-Native Onboarding (New User → First Project)
*Redesign `aec setup` to work as agent-driven onboarding. Agent scans, reasons, asks policy questions, installs.*

### Phase 4: Multi-Project Intelligence (Second Project, Global Promotion)
*When a second project is added, AEC and the agent identify commonalities and suggest global-scope opportunities.*

### Phase 5: Established Environment Integration (Retrofit Without Clobbering)
*For users who already have AEC set up with existing skills/rules/agents, integrate packages gracefully with rollback support.*

### Phase 6: Rules as Packages (Convention Packages)
*Repackage existing AEC rules from "Matt's opinionated rules" into installable convention packages that users choose during onboarding. Base package is universal; everything else is opt-in.*

---

## Phase 0: Seed Data Rule + Skill

**Why first:** This delivers immediate value (agents start handling seed data correctly) and becomes the test case for the package system in Phase 1.

### Task 0.1: Create the Seed Data Rule

**Files:**
- Create: `.agent-rules/frameworks/database/seed-data.md`

- [ ] **Step 1: Write the rule file**

```markdown
---
name: seed-data-management
description: Conventions for reference data, seed data, and fixture data across environments
version: 1.0.0
category: frameworks/database
---

# Seed Data Management

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
- **Alembic:** Use `op.bulk_insert()` in migration `upgrade()` functions
- **Prisma:** Include in migration SQL or use `prisma db seed` with a migration-aware script
- **Django:** Use data migrations (`RunPython` in migration files)

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
- **Alembic:** `scripts/seed.py` or `make seed`
- **Prisma:** `prisma/seed.ts` (runs via `prisma db seed`)

### Fixture Data (→ Test Framework)

Synthetic data for development and testing. Never touches production.

**Examples:** test users, sample content, edge-case data, demo scenarios, performance test datasets

**Deployed to:** Local and staging ONLY, never production
**Mechanism:**
- **Automated tests:** Test factories/builders that create data per-test, rolled back after each test
- **Local dev:** Dev seed scripts for convenience data (idempotent, re-runnable)
- **Staging:** Explicit staging-only seed target, run manually post-deploy

**Key principle:** Tests must never depend on pre-existing data. Each test declares or creates what it needs. If a test breaks when run in isolation, its data setup is wrong.

## Environment Strategy

| Environment | Reference Data | Seed Data | Fixture Data |
|------------|---------------|-----------|--------------|
| Automated tests | Via migrations (fresh DB) | Not used | Per-test factories |
| Local dev | Via migrations | `make seed` on demand | Dev seed script |
| Staging | Via deploy migrations | Explicit post-deploy | Staging seed script |
| Production | Via deploy migrations | Bootstrap once | Never |

### Test Environment

- **Fresh database per test run.** Spin up clean instance (Docker), apply migrations (which include reference data), run tests.
- **Test isolation:** Each test gets a transaction that rolls back, or truncate-and-reseed between tests.
- **No dirty environments.** Tests must not depend on what ran before them.

### Local Development

- After `make db:reset` or equivalent, run `make seed` to populate convenience data.
- Seeds are idempotent — re-running is safe and expected.
- Reference data already present from migrations; seed scripts add operational and convenience data.

### Staging

- Migrations deploy automatically (same pipeline as production), bringing reference data.
- Staging-specific data (test accounts, demo content) applied via separate, explicitly-run target.
- Never automatic on deploy — prevents accidental test data if pipeline is misconfigured.

### Production

- Migrations only. Reference data arrives with schema changes.
- Bootstrap seed (first admin user) runs once during initial setup.
- No fixture data, ever.

## When This Rule Applies

If you are doing ANY of the following, you must consider seed data implications:

1. **Creating a new database table** — Does it need default rows? → Reference data migration
2. **Adding a status/enum/role field** — What are the valid values? → Reference data migration
3. **Adding a feature that requires data to exist** — First user? Default org? → Seed data script
4. **Writing tests** — Don't assume data exists. Create what you need per-test.
5. **Modifying existing reference data** — New status value? New role? → New migration that adds it

**When in doubt, invoke the seed-data skill for a guided walkthrough.**
```

- [ ] **Step 2: Verify rule parses correctly**

Run: `python3 -c "from aec.lib.sources import discover_available; import json; print(json.dumps(discover_available('/Users/mattbernier/projects/agents-environment-config/.agent-rules', 'rules'), indent=2))" | grep seed`
Expected: `seed-data-management` appears in available rules

- [ ] **Step 3: Commit**

```bash
git add .agent-rules/frameworks/database/seed-data.md
git commit -m "feat(rules): add seed data management conventions"
```

### Task 0.2: Create the Seed Data Skill

**Files:**
- Create: `.claude/skills/seed-data/SKILL.md`

- [ ] **Step 1: Write the skill file**

The skill is invoked during plan-writing, implementation, or on-demand. It walks the agent through classifying data and generating the right artifacts.

```markdown
---
name: seed-data
description: Classify application data as reference/seed/fixture, determine environment targeting, and generate appropriate files
version: 1.0.0
author: AEC
---

# Seed Data Classification & Generation

Use this skill when creating or modifying data that needs to exist in databases across environments.

## When to Use

- Creating new database tables with default/lookup rows
- Adding status fields, roles, permissions, or enum values stored in DB
- Adding features that require baseline data to function
- Writing tests that depend on specific data existing
- Modifying existing reference data (adding new statuses, roles, etc.)

## Classification Checklist

For each piece of data being introduced or modified, ask:

### 1. Does the application break without this data?

**YES → Reference Data.** This belongs in a database migration.
- Create an idempotent migration that inserts the data
- It will deploy to ALL environments automatically
- It is versioned and tested like schema changes
- Example: A `workflow_statuses` table that the app queries on every request

**NO → Continue to question 2.**

### 2. Is this data needed for the application to be useful (not just functional)?

**YES → Seed Data.** This belongs in a seed script.
- Add to the project's seed script (see framework patterns below)
- It must be idempotent (safe to re-run)
- It deploys to all environments but may vary (dev admin password ≠ prod admin password)
- Example: The first admin user account

**NO → Fixture Data.** This belongs in test infrastructure.
- For automated tests: use factories/builders, create per-test, rollback after
- For local dev: add to dev seed script for convenience
- For staging: add to staging-only seed target
- NEVER goes to production
- Example: Test users like "alice@test.com", sample blog posts

## Framework Patterns

### Supabase
- **Reference data:** `supabase/migrations/YYYYMMDDHHMMSS_add_<name>.sql` with idempotent INSERTs
- **Seed data:** `supabase/seed.sql` (runs on `supabase db reset`)
- **Fixtures:** Test files create their own data; dev convenience in seed.sql

### Alembic (Python/SQLAlchemy)
- **Reference data:** `op.bulk_insert()` inside migration `upgrade()` function
- **Seed data:** `scripts/seed.py` or `make seed` management command
- **Fixtures:** pytest fixtures with factory functions; transaction rollback per test

### Prisma (TypeScript)
- **Reference data:** Raw SQL in migration files under `prisma/migrations/`
- **Seed data:** `prisma/seed.ts` (runs via `npx prisma db seed`)
- **Fixtures:** Test helpers with Prisma client; cleanup via truncation or transaction

### Django
- **Reference data:** Data migrations using `RunPython` in migration files
- **Seed data:** Management command (`python manage.py seed`)
- **Fixtures:** pytest-django fixtures with factory_boy; transaction rollback per test

## Plan Writing Integration

When writing a plan that involves new models or data:

1. Add a "Data Requirements" section to the plan
2. For each data item, classify using the checklist above
3. Include explicit tasks for:
   - Reference data → migration file creation + migration test
   - Seed data → seed script update + idempotency verification
   - Fixture data → factory/builder creation in test infrastructure

## Pre-Commit Check

Before committing changes that introduce new models, enums, or lookup data:

- [ ] All reference data has corresponding migrations
- [ ] Migrations are idempotent (can run twice without error)
- [ ] Seed scripts updated if new bootstrap data needed
- [ ] Tests create their own data (no dependency on seeds or fixtures from other tests)
- [ ] No fixture/test data in migration files
- [ ] No production credentials in seed files (use env vars)
```

- [ ] **Step 2: Verify skill is discoverable**

Run: `python3 -c "from aec.lib.sources import discover_available; import json; print(json.dumps(discover_available('/Users/mattbernier/projects/agents-environment-config/.claude/skills', 'skills'), indent=2))" | grep seed`
Expected: `seed-data` appears in available skills

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/seed-data/SKILL.md
git commit -m "feat(skills): add seed data classification and generation skill"
```

### Task 0.3: Add Seed Data Awareness to AGENTINFO Template

**Note:** Cross-rule nudges (plans-checklists.md, quality/gates.md, etc.) are **deferred to Phase 1** where the snippet injection engine handles them properly. Manually editing 7 files now would create work that Phase 1 replaces. Instead, we add a lightweight instruction to AGENTINFO.md that any project can include.

**Files:**
- Modify: `AGENTINFO.md`

- [ ] **Step 1: Add seed data awareness section to AGENTINFO.md template**

```markdown
### Seed Data Awareness
When writing plans or implementing features that involve database models, statuses, enums, roles, or lookup data:
1. Invoke the `seed-data` skill for guided data classification
2. Include data migration tasks in implementation plans
3. Verify data requirements during pre-commit quality checks
See `.agent-rules/frameworks/database/seed-data.md` for conventions.
```

- [ ] **Step 2: Regenerate agent files**

Run: `python3 scripts/generate-agent-files.py`
Verify CLAUDE.md, GEMINI.md, AGENTS.md, QWEN.md all updated with new rule references.

- [ ] **Step 3: Commit**

```bash
git add AGENTINFO.md CLAUDE.md GEMINI.md AGENTS.md QWEN.md .agent-rules/frameworks/database/seed-data.md
git commit -m "feat(docs): add seed data rule and awareness to AGENTINFO template"
```

---

## Phase 1: Package System

**Goal:** AEC learns what a "package" is — a higher-order bundle that **composes existing install commands** (`aec install rule`, `aec install skill`, `aec install agent`) and adds a coordination layer on top: template-based file rendering that keeps installed items consistent with each other.

**Key principle:** `aec install package seed-data` internally runs `aec install rule seed-data-management` + `aec install skill seed-data` via the existing infrastructure. The manifest tracks individual items the same way it does today. The package adds: (1) the knowledge that these items belong together, (2) template files that modify other installed items for consistency, and (3) hash tracking so user modifications are never silently overwritten.

### Template System Architecture

Instead of injecting snippet blocks into files after installation, packages define **template versions** of files they need to modify. Templates use handlebars syntax for tag resolution and conditional logic.

**How it works:**
1. AEC maintains source files (rules, skills, agents) — unchanged from today
2. Packages provide **template overrides** — alternative versions of specific files with `{{package:name:tag}}` template tags
3. On install, AEC checks if any installed package has a template for the file being installed
4. If yes: resolve the template with all installed packages' vars, write the rendered result
5. If no: straight copy (zero overhead, same as today)
6. Hash every written file. Before future writes, compare hash to detect user modifications.

**Why templates, not snippet injection:**
- No marker comments cluttering output files
- Files regenerated from a single source of truth
- Package interactions handled at template resolution time via handlebars conditionals
- Aligns with how `aec generate rules` already works (generate from source → output)

### Package Structure

```
packages/
  seed-data/
    package.yaml          # Manifest: what to install, template vars, ordering
    rules/
      seed-data.md        # Source for: aec install rule seed-data-management
    skills/
      seed-data/
        SKILL.md           # Source for: aec install skill seed-data
    templates/             # Template overrides for OTHER items (mirrors file paths)
      rules/
        general/
          plans-checklists.md        # Template version of plans-checklists.md
        topics/
          deployment/
            environments.md          # Template version of environments.md
          quality/
            gates.md                 # Template version of gates.md
        frameworks/
          database/
            supabase.md              # Template version (optional, only if supabase installed)
            alembic.md
            prisma.md
        general/
          development-workflow.md
```

Each template file has frontmatter tracking its source:

```markdown
---
based_on:
  item: rules/general/plans-checklists.md
  version: 1.2.0
package: seed-data
package_version: 1.0.0
---

# Plans and Checklists Rules

## Planning Workflow
... (original content) ...

{{#if package:seed-data}}
### Data Requirements Check
If a plan introduces new database tables, status fields, enums, roles, permissions, or lookup data:
- Classify each data item as Reference Data, Seed Data, or Fixture Data
- See `.agent-rules/frameworks/database/seed-data.md` for classification criteria
- Invoke the `seed-data` skill for guided classification and file generation
- Include explicit tasks in the plan for data migrations, seed scripts, or test factories
{{/if}}

{{#if package:observability}}
### Observability Check
... (content from observability package) ...
{{#if package:seed-data}}
- [ ] Data migration monitoring configured
{{/if}}
{{/if}}
```

### package.yaml Schema

```yaml
name: seed-data
version: 1.0.0
description: >
  Seed data management conventions — classifies application data as
  reference (migrations), seed (bootstrap scripts), or fixture (test framework)
  with environment-targeting rules and agent workflow integration.
author: AEC

# What this package installs (uses existing aec install infrastructure)
contents:
  rules:
    - source: rules/seed-data.md
      target: frameworks/database/seed-data.md
  skills:
    - source: skills/seed-data/
      target: seed-data/
      agents: [claude]  # Only installed for Claude (skill format is agent-specific)

# Template overrides for other installed items
# Only processed if the target item is installed
templates:
  - source: templates/rules/general/plans-checklists.md
    target: rules/general/plans-checklists.md
    description: "Adds data classification checkpoint to plan writing"
  - source: templates/rules/topics/deployment/environments.md
    target: rules/topics/deployment/environments.md
    description: "Adds data deployment rules per environment"
  - source: templates/rules/topics/quality/gates.md
    target: rules/topics/quality/gates.md
    description: "Adds seed data verification to pre-commit gates"
  - source: templates/rules/general/development-workflow.md
    target: rules/general/development-workflow.md
    description: "Adds seed data awareness to the dev loop"
  - source: templates/rules/frameworks/database/supabase.md
    target: rules/frameworks/database/supabase.md
    description: "Adds Supabase-specific seed data conventions"
    optional: true  # Only if supabase rule is installed
  - source: templates/rules/frameworks/database/alembic.md
    target: rules/frameworks/database/alembic.md
    description: "Adds Alembic-specific seed data conventions"
    optional: true
  - source: templates/rules/frameworks/database/prisma.md
    target: rules/frameworks/database/prisma.md
    description: "Adds Prisma-specific seed data conventions"
    optional: true

# Template resolution ordering
# If this package's templates reference another package's tags, list it here
install_after: []   # e.g., ["observability"] — resolve observability tags first
install_before: []  # e.g., ["testing-standards"] — this package's tags resolved before testing

# Dependencies (packages that must be installed first)
depends_on: []

# Tags for search/discovery
tags: [database, testing, deployment, data-management]
```

### Task 1.1: Design package.yaml Schema and Loader

**Files:**
- Modify: `pyproject.toml` (add PyYAML and pybars3 dependencies)
- Create: `aec/lib/packages.py`
- Create: `tests/test_packages.py`

- [ ] **Step 0: Add dependencies**

Add `PyYAML>=6.0` and `pybars3>=0.9` (Python handlebars implementation) to `pyproject.toml` dependencies. The codebase currently uses JSON exclusively; YAML is needed for package manifests, pybars3 for template rendering. Verify with `pip install -e .` and `python -c "import yaml; import pybars"`.

Note: evaluate pybars3 vs chevron vs a minimal custom implementation. The template logic needed is limited (`{{#if}}`, `{{variable}}`) — a heavyweight dependency may not be worth it. Decision should be made during implementation.

- [ ] **Step 1: Write failing test for package manifest parsing**

```python
def test_parse_package_manifest_valid():
    """Parse a valid package.yaml and return structured metadata."""
    result = parse_package_manifest(yaml_content)
    assert result["name"] == "seed-data"
    assert result["version"] == "1.0.0"
    assert "contents" in result
    assert "templates" in result

def test_parse_package_manifest_with_ordering():
    """Package with install_after/install_before parsed correctly."""

def test_parse_template_frontmatter():
    """Template files have based_on with item path and version."""
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `parse_package_manifest()`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Write failing tests for template resolution**

```python
def test_resolve_templates_skips_uninstalled_targets():
    """Templates targeting uninstalled items are skipped."""

def test_resolve_templates_includes_installed_targets():
    """Templates targeting installed items are included in resolution."""

def test_resolve_templates_optional_skipped_silently():
    """Optional templates for missing targets produce no warning."""

def test_resolve_ordering_respects_install_after():
    """Packages with install_after have their tags resolved in correct order."""
```

- [ ] **Step 6: Implement template resolution logic**
- [ ] **Step 7: Run all tests, commit**

```bash
git commit -m "feat(packages): add package manifest parser and template resolver"
```

### Task 1.2: Implement Template Engine and Tracked File Writer

**Files:**
- Create: `aec/lib/template_engine.py`
- Create: `aec/lib/tracked_writer.py`
- Create: `tests/test_template_engine.py`
- Create: `tests/test_tracked_writer.py`

Two components: (1) the template engine that processes handlebars tags based on installed packages, and (2) the tracked writer that ALL AEC file writes must go through — hashes before writing, records after, and checks for user modifications before overwriting.

**Template Engine:**

- [ ] **Step 1: Write failing tests for template rendering**

```python
def test_render_with_package_installed():
    """{{#if package:seed-data}} block is included when seed-data is installed."""

def test_render_without_package_installed():
    """{{#if package:seed-data}} block is removed when seed-data is not installed."""

def test_render_nested_conditionals():
    """{{#if package:seed-data}}...{{#if package:observability}}...{{/if}}{{/if}} works."""

def test_render_variable_substitution():
    """{{package:seed-data:description}} resolves to package's description value."""

def test_render_preserves_non_template_content():
    """Content without template tags passes through unchanged."""

def test_render_strips_template_frontmatter():
    """based_on frontmatter is stripped from rendered output."""

def test_render_unicode_content():
    """Templates with unicode content render correctly."""

def test_render_multiple_packages():
    """Multiple packages' tags in one template all resolve correctly."""
```

- [ ] **Step 2: Implement template engine**

```python
def render_template(
    template_content: str,
    installed_packages: dict[str, dict],  # {name: {version, vars, ...}}
) -> str:
    """Render a template file with handlebars tags resolved.
    
    1. Parse template frontmatter (based_on metadata)
    2. Build context: {package: {name: True/False for each known package}}
    3. Process handlebars tags
    4. Return rendered content (frontmatter stripped)
    """
```

- [ ] **Step 3: Run tests, commit**

**Tracked Writer:**

- [ ] **Step 4: Write failing tests for tracked writer**

```python
def test_write_and_track_stores_hash():
    """After writing, hash is recorded in manifest."""

def test_write_detects_user_modification():
    """If file hash doesn't match stored hash, return modification warning."""

def test_write_own_writes_dont_trigger_warning():
    """AEC's own writes update the stored hash, so subsequent checks pass."""

def test_hash_file_vs_directory():
    """File items hashed as file, directory items hashed as directory."""

def test_hash_type_from_frontmatter():
    """Item's hash_type determined from frontmatter or inferred from filesystem."""

def test_write_to_nonexistent_destination():
    """First write to a new destination works without hash check."""
```

- [ ] **Step 5: Implement tracked writer**

```python
def write_tracked(
    content: str | Path,
    destination: Path,
    manifest: dict,
    scope: str,
    item_type: str,
    name: str,
) -> WriteResult:
    """Single function for ALL AEC file writes.
    
    1. If destination exists, hash current file and compare to stored hash
    2. If mismatch → return WriteResult with modification_detected=True
       (caller decides whether to warn user and proceed)
    3. Hash the new content BEFORE writing
    4. Write to destination
    5. Record new hash in manifest
    """

def check_modification(
    destination: Path,
    manifest: dict,
    scope: str,
    item_type: str,
    name: str,
) -> ModificationCheck:
    """Check if a file has been modified since AEC last wrote it.
    Returns: unmodified | modified | new_file (no previous hash)
    """
```

- [ ] **Step 6: Run tests, commit**

```bash
git commit -m "feat(packages): add template engine and tracked file writer"
```

### Task 1.3: Implement `aec install package <name>`

**Files:**
- Modify: `aec/commands/install_cmd.py`
- Modify: `aec/cli.py`
- Create: `tests/test_install_package.py`

Package install is a **composition layer** — it calls existing `run_install()` for each item in the package, then resolves templates for any files that have template overrides. Individual items are tracked in the manifest the same way they would be if installed directly. The package itself is recorded separately so AEC knows these items were installed as a group.

- [ ] **Step 1: Write failing tests for package install flow**

```python
def test_install_package_uses_existing_install():
    """Package install calls run_install() for each rule, skill, and agent in the package."""

def test_install_package_items_tracked_individually():
    """Each item appears in manifest as if installed directly (rules, skills sections)."""

def test_install_package_recorded_as_group():
    """Package itself recorded in manifest 'packages' section with list of member items."""

def test_install_package_renders_templates():
    """Template files are rendered with all installed packages' context and written via tracked writer."""

def test_install_package_skips_templates_for_uninstalled_targets():
    """Templates targeting uninstalled items are skipped."""

def test_install_package_shows_summary():
    """Install prints summary of what was installed and which templates were rendered."""

def test_install_package_agent_specific_content():
    """Agent-specific content only installed for detected agents (e.g., skip .cursor/ if Cursor not installed)."""

def test_install_package_json_output():
    """--format json returns structured result with installed items and rendered templates."""

def test_install_package_skips_already_installed_items():
    """If a rule/skill from the package is already installed, skip it and note it."""

def test_install_package_checks_modification_before_template_render():
    """If a target file was user-modified, warn before replacing with rendered template."""
```

- [ ] **Step 2: Extend `run_install()` to handle `item_type="package"`**

The implementation should:
1. Parse `package.yaml`
2. For each item in `contents`, call `run_install(item_type, name, ...)` — reusing existing infrastructure
3. Record the package in a `packages` section of the manifest: `{name, version, items: [...], templates: [...]}`
4. For each template in `templates`:
   a. Check if target item is installed — skip if not (skip silently if `optional: true`)
   b. Check modification status of target file via `check_modification()`
   c. If modified → warn user with diff + options (yes/no/ignore from now on)
   d. Gather context from ALL installed packages
   e. Render template via `render_template()`
   f. Write via `write_tracked()` — single atomic write with hash recording

- [ ] **Step 3: Add template confirmation UX**

```
Installing package: seed-data v1.0.0...
  ✓ Installed rule: seed-data-management (via aec install rule)
  ✓ Installed skill: seed-data (via aec install skill)

This package enhances 7 of your installed items with template overrides:

  Required:
  1) plans-checklists.md — Adds data classification checkpoint to plan writing
  2) deployment/environments.md — Adds data deployment rules per environment
  3) quality/gates.md — Adds seed data verification to pre-commit gates
  4) development-workflow.md — Adds seed data awareness to the dev loop

  Optional (framework-specific):
  5) supabase.md — Adds Supabase-specific seed data conventions
  6) alembic.md — Adds Alembic-specific seed data conventions  [not installed, skipping]
  7) prisma.md — Adds Prisma-specific seed data conventions    [not installed, skipping]

Apply template enhancements?
  1) Apply all that match my installed items
  2) Review one by one (show diffs)
  3) Skip templates — just install the core items
```

- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(packages): implement package install as composition over existing install"
```

### Task 1.4: Implement `aec uninstall package <name>`

**Files:**
- Modify: `aec/commands/install_cmd.py`
- Create: `tests/test_uninstall_package.py`

Package uninstall reverses the composition: re-renders templates WITHOUT this package's context (removing its content from affected files), then optionally calls existing `run_uninstall()` for each constituent item.

- [ ] **Step 1: Write failing tests**

```python
def test_uninstall_package_rerenders_templates():
    """Affected files re-rendered without this package's context — its content disappears."""

def test_uninstall_package_calls_existing_uninstall():
    """Each constituent item uninstalled via existing run_uninstall()."""

def test_uninstall_package_removes_package_record():
    """Package record removed from manifest 'packages' section."""

def test_uninstall_package_preserves_other_package_content():
    """If another package also has template content in the same file, it's preserved."""

def test_uninstall_package_keeps_items_if_requested():
    """User can choose to remove only template enhancements, keeping individual items."""

def test_uninstall_checks_modification_before_rerender():
    """If a template-rendered file was user-modified, warn before re-rendering."""
```

- [ ] **Step 2: Implement package uninstall with option to keep individual items**

```
Uninstalling package: seed-data...

This will:
  • Re-render 5 template-enhanced files without seed-data content
  • Remove rule: seed-data-management
  • Remove skill: seed-data

Keep the individual rule and skill installed? [y/N]:
```

If yes: re-render templates and remove package record only, items stay installed individually.
If no: re-render templates, then uninstall all constituent items.

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(packages): implement package uninstall with keep-items option"
```

### Task 1.5: Implement Package Partials Tracking

**Files:**
- Create: `aec/lib/package_partials.py`
- Modify: `aec/commands/install_cmd.py` (hook into post-install and post-update)
- Create: `tests/test_package_partials.py`

**Concept:** Instead of scanning all package manifests on every install, maintain a reactive tracking file (`package-partials.json`) that records which items from which packages are installed, at what version, and in what scope. When the last item of a package gets installed, the tripwire fires with scope-aware options.

**File location:** `~/.agents-environment-config/package-partials.json` (global, since it tracks items across all scopes)

**Schema:**
```json
{
  "seed-data": {
    "package_version": "1.0.0",
    "total_items": 2,
    "items": {
      "rule:seed-data-management": {
        "version": "1.0.0",
        "scope": "global",
        "installed_at": "2026-04-10T18:00:00Z"
      },
      "skill:seed-data": {
        "version": "1.0.0",
        "scope": "/Users/matt/projects/my-app",
        "installed_at": "2026-04-10T18:05:00Z"
      }
    },
    "complete": true,
    "package_installed": false,
    "dismissed": false
  }
}
```

- [ ] **Step 1: Write failing tests for partial tracking**

```python
def test_post_install_creates_partial_entry():
    """After installing an item that belongs to a package, package-partials.json is updated."""

def test_partial_tracks_scope():
    """Each item records whether it was installed globally or in a specific repo."""

def test_partial_marks_complete_when_all_installed():
    """When the last item is installed, complete=true."""

def test_partial_not_created_for_non_package_items():
    """Items that don't belong to any package don't create partial entries."""

def test_partial_tracks_multiple_packages():
    """An item can belong to multiple packages; all are tracked."""
```

- [ ] **Step 2: Implement partial tracking in post-install hook**

```python
def update_package_partials(
    item_type: str,
    item_name: str,
    item_version: str,
    scope: Scope,
    available_packages: dict,
) -> list[dict]:
    """Update package-partials.json after an install.
    
    1. Scan package manifests for packages containing this item
    2. Create/update partial entry with scope info
    3. Check if any package is now complete
    4. Return list of newly-completed packages (for tripwire)
    """
```

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(packages): add reactive package-partials tracking"
```

### Task 1.6: Implement Scope-Aware Tripwire

**Files:**
- Create: `aec/lib/tripwire.py`
- Modify: `aec/commands/install_cmd.py`
- Create: `tests/test_tripwire.py`

When `package-partials.json` shows a package is complete, fire the tripwire with scope-aware options.

- [ ] **Step 1: Write failing tests for scope scenarios**

```python
def test_tripwire_all_global():
    """All items in global scope → offer global package install."""

def test_tripwire_all_same_repo():
    """All items in same repo → offer local install or promote-to-global."""

def test_tripwire_mixed_scopes():
    """Items in mixed scopes → show where each is, offer to consolidate to global."""

def test_tripwire_already_installed_package():
    """If package is already installed, no tripwire."""

def test_tripwire_dismissed():
    """If user dismissed this package's tripwire before, don't fire again."""

def test_tripwire_non_interactive():
    """In --non-interactive mode, log suggestion to JSON output, don't prompt."""

def test_tripwire_json_output():
    """In --format json, include 'package_suggestions' with scope details."""
```

- [ ] **Step 2: Implement tripwire with three scope scenarios**

**Scenario 1: All items in global scope**
```
  ✓ Installed skill: seed-data (global)

  ℹ  All items from the seed-data package are installed globally.
     
     Seed data management conventions — classifies application data as
     reference (migrations), seed (bootstrap scripts), or fixture (test
     framework) with environment-targeting rules and agent workflow integration.
     
     Installing the package wires these items together with integration
     snippets that keep your rules consistent:
     • Adds data classification checkpoint to plan writing
     • Adds seed data verification to pre-commit quality gates
     • ...and 5 more

     Install seed-data package globally? [Y/n]:
```

**Scenario 2: All items in same repo**
```
  ✓ Installed skill: seed-data (→ /Users/matt/projects/my-app)

  ℹ  All items from the seed-data package are installed in my-app.

     Seed data management conventions — classifies application data as...

     How would you like to install the package?
     1) Install in this repo only (my-app)
     2) Move all items to global and install package globally
        (benefits all your projects, removes local copies)
     3) Skip for now

     Choose [1]:
```

**Scenario 3: Mixed scopes**
```
  ✓ Installed skill: seed-data (→ /Users/matt/projects/my-app)

  ℹ  All items from the seed-data package are installed, but in different scopes:
     • rule: seed-data-management → global
     • skill: seed-data → /Users/matt/projects/my-app

     Seed data management conventions — classifies application data as...

     To install the package, all items need to be in the same scope.

     Options:
     1) Move everything to global and install package globally
        (moves skill:seed-data from my-app → global)
     2) Skip for now

     Choose [1]:
```

- [ ] **Step 3: Implement scope consolidation (move items between scopes)**

When the user chooses to promote to global:
1. Copy item from local to global via existing install
2. Remove local copy via existing uninstall
3. Update manifest and package-partials
4. Apply integration snippets at the target scope

- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(packages): add scope-aware tripwire with consolidation options"
```

### Task 1.7: Implement Package-Aware Updates

**Files:**
- Modify: `aec/commands/update_cmd.py` (or wherever update lives)
- Modify: `aec/lib/package_partials.py`
- Create: `tests/test_package_update.py`

When an individual item is updated and it belongs to a package, check if the package version has also changed and whether other items in the package need updating too.

- [ ] **Step 1: Write failing tests**

```python
def test_update_item_checks_package_version():
    """When updating a rule that's part of a package, check if package version changed."""

def test_update_cascades_to_package_siblings():
    """If package v1.1.0 updated both rule and skill, updating one offers to update the other."""

def test_update_detects_new_package_items():
    """If package v1.1.0 added a new agent, offer to install it."""

def test_update_rerenders_templates():
    """If template files changed in new package version, re-render affected files."""

def test_update_partials_version_tracking():
    """package-partials.json updated with new package version and item versions."""

def test_update_user_modified_item():
    """If user manually modified an item (hash differs), warn before updating."""
```

- [ ] **Step 2: Implement package-aware update flow**

```
Updating rule: seed-data-management v1.0.0 → v1.1.0...
  ✓ Updated rule: seed-data-management

  ℹ  This item is part of package seed-data, which also updated to v1.1.0.
     Other items in this package:
     • skill: seed-data — v1.0.0 → v1.1.0 available
     
     Update remaining items? [Y/n]:
     
     ✓ Updated skill: seed-data
     ✓ Re-rendered 3 template-enhanced files
```

- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(packages): add package-aware cascading updates"
```

### Task 1.8: Create Seed Data as First Package

**Files:**
- Create: `packages/seed-data/package.yaml`
- Move: `.agent-rules/frameworks/database/seed-data.md` → `packages/seed-data/rules/seed-data.md`
- Move: `.claude/skills/seed-data/SKILL.md` → `packages/seed-data/skills/seed-data/SKILL.md`
- Create: `packages/seed-data/integrations/*.snippet.md` (7 snippet files)

- [ ] **Step 1: Create package directory structure**
- [ ] **Step 2: Write package.yaml manifest**
- [ ] **Step 3: Create snippet files for each integration point**

Each snippet file contains ONLY the content to inject (no markers — the engine adds those):

Example `integrations/quality-gates.snippet.md`:
```markdown
### Data Integrity
- [ ] **Reference Data Migrations** - New models/enums have corresponding idempotent migrations
- [ ] **No Test Data in Migrations** - Migration files contain only reference data, not fixtures
- [ ] **Seed Script Idempotency** - Seed scripts safe to re-run without duplicating data
- [ ] **Test Data Independence** - Tests create their own data, no dependency on seed state
```

- [ ] **Step 4: Test install/uninstall cycle end-to-end**
- [ ] **Step 5: Commit**

```bash
git commit -m "feat(packages): create seed-data as first AEC package"
```

---

## Phase 2: Agent-Friendly CLI

**Goal:** Every AEC command produces structured output that agents can parse and act on. Non-interactive mode eliminates prompts so agents can drive the full workflow.

### Task 2.1: Add `--format json` to All Commands

**Files:**
- Modify: `aec/cli.py`
- Modify: `aec/lib/console.py` (add structured output mode)
- Create: `tests/test_json_output.py`

- [ ] **Step 1: Write failing tests**

```python
def test_list_json_output():
    """aec list --format json returns parseable JSON with items array."""

def test_install_json_output():
    """aec install --format json returns status, installed items, available integrations."""

def test_search_json_output():
    """aec search --format json returns structured search results."""
```

- [ ] **Step 2: Add global `--format` option to CLI**
- [ ] **Step 3: Modify Console to support structured output collection**
- [ ] **Step 4: Update key commands: list, search, info, install, doctor, discover**
- [ ] **Step 5: Run tests, commit**

```bash
git commit -m "feat(cli): add --format json output to all commands"
```

### Task 2.2: Add `--non-interactive` Mode

**Files:**
- Modify: `aec/cli.py` (global flag)
- Modify: `aec/lib/console.py` (suppress prompts)
- Create: `tests/test_non_interactive.py`

- [ ] **Step 1: Write failing tests**

```python
def test_non_interactive_uses_defaults():
    """In non-interactive mode, all prompts use their default value."""

def test_non_interactive_combined_with_json():
    """--non-interactive --format json produces pure JSON with no prompts."""

def test_non_interactive_reports_skipped_prompts():
    """JSON output includes 'decisions' array showing what was auto-decided."""
```

- [ ] **Step 2: Implement global `--non-interactive` flag**
- [ ] **Step 3: Modify all `input()` calls to check flag and use defaults**
- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(cli): add --non-interactive mode for agent-driven workflows"
```

### Task 2.3: Add `aec catalog` Command

**Files:**
- Create: `aec/commands/catalog.py`
- Modify: `aec/cli.py`
- Create: `tests/test_catalog.py`

Exposes the full AEC catalog (all available rules, skills, agents, packages) with metadata so agents can reason about what to install.

**Command taxonomy clarification (no overlap with existing commands):**
- `aec list` — shows **installed** items (what you have) — *already exists*
- `aec catalog` — shows **available** items with install status (what you could have) — *new*
- `aec search` — filters across both installed and available by keyword — *already exists*

`aec catalog` is the agent-facing complement to `aec list`. An agent runs `aec catalog --format json` to see the full menu of what AEC offers, cross-referenced against what's already installed. It includes packages and their constituent items, so the agent can recommend bundles, not just individual items.

- [ ] **Step 1: Write failing tests**

```python
def test_catalog_lists_all_available_items():
    """aec catalog --format json returns all available items with metadata."""

def test_catalog_includes_package_details():
    """Packages include integration points and dependencies."""

def test_catalog_shows_install_status():
    """Each item shows whether it's installed globally, locally, or not at all."""
```

- [ ] **Step 2: Implement catalog command**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cli): add aec catalog command for agent-driven discovery"
```

### Task 2.4: Add Logging Infrastructure

**Files:**
- Create: `aec/lib/logging.py`
- Modify: `aec/cli.py`
- Create: `tests/test_logging.py`

All AEC operations are logged to `~/.agents-environment-config/logs/` so humans can review what the agent did.

- [ ] **Step 1: Write failing tests**

```python
def test_log_file_created_per_session():
    """Each CLI invocation creates a timestamped log entry."""

def test_log_captures_install_operations():
    """Install operations logged with item name, scope, and outcome."""

def test_log_format_human_readable():
    """Log entries are human-readable with timestamps."""
```

- [ ] **Step 2: Implement logging to `~/.agents-environment-config/logs/`**
- [ ] **Step 3: Add `aec logs` command to view recent activity**
- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(cli): add operation logging and aec logs command"
```

---

## Phase 3: Agent-Native Onboarding

**Goal:** Redesign `aec setup` so an agent can drive the entire onboarding process, with the human only answering policy questions.

### Design Principles

1. **Agent scans, AEC reports.** The agent reads code; AEC reports what's available and what's installed.
2. **Agent reasons, human decides.** The agent proposes packages based on the repo; the human approves.
3. **AEC executes.** The agent calls `aec install` commands; AEC handles file operations.
4. **AEC logs.** Everything is logged so the human can review.

### Task 3.1: Add `aec scan` Command

**Files:**
- Create: `aec/commands/scan.py`
- Modify: `aec/cli.py`
- Create: `tests/test_scan.py`

Returns structured information about a repo that an agent can use to make install decisions. AEC doesn't reason — it reports facts.

- [ ] **Step 1: Write failing tests**

```python
def test_scan_detects_frameworks():
    """Scan returns detected frameworks (Next.js, FastAPI, etc.)."""

def test_scan_detects_databases():
    """Scan returns detected database tools (Prisma, Supabase, Alembic, etc.)."""

def test_scan_detects_test_runners():
    """Scan returns detected test frameworks."""

def test_scan_detects_existing_agent_configs():
    """Scan returns which agent configs exist (.claude/, .cursor/, .gemini/, etc.)."""

def test_scan_detects_installed_aec_items():
    """Scan returns what AEC items are already installed."""

def test_scan_json_output():
    """Scan returns everything as structured JSON."""
```

Expected output shape:
```json
{
  "project": {
    "path": "/Users/matt/projects/my-app",
    "name": "my-app",
    "aec_initialized": false
  },
  "detected": {
    "languages": ["typescript", "python"],
    "frameworks": ["nextjs"],
    "databases": ["prisma", "supabase"],
    "test_runners": ["vitest", "playwright"],
    "agents": {
      "claude": {"installed": true, "config_exists": true},
      "cursor": {"installed": true, "config_exists": true},
      "gemini": {"installed": false, "config_exists": false},
      "qwen": {"installed": false, "config_exists": false},
      "codex": {"installed": false, "config_exists": false}
    }
  },
  "aec_state": {
    "global_items": {"skills": [...], "rules": [...], "agents": [...]},
    "local_items": {"skills": [], "rules": [], "agents": []},
    "available_packages": [...]
  }
}
```

- [ ] **Step 2: Implement scan command**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cli): add aec scan for agent-driven project analysis"
```

### Task 3.2: Create Onboarding Skill for Agents

**Files:**
- Create: `.claude/skills/aec-onboarding/SKILL.md`

This skill tells the agent HOW to onboard a project using AEC. The agent follows this workflow, calling AEC CLI commands and asking the human policy questions.

- [ ] **Step 1: Write the onboarding skill**

The skill instructs the agent to:
1. Run `aec scan --format json` to understand the project
2. Run `aec catalog --format json` to see what's available
3. Cross-reference scan results with catalog to identify relevant packages
4. Ask the human 3-5 policy questions based on what was detected
5. Run `aec setup <path> --non-interactive --format json` to initialize
6. Run `aec install package <name> --non-interactive --format json` for each selected package
7. Present a summary with links to logs and configs

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(skills): add aec-onboarding skill for agent-driven project setup"
```

### Task 3.3: Redesign `aec setup` for Agent Compatibility

**Files:**
- Modify: `aec/commands/repo.py` (or wherever setup lives)
- Create: `tests/test_setup_agent_mode.py`

- [ ] **Step 1: Write failing tests**

```python
def test_setup_non_interactive_creates_defaults():
    """Non-interactive setup creates all directories and configs with defaults."""

def test_setup_json_output_reports_actions():
    """JSON output lists every file created and config set."""

def test_setup_idempotent():
    """Running setup on already-setup repo is safe and reports current state."""
```

- [ ] **Step 2: Ensure setup works cleanly in `--non-interactive --format json` mode**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cli): make aec setup agent-compatible with non-interactive JSON mode"
```

---

## Phase 4: Multi-Project Intelligence

**Goal:** When a user adds a second project, the agent (not AEC) identifies commonalities and suggests promoting shared items to global scope.

### Task 4.1: Add `aec compare` Command

**Files:**
- Create: `aec/commands/compare.py`
- Modify: `aec/cli.py`
- Create: `tests/test_compare.py`

Returns structured comparison of what's installed across tracked repos. Agent uses this to reason about global promotion opportunities.

- [ ] **Step 1: Write failing tests**

```python
def test_compare_finds_common_rules():
    """Items installed in 2+ repos are flagged as global candidates."""

def test_compare_finds_unique_items():
    """Items only in one repo are flagged as project-specific."""

def test_compare_json_output():
    """Comparison returns structured JSON the agent can reason about."""
```

Expected output shape:
```json
{
  "tracked_repos": ["/path/to/repo1", "/path/to/repo2"],
  "common": {
    "rules": ["seed-data-management", "typescript-standards"],
    "skills": ["commit", "seed-data"],
    "packages": ["seed-data"]
  },
  "unique": {
    "/path/to/repo1": {"rules": ["supabase"], "skills": ["webapp-testing"]},
    "/path/to/repo2": {"rules": ["alembic"], "skills": []}
  },
  "promotion_candidates": [
    {
      "item": "seed-data",
      "type": "package",
      "installed_in": ["/path/to/repo1", "/path/to/repo2"],
      "suggestion": "Install globally to share across all projects"
    }
  ]
}
```

- [ ] **Step 2: Implement compare command**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cli): add aec compare for multi-project commonality detection"
```

### Task 4.2: Add `aec promote` Command

**Files:**
- Create: `aec/commands/promote.py`
- Create: `tests/test_promote.py`

Moves a locally-installed item to global scope and removes the local copies. This reuses the scope consolidation logic from Task 1.6 (tripwire) but as an explicit user-initiated command rather than a reactive suggestion.

- [ ] **Step 1: Write failing tests**

```python
def test_promote_moves_to_global():
    """Item copied to global, local copies removed, manifest updated."""

def test_promote_preserves_integrations():
    """Integrations in local repos are preserved after promotion."""

def test_promote_reports_affected_repos():
    """Output lists which repos were affected."""

def test_promote_json_output():
    """--format json returns structured result with affected repos and items."""
```

- [ ] **Step 2: Implement promote command (inherits --format json from Phase 2 global flag)**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(cli): add aec promote for local-to-global item promotion"
```

---

## Phase 5: Established Environment Integration

**Goal:** For users like Matt who already have AEC set up with existing skills, rules, and agents, integrate packages gracefully without clobbering anything, with rollback support.

### Design Principles

1. **Never overwrite without asking.** If a target file has been modified since AEC installed it (content hash differs), ask before touching it.
2. **User-owned content is sacred.** Rules, skills, or agents the user created (not from AEC catalog) are never modified, moved, or deleted.
3. **Rollback is always available.** Every package install creates a backup; `aec rollback` restores the previous state.
4. **Integration snippets are clearly marked.** Marker comments make it obvious what AEC added vs what the user wrote.

### Task 5.1: Implement User-Owned Item Detection

**Files:**
- Create: `aec/lib/ownership.py`
- Create: `tests/test_ownership.py`

- [ ] **Step 1: Write failing tests**

```python
def test_detect_aec_managed_item():
    """Items in manifest with matching hash are AEC-managed."""

def test_detect_user_owned_item():
    """Items not in manifest are user-owned."""

def test_detect_modified_aec_item():
    """Items in manifest but with different hash are modified-AEC (user edited)."""
```

- [ ] **Step 2: Implement ownership detection**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(packages): add user-owned vs AEC-managed item detection"
```

### Task 5.2: Implement Backup and Rollback

**Files:**
- Create: `aec/lib/backup.py`
- Create: `aec/commands/rollback.py`
- Create: `tests/test_backup.py`

- [ ] **Step 1: Write failing tests**

```python
def test_backup_created_on_package_install():
    """Before modifying any file, a timestamped backup is created."""

def test_rollback_restores_previous_state():
    """aec rollback <package> restores all files to pre-install state."""

def test_rollback_removes_injected_snippets():
    """Rollback removes snippet markers and content."""

def test_backup_location():
    """Backups stored in .aec-backup/ with ISO timestamps."""

def test_rollback_json_output():
    """--format json returns structured result with restored files."""
```

- [ ] **Step 2: Implement backup on install**
- [ ] **Step 3: Implement rollback command (inherits --format json from Phase 2 global flag)**
- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(packages): add backup and rollback for safe package management"
```

### Task 5.3: Implement `aec register` Command

**Files:**
- Create: `aec/commands/register.py`
- Modify: `aec/cli.py`
- Create: `tests/test_register.py`

Registers user-owned items so AEC tracks them without managing them.

- [ ] **Step 1: Write failing tests**

```python
def test_register_adds_user_owned_item():
    """Registered item appears in manifest with owner: 'user'."""

def test_register_prevents_aec_update():
    """aec update skips user-owned items."""

def test_register_prevents_discovery_flagging():
    """aec discover does not flag registered items as untracked."""

def test_uninstall_user_owned_keeps_files():
    """aec uninstall on user-owned item removes manifest entry but keeps files."""

def test_register_json_output():
    """--format json returns structured registration confirmation."""
```

- [ ] **Step 2: Implement register command with owner field in manifest**
- [ ] **Step 3: Update `aec list` to show ownership column**
- [ ] **Step 4: Run tests, commit**

```bash
git commit -m "feat(cli): add aec register for user-owned item tracking"
```

### Task 5.4: Integration Conflict Resolution

**Files:**
- Modify: `aec/lib/snippet_injection.py`
- Create: `tests/test_integration_conflicts.py`

- [ ] **Step 1: Write failing tests**

```python
def test_inject_into_user_modified_file():
    """If target file was modified by user, show diff and ask before injecting."""

def test_inject_into_user_owned_file():
    """If target file is user-owned (not from AEC), inject is offered but not forced."""

def test_inject_preserves_user_content():
    """User content outside markers is never touched."""
```

- [ ] **Step 2: Add conflict detection to injection engine**
- [ ] **Step 3: Run tests, commit**

```bash
git commit -m "feat(packages): add conflict resolution for established environments"
```

---

## Non-Claude Agent Considerations

### Current State

AEC supports 5 agents (Claude, Cursor, Gemini, Qwen, Codex) via `agents.json`, but the current implementation is Claude-centric:
- Skills live in `.claude/skills/` — other agents don't read this directory
- Agent instruction files (CLAUDE.md, GEMINI.md, etc.) are generated from rules, but skills are Claude-only
- Hooks are supported for Claude, Cursor, and Gemini but with different config formats

### What Needs to Change

#### Phase 2 Impact: Agent-Friendly CLI
- `--format json` and `--non-interactive` work for ANY agent, not just Claude
- The CLI is the interface — any agent that can run shell commands can drive AEC
- No Claude-specific assumptions in CLI output

#### Phase 3 Impact: Onboarding
- `aec scan` must detect ALL installed agents, not just Claude
- The onboarding skill is Claude-specific (lives in `.claude/skills/`), but the equivalent for other agents should be possible:
  - Gemini: equivalent skill or instruction in GEMINI.md
  - Cursor: rule in `.cursor/rules/` that references AEC CLI commands
  - Codex/Qwen: instruction in AGENTS.md/QWEN.md
- `aec setup` must create config directories for ALL detected agents, not just Claude

#### Phase 1 Impact: Packages
- Package contents may include agent-specific items:
  ```yaml
  contents:
    rules:
      - source: rules/seed-data.md
        target: frameworks/database/seed-data.md
    skills:
      - source: skills/seed-data/
        target: seed-data/
        agents: [claude]  # Only installed for Claude
    cursor_rules:
      - source: cursor-rules/seed-data.mdc
        target: seed-data.mdc
        agents: [cursor]  # Only installed for Cursor
  ```
- Integration snippets should work across agent instruction files:
  ```yaml
  integrations:
    - target: rules/general/plans-checklists.md
      snippet: integrations/plans-checklists.snippet.md
      # This rule is shared — all agents read it via .agent-rules/
  ```

#### Discovery Impact
- `aec scan` reports which agents are installed and have configs
- Agent doesn't assume all supported agents are present
- Package install adapts to detected agents — if Cursor isn't installed, skip `.cursor/rules/` content

### Implementation Approach

1. **`agents.json` is the source of truth** — already defines which agents exist and their config paths
2. **`aec scan` uses `detect_agents()`** — already implemented, reports what's actually installed
3. **Package install checks detected agents** — only installs agent-specific content for agents that are present
4. **CLI output is agent-agnostic** — JSON output doesn't assume the consumer is Claude
5. **Skills remain agent-specific** — a Claude skill is in `.claude/skills/`, a Cursor rule is in `.cursor/rules/`. Packages can bundle both.

---

## User-Owned Content (Bring Your Own)

### Problem

Users create their own rules, skills, and agents that aren't in the AEC catalog. These must:
- Not be overwritten by `aec update` or `aec install`
- Be tracked so `aec list` shows them
- Be supported in the package integration system (snippets can target user-owned files if the user allows)
- Survive `aec setup` and `aec discover` without being flagged as "untracked"

### Solution

#### Ownership Model

Every installed item has an `owner` field in the manifest:

```json
{
  "skills": {
    "seed-data": {
      "version": "1.0.0",
      "owner": "aec",
      "contentHash": "sha256:...",
      "installedAt": "2026-04-10T..."
    },
    "my-custom-linter": {
      "version": "1.0.0",
      "owner": "user",
      "contentHash": "sha256:...",
      "registeredAt": "2026-04-10T..."
    }
  }
}
```

#### `aec register` Command

```bash
# Register a user-owned skill so AEC tracks it without managing it
aec register skill my-custom-linter
# → Records in manifest with owner: "user"
# → aec list shows it
# → aec update skips it
# → aec discover won't flag it as untracked
# → Package integrations can target it (with user approval)
```

#### Protection Rules

| Operation | AEC-owned | User-owned |
|-----------|-----------|------------|
| `aec update` | Updates if newer version available | Skipped |
| `aec install` (overwrite) | Asks, then overwrites | Warns, requires `--force` |
| `aec discover` | Shows as "installed" | Shows as "registered" |
| Package integration | Applied automatically | Offered, requires approval |
| `aec uninstall` | Removes files and manifest entry | Removes manifest entry only, files stay |

---

## Best Practices Offered During Onboarding

When the agent onboards a project, it should surface best practices based on what's detected. These aren't forced — they're offered as packages or recommendations.

| Detection | Best Practice Offered |
|-----------|----------------------|
| Database tool detected (Prisma, Supabase, Alembic) | Seed data package |
| Test runner detected but no test standards rule | Testing standards rule |
| Multiple environments in deploy config | Deployment environments rule |
| TypeScript detected | TypeScript typing standards rule |
| API routes detected | API design standards rule |
| No quality gates | Quality gates rule |
| Git repo with no commit conventions | Git workflow rule |
| No observability setup | Monitoring rule |
| No accessibility testing | Accessibility standards rule |

The agent reasons about relevance; AEC provides the catalog. The human approves.

---

## Relationship to Discovery Spec

The [Discovery spec](../specs/2026-04-10-discovery-adopt-design.md) and this plan are **complementary, not overlapping**. They share infrastructure but serve different purposes:

| Concern | Discovery Spec | This Plan |
|---------|---------------|-----------|
| **Purpose** | Find existing files that match AEC catalog items | Bundle, install, and integrate packages of rules+skills |
| **Command** | `aec discover` (similarity scanning) | `aec scan` (project analysis for onboarding) |
| **File comparison** | Hash-based similarity (Quick/Normal/Deep) | Not applicable — packages are installed fresh |
| **Backup** | `.aec-backup/` with timestamps | Same mechanism — shared utility |
| **Dismissals** | `.aec.json` dismissed section | Not applicable |
| **Catalog hashes** | `catalog-hashes.json` | Package manifests (`package.yaml`) |

**Shared infrastructure to build once:**
- `.aec-backup/` backup/restore utilities (both specs use the same pattern)
- Content hashing (`hash_skill_directory()` already exists)
- Manifest v2 read/write (both add new fields)

**Integration points:**
- `aec discover` should recognize package-installed items as "installed" (not flag them as untracked)
- `aec scan` (this plan) reports project facts; `aec discover` (spec) finds similarity matches. Different commands, complementary purposes.
- The existing `aec discover` command (Raycast-based repo discovery) will be reconciled with the spec's similarity-based `aec discover` as part of the spec's implementation — this plan does not modify the existing `aec discover` command.

**Dependency:** The discovery spec's similarity engine is a separate workstream. This plan does not depend on it and does not conflict with it.

---

## Migration Path for Existing Users

For users already running AEC (like the author):

1. **Phase 0** is immediately usable — install the seed-data rule and skill manually via existing `aec install`
2. **Phase 1** introduces packages — existing rules/skills become package-eligible. Migration:
   - Run `aec doctor` — detects items that are now available as packages
   - Offers to convert: "seed-data rule and skill are now available as the seed-data package. Convert? This will add integration snippets to your existing rules."
   - Rollback available if integration snippets cause issues
3. **Phase 2** is additive — `--format json` and `--non-interactive` don't change existing behavior
4. **Phase 3** is optional — existing users don't need to re-onboard. But if they run `aec scan`, they get recommendations for packages they're missing.
5. **Phase 4** requires tracked repos — for users with existing repos, `aec compare` reads from the setup tracking log (`setup-repo-locations.txt` or `tracked-repos.json` when migrated). Repos set up before Phase 4 are already tracked. Users who set up repos manually (without `aec setup`) can run `aec setup <path>` retroactively — it's idempotent and won't clobber existing configs.
6. **Phase 5** specifically handles their case — ownership detection, backup, rollback, `aec register` for user-owned content

No existing setup is broken. Everything is opt-in. Rollback is always available.

---

## Phase 6: Rules as Packages (Convention Packages)

**Goal:** Repackage the existing 38 AEC rules from a monolithic "install everything" model into opt-in convention packages. Users choose which conventions match their workflow during onboarding. The current rules are opinionated (created by one person) — other users should get to pick which opinions they share.

### Package Tiers

**Base (installed automatically — truly universal, non-opinionated):**
- Security basics (secrets management, no credentials in code)
- Git fundamentals (conventional commits, branch naming)
- Error handling essentials

**Convention packages (offered during onboarding — user chooses):**

| Package | Current Rules Included | Description |
|---------|----------------------|-------------|
| `quality-gates` | quality/gates.md, quality/error-handling.md, quality/logging.md | Strict pre-commit/pre-push quality checks |
| `testing-standards` | testing/standards.md, testing/organization.md, testing/tools.md | TDD, fixture patterns, coverage requirements |
| `typescript-conventions` | typescript/typing-standards.md | TypeScript typing and style conventions |
| `python-conventions` | python/style.md | Python style conventions |
| `database-conventions` | database/connection-management.md, database/supabase.md, database/alembic.md, database/prisma.md, database/sqlalchemy.md | DB patterns, connection management, ORM conventions |
| `api-standards` | api/design-standards.md | API design conventions |
| `deployment-standards` | deployment/environments.md | Environment management, CI/CD |
| `accessibility` | accessibility/standards.md | Accessibility standards |
| `observability` | observability/monitoring.md | Monitoring, logging |
| `seed-data` | (new from Phase 0) | Reference data, seed data, fixture data conventions |

**Cross-cutting packages with templates:**
The `seed-data` package is the model — it has its own rule + skill, plus templates that enhance `quality-gates`, `deployment-standards`, `database-conventions`, and `testing-standards` if those are also installed. Other packages can follow the same pattern.

### Task 6.1: Audit Current Rules for Package Boundaries

**Files:**
- Read: all 38 rules in `.agent-rules/`
- Create: `docs/superpowers/specs/rules-as-packages-mapping.md`

- [ ] **Step 1: Map every rule to a proposed package**
- [ ] **Step 2: Identify cross-package dependencies (which rules reference each other)**
- [ ] **Step 3: Identify which rules are truly universal vs opinionated**
- [ ] **Step 4: Document the mapping and get user approval**
- [ ] **Step 5: Commit**

### Task 6.2: Create Base Package

- [ ] **Step 1: Extract universal rules into `packages/base/`**
- [ ] **Step 2: Write package.yaml with no dependencies**
- [ ] **Step 3: Test install from scratch**
- [ ] **Step 4: Commit**

### Task 6.3: Create Convention Packages

- [ ] **Step 1: For each convention package, create `packages/<name>/` with package.yaml, rules, and templates**
- [ ] **Step 2: Write templates for cross-package interactions (e.g., seed-data enhancing quality-gates)**
- [ ] **Step 3: Test install combinations**
- [ ] **Step 4: Commit**

### Task 6.4: Update Onboarding to Offer Convention Packages

- [ ] **Step 1: Update the onboarding skill (Task 3.2) to present convention packages**
- [ ] **Step 2: Update `aec setup` to install base package automatically, offer conventions**
- [ ] **Step 3: Test onboarding flow end-to-end**
- [ ] **Step 4: Commit**

### Task 6.5: Migration for Existing Users

- [ ] **Step 1: `aec doctor` detects existing monolithic rule installation**
- [ ] **Step 2: Offer to convert to package-based installation**
  - Maps installed rules to convention packages
  - Shows which packages would cover their current setup
  - Offers to convert (with rollback)
- [ ] **Step 3: Test migration flow**
- [ ] **Step 4: Commit**

---

## Integration Constraints (Must Address in Phase 1)

The template system resolves most of the snippet injection constraints, but these still need attention:

1. **`aec validate` + pre-commit parity check** — Compares `.cursor/rules/*.mdc` against `.agent-rules/*.md`. Template-rendered files will have additional content from packages. Fix: validation should compare the rendered output against the expected rendering (template + installed packages), not against the raw `.cursor/rules/` source. Alternatively, `.cursor/rules/` sources could also use the same templates, keeping parity.

2. **`aec generate rules`** — Regenerates `.agent-rules/` from `.cursor/rules/`. After generation, the template engine must re-render any files that have template overrides from installed packages. The `package-partials.json` tracking knows which files were template-rendered, so the generation pipeline becomes: strip frontmatter → write base file → check for template overrides → re-render if needed → hash and track.

3. **`aec uninstall` individual items that belong to a package** — Uninstalling `rule seed-data-management` when it's part of an installed package leaves stale package records. Fix: post-uninstall check against `package-partials.json`, warn user, offer to uninstall the full package or re-render templates without the missing item.

4. **`agent_files.py` yaml import** — Already has `try: import yaml` with `HAS_YAML` fallback. Adding PyYAML as a required dependency means the guard is no longer needed. Clean up during Phase 1.

5. **ALL existing file writes must migrate to `write_tracked()`** — Every place in AEC that writes a file (install, generate, setup, etc.) must go through the tracked writer so hash tracking is consistent. This is a cross-cutting change that touches multiple commands. Audit all `write_text()`, `shutil.copy2()`, `shutil.copytree()` calls.

---

## Known Gaps (Deferred)

These are acknowledged gaps that are acceptable for v1 but should be addressed in future iterations:

1. **Package versioning/update strategy** — `package.yaml` has a `version` field, but no `aec update` logic for packages yet. What happens to existing integration snippets when a package version bumps? Deferred until real-world usage reveals the right pattern.
2. **Non-Claude agent onboarding skills** — The onboarding skill (Task 3.2) is Claude-specific. Equivalents for Gemini (GEMINI.md instruction), Cursor (.cursor/rules/), and Codex (AGENTS.md) should be created but are not scoped in this plan.
3. **Best practices recommendation engine** — The best practices table in the onboarding section is design thinking that Task 3.2's onboarding skill should encode. Consider whether the mapping should be data-driven (`recommendations.json`) or hardcoded in the skill.
