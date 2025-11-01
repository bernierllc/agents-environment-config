<!-- 759781a0-49f3-4f1d-ba61-a5e484ca0a70 08510841-731f-4f80-bfd7-868bf113fb85 -->
# Cursor Rules Consolidation Plan

## Current Status

**Last Updated**: Files moved to this repo and initial consolidation started.

**Completed**:
- ✅ Created directory structure following MECE pattern
- ✅ Moved and organized general rules into `general/` directory
- ✅ Added frontmatter to all general rules (architecture, development-workflow, documentation, security, port-management, project-setup-cli)
- ✅ Testing framework rules already consolidated with frontmatter
- ✅ Updated README.mdc with current structure and navigation
- ✅ Consolidated 38 rules files from 189 source files
- ✅ Created Python style guide
- ✅ Created TypeScript typing standards (consolidated from 5+ sources)
- ✅ Created FastAPI patterns
- ✅ Created SQLAlchemy patterns
- ✅ Created Prisma patterns
- ✅ Created Alembic patterns
- ✅ Created Supabase patterns
- ✅ Created Git workflow rules (consolidated from 3+ sources)
- ✅ Created API design standards (consolidated from 4+ sources)
- ✅ Created quality gates (consolidated from 2+ sources)
- ✅ Created error handling rules
- ✅ Created logging standards
- ✅ Created plans-checklists rules
- ✅ Created rules-about-rules meta rules
- ✅ Created React Native/Expo rules
- ✅ Created Next.js App Router rules
- ✅ Created Tailwind CSS rules
- ✅ Created Tamagui rules
- ✅ Created authentication and secrets management rules
- ✅ Created package management rules
- ✅ Created README files for all major directories

**Progress**: 38/189 files consolidated (~20% complete, but covering all major categories)

**Remaining Work**:
- Continue extracting patterns from remaining project-specific files
- Some project-specific rules should remain in projects with proper frontmatter
- Create migration guide for projects

## Phase 1: Audit and Analysis

### 1.1 Complete File Inventory

- [ ] Create comprehensive inventory of all 139+ .mdc files found
- [ ] Map each file to its source project/directory
- [ ] Document current frontmatter structure for each file

### 1.2 Content Analysis

For each .mdc file, analyze:

- [ ] **Scope Determination**: 
  - General (applies to all projects)
  - Language-specific (Python, TypeScript, etc.)
  - Stack-specific (Next.js, React Native, FastAPI, etc.)
  - Framework-specific (Prisma, Alembic, Tailwind, etc.)
  - Project-specific (formExpert.co, SCF-Neue, etc.)
- [ ] **Content Quality**: Identify valuable content vs duplicates/outdated
- [ ] **Dependencies**: Note if rules reference other rules or project-specific code
- [ ] **Frontmatter Gaps**: Identify missing description, globs, alwaysApply fields

### 1.3 Mocking Best Practices Research

- [ ] Research tiered mocking strategies (unit → integration → E2E)
- [ ] Define verification strategy to ensure mocks match reality (contract tests, golden files, schema/type checks, integration parity tests)
- [ ] Select canonical references (e.g., Martin Fowler Mocks vs Stubs, Google Testing Blog, Thoughtworks Tech Radar) and link them
- [ ] Document guidance on where mocks are acceptable vs prohibited

## Phase 2: Category Classification

### 2.1 General Rules (Always Apply)

These apply universally across all projects:

- Core architectural principles
- Git workflow standards
- Documentation standards  
- Security basics
- Development workflow
- Quality gates (general)
- Plans/checklists usage

**Source files to consolidate:**

- `.cursor/rules/architecture.mdc`
- `.cursor/rules/development-workflow.mdc`
- `.cursor/rules/documentation.mdc`
- `.cursor/rules/security.mdc`
- `.cursor/rules/port-management.mdc`
- `tools/.cursor/rules/cursor-rules.mdc`
- `tools/.cursor/rules/shared.mdc`
- `tools/.cursor/rules/rules.mdc`
- `mara/Sites/.cursor/rules/00-core.mdc`
- Various `git.mdc` files (general patterns)

### 2.2 Language-Specific Rules

Organize by programming language:

#### 2.2.1 Python Rules (`python/`)

- Python style (PEP 8, Black, type hints)
- Python-specific patterns
- Virtual environment requirements

**Source files:**

- `mara/Sites/.cursor/rules/01-python-style.mdc`
- `prevost/.cursor/rules/flake8-formatting.mdc`
- `prevost/.cursor/rules/python-server-apis.mdc`
- General Python rules from various projects

#### 2.2.2 TypeScript Rules (`typescript/`)

- TypeScript typing standards (no `any`, strict mode)
- Type safety requirements
- React import patterns

**Source files:**

