# Development Workflow Rules

## Version Control

### Branching Strategy
- **Feature Branches**: Use feature branches for all new development
- **Main Branch Protection**: Don't commit new changes to main branch
- **Conventional Commits**: Use conventional commit style for all commits
- **Commit Frequency**: Make commits for each feature/update

### Commit Standards
```bash
# Conventional commit format
<type>(<scope>): <description>

# Examples
feat(api): add user authentication endpoint
fix(port): resolve port conflict in development
docs(readme): update installation instructions
refactor(models): extract user validation logic
```

## Code Quality

### Documentation Standards
- **Public Symbols**: Docstrings on every public symbol
- **Self-Documenting**: Expressive identifiers, minimal explanatory comments
- **Code Comments**: Only when necessary, prefer clear code over comments

### Error Handling
- **Explicit Handling**: No uncaught exceptions
- **Error Messages**: Clear, actionable error messages
- **Logging**: Appropriate logging levels for debugging

### Code Organization
- **Separation of Concerns**: Models, repositories, routes, docs in separate packages
- **DRY Principle**: Reuse abstractions and ship simplest working solution
- **KISS Principle**: Keep it simple and straightforward

## Development Environment

### Python Projects
- **Virtual Environment**: Ensure local venv exists; create if absent
- **Dependency Management**: Use requirements.txt or pyproject.toml
- **Environment Isolation**: Never use system Python for project dependencies

### Database Standards
- **Default Database**: PostgreSQL unless project rules specify otherwise
- **Connection Management**: Proper connection pooling and error handling
- **Migrations**: Version-controlled database schema changes

### Shell Scripts
- **Commander.js**: Use commander.js for CLI tools
- **Human-Friendly**: Clear, helpful output with color coding
- **Error Handling**: Graceful error handling and user feedback

## Project Setup

### New Projects
- **Port Management**: Use Project Setup CLI for port management
- **Cursor Rules**: Copy cursor rules to new projects
- **Documentation**: Initialize with proper documentation structure

### Existing Projects
- **Port Validation**: Run port validation before making changes
- **Dependency Updates**: Keep dependencies current and secure
- **Code Review**: Review changes before merging

## Refactoring Guidelines

### When to Refactor
- **Large Files**: If file/function/method/class gets too large to manage
- **Code Duplication**: When DRY principle is violated
- **Performance Issues**: When code performance is suboptimal
- **Maintainability**: When code becomes hard to understand or modify

### Refactoring Process
1. **Create Plan**: Document refactor plan in `./plans/` directory
2. **Consider Reusability**: Plan for reusability with other functionality
3. **Safe Migration**: Move functionality to more manageable state
4. **Test Thoroughly**: Ensure all functionality works after refactoring
5. **Update Documentation**: Update docs to reflect changes

## Integration Standards

### MCP Servers
- **API Integration**: Install MCP server for project APIs
- **Security Requirements**: MUST respect authorization and authentication
- **Environment Restrictions**: If cannot respect auth, MUST only run in dev environments
- **Documentation**: Document MCP server configuration and usage

### External Services
- **API Authentication**: Proper authentication for all external APIs
- **Error Handling**: Graceful handling of external service failures
- **Rate Limiting**: Respect rate limits and implement backoff strategies

## Documentation Maintenance

### Documentation Updates
- **Functionality Changes**: Update docs when functionality changes
- **Mock Implementations**: Ensure implementation docs are added/updated for mocks
- **Cross-References**: Maintain cross-links between related documentation
- **Task Lists**: Use task lists (- [ ] / - [x]) in planning docs

### Documentation Structure
- **Architecture**: Note in `.cursor/rules/*.mdc` files
- **Detailed Docs**: Store in `/docs/**/*.md`
- **Planning**: Store in `./plans/**/*.md`
- **Be Pithy**: Link to files rather than including all content

## Quality Assurance

### Testing
- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Port Validation**: Validate port configuration

### Code Review
- **Peer Review**: All changes reviewed by team members
- **Automated Checks**: Use linting and formatting tools
- **Security Review**: Security implications of changes
- **Performance Review**: Performance impact of changes

## References
- **Port Management**: See `port-management.mdc`
- **CLI Tools**: See `project-setup-cli.mdc`
- **Architecture**: See `architecture.mdc`
- **Documentation**: See `/docs/` directory