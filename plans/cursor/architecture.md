# Cursor Rules Architecture

## Global vs Project-Specific Rules

### Global Rules (This Repository)

The rules in `agents-environment-config/.cursor/rules/` are **global rules** that apply across all projects. These contain:

- **General patterns** that work across projects
- **Technology-specific standards** (TypeScript, Python, React, etc.)
- **Cross-cutting concerns** (API design, Git workflow, security, quality)
- **Framework conventions** (Next.js, FastAPI, Prisma, etc.)

**Location**: `agents-environment-config/.cursor/rules/`

**Usage**: Cursor IDE automatically discovers rules in parent directories. When you have this repository as a parent or sibling, Cursor will apply these rules.

### Project-Specific Rules

Project-specific rules stay in their respective projects:

- **Project-specific patterns** unique to that codebase
- **Business logic rules** specific to the domain
- **Custom workflows** for that project
- **Project-specific conventions** that don't apply elsewhere

**Location**: `{project}/.cursor/rules/`

**Usage**: These rules apply only to that specific project.

## How Cursor Discovers Rules

Cursor searches for rules in this order:

1. **Project directory**: `{project}/.cursor/rules/**/*.mdc`
2. **Parent directories**: Walks up the directory tree looking for `.cursor/rules/`
3. **Global repository**: If `agents-environment-config` is in the path, finds global rules

### Example Directory Structure

```
/Users/mattbernier/projects/
├── agents-environment-config/        # Global rules repository
│   └── .cursor/rules/               # Global rules (this repo)
│       ├── general/
│       ├── languages/
│       ├── stacks/
│       └── ...
│
├── my-project/                      # Project-specific
│   └── .cursor/rules/               # Project-specific rules
│       ├── domain-specific.mdc      # Only applies to this project
│       └── custom-workflow.mdc      # Project-specific workflow
│
└── another-project/
    └── .cursor/rules/
        └── project-rules.mdc
```

## Rule Precedence

When both global and project-specific rules exist:

1. **Project rules take precedence** for conflicts
2. **Global rules provide defaults** for general patterns
3. **Both are applied** - they complement each other

## Best Practices

### For Global Rules

✅ **DO include:**
- Language standards (TypeScript, Python)
- Framework conventions (Next.js, FastAPI)
- Cross-cutting patterns (API design, Git workflow)
- Quality standards (testing, accessibility)
- Security best practices

❌ **DON'T include:**
- Business logic specific to one project
- Project-specific domain patterns
- Custom workflows unique to one codebase

### For Project-Specific Rules

✅ **DO include:**
- Project-specific domain patterns
- Business logic conventions
- Custom workflows for that project
- Project-specific tooling

✅ **DO reference:**
- Link to global rules when relevant
- Extend global rules with project-specific additions
- Use frontmatter to indicate project scope

❌ **DON'T duplicate:**
- General patterns already in global rules
- Technology standards (use global rules)
- Cross-cutting concerns (use global rules)

## Example: Project-Specific Rule

```markdown
---
description: Project-specific authentication patterns for FormExpert
globs: ["**/api/auth/**"]
alwaysApply: false
tags: [auth, formexpert, project-specific]
---

# FormExpert Authentication Patterns

> **Note**: For general authentication patterns, see `agents-environment-config/.cursor/rules/topics/security/authentication.mdc`

## Project-Specific Rules

This project uses Clerk with specific boundary patterns:

- Clerk ID → Internal UUID mapping (see global auth rules)
- Project-specific user roles
- Custom permission checks for form ownership

## Project-Specific Implementation

[Project-specific details here]
```

## Migration Strategy

### For Existing Projects

1. **Audit project rules**: Identify what's truly project-specific
2. **Remove duplicates**: Delete rules covered by global rules
3. **Reference global rules**: Link to global rules in project READMEs
4. **Keep project-specific**: Maintain unique patterns for that project

### Example Migration

**Before:**
```
my-project/.cursor/rules/
├── typescript.mdc          # Duplicate of global rule
├── api-standards.mdc       # Duplicate of global rule
├── git-workflow.mdc        # Duplicate of global rule
└── domain-specific.mdc     # Project-specific (keep)
```

**After:**
```
my-project/.cursor/rules/
├── README.mdc              # References global rules
└── domain-specific.mdc     # Project-specific (keep)
```

**README.mdc:**
```markdown
# Project Rules

This project uses global rules from `agents-environment-config/.cursor/rules/`.

## Project-Specific Rules

- `domain-specific.mdc` - Business logic patterns unique to this project

## Global Rules Used

- TypeScript standards: `agents-environment-config/.cursor/rules/languages/typescript/typing-standards.mdc`
- API standards: `agents-environment-config/.cursor/rules/topics/api/design-standards.mdc`
- Git workflow: `agents-environment-config/.cursor/rules/topics/git/workflow.mdc`
```

## Verification

To verify rules are being discovered:

1. **Check Cursor IDE**: Rules should appear in Cursor's rules panel
2. **Test application**: Verify rules apply to code generation
3. **Review conflicts**: Ensure project rules complement global rules

## Summary

- **Global rules** = Shared patterns, standards, conventions (in `agents-environment-config`)
- **Project rules** = Unique patterns, business logic, custom workflows (in each project)
- **Both apply** = Cursor combines both rule sets
- **Reference, don't duplicate** = Projects should reference global rules, not copy them

This architecture ensures:
- ✅ Consistency across projects
- ✅ Reduced duplication
- ✅ Easy maintenance of standards
- ✅ Flexibility for project-specific needs


