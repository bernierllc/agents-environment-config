# Quality Gates

## Overview

Quality gates are mandatory checkpoints that ensure code quality, reliability, and maintainability. **NO EXCEPTIONS** - These quality gates must be passed before ANY commit or push.

## Pre-Commit Quality Gates

### Code Quality
- [ ] **TypeScript Compilation** - `tsc --noEmit` passes with no errors
- [ ] **Linting** - ESLint passes with no errors or warnings
- [ ] **Code Formatting** - Prettier formatting applied
- [ ] **Type Safety** - No `any` types, proper type definitions
- [ ] **Build Success** - `npm run build` completes successfully

### Testing Requirements
- [ ] **Tests Written** - Comprehensive tests for all changes
- [ ] **Tests Passing** - All relevant tests pass locally
- [ ] **Test Coverage** - Minimum 80% coverage, 100% for critical paths
- [ ] **No Test Failures** - Zero failing tests allowed

### Documentation Requirements
- [ ] **API Documentation** - New/changed endpoints documented
- [ ] **Code Comments** - Inline documentation updated
- [ ] **Documentation Updates** - Update docs when functionality changes

## Pre-Push Quality Gates

### Full Test Suite
- [ ] **All Test Phases** - Unit, integration, e2e tests pass
- [ ] **Build Verification** - Application builds without errors
- [ ] **Type Checking** - TypeScript compilation successful
- [ ] **Linting** - All linting rules pass

## Environment-Specific Quality Gates

### Development Branch
- ✅ TypeScript Compilation
- ✅ ESLint Validation
- ✅ Build Verification
- ✅ Test Coverage
- ✅ Database Migrations (must be safe)

### Staging Branch
- ✅ All Development Gates
- ✅ Full Test Suite
- ✅ Database Safety
- ✅ Environment Variables configured
- ✅ Deployment Health

### Main Branch (Production)
- ✅ All Staging Gates
- ✅ Staging Verification
- ✅ Database Backup
- ✅ Rollback Plan
- ✅ Security Review
- ✅ Monitoring configured

## Quality Metrics

### Code Quality
- **TypeScript Coverage**: 100% of files typed
- **ESLint Compliance**: 0 warnings/errors
- **Test Coverage**: >80% for critical paths
- **Build Success Rate**: 100%

### Performance
- **API Response Time**: <500ms for most endpoints
- **Build Time**: <5 minutes
- **Test Execution**: <2 minutes

## Enforcement

### Automated Enforcement
- Pre-commit hooks prevent commits that fail quality gates
- Pre-push hooks prevent pushes that fail quality gates
- CI/CD pipelines enforce quality gates

### Manual Enforcement
- Code review checklist includes quality gate verification
- Team standards require passing all quality gates

## Failure Handling

### When Quality Gates Fail
1. **Immediate Fix** - Address issues before committing
2. **Documentation** - Document any temporary workarounds
3. **Follow-up** - Create tickets for technical debt
4. **Team Communication** - Notify team of blocking issues

## Quality Gate Categories

### Critical Gates (Must Pass)
- TypeScript Compilation
- Test Suite
- Security Scan
- Build Success

### Important Gates (Should Pass)
- Test Coverage
- Performance
- Documentation
- Code Quality

## References
- **Development Workflow**: See `general/development-workflow.mdc`
- **Testing**: See `frameworks/testing/standards.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
