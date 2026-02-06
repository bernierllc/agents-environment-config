# Architecture Rules

## Core Principles

### Design Philosophy
- **Separation of Concerns**: Models, repositories, routes, docs live in their own packages
- **DRY + KISS**: Reuse abstractions and ship the simplest working solution
- **Self-documenting Code**: Expressive identifiers, minimal explanatory comments
- **Conventions**: Extend existing code style and architecture—never reinvent

### System Architecture
- **Database Default**: PostgreSQL unless project rules specify otherwise
- **Python Environment**: If python backend exists, ensure local venv; create if absent
- **Shell Scripts**: Use commander.js, human-friendly with color coding
- **Documentation**: Store in `/docs/**/*.md` with cross-links to related docs

## File Organization

### Directory Structure
```
project/
├── docs/           # Documentation
├── plans/          # Planning docs with task lists
├── .cursor/rules/  # Cursor rules
├── models/         # Data models
├── repositories/   # Data access layer
├── routes/         # API routes
└── [tech-specific] # Framework-specific directories
```

### Documentation Standards
- **Architecture, Design, Functionality, Principles**: Note in `.cursor/rules/*.mdc` files
- **Be Pithy**: Link to files in `/docs/` rather than including all content
- **Planning Docs**: Store in `./plans/**/*.md`, use task lists (- [ ] / - [x]) and cross-link
- **Implementation Docs**: If mock, ensure docs have implementation docs added/updated

## Code Quality

### Error Handling
- **Explicit Error Handling**: No uncaught exceptions
- **Docstrings**: On every public symbol
- **Validation**: Comprehensive input validation and error reporting

### Refactoring Guidelines
- **Size Management**: If file/function/method/class gets too large, suggest refactor plan in `./plans/`
- **Reusability**: Consider reusability with other functionality in the project
- **Safe Refactoring**: Move functionality to more manageable and reusable state

## Integration Standards

### MCP Servers
- **API Integration**: If project has APIs, install MCP server for those APIs
- **Security**: MCP server MUST respect authorization and authentication
- **Environment**: If cannot respect auth, MUST only run in dev environments

### External Dependencies
- **Database**: PostgreSQL as default
- **Python**: Local virtual environment required
- **Shell Scripts**: Commander.js with color coding
- **CLI Tools**: Human-friendly interfaces

## Maintenance

### Cursor Rule Upkeep
- **Missing Rules**: If `./cursor/rules` is missing, stale, or decision needs to be in rules, propose updates
- **Legacy Files**: Flag any legacy `.cursorrules` file at once
- **Documentation Updates**: If functionality changes, update docs accordingly

### Version Control
- **Feature Branches**: Use feature branches for all changes
- **Conventional Commits**: Make commits for each feature/update using conventional commit style
- **GitHub Workflow**: Don't commit new changes to main branch; create feature branches

## References
- **Port Management**: See `port-management.mdc`
- **CLI Tools**: See `project-setup-cli.mdc`
- **Documentation**: See `/docs/` directory
- **Planning**: See `/plans/` directory