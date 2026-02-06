# Git Workflow Rules

## Branching Strategy

### Feature Branches
- **Use feature branches for all new development**
- Never commit directly to `main` or `production`
- Always create feature branches from `main`

### Branch Naming Convention
Use this naming convention for feature branches:
```
{type}/{milestone-name}-{short-description}
```

Valid types:
- `feat`: Features
- `fix`: Bugfixes
- `chore`: Maintenance
- `refactor`: Refactoring

Examples:
- `feat/milestone3-invite-flow`
- `fix/milestone1-header-crash`
- `chore/infra-database-rotate`

### Syncing Before PR
Before opening a PR, ensure your feature branch is rebased on the latest `main`:

```bash
git fetch origin
git rebase origin/main
```

## Commit Standards

### Conventional Commit Format
Use conventional commit style for all commits:

```bash
<type>(<scope>): <description>

# Examples
feat(api): add user authentication endpoint
fix(port): resolve port conflict in development
docs(readme): update installation instructions
refactor(models): extract user validation logic
```

### Commit Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `style`: Code style changes (formatting, etc.)
- `perf`: Performance improvements

### Commit Frequency
- Make commits for each feature/update
- Commit frequently with clear messages
- Group related changes in single commits

## Pull Request Workflow

### PR Flow
1. **Open a Draft PR early** to communicate your direction
2. Clearly describe:
   - What is being changed
   - Why it's needed
   - Any relevant issue, milestone, or design doc

### Requirements Before Merge
- ✅ Code review completed
- ✅ Tests pass
- ✅ Conflicts resolved (rebase preferred)
- ✅ Conventional commit title in squash merge

### Merging
- Use **Squash and Merge** for feature branches
- The final commit message should be clean and follow conventional format
- PR title should follow conventional commit format

## Release Workflow

### Semantic Versioning
- **Major (X.0.0):** Breaking changes
- **Minor (0.X.0):** New features, backwards compatible
- **Patch (0.0.X):** Bug fixes, backwards compatible

### Release Process
1. Create feature branch from main
2. Make commits with conventional commit style
3. Create release notes file in `release_notes/RELEASE_NOTES_vX.Y.Z.md`
4. Update README.md with new version number
5. Update CHANGELOG.md with changes
6. Create PR to merge into main
7. After merge, tag and create GitHub release:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --notes-file release_notes/RELEASE_NOTES_vX.Y.Z.md
   ```

### Release Notes
- Release notes should be written BEFORE creating the PR
- Include PR numbers in release notes for traceability
- Highlight breaking changes prominently

## Best Practices

### Branch Management
- Always work on feature branches, never directly on main
- Keep branches focused on single features or fixes
- Delete merged branches after merge

### Conflict Resolution
- Pull latest main before creating PR
- Rebase feature branch on main if conflicts exist
- Resolve conflicts carefully and test after resolution

### Collaboration
- Use Draft PRs for early feedback
- Request reviews from appropriate team members
- Respond to review comments promptly

## References
- **Development Workflow**: See `general/development-workflow.mdc`
- **Architecture**: See `general/architecture.mdc`
