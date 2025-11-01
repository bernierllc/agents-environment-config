# Cursor Rules Consolidation Inventory

## File Count
- Total .mdc files found: 189
- Files already consolidated in this repo: 11
- Files remaining to consolidate: ~178

## Consolidation Strategy

### Phase 1: General Rules (Always Apply)
Files to consolidate into `general/`:
- [x] architecture.mdc (already moved)
- [x] development-workflow.mdc (already moved)
- [x] documentation.mdc (already moved)
- [x] security.mdc (already moved)
- [x] port-management.mdc (already moved)
- [x] project-setup-cli.mdc (already moved)
- [ ] plans-and-checklists.mdc (from tools)
- [ ] cursor-rules.mdc (from tools - rules about rules)
- [ ] rules.mdc (from tools/mbernier.com - rules about rules)
- [ ] shared.mdc (from tools - general development rules)

### Phase 2: Language-Specific Rules

#### Python
- mara/Sites/01-python-style.mdc
- prevost/flake8-formatting.mdc
- prevost/python-server-apis.mdc

#### TypeScript
- SCF-Neue/typescript-typing.mdc (already has frontmatter)
- EarnLearn/el_new_app/strict-typing.mdc
- mbernier.com/coding/linting-type-safety.mdc
- tools/coding/linting-type-safety.mdc
- robert_champion/barevents/typescript-strict.mdc
- vibeapp.studio/typescript.mdc

### Phase 3: Stack-Specific Rules

#### Next.js
- vibeapp.studio/nextjs-react.mdc
- Builders_Main/vibeapp.studio/project-structure.mdc

#### React Native
- SCF-Neue/react-native.mdc

#### Python Backend
- mara/Sites/02-fastapi.mdc
- prevost/python-server-apis.mdc

### Phase 4: Framework Rules

#### Database
- SCF-Neue/supabase.mdc
- SCF-Neue/trpc-supabase-patterns.mdc
- Builders_Main/vibeapp.studio/database.mdc
- vibeapp.studio/database.mdc
- robert_champion/barevents/alembic.mdc
- mara/Sites/03-sqlalchemy-db.mdc
- EarnLearn/el_new_app/database-migration-safety.mdc

#### UI
- vibeapp.studio/styling.mdc
- SCF-Neue/tamagui-debugging.mdc
- SCF-Neue/tamagui-properties.mdc
- SCF-Neue/ui-development.mdc
- mara/Sites/04-react.mdc

#### Testing
- [x] frameworks/testing/standards.mdc (already consolidated)
- [x] frameworks/testing/organization.mdc (already consolidated)
- [x] frameworks/testing/tools.mdc (already consolidated)
- Various testing.mdc files from projects (extract general patterns)

### Phase 5: Topic Rules

#### API
- prevost/api-standards.mdc
- prevost/api-request-flow.mdc
- EarnLearn/el_new_app/api-client-ui.mdc
- SCF-Neue/api-testing.mdc
- vibeapp.studio/api-standards.mdc
- robert_champion/barevents/api-integration.mdc

#### Git
- mara/energy_site/branching.mdc
- mara/energy_site/pull-requests.mdc
- tools/git-workflow.mdc (if exists)
- mcp-ask-questions/commits.mdc

#### Security
- formExpert.co/authentication-boundaries.mdc
- mara/Sites/security_secrets.mdc
- mara/Sites/rbac_okta.mdc
- mbernier.com/security-vulnerabilities.mdc

#### Quality
- EarnLearn/el_new_app/quality-gates.mdc
- EarnLearn/el_new_app/production-ready.mdc
- mbernier.com/coding/quality-gates.mdc
- SCF-Neue/code-quality.mdc
- robert_champion/barevents/code-quality.mdc
- neverhub/build-quality.mdc

### Phase 6: Package Rules (tools/)
- tools/packages/*.mdc (various package-specific rules)
- tools/package-management.mdc
- tools/package-reuse.mdc
- tools/publishing.mdc
- EarnLearn/el_new_app/bernierllc-packages.mdc
- vibeapp.studio/bernierllc-packages.mdc
- mbernier.com/bernierllc-packages.mdc

## Notes
- Many files have duplicates across projects (e.g., testing.mdc, api-standards.mdc)
- Some files are project-specific and should remain in their projects with proper frontmatter
- General patterns should be extracted and consolidated