- `SCF-Neue/.cursor/rules/typescript-typing.mdc`
- `EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc`
- `mbernier.com/mbernier.com/.cursor/rules/coding/linting-type-safety.mdc`
- `robert_champion/barevents/.cursor/rules/typescript-strict.mdc`

### 2.3 Stack-Specific Rules

#### 2.3.1 Next.js Stack (`stacks/nextjs/`)

- Next.js App Router patterns
- React component standards
- Server vs Client components

**Source files:**

- `vibeapp.studio/.cursor/rules/nextjs-react.mdc`
- `Builders_Main/vibeapp.studio/.cursor/rules/project-structure.mdc`
- Next.js-specific patterns from various projects

#### 2.3.2 React Native/Expo Stack (`stacks/react-native/`)

- Expo development commands
- Platform-specific files
- EAS build commands
- React Native patterns

**Source files:**

- `SCF-Neue/.cursor/rules/react-native.mdc`
- React Native patterns from other projects

#### 2.3.3 Python Backend Stack (`stacks/python-backend/`)

- FastAPI patterns
- API structure
- Flask patterns (if any)

**Source files:**

- `mara/Sites/.cursor/rules/02-fastapi.mdc`
- `prevost/.cursor/rules/python-server-apis.mdc`
- `prevost/.cursor/rules/api-standards.mdc`

### 2.4 Framework/Tool-Specific Rules

#### 2.4.1 Database Frameworks (`frameworks/database/`)

- Prisma patterns
- Supabase patterns
- SQLAlchemy patterns
- Alembic migrations

**Source files:**

- `SCF-Neue/.cursor/rules/supabase.mdc`
- `SCF-Neue/.cursor/rules/trpc-supabase-patterns.mdc`
- `Builders_Main/vibeapp.studio/.cursor/rules/database.mdc`
- `robert_champion/barevents/.cursor/rules/alembic.mdc`
- `mara/Sites/.cursor/rules/03-sqlalchemy-db.mdc`
- `EarnLearn/el_new_app/.cursor/rules/database-migration-safety.mdc`

#### 2.4.2 UI Frameworks (`frameworks/ui/`)

- Tailwind CSS styling
- Tamagui patterns
- React component patterns
- Styling standards

**Source files:**

- `vibeapp.studio/.cursor/rules/styling.mdc`
- `SCF-Neue/.cursor/rules/tamagui-debugging.mdc`
- `SCF-Neue/.cursor/rules/tamagui-properties.mdc`
- `SCF-Neue/.cursor/rules/ui-development.mdc`
- `mara/Sites/.cursor/rules/04-react.mdc`

#### 2.4.3 Testing Frameworks (`frameworks/testing/`)

- Testing standards (no mocks)
- Test organization
- Coverage requirements
- Testing tools

**Source files:**

- `tools/.cursor/rules/coding/testing-standards.mdc`
- `robert_champion/barevents/.cursor/rules/testing.mdc`
- `vibeapp.studio/.cursor/rules/testing.mdc`
- `houseofgenius/.cursor/rules/testing.mdc`
- `prevost/.cursor/rules/testing.mdc`
- `EarnLearn/el_new_app/.cursor/rules/testing-patterns.mdc`
- `EarnLearn/el_new_app/.cursor/rules/tdd.mdc`

### 2.5 Topic-Specific Rules

#### 2.5.1 Git Workflow (`topics/git/`)

- Branching strategies
- Commit conventions
- PR workflows
- Git hooks

**Source files:**

- `mara/energy_site/.cursor/rules/branching.mdc`
- `mara/energy_site/.cursor/rules/git.mdc`
- `mara/energy_site/.cursor/rules/pull-requests.mdc`
- `tools/.cursor/rules/git-workflow.mdc`
- Various `git.mdc` files (project-specific patterns to extract)

#### 2.5.2 API Development (`topics/api/`)

- API design standards
- Error handling
- Authentication patterns
- API client usage

**Source files:**

- `prevost/.cursor/rules/api-standards.mdc`
- `prevost/.cursor/rules/api-request-flow.mdc`
- `EarnLearn/el_new_app/.cursor/rules/api-client-ui.mdc`
- `SCF-Neue/.cursor/rules/api-testing.mdc`
- `vibeapp.studio/.cursor/rules/api-standards.mdc`

#### 2.5.3 Security (`topics/security/`)

- Authentication boundaries
- Secrets management
- Security patterns
- RBAC

**Source files:**

- `formExpert.co/.cursor/rules/authentication-boundaries.mdc`
- `mara/Sites/.cursor/rules/security_secrets.mdc`
- `mara/Sites/.cursor/rules/rbac_okta.mdc`
- `mbernier.com/mbernier.com/.cursor/rules/security-vulnerabilities.mdc`

#### 2.5.4 Quality and Standards (`topics/quality/`)

- Quality gates
- Code quality standards
- Linting patterns
- Production readiness

**Source files:**

