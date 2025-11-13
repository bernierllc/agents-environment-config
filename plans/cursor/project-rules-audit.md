# Project Rules Audit Report

This report identifies which project-specific rule files can be removed because they're covered by global rules.

## Summary

- **Total projects audited**: 22

- **Total rule files**: 190

- **Can remove (covered by global)**: 125

- **Keep (project-specific)**: 50

- **Review needed**: 15


## Recommendations


1. **Remove files** marked as 'Can Remove' - they're covered by global rules

2. **Keep files** marked as 'Project-Specific' - they contain unique project patterns

3. **Review files** marked as 'Review Needed' - manually check if they're duplicates


## Builders_Main/vibe_scaffold/.cursor

**Total files**: 5


### Can Remove (Covered by Global Rules)

- `plans.mdc` → general/plans-checklists.mdc

- `environment.mdc` → topics/deployment/environments.mdc

- `development.mdc` → general/development-workflow.mdc



### Keep (Project-Specific)

- `ideas.mdc` - Project-specific pattern

- `global.mdc` - Project-specific pattern



---


## Builders_Main/vibeapp.studio/.cursor

**Total files**: 6


### Can Remove (Covered by Global Rules)

- `database.mdc` → frameworks/database/prisma.mdc

- `auth.mdc` → topics/security/authentication.mdc

- `troubleshooting/errors.mdc` → topics/quality/error-handling.mdc

- `versioning/git.mdc` → topics/git/workflow.mdc



### Keep (Project-Specific)

- `npm-run.mdc` - Project-specific pattern

- `project-structure.mdc` - Project-specific pattern



---


## EarnLearn/earnlearn/application/.cursor

**Total files**: 1


### Keep (Project-Specific)

- `principles.mdc` - Project-specific pattern



---


## EarnLearn/el_new_app/.cursor

**Total files**: 19


### Can Remove (Covered by Global Rules)

- `api-client-ui.mdc` → topics/api/design-standards.mdc

- `strict-typing.mdc` → languages/typescript/typing-standards.mdc

- `production-ready.mdc` → topics/quality/gates.mdc

- `plans.mdc` → general/plans-checklists.mdc

- `git.mdc` → topics/git/workflow.mdc

- `database-driven-config.mdc` → frameworks/database/prisma.mdc

- `testing-patterns.mdc` → frameworks/testing/standards.mdc

- `error-handling.mdc` → topics/quality/error-handling.mdc

- `deployment.mdc` → topics/deployment/environments.mdc

- `logging.mdc` → topics/quality/logging.mdc

- `ui.mdc` → frameworks/ui/tamagui.mdc

- `database-migration-safety.mdc` → frameworks/database/prisma.mdc

- `quality-gates.mdc` → topics/quality/gates.mdc

- `bernierllc-packages.mdc` → packages/package-management.mdc

- `accessibility.mdc` → topics/accessibility/standards.mdc



### Review Needed

- `polymorphic-user-pattern.mdc` - No clear match - needs manual review

- `user-logins.mdc` - No clear match - needs manual review

- `statuses.mdc` - No clear match - needs manual review

- `tdd.mdc` - No clear match - needs manual review



---


## EarnLearn/fork/.cursor

**Total files**: 13


### Can Remove (Covered by Global Rules)

- `api-client-ui.mdc` → topics/api/design-standards.mdc

- `strict-typing.mdc` → languages/typescript/typing-standards.mdc

- `production-ready.mdc` → topics/quality/gates.mdc

- `plans.mdc` → general/plans-checklists.mdc

- `git.mdc` → topics/git/workflow.mdc

- `testing-patterns.mdc` → frameworks/testing/standards.mdc

- `error-handling.mdc` → topics/quality/error-handling.mdc

- `logging.mdc` → topics/quality/logging.mdc

- `ui.mdc` → frameworks/ui/tamagui.mdc

- `quality-gates.mdc` → topics/quality/gates.mdc

- `accessibility.mdc` → topics/accessibility/standards.mdc



### Review Needed

- `statuses.mdc` - No clear match - needs manual review

- `tdd.mdc` - No clear match - needs manual review



---


## SCF-Neue/.cursor

**Total files**: 16


### Can Remove (Covered by Global Rules)

- `react-native.mdc` → stacks/react-native/expo-development.mdc

- `supabase.mdc` → frameworks/database/supabase.mdc

- `typescript-typing.mdc` → languages/typescript/typing-standards.mdc

- `tamagui-debugging.mdc` → frameworks/ui/tamagui.mdc

- `tamagui-properties.mdc` → frameworks/ui/tamagui.mdc

- `api-testing.mdc` → topics/api/design-standards.mdc

- `ui-development.mdc` → frameworks/ui/tamagui.mdc

- `trpc-supabase-patterns.mdc` → frameworks/database/supabase.mdc

- `code-quality.mdc` → topics/quality/gates.mdc



### Keep (Project-Specific)

- `vibe-kanban.mdc` - Project-specific pattern

- `route-naming-convention.mdc` - Project-specific pattern

- `workspace-commands.mdc` - Project-specific pattern

