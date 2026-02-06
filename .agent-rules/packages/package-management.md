# Package Management Rules

## Mandatory Use of ./manager CLI

**NEVER use basic npm commands or legacy tools for package management.** Always use the comprehensive `./manager` CLI system:

### Primary Package Management Tool

**`./manager`** - The ONLY way to manage packages in this repository

```bash
# Use ./manager for ALL package operations
./manager publish [package] [bump] [message]
./manager validate
./manager check
./manager build
./manager test
./manager status
./manager list [filter]
./manager track [package]
```

### Forbidden Commands

**DO NOT USE:**
- `npm publish` directly
- `npm version` manually
- Manual version bumping in package.json
- `development-cli` (legacy tool)
- Any other publishing tools

**ALWAYS USE:**
- `./manager publish` for publishing
- `./manager validate` for validation
- `./manager check` for development checks

## Package Development Rules

### Core Package Rules
- **Dependency-free**: Core packages must not import other internal packages
- **Atomic functionality**: Single responsibility, focused purpose
- **Pure functions**: Predictable, testable, side-effect free
- **Strict typing**: No implicit `any`, comprehensive interfaces
- **Self-contained**: All functionality implemented internally

### Service Package Rules
- **Compose core packages**: Use core packages as dependencies
- **Opinionated layer**: Provide configured, ready-to-use services
- **Adapter support**: Handle multiple implementation options
- **Centralized error handling**: Use standard error patterns

## Package Reuse Guidelines

### Before Creating New Packages
1. **Search existing packages**: Check if functionality already exists
2. **Evaluate partial matches**: Consider extending existing packages
3. **Use composition**: Combine existing packages rather than recreating
4. **Document decisions**: Record rationale in planning files

### Package Dependencies
- **Core packages**: No internal dependencies (except types)
- **Service packages**: Can depend on core packages
- **Suite packages**: Compose multiple service packages

## Quality Gates

### Before Publishing
- [ ] Package validation: `./manager validate`
- [ ] Development checks: `./manager check`
- [ ] Build success: `./manager build`
- [ ] Tests passing: `./manager test`
- [ ] Documentation complete: README.md, API docs, examples

### Package Requirements
- **Comprehensive README.md**: Purpose, usage, examples
- **API documentation**: Clear interface definitions
- **TypeScript types**: Strict typing, no implicit any
- **Test coverage**: Comprehensive testing for edge cases
- **Error handling**: Proper error types and handling

## References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