- `mbernier.com/mbernier.com/.cursor/rules/coding/quality-gates.mdc`
- `SCF-Neue/.cursor/rules/code-quality.mdc`
- `EarnLearn/el_new_app/.cursor/rules/production-ready.mdc`
- `EarnLearn/el_new_app/.cursor/rules/quality-gates.mdc`
- `robert_champion/barevents/.cursor/rules/code-quality.mdc`

### 2.6 Project-Specific Rules

These remain in project directories but should have proper frontmatter indicating they're project-specific:

**Keep in project directories:**

- `formExpert.co/.cursor/rules/*.mdc` (with project-specific frontmatter)
- `SCF-Neue/.cursor/rules/*.mdc` (Extract general patterns, keep SCF-specific)
- `EarnLearn/*/.cursor/rules/*.mdc` (Extract general patterns)
- `prevost/.cursor/rules/*.mdc` (Extract general patterns, keep Prevost-specific)
- `mara/*/.cursor/rules/*.mdc` (Extract general patterns)
- `vibeapp.studio/.cursor/rules/*.mdc` (Extract general patterns)
- All other project-specific rules

## Phase 3: Directory Structure Design

### 3.1 Proposed Structure

```
.cursor/rules/
├── README.mdc                    # Index and navigation
├── general/                      # Always-apply rules
│   ├── architecture.mdc
│   ├── development-workflow.mdc
│   ├── documentation.mdc
│   ├── git-workflow.mdc
│   ├── plans-checklists.mdc
│   ├── quality-gates.mdc
│   └── security.mdc
├── languages/                    # Language-specific
│   ├── python/
│   │   ├── style.mdc
│   │   ├── type-hints.mdc
│   │   └── virtual-environments.mdc
│   ├── typescript/
│   │   ├── typing-standards.mdc
│   │   ├── strict-mode.mdc
│   │   └── react-imports.mdc
│   └── README.mdc
├── stacks/                      # Stack-specific
│   ├── nextjs/
│   │   ├── app-router.mdc
│   │   ├── react-components.mdc
│   │   └── project-structure.mdc
│   ├── react-native/
│   │   ├── expo-development.mdc
│   │   ├── platform-files.mdc
│   │   └── eas-builds.mdc
│   ├── python-backend/
│   │   ├── fastapi.mdc
│   │   └── api-structure.mdc
│   └── README.mdc
├── frameworks/                   # Framework/tool-specific
│   ├── database/
│   │   ├── prisma.mdc
│   │   ├── supabase.mdc
│   │   ├── sqlalchemy.mdc
│   │   └── alembic.mdc
│   ├── ui/
│   │   ├── tailwind-css.mdc
│   │   ├── tamagui.mdc
│   │   └── react-components.mdc
│   ├── testing/
│   │   ├── standards.mdc
│   │   ├── organization.mdc
│   │   └── tools.mdc
│   └── README.mdc
├── topics/                      # Cross-cutting topics
│   ├── api/
│   │   ├── design-standards.mdc
│   │   ├── error-handling.mdc
│   │   └── client-usage.mdc
│   ├── git/
│   │   ├── branching.mdc
│   │   ├── commits.mdc
│   │   └── pull-requests.mdc
│   ├── security/
│   │   ├── authentication.mdc
│   │   ├── secrets.mdc
│   │   └── rbac.mdc
│   ├── quality/
│   │   ├── gates.mdc
│   │   ├── code-quality.mdc
│   │   └── production-readiness.mdc
│   └── README.mdc
└── packages/                     # Package-specific (for tools/)
    ├── bernierllc-packages.mdc
    ├── package-reuse.mdc
    ├── package-management.mdc
    └── publishing.mdc
```

## Phase 4: Frontmatter Standardization

### 4.1 Standard Frontmatter Template

```yaml
---
description: Clear, concise description of what this rule covers
globs: ["**/*.ts", "**/*.tsx"]  # File patterns when applicable
alwaysApply: false  # true for general rules, false for specific
tags: [typescript, react, components]  # Optional: for searchability
---
```

### 4.2 Frontmatter by Category

#### General Rules

```yaml
---
description: Core architectural principles
alwaysApply: true
---
```

#### Language-Specific Rules

```yaml
---
description: TypeScript typing standards and best practices
globs: ["**/*.ts", "**/*.tsx"]
alwaysApply: false
tags: [typescript, typing, strict-mode]
---
```

#### Stack-Specific Rules

```yaml
---
description: Next.js App Router and React component standards
globs: ["src/app/**", "src/components/**"]
alwaysApply: false
tags: [nextjs, react, app-router]
---
```

#### Framework Rules

```yaml
---
description: Prisma database patterns and conventions
globs: ["prisma/**", "**/*prisma*.ts"]
alwaysApply: false
tags: [prisma, database, orm]
---
```

#### Project-Specific Rules