- `project-guardrails.mdc` - Project-specific pattern

- `avoid-barrel-files.mdc` - Project-specific pattern

- `route-constants.mdc` - Project-specific pattern

- `browser-server-management.mdc` - Project-specific pattern



---


## Tools_/bernier_tools/app_dump/.cursor

**Total files**: 1


### Keep (Project-Specific)

- `global.mdc` - Project-specific pattern



---


## Tools_/bernier_tools/app_dump/output/earnlearn/application/.cursor

**Total files**: 1


### Keep (Project-Specific)

- `principles.mdc` - Project-specific pattern



---


## complement_cursor/.cursor

**Total files**: 5


### Can Remove (Covered by Global Rules)

- `cursor-rules.mdc` → general/rules-about-rules.mdc

- `github-rule.mdc` → topics/git/workflow.mdc



### Keep (Project-Specific)

- `clarifying-questions.mdc` - Project-specific pattern

- `privacy-hipaa.mdc` - Project-specific pattern

- `docs-updates.mdc` - Project-specific pattern



---


## formExpert.co/.cursor

**Total files**: 4


### Can Remove (Covered by Global Rules)

- `plans.mdc` → general/plans-checklists.mdc

- `workflow.mdc` → general/development-workflow.mdc

- `authentication-boundaries.mdc` → topics/security/authentication.mdc



### Keep (Project-Specific)

- `general.mdc` - Project-specific pattern



---


## houseofgenius/.cursor

**Total files**: 8


### Can Remove (Covered by Global Rules)

- `git.mdc` → topics/git/workflow.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `testing-changes.mdc` → frameworks/testing/standards.mdc



### Keep (Project-Specific)

- `sycophancy.mdc` - Project-specific pattern

- `forms.mdc` - Project-specific pattern

- `browser.mdc` - Project-specific pattern

- `docs.mdc` - Project-specific pattern



### Review Needed

- `backend/email_templates.mdc` - No clear match - needs manual review



---


## mara/Sites/.cursor

**Total files**: 12


### Can Remove (Covered by Global Rules)

- `01-python-style.mdc` → languages/python/style.mdc

- `suggest_missing_rules.mdc` → general/rules-about-rules.mdc

- `observability.mdc` → topics/observability/monitoring.mdc

- `03-sqlalchemy-db.mdc` → frameworks/database/sqlalchemy.mdc

- `security_secrets.mdc` → topics/security/authentication.mdc

- `02-fastapi.mdc` → stacks/python-backend/fastapi.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `rbac_okta.mdc` → topics/security/authentication.mdc



### Keep (Project-Specific)

- `sharepoint-docs.mdc` - Project-specific pattern

- `00-core.mdc` - Project-specific pattern



### Review Needed

- `04-react.mdc` - No clear match - needs manual review

- `audit-log.mdc` - No clear match - needs manual review



---


## mara/energy_site/.cursor

**Total files**: 5


### Can Remove (Covered by Global Rules)

- `plans.mdc` → general/plans-checklists.mdc

- `git.mdc` → topics/git/workflow.mdc

- `pull-requests.mdc` → topics/git/workflow.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `branching.mdc` → topics/git/workflow.mdc



---


## mbernier.com/mbernier.com/.cursor

**Total files**: 10


### Can Remove (Covered by Global Rules)

- `plans-checklists.mdc` → general/plans-checklists.mdc

- `git.mdc` → topics/git/workflow.mdc

- `rules.mdc` → general/rules-about-rules.mdc

- `security-vulnerabilities.mdc` → topics/security/authentication.mdc

- `bernierllc-packages.mdc` → packages/package-management.mdc

- `coding/documentation.mdc` → general/documentation.mdc

- `coding/testing.mdc` → frameworks/testing/standards.mdc

- `coding/linting-type-safety.mdc` → languages/typescript/typing-standards.mdc

- `coding/quality-gates.mdc` → topics/quality/gates.mdc



### Keep (Project-Specific)

- `coding/coding.mdc` - Project-specific pattern



---


## mcp-ask-questions/.cursor

**Total files**: 2


### Can Remove (Covered by Global Rules)

- `commits.mdc` → topics/git/workflow.mdc



### Review Needed

- `open_source.mdc` - No clear match - needs manual review



---


## neveradmin/.cursor

**Total files**: 4


### Can Remove (Covered by Global Rules)

- `cursor-execution-rules.mdc` → general/rules-about-rules.mdc



### Keep (Project-Specific)

- `agent-guidelines.mdc` - Project-specific pattern

- `ai-agent-operations.mdc` - Project-specific pattern

- `vibe-kanban-tickets.mdc` - Project-specific pattern



---


## neverhub/.cursor

**Total files**: 5


### Can Remove (Covered by Global Rules)

- `cursor-rules.mdc` → general/rules-about-rules.mdc

- `build-quality.mdc` → topics/quality/gates.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `questions-documentation.mdc` → general/documentation.mdc



### Keep (Project-Specific)

- `vibe-kanban.mdc` - Project-specific pattern



---


## ports/test-project/.cursor

**Total files**: 2


### Can Remove (Covered by Global Rules)

- `project-setup-cli.mdc` → general/project-setup-cli.mdc

- `port-management.mdc` → general/port-management.mdc



---


## prevost/.cursor

**Total files**: 15


### Can Remove (Covered by Global Rules)

- `api-verification-scripts.mdc` → topics/api/design-standards.mdc

- `flake8-formatting.mdc` → languages/python/style.mdc

- `linter-errors.mdc` → topics/quality/error-handling.mdc

- `react-hydration-errors.mdc` → topics/quality/error-handling.mdc

- `dev-environment.mdc` → topics/deployment/environments.mdc

- `python-server-apis.mdc` → stacks/python-backend/fastapi.mdc

- `api-request-flow.mdc` → topics/api/design-standards.mdc

- `documentation.mdc` → general/documentation.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `api-standards.mdc` → topics/api/design-standards.mdc

- `app-architecture.mdc` → general/architecture.mdc



### Keep (Project-Specific)

- `coding-practices.mdc` - Project-specific pattern

- `workflow-crawling.mdc` - Project-specific pattern

- `scripts-structure.mdc` - Project-specific pattern



### Review Needed

- `root-directory.mdc` - No clear match - needs manual review



---


## robert_champion/barevents/.cursor

**Total files**: 17


### Can Remove (Covered by Global Rules)

- `git-workflow.mdc` → topics/git/workflow.mdc

- `documentation.mdc` → general/documentation.mdc

- `server.mdc` → stacks/python-backend/fastapi.mdc

- `git.mdc` → topics/git/workflow.mdc

- `git-cursor-rules.mdc` → general/rules-about-rules.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `typescript-strict.mdc` → languages/typescript/typing-standards.mdc

- `code-quality.mdc` → topics/quality/gates.mdc

- `alembic.mdc` → frameworks/database/alembic.mdc

- `accessibility-admin.mdc` → topics/accessibility/standards.mdc

- `questions-documentation.mdc` → general/documentation.mdc

- `api-integration.mdc` → topics/api/design-standards.mdc



### Keep (Project-Specific)

- `react-development.mdc` - Project-specific pattern

- `project-structure.mdc` - Project-specific pattern



### Review Needed

- `linter-issues.mdc` - No clear match - needs manual review

- `file-size-limits.mdc` - No clear match - needs manual review

- `code-changes.mdc` - No clear match - needs manual review



---


## tools/.cursor

**Total files**: 26


### Can Remove (Covered by Global Rules)

- `cursor-rules.mdc` → general/rules-about-rules.mdc

- `git-workflow.mdc` → topics/git/workflow.mdc

- `publishing.mdc` → packages/package-management.mdc

- `package-reuse.mdc` → packages/package-reuse.mdc

- `plans-and-checklists.mdc` → general/plans-checklists.mdc

- `package-management.mdc` → packages/package-management.mdc

- `rules.mdc` → general/rules-about-rules.mdc

- `documentation/readme.mdc` → general/documentation.mdc

- `markdown/markdown-rules.mdc` → general/rules-about-rules.mdc

- `scripts/npm-publish.mdc` → packages/package-management.mdc

- `coding/linting-type-safety.mdc` → languages/typescript/typing-standards.mdc

- `coding/testing-standards.mdc` → frameworks/testing/standards.mdc



### Keep (Project-Specific)

- `atomic-package-identification.mdc` - Project-specific pattern

- `version-management.mdc` - Project-specific pattern

- `shared.mdc` - Project-specific pattern

- `licensing.mdc` - Project-specific pattern

- `partial-package-matches.mdc` - Project-specific pattern

- `scripts/scripts.mdc` - Project-specific pattern

- `packages/service.mdc` - Project-specific pattern

- `packages/core.mdc` - Project-specific pattern

- `packages/suite.mdc` - Project-specific pattern

- `packages/util.mdc` - Project-specific pattern

- `packages/min-requirements.mdc` - Project-specific pattern

- `coding/separation-of-concerns.mdc` - Project-specific pattern

- `coding/index.mdc` - Project-specific pattern

- `coding/coding.mdc` - Project-specific pattern



---


## vibeapp.studio/.cursor

**Total files**: 13


### Can Remove (Covered by Global Rules)

- `database.mdc` → frameworks/database/prisma.mdc

- `git.mdc` → topics/git/workflow.mdc

- `testing.mdc` → frameworks/testing/standards.mdc

- `typescript.mdc` → languages/typescript/typing-standards.mdc

- `styling.mdc` → frameworks/ui/tailwind-css.mdc

- `api-standards.mdc` → topics/api/design-standards.mdc

- `nextjs-react.mdc` → stacks/nextjs/app-router.mdc

- `bernierllc-packages.mdc` → packages/package-management.mdc

- `troubleshooting/errors.mdc` → topics/quality/error-handling.mdc

- `versioning/git.mdc` → topics/git/workflow.mdc



### Keep (Project-Specific)

- `npm-run.mdc` - Project-specific pattern

- `project-structure.mdc` - Project-specific pattern



### Review Needed

- `agents.mdc` - No clear match - needs manual review



---