```yaml
---
description: FormExpert.co architectural principles
globs: []
alwaysApply: false
tags: [formexpert, project-specific]
scope: project  # Indicates this is project-specific
project: formexpert.co
---
```

## Phase 5: Content Consolidation Strategy

### 5.1 Extraction Process

For each source file:

1. **Identify Core Content**: Extract universally applicable principles
2. **Identify Project-Specific Content**: Flag for project directory or removal
3. **Merge Duplicates**: Combine similar rules from multiple sources
4. **Preserve Best Content**: Keep the most comprehensive, well-written version
5. **Cross-Reference**: Link related rules appropriately

### 5.2 Quality Filters

- **Keep**: Well-written, comprehensive, actively used rules
- **Merge**: Similar rules with complementary content
- **Extract**: General patterns from project-specific files
- **Archive**: Outdated or superseded rules (mark as deprecated)
- **Remove**: Truly project-specific details that don't apply elsewhere

### 5.3 Consolidation Examples

#### Example 1: Testing Standards

**Sources:**

- `tools/.cursor/rules/coding/testing-standards.mdc`
- `robert_champion/barevents/.cursor/rules/testing.mdc`
- Multiple other testing.mdc files

**Consolidated to:** `frameworks/testing/standards.mdc`

- Merge "no mocks" principle from all
- Merge coverage requirements
- Merge test organization patterns
- Keep tool-specific examples but generalize

#### Example 2: TypeScript Typing

**Sources:**

- `SCF-Neue/.cursor/rules/typescript-typing.mdc`
- `EarnLearn/el_new_app/.cursor/rules/strict-typing.mdc`

**Consolidated to:** `languages/typescript/typing-standards.mdc`

- Merge "no any" principle
- Keep React import patterns from SCF-Neue
- Keep strict mode requirements from EarnLearn
- Add to general TypeScript rules

#### Example 3: Git Workflow

**Sources:**

- Multiple `git.mdc` files
- `mara/energy_site/.cursor/rules/branching.mdc`

**Consolidated to:** `topics/git/branching.mdc` and `topics/git/workflow.mdc`

- Extract general branching patterns
- Keep project-specific patterns in project directories

## Phase 6: Implementation Steps

### Step 1: Create Directory Structure

- [x] Create all top-level directories
- [x] Create subdirectories for categories
- [x] Create README.mdc files for navigation

### Step 2: Process General Rules First

- [x] Consolidate architecture rules
- [x] Consolidate development workflow
- [x] Consolidate documentation standards
- [x] Consolidate security basics
- [x] Ensure alwaysApply: true for general rules
- [x] Added frontmatter to all general rules
- [x] Moved general rules to `general/` directory

### Step 3: Process Language Rules

- [ ] Consolidate Python rules
- [ ] Consolidate TypeScript rules
- [ ] Extract language patterns from project-specific files

### Step 4: Process Stack Rules

- [ ] Consolidate Next.js rules
- [ ] Consolidate React Native rules
- [ ] Consolidate Python backend rules

### Step 5: Process Framework Rules

- [ ] Consolidate database framework rules
- [ ] Consolidate UI framework rules
- [x] Consolidate testing framework rules (already consolidated with frontmatter)

### Step 6: Process Topic Rules

- [ ] Consolidate API development rules
- [ ] Consolidate Git rules
- [ ] Consolidate security rules
- [ ] Consolidate quality rules

### Step 7: Update Project-Specific Rules

- [ ] Add proper frontmatter to project-specific rules
- [ ] Mark project-specific scope
- [ ] Link to general rules where applicable
- [ ] Keep only truly project-specific content

### Step 8: Create Navigation and Index

- [x] Create comprehensive README.mdc
- [x] Cross-reference related rules
- [x] Document organization structure
- [x] Add usage guidelines

### Step 9: Validation

- [x] Verify all rules have proper frontmatter (general rules and testing framework rules completed)
- [ ] Check for broken cross-references
- [ ] Ensure no duplicate content
- [x] Validate glob patterns (testing rules have appropriate globs)
- [ ] Test rule application in Cursor IDE

## Phase 7: Documentation

### 7.1 Create Master README

- Overview of organization structure
- How to find relevant rules
- How rules are applied
- How to contribute new rules
- How to update existing rules

### 7.2 Migration Notes

- Document what moved where
- Note deprecated rules
- Provide migration guide for projects
- Create checklist for projects to update references

## Success Criteria

✅ All 139+ .mdc files have been audited and categorized

✅ General patterns extracted from project-specific files

✅ Consolidated rules organized in logical directory structure

✅ All rules have proper, consistent frontmatter

✅ No duplicate content (unless intentional for different contexts)

✅ Project-specific rules properly marked and organized

✅ Navigation and cross-references working

✅ Rules can be discovered and applied correctly by Cursor IDE

