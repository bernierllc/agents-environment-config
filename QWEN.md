# Qwen Code Agent Instructions

> 🚨 **Canonical Source**: All project-specific context now lives in `AGENTINFO.md`. Read/update that file first; this profile only adds Qwen-specific reminders.

**Maintaining AGENTINFO.md:**
- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately
- Mirror every requirement from `AGENTINFO.md` (project structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, documentation)
- When responding, cite the relevant sections of `AGENTINFO.md` rather than restating them—this avoids stale guidance
- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`
- If you discover new constraints, update `AGENTINFO.md` instead of duplicating details here

## Overview

This file contains development rules and standards for the Qwen Code AI coding assistant.
These instructions are generated from `.cursor/rules/` and incorporate essential development
principles, coding standards, and best practices. This file can be committed to git repositories
so that anyone cloning the project will have consistent coding standards even without access
to the global agents-environment-config repository.

> **Note**: For detailed information and the latest updates, see the source rule files in
> `.cursor/rules/` if available in this repository. For project-specific information, see `AGENTINFO.md`.

---

## Core Development Principles

These principles apply universally across all projects:

### Core architectural principles and design philosophy

### Core Principles
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
### File Organization
### Directory Structure
### Documentation Standards
- **Architecture, Design, Functionality, Principles**: Note in `.cursor/rules/*.mdc` files
- **Be Pithy**: Link to files in `/docs/` rather than including all content
- **Planning Docs**: Store in `./plans/**/*.md`, use task lists (- [ ] / - [x]) and cross-link
- **Implementation Docs**: If mock, ensure docs have implementation docs added/updated
### Code Quality
### Error Handling
- **Explicit Error Handling**: No uncaught exceptions
- **Docstrings**: On every public symbol
- **Validation**: Comprehensive input validation and error reporting
### Refactoring Guidelines
- **Size Management**: If file/function/method/class gets too large, suggest refactor plan in `./plans/`
- **Reusability**: Consider reusability with other functionality in the project
- **Safe Refactoring**: Move functionality to more manageable and reusable state
### Integration Standards
### MCP Servers
- **API Integration**: If project has APIs, install MCP server for those APIs
- **Security**: MCP server MUST respect authorization and authentication
- **Environment**: If cannot respect auth, MUST only run in dev environments
### External Dependencies
- **Database**: PostgreSQL as default
- **Python**: Local virtual environment required
- **Shell Scripts**: Commander.js with color coding
- **CLI Tools**: Human-friendly interfaces
### Maintenance
### Cursor Rule Upkeep
- **Missing Rules**: If `./cursor/rules` is missing, stale, or decision needs to be in rules, propose updates
- **Legacy Files**: Flag any legacy `.cursorrules` file at once
- **Documentation Updates**: If functionality changes, update docs accordingly
### Version Control
- **Feature Branches**: Use feature branches for all changes
- **Conventional Commits**: Make commits for each feature/update using conventional commit style
- **GitHub Workflow**: Don't commit new changes to main branch; create feature branches
### References
- **Port Management**: See `port-management.mdc`
- **CLI Tools**: See `project-setup-cli.mdc`
- **Documentation**: See `/docs/` directory
- **Planning**: See `/plans/` directory

*Source: `.cursor/rules/general/architecture.mdc`*

### Version control, code quality, and development environment standards

### Version Control
### Branching Strategy
- **Feature Branches**: Use feature branches for all new development
- **Main Branch Protection**: Don't commit new changes to main branch
- **Conventional Commits**: Use conventional commit style for all commits
- **Commit Frequency**: Make commits for each feature/update
### Commit Standards
### Code Quality
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
### Development Environment
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
### Project Setup
### New Projects
- **Port Management**: Use Project Setup CLI for port management
- **Cursor Rules**: Copy cursor rules to new projects
- **Documentation**: Initialize with proper documentation structure
### Existing Projects
- **Port Validation**: Run port validation before making changes
- **Dependency Updates**: Keep dependencies current and secure
- **Code Review**: Review changes before merging
### Refactoring Guidelines
### When to Refactor
- **Large Files**: If file/function/method/class gets too large to manage
- **Code Duplication**: When DRY principle is violated
- **Performance Issues**: When code performance is suboptimal
- **Maintainability**: When code becomes hard to understand or modify
### Refactoring Process
1. **Create Plan**: Document refactor plan in `./plans/` directory
### Integration Standards
### MCP Servers
- **API Integration**: Install MCP server for project APIs
- **Security Requirements**: MUST respect authorization and authentication
- **Environment Restrictions**: If cannot respect auth, MUST only run in dev environments
- **Documentation**: Document MCP server configuration and usage
### External Services
- **API Authentication**: Proper authentication for all external APIs
- **Error Handling**: Graceful handling of external service failures
- **Rate Limiting**: Respect rate limits and implement backoff strategies
### Documentation Maintenance
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
### Quality Assurance
### Testing
- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Port Validation**: Validate port configuration
### Code Review
- **Peer Review**: All changes reviewed by team members
- **Automated Checks**: Use linting and formatting tools

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/general/development-workflow.mdc`*

### Documentation standards, file organization, and content guidelines

### Documentation Standards
### File Organization
- **Documentation**: Store in `/docs/**/*.md`
- **Planning Docs**: Store in `./plans/**/*.md`
- **Cursor Rules**: Store in `.cursor/rules/*.mdc`
- **Architecture Notes**: Note in `.cursor/rules/*.mdc` files
### Content Standards
- **Be Pithy**: Link to files in `/docs/` rather than including all content
- **Cross-References**: Use task lists (- [ ] / - [x]) and cross-link related docs
- **No Emojis**: Do not use emojis in markdown, ./docs, or ./plans files
- **Self-Documenting**: Prefer clear code over extensive documentation
### Documentation Types
### Architecture Documentation
- **Design Principles**: Note in `.cursor/rules/architecture.mdc`
- **System Design**: Link to detailed docs in `/docs/`
- **Component Relationships**: Document in planning docs
- **Decision Records**: Track architectural decisions
### Implementation Documentation
- **Code Comments**: Minimal, only when necessary
- **API Documentation**: Docstrings on every public symbol
- **Function Documentation**: Clear parameter and return descriptions
- **Class Documentation**: Purpose and usage examples
### Planning Documentation
- **Task Lists**: Use - [ ] for pending, - [x] for completed
- **Cross-Links**: Link to related planning and implementation docs
- **Refactoring Plans**: Document in `./plans/` when code gets too large
- **Feature Planning**: Track feature development and dependencies
### Documentation Maintenance
### Update Requirements
- **Functionality Changes**: Update docs when functionality changes
- **Mock Implementations**: Ensure implementation docs are added/updated for mocks
- **API Changes**: Update API documentation immediately
- **Architecture Changes**: Update architecture documentation
### Documentation Workflow
1. **Create**: Write documentation alongside code
### Code Documentation
### Docstring Standards
- **Public Symbols**: Docstrings on every public symbol
- **Format**: Use consistent docstring format
- **Examples**: Include usage examples where helpful
- **Parameters**: Document all parameters and return values
### Comment Standards
- **Minimal Comments**: Only when code is not self-explanatory
- **Why Not What**: Explain why, not what the code does
- **TODO Comments**: Use sparingly, with clear ownership
- **Deprecation**: Mark deprecated code clearly
### Planning Documentation
### Planning Structure
### Task List Format
### Cross-References
- **Related Features**: Link to related feature plans
- **Implementation Docs**: Link to implementation documentation
- **Architecture Docs**: Link to relevant architecture decisions
- **Code References**: Link to specific code files
### Documentation Tools
### Markdown Standards
- **Headers**: Use consistent header hierarchy
- **Lists**: Use appropriate list types
- **Code Blocks**: Use syntax highlighting
- **Links**: Use descriptive link text
### Documentation Generation
- **API Docs**: Generate from docstrings
- **Code Coverage**: Document test coverage
- **Architecture Diagrams**: Use Mermaid or similar
- **Flow Charts**: Document complex workflows
### Quality Assurance
### Documentation Review
- **Accuracy**: Verify all information is correct
- **Completeness**: Ensure all necessary information is included
- **Clarity**: Check for clear, understandable language
- **Consistency**: Maintain consistent style and format
### Documentation Testing
- **Link Validation**: Ensure all links work
- **Code Examples**: Test all code examples
- **Screenshots**: Verify screenshots are current
- **Instructions**: Follow instructions to verify accuracy
### References
- **Architecture**: See `architecture.mdc`
- **Development Workflow**: See `development-workflow.mdc`
- **Port Management**: See `port-management.mdc`

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/general/documentation.mdc`*

### Plans and checklist usage standards for project planning and task tracking

### Planning Workflow
### When to Create Plans
- Every new feature, tool, or improvement should begin with a plans/ document
- If a `./plans/` doc for the topic does not exist, create one named after the task or feature
- Use `./plans/` or `./plans/<category>/` folders for organization
### Plan File Structure
### Task List Format
### Checklist Standards
- Use `- [ ]` for incomplete tasks
- Use `- [x]` or `✅` to mark completed tasks
- Update checklists as progress is made
- Add subtasks as they are discovered
### Plan Maintenance
- **DO NOT create summary docs** - Update the plans doc with the checklist that already exists
- If a plan file already exists, update it with a checklist of subtasks, questions, or goals
- As you implement tasks, mark checklist items complete directly in the .md plan files
- The plan document should evolve as progress is made and additional substeps are discovered
### File Completion Process
1. When ALL tasks in a plan file are completed `- [x]`:
   - **Move file** to `./plans/completed/` directory (if applicable)
   - **Update** coordination documents to reflect completion
   - **Commit** changes with conventional commit message
### Cross-References
- Link to related planning and implementation docs
- Reference code files in completed task notes
- Link to architecture decisions and documentation
### References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **Documentation**: See `general/documentation.mdc`

*Source: `.cursor/rules/general/plans-checklists.mdc`*

### Centralized port management system to prevent conflicts across projects

### Objective
### Port Management System
### Central Port Registry
- **File**: `~/projects/ports.json`
- **Format**: JSON with project-specific port allocations
- **Updates**: Required before adding new services or changing ports
### Port Allocation Rules
#### Port Registration Requirements
- **MANDATORY**: All projects MUST register ports in `~/projects/ports.json`
- **BEFORE**: Adding new services or changing existing ports
- **VERIFY**: Check for conflicts before committing port changes
- **UPDATE**: Registry immediately after port changes
#### Port Range Allocations
- **System Ports**: 1-1023 (reserved for system)
- **User Ports**: 1024-49151 (available for projects)
- **Dynamic Ports**: 49152-65535 (OS-assigned)
- **Testing Range**: 5000-5999 (test containers)
- **Development Range**: 3000-3999 (dev servers)
- **Database Range**: 5400-5499 (databases)
- **Cache Range**: 6300-6399 (Redis, Memcached)
- **Webhook Range**: 34000-34999 (test webhooks)
#### Port Naming Convention
### Port Management Workflow
### Adding New Ports
1. **Check Registry**: Review `~/projects/ports.json` for conflicts
### Changing Existing Ports
1. **Identify Impact**: Check all projects using the port
### Resolving Conflicts
1. **Identify Conflicting Projects**: List all affected projects
### Port Validation Rules
### Pre-commit Validation
- **Check Registry**: Ensure all project ports are registered
- **Verify No Conflicts**: No duplicate port assignments
- **Validate Ranges**: Ports within appropriate ranges
- **Test Availability**: Verify ports are available
### Port Assignment Guidelines
- **Production Services**: Use stable, well-known ports
- **Development Services**: Use 3000-3999 range
- **Test Services**: Use 5000-5999 range
- **Database Services**: Use 5400-5499 range
- **Cache Services**: Use 6300-6399 range
- **Webhook Services**: Use 34000-34999 range
### Environment-Specific Ports
- **Production**: Stable ports, avoid conflicts
- **Development**: Can use dynamic ranges
- **Testing**: Use dedicated test ranges
- **Staging**: Mirror production port structure
### Port Management Tools
### CLI Tool
- **Path**: `/Users/mattbernier/projects/ports/index.js`
- **Setup**: `node index.js setup [project-dir] -t [tech-stack]`
- **Validate**: `node index.js validate`
- **Help**: `node index.js --help`
### Validation Scripts
### Best Practices
### Documentation
- **Clear Descriptions**: Explain purpose of each port
- **Environment Tags**: Mark production vs development
- **Dependency Notes**: Document port relationships
- **Change History**: Track port changes over time
### Conflict Prevention
- **Range Separation**: Use different ranges for different purposes
- **Project Isolation**: Avoid sharing ports between projects
- **Reserved Ranges**: Keep system ranges reserved
- **Future Planning**: Leave room for expansion
### Testing and Validation
- **Port Availability**: Test before assignment
- **Service Integration**: Verify services work on assigned ports
- **Conflict Detection**: Regular validation of registry
- **Rollback Plan**: Ability to revert port changes
### Emergency Procedures
### Port Conflict Resolution
1. **Immediate**: Stop conflicting services
### Port Registry Recovery
1. **Backup**: Restore from version control
### Checklist
### Before Adding New Service
- [ ] Check `~/projects/ports.json` for conflicts
- [ ] Select appropriate port from correct range
- [ ] Update port registry with new entry

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/general/port-management.mdc`*

### Project Setup CLI tool usage for port management and consistent development environments

### Objective
### CLI Tool Information
### Tool Location
- **Path**: `/Users/mattbernier/projects/ports/index.js`
- **Type**: Node.js CLI tool with Commander.js
- **Dependencies**: Installed in `/Users/mattbernier/projects/ports/`
### Quick Access Commands
### Primary Use Cases
### New Project Setup
When creating a new project, ALWAYS use the CLI tool to:
- Set up port management
- Copy cursor rules
- Configure tech stack
### Port Validation
### Port Conflict Resolution
### Available Commands
### Setup Command
### Validate Command
### Help Command
### File Structure After Setup
### Common Workflows
### Starting a New Project
1. **Create project directory**: `mkdir my-project && cd my-project`
### Adding Services to Existing Project
1. **Check current ports**: `cat .ports.json`
### Resolving Port Conflicts
1. **Identify conflict**: Check validation output
### Integration with AI Agents
### When to Use the CLI
- **New project creation**: Always use CLI for initial setup
- **Port conflicts**: Use CLI to resolve and prevent conflicts
- **Environment setup**: Use CLI to ensure consistent development environment
- **Port validation**: Use CLI before committing changes
### AI Agent Instructions
1. **Check for .ports.json**: Look for port configuration file
### Error Handling
1. **Check dependencies**: Ensure Node.js and npm packages are installed
### Best Practices
### Project Setup
1. **Always use CLI**: Don't manually set up port management
### Port Management
1. **Respect port ranges**: Use appropriate ranges for different service types
2. **Avoid conflicts**: Check central registry before assigning ports
3. **Update registry**: Always update central registry when changing ports
### Development Workflow
1. **Start with CLI**: Use CLI for initial project setup
### Additional Resources
### Documentation
- **Full docs**: `/Users/mattbernier/projects/ports/docs/README.md`
- **Port management rules**: `.cursor/rules/port-management.mdc`
- **Validation script**: `validate-ports.sh`
### Configuration Files
- **Central registry**: `~/projects/ports.json`
- **Project ports**: `[project]/.ports.json`
- **CLI config**: `/Users/mattbernier/projects/ports/package.json`
### Troubleshooting
- **Common issues**: See docs/README.md troubleshooting section
- **Debug mode**: Add console.log statements to CLI tool
- **Manual validation**: Run `bash validate-ports.sh` directly
### References
- **Port Management**: See `port-management.mdc`
- **Architecture**: See `architecture.mdc`
- **Documentation**: See `/docs/project-setup-cli.md`

*Source: `.cursor/rules/general/project-setup-cli.mdc`*

### Rules for managing and maintaining cursor rules files themselves

### Core Principle
### Global vs Project-Specific Rules
### Global Rules (This Repository)
- General patterns and standards that work across projects
- Language-specific conventions (TypeScript, Python)
- Framework standards (Next.js, FastAPI, React Native)
- Cross-cutting topics (API design, Git workflow, security, quality)
**Location**: `agents-environment-config/.cursor/rules/`
### Project-Specific Rules
- Focus on project-specific patterns and business logic
- Reference global rules where applicable (avoid duplication)
- Handle custom workflows unique to that project
**Location**: `{project}/.cursor/rules/`
**How Cursor applies them**: Cursor discovers rules in parent directories, so global rules apply automatically. Project-specific rules take precedence for conflicts. Both rule sets complement each other.
### Guidelines for Rule Files
### Structure
- Prefer small, focused rules with clear intent
- Keep terminology consistent across all rules
- When multiple files cover the same topic, consolidate into one and deprecate the rest
### Content Standards
- Prefer active voice and imperative style ("Do X", "Avoid Y")
- Fix typos immediately; clear language beats clever phrasing
- Use short rationale lines for non-obvious rules (1–2 sentences max)
### Maintenance Process
- When you change behavior or standards, submit an edit to the relevant rule file in the same PR
- When adopting a new convention, add it to the appropriate rule file and reference related docs in `/docs/`
- Link to decisions or plans in `./plans/` when context helps future readers
- Run linting before committing rule changes to ensure formatting stays consistent
### Conflict Resolution
- If a rule conflicts with reality, propose an update rather than a workaround
- Rules should reflect actual practices, not aspirational goals
- Update rules when practices change
### Documentation
- When adopting a new convention, add it to the appropriate rule file and reference related docs in `/docs/`
- Link to decisions or plans in `./plans/` when context helps future readers
- Cross-reference related rules appropriately
### References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **Documentation**: See `general/documentation.mdc`

*Source: `.cursor/rules/general/rules-about-rules.mdc`*

### Security standards, authentication, authorization, and data protection

### Security Standards
### Authentication and Authorization
- **MCP Servers**: If project has APIs, install MCP server for those APIs
- **Security Requirements**: MCP server MUST respect authorization and authentication
- **Environment Restrictions**: If cannot respect auth, MUST only run in dev environments
- **API Security**: Proper authentication for all external APIs
### Data Protection
- **Sensitive Data**: Never commit sensitive data to version control
- **Environment Variables**: Use environment variables for secrets
- **Database Security**: Secure database connections and queries
- **Input Validation**: Validate all user inputs
### Security Implementation
### API Security
- **Authentication**: Implement proper authentication mechanisms
- **Authorization**: Check permissions for all operations
- **Rate Limiting**: Implement rate limiting for API endpoints
- **Input Sanitization**: Sanitize all inputs to prevent injection attacks
### Database Security
- **Connection Security**: Use encrypted connections
- **Query Security**: Use parameterized queries
- **Access Control**: Implement proper database access controls
- **Audit Logging**: Log security-relevant database operations
### Environment Security
- **Development vs Production**: Separate security configurations
- **Secret Management**: Use secure secret management systems
- **Network Security**: Implement proper network security measures
- **Monitoring**: Monitor for security incidents
### Security Best Practices
### Code Security
- **Secure Coding**: Follow secure coding practices
- **Dependency Management**: Keep dependencies updated and secure
- **Error Handling**: Don't expose sensitive information in errors
- **Logging**: Log security events appropriately
### Infrastructure Security
- **Server Security**: Secure server configurations
- **Network Security**: Implement proper network security
- **Backup Security**: Secure backup and recovery procedures
- **Incident Response**: Have incident response procedures
### Security Monitoring
### Logging and Monitoring
- **Security Events**: Log all security-relevant events
- **Access Logs**: Monitor access to sensitive resources
- **Error Monitoring**: Monitor for security-related errors
- **Performance Monitoring**: Monitor for unusual patterns
### Incident Response
- **Detection**: Implement security incident detection
- **Response**: Have clear incident response procedures
- **Recovery**: Plan for security incident recovery
- **Learning**: Learn from security incidents
### Security Testing
### Security Testing Requirements
- **Vulnerability Scanning**: Regular vulnerability scans
- **Penetration Testing**: Periodic penetration testing
- **Code Review**: Security-focused code reviews
- **Dependency Scanning**: Scan for vulnerable dependencies
### Testing Procedures
- **Automated Testing**: Include security tests in CI/CD
- **Manual Testing**: Manual security testing procedures
- **Third-Party Testing**: Use external security testing services
- **Compliance Testing**: Test for regulatory compliance
### Security Documentation
### Security Documentation Requirements
- **Security Policies**: Document security policies and procedures
- **Incident Response**: Document incident response procedures
- **Security Architecture**: Document security architecture decisions
- **Compliance**: Document compliance requirements
### Documentation Standards
- **Security Guidelines**: Clear security guidelines for developers
- **Threat Modeling**: Document threat models and mitigations
- **Security Controls**: Document implemented security controls
- **Risk Assessment**: Document security risk assessments
### References
- **Architecture**: See `architecture.mdc`
- **Development Workflow**: See `development-workflow.mdc`
- **Port Management**: See `port-management.mdc`
- **CLI Tools**: See `project-setup-cli.mdc`

*Source: `.cursor/rules/general/security.mdc`*

## Language-Specific Rules

These rules apply when working with specific languages. They are conditionally relevant
based on the file types being edited:

### Python style guide - PEP 8, Black formatting, type hints, and code organization
*Applies to: **/*.py*

### Code Formatting
### PEP 8 Compliance
- Follow PEP 8 style guide
- Use Black formatter with line length of 88 characters
### Flake8 Configuration
When configuring Flake8, you may omit these checks if preferred:
- No trailing whitespace on code lines
- Lines should be shorter than 79 characters (use 88 with Black)
- No blank spaces on empty lines
- One empty line at the end of the file
### Type Hints
### Required Type Hints
- **Use type-hints everywhere** - All functions must have type annotations
- Prefer explicit types over implicit inference
- Use `typing` module for complex types
### File System Operations
### Path Handling
- **Prefer `Path` from `pathlib`** over `os.path`
- Use pathlib for all file operations
### Documentation
### Docstring Standards
- Use **Google style docstrings** for all functions, classes, and modules
- Include parameter descriptions and return types
- Document exceptions that may be raised
### Virtual Environments
### Environment Requirements
- **Python always requires venv** - Always use virtual environments
- Never use system Python for project dependencies
- Create virtual environment if it doesn't exist
### Code Organization
### Project Structure
- Organize code into logical modules
- Separate concerns: routes, schemas, repositories
- Keep related functionality together
### Import Organization
- Group imports: standard library, third-party, local
- Use absolute imports when possible
- Avoid circular imports
### References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **FastAPI**: See `stacks/python-backend/fastapi.mdc`

*Source: `.cursor/rules/languages/python/style.mdc`*

### TypeScript typing standards and best practices - strict mode, no any, proper type definitions
*Applies to: **/*.ts, **/*.tsx*

### Core Typing Principles
### Zero Tolerance for `any`
- **NEVER use `any` type** - it defeats the purpose of TypeScript's type safety
- **PREFER `unknown` over `any`** when the type is truly unknown
- **ALWAYS define explicit types** for function parameters and return values
- **USE proper interface/type definitions** for complex objects and data structures
- **LEVERAGE TypeScript's type inference** but be explicit when unclear
### Strict Mode Requirements
- All code must be written in TypeScript with strict mode enabled
- Follow TypeScript strict mode rules
- No use of `any`, `@ts-ignore`, or type coercion without explanation
- Validate code with `tsc --noEmit` in CI and before publishing or merging
### Type Safety Checklist
- [ ] All function parameters have explicit types
- [ ] All function return types are defined
- [ ] All component props are properly typed
- [ ] All API responses have defined interfaces
- [ ] All state variables have proper types
- [ ] No `any` types are used
- [ ] Type guards are used for runtime validation
- [ ] Generic types are used for reusable code
- [ ] Error types are specific and well-defined
### React Import Standards
### Direct Imports Preferred
- **PREFER direct imports** from React instead of namespace imports
- **USE destructured imports** for React hooks and components
- **AVOID namespace imports** when individual imports are available
### Function and Method Typing
### Component Props Typing
### API and Data Typing
### End-to-End Type Safety
All data flows must be fully type-safe from database to UI. This includes:
- API endpoints
- Service layers
- UI components
- Database queries
### Action Required
1. **No `any` Types**: Replace all `any` types with proper interfaces
4. **UI Component Props**: All component props must be strictly typed
### Generic Types and Reusability
### Error Handling Typing
### State Management Typing
### Linting and Validation
### Pre-commit Checks
- Ensure all code passes linting before committing
- Use the project's `.eslintrc`, `.prettierrc`, and `.editorconfig` for formatting and standards
- Do not commit code that triggers TypeScript or ESLint errors
### Quality Gates
- TypeScript compilation must pass with no errors
- ESLint must pass with no warnings
- All modified files must pass type checking before commit
### Common Anti-Patterns to Avoid
- **DON'T use `any`** - defeats TypeScript's purpose
- **DON'T use `@ts-ignore`** without good reason
- **DON'T use `as` assertions** without proper validation
- **DON'T skip return type annotations** for public functions
- **DON'T use `object`** when you mean a specific object shape
- **DON'T commit code** that triggers TypeScript or ESLint errors
### Code Generation Guidelines
- Prefer typed function signatures and clear parameter names

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/languages/typescript/typing-standards.mdc`*

## Stack-Specific Rules

These rules apply when using specific technology stacks:

### Next.js App Router patterns, React component standards, and project structure
*Applies to: src/app/**, src/components/**, **/app/**...*

### Next.js App Router Patterns
### Server Components (Default)
### Client Components (Explicit)
### File Structure (App Router)
### Component Standards
### Functional Components with TypeScript
All React components must have proper TypeScript interfaces and explicit return types.
### Error Boundaries
### Performance Patterns
### React.memo for Expensive Components
### Dynamic Imports for Code Splitting
### API Integration Patterns
### Server Actions (Preferred)
Prefer server actions for form handling and server-side operations.
### API Routes for External APIs
### Project Structure
### Directory Organization
### Code Organization
- Feature-based organization within `/src/`
- Shared utilities in `/lib/`
- Type definitions centralized in `/types/`
- Tests co-located with implementation
### Component Creation Checklist
1. ✅ **TypeScript Interface** - Props properly typed
### Quality Gates
- **TypeScript Strict** - No `any` types, explicit interfaces
- **Build Validation** - `npm run build` must succeed
- **Component Tests** - React Testing Library tests
- **Accessibility** - WCAG 2.1 AA compliance
### References
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
- **API Standards**: See `topics/api/design-standards.mdc`
- **Testing**: See `frameworks/testing/standards.mdc`
- **Architecture**: See `general/architecture.mdc`

*Source: `.cursor/rules/stacks/nextjs/app-router.mdc`*

### FastAPI patterns and conventions for Python backend development
*Applies to: **/routes/**/*.py, **/schemas/**/*.py, **/repositories/**/*.py...*

### File Organization
### Directory Structure
- `routers/` - API route handlers
- `schemas/` - Pydantic models for request/response validation
- `repositories/` - Data access layer
### Pydantic Models
### Pydantic v2 Standards
- **Use Pydantic v2 BaseModel** with `model_config`
- Define schemas for all request/response models
- Use proper field types and validators
### Route Handlers
### Response Models
- **All routes return `response_model`** - Define explicit response types
- Use proper HTTP status codes
- Handle errors consistently
### Background Tasks
### Long-Running Operations
- **Use background tasks** for long jobs
- Use FastAPI's BackgroundTasks for non-critical operations
- Use task queues (Celery, etc.) for critical background work
### Security
### CSRF Protection
- **Don't disable CSRF on JWT cookie endpoints** - Maintain security
- Use proper authentication mechanisms
- Validate all inputs
### API Structure
### Endpoint Organization
- `/api/admin` - Admin UI endpoints (requires both keys)
- `/api/crawler` - Crawler functionality (requires X-API-Key)
- `/api/` - Public endpoints (requires X-API-Key)
### Error Handling
### References
- **Python Style**: See `languages/python/style.mdc`
- **Architecture**: See `general/architecture.mdc`
- **SQLAlchemy**: See `frameworks/database/sqlalchemy.mdc`

*Source: `.cursor/rules/stacks/python-backend/fastapi.mdc`*

### React Native and Expo development guidelines, commands, and patterns
*Applies to: apps/expo/**/*, **/*.native.*, **/*.ios.*...*

### Command Usage
### Workspace Commands
- **ALWAYS use `pnpm dev`** instead of `expo start` directly
- **ALWAYS use `pnpm ios`** for iOS development (includes Xcode version check)
- **ALWAYS use `pnpm android`** for Android development
- **ALWAYS use `pnpm web`** for web development
- **ALWAYS use `pnpm web:build`** for production web builds
- **NEVER run `expo start`** directly - use workspace commands
### EAS Build Commands
- **Development builds**: `pnpm eas:build:dev:*` (simulator, device, local)
- **Staging builds**: `pnpm eas:build:staging:*`
- **Submit builds**: `pnpm eas:submit:*`
- **Update builds**: `pnpm eas:update:*`
- **Platform-specific**: Add `:ios` or `:android` suffix
### Server Assumptions
- **ASSUME Expo dev server** is running on `http://localhost:8081`
- **ASSUME Metro bundler** is running and watching for changes
- **DO NOT start Expo servers** unless explicitly requested
### Development Workflow
- **Test on actual devices** when possible
- **Use Expo Go app** for quick testing
- **Test on both iOS and Android** when making platform-specific changes
- **Use `pnpm prebuild`** before native builds
- **Check Xcode version** automatically with `pnpm ios`
### Platform-Specific Files
- `.native.tsx` - React Native specific implementations
- `.ios.tsx` - iOS specific implementations
- `.android.tsx` - Android specific implementations
- `.web.tsx` - Web specific implementations
### Key Generation
### Security Requirements
- **ALWAYS use `randomUUID()` from `expo-crypto`** for generating unique keys and identifiers
- **NEVER use `Math.random()` or other insecure methods** for key generation
- **IMPORT from `expo-crypto`** when generating UUIDs for React keys, database IDs, or any unique identifiers
### Testing Approach
- **Prompt user to test** on actual device or simulator
- **Suggest using Expo Go** for quick testing
- **Recommend testing on both platforms** for cross-platform features
### File Locations
- Expo config: `app.json` or `app.config.js`
- Native code: `ios/` and `android/` directories (generated by `prebuild`)
- Shared code: `src/` directory
- Platform-specific: Use file extensions (`.ios.tsx`, `.android.tsx`)
### References
- **Development Workflow**: See `general/development-workflow.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`

*Source: `.cursor/rules/stacks/react-native/expo-development.mdc`*

## Framework-Specific Rules

These rules apply when using specific frameworks or tools:

### Database

#### Alembic migration patterns and conventions for Python SQLAlchemy projects

### Command Usage
### Standard Commands
### Migration Best Practices
### Autogenerate Migrations
- Autogenerate always works (all models imported in env.py)
- Review autogenerated migrations before applying
- Never auto-generate without review
- Manual migration review ensures correctness
### Database Configuration
- DB URL is always read from app config, not alembic.ini
- Use environment variables for database URLs
- Different URLs for different environments
### Migration Management
- **Alembic revision every PR** - Create migrations for each pull request
- **Never auto-generate without review** - Always review generated migrations
- Manual migration review ensures correctness
### Migration Workflow
1. **Make schema changes** in SQLAlchemy models
### Common Patterns
### Adding a Column
### Creating a Table
### Best Practices
1. **Review all migrations** before applying
4. **Never edit existing migrations** (create new ones)
### References
- **SQLAlchemy**: See `frameworks/database/sqlalchemy.mdc`
- **Python**: See `languages/python/style.mdc`
- **FastAPI**: See `stacks/python-backend/fastapi.mdc`

*Source: `.cursor/rules/frameworks/database/alembic.mdc`*

#### Prisma database patterns and conventions for Next.js and TypeScript projects

### Prisma Client Setup
### Singleton Pattern
### Database Operations
### Type Safety
- Use Prisma-generated types consistently
- Leverage TypeScript types from `@prisma/client`
- Use `Prisma.*` utility types for operations
### Query Patterns
### Migration Management
### Schema Changes
- All schema changes require migrations
- Use `npx prisma migrate dev` for development
- Use `npx prisma migrate deploy` for production
- Never edit migration files after creation
### Schema Validation
### Best Practices
### Transactions
### Error Handling
### Soft Delete Pattern
### References
- **Database**: See `frameworks/database/supabase.mdc` for Supabase patterns
- **SQLAlchemy**: See `frameworks/database/sqlalchemy.mdc` for Python patterns
- **TypeScript**: See `languages/typescript/typing-standards.mdc`

*Source: `.cursor/rules/frameworks/database/prisma.mdc`*

#### SQLAlchemy database patterns and conventions

### Naming Conventions
### Tables and Models
- **snake_case for tables** - Use snake_case for table names
- **Singular model classes** - Model class names should be singular
### Primary Keys
### UUID Primary Keys
- **Use UUID(as_uuid=True) PKs** - Use UUID primary keys with proper type handling
### Soft Delete Pattern
### Deleted At Timestamp
- **Use soft-delete pattern via `deleted_at`** - Don't hard delete records
### Alembic Migrations
### Migration Management
- **Alembic revision every PR** - Create migrations for each pull request
- **Never auto-generate without review** - Always review generated migrations
- Manual migration review ensures correctness
### Migration Best Practices
- Review all auto-generated migrations
- Test migrations on development database first
- Keep migrations small and focused
- Never edit existing migrations (create new ones)
### Database Connection
### Connection Management
- Use connection pooling
- Proper session management
- Handle connection errors gracefully
### References
- **Python Style**: See `languages/python/style.mdc`
- **FastAPI**: See `stacks/python-backend/fastapi.mdc`
- **Architecture**: See `general/architecture.mdc`

*Source: `.cursor/rules/frameworks/database/sqlalchemy.mdc`*

#### Supabase development guidelines, commands, and database patterns

### Command Usage
### Workspace Commands
- **ALWAYS use `pnpm supa`** instead of global supabase CLI
- **NEVER use `supabase` directly** - always go through pnpm workspace
### Common Supabase Commands
- Start local Supabase: `pnpm supa start`
- Stop local Supabase: `pnpm supa stop`
- Generate types: `pnpm supa:generate` (local) or `pnpm supa:generate:remote`
- Create migration: `pnpm supa migration:new <name>`
- Apply migrations: `pnpm supa migration:up`
- Reset database: `pnpm supa reset`
- Check status: `pnpm supa status`
- Open Studio: `pnpm supa:studio` (http://127.0.0.1:54323)
- Open Mailpit: `pnpm supa:mailpit` (http://127.0.0.1:54324)
### Development Workflow
- **ASSUME Supabase is running** on `http://localhost:54321` unless told otherwise
- **Check `pnpm supa status`** before suggesting database operations
- **Use local types generation** (`pnpm supa:generate`) for development
- **Test API endpoints** using browser extensions or curl, not by starting servers
### File Locations
- Supabase config: `supabase/config.toml`
- Migrations: `supabase/migrations/`
- Types: `supabase/types.ts`
- Seed data: `supabase/seed.sql`
### Database Structure
### Conventions
- All tables use UUIDs for IDs (text-based UUIDs)
- Timestamps use `timestamptz`
- Junction tables follow naming pattern: `table1_table2`
- All tables have `created_at` and `updated_at` fields
### Schema Organization
### Row Level Security (RLS)
### Core Principle: NEVER Bypass RLS
### RLS Setup Pattern
### Security Layers
1. **Table Grants** - Grant appropriate permissions to roles
### Migration Template
### Best Practices
1. **Always enable RLS** on tables with sensitive data
6. **Prefer explicit grants** over broad permissions
### References
- **Database**: See `frameworks/database/sqlalchemy.mdc` for SQLAlchemy patterns
- **Security**: See `general/security.mdc`
- **Architecture**: See `general/architecture.mdc`

*Source: `.cursor/rules/frameworks/database/supabase.mdc`*

### Testing

#### Test organization, file layout, coverage targets

### Structure (example)
### Naming
- `*.test.ts[x]` for unit/integration
- E2E naming aligns with the chosen runner (e.g., Playwright)
### Coverage Targets
- Unit/integration: >= 80% for new/changed code; 100% for critical paths
- E2E: focus on mission‑critical flows (smoke + regression)
### Scope
- Keep unit tests close to implementation
- Place integration tests near the composing boundary

*Source: `.cursor/rules/frameworks/testing/organization.mdc`*

#### Testing standards with tiered mocks and reality verification

### Principles
- Prefer small, fast tests near the code; grow realism as you move up the test pyramid.
- **CRITICAL: All mocks in testing MUST be tested to match the ACTUAL thing they are mocking, otherwise the mocks are fucking useless and only cause problems.**
- Mocks are acceptable at lower levels when they are verified to match reality and do not hide defects.
- Avoid global toggles that bypass tests; failures must be fixed or the test adjusted with rationale.
### Test Pyramid and Mocking Strategy
1. Unit tests (allow mocks) — fast feedback on small units
   - Use test doubles for IO and slow deps (network, DB, filesystem).
   - Keep mocks minimal; prefer fakes over complex behaviors.
   - Replace unit-level mocks with real adapters where feasible.
   - Validate wiring across module boundaries and data contracts.
   - Exercise the system through public interfaces.
   - Only mock external third‑party services you do not control.
### UI Testing Workflow

**CRITICAL: For creating UI tests, use Playwright MCP with the actual UI to identify how the actual UI works in order to write or validate what is in the Playwright tests. Then run the Playwright tests and make sure they work against the actual UI as it actually works.**

### UI Test Creation Process
1. **Discovery Phase**: Use Playwright MCP to interact with the actual running UI
   - Navigate to the UI and explore its behavior
   - Identify selectors, interactions, and states through actual usage
   - Document how the UI actually responds to user actions
2. **Test Writing**: Write Playwright tests based on actual UI behavior discovered
   - Use selectors and interactions verified against the real UI
   - Ensure tests match the actual UI workflow, not assumptions
3. **Validation**: Run tests against the actual UI and verify they work correctly
   - Tests must pass against the real UI as it actually works
   - Adjust tests if UI behavior differs from assumptions
   - Never write tests without first verifying against the actual UI
### Mock Verification (Make Mocks Match Reality)

**CRITICAL: All mocks in testing MUST be tested to match the ACTUAL thing they are mocking, otherwise the mocks are fucking useless and only cause problems.**

- Contract tests: Assert provider/consumer agree on request/response shapes.
- Golden files/snapshots: Record real responses and reuse as fixtures; refresh on schema changes.
- Schema/type guards: Validate fixtures against JSON Schema or TypeScript types at test load.
- Parity runs: Periodically hit real services in CI nightly jobs to detect drift.
### When To Mock
- Allowed: low‑level unit tests for adapters, network clients, DB gateways.
- Allowed: failure scenarios that are costly/risky to reproduce (timeouts, 5xx).
- Avoid: mocking your own domain logic; prefer real collaboration between domain services.
- Avoid: mocks in E2E unless isolating non-deterministic third parties.
### Quality Bars
- Unit: fast (<100ms), isolated, deterministic. High branch/path coverage.
- Integration: validate cross‑module contracts and realistic data flows.
- E2E: validate critical paths; focus on user‑visible correctness.
### Test Isolation
### Core Principle
**Tests must be isolated by default** — data from one test suite should not affect another, and tests within a suite should not depend on each other unless explicitly necessary.
### Isolation Requirements
- **Between test suites**: Each test suite must clean up its own state and not rely on data created by other suites.
- **Between tests**: Each test must set up and tear down its own data. Tests should be able to run in any order.
- **Shared state**: Only share data between tests when explicitly necessary and documented with clear rationale.
- **Database/state**: Use transactions, test databases, or fixtures that are reset between tests. Never rely on shared mutable state.
### Implementation Guidelines
- **Setup/teardown**: Use `beforeEach`/`afterEach` or `beforeAll`/`afterAll` hooks to establish and clean up test state.
- **Transaction rollback**: Wrap database-dependent tests in transactions that roll back after each test.
- **Isolated test databases**: Use separate test databases or schemas per test suite when possible.
- **Fixtures**: Create fresh test data per test rather than reusing data across tests.
- **Global state**: Avoid global variables, singletons, or shared caches that persist between tests.
- **Concurrent execution**: Tests should be safe to run in parallel without interference.
### Exceptions and Documentation
- **Shared fixtures**: When sharing data is necessary (e.g., expensive setup, read-only reference data), document the rationale and ensure the shared state is immutable or reset between uses.
- **Integration test dependencies**: Integration tests may share a database schema, but each test must still clean up its own modifications.
- **E2E scenarios**: E2E tests may require shared state to simulate real user workflows; document these dependencies clearly.
### Fixture Hygiene
- Keep fixtures small and representative; remove unused fields.
- Co-locate fixtures with tests; document provenance (e.g., captured on 2025‑10‑29).
- Validate fixtures against schemas/types on load.
### Tooling Hints

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/frameworks/testing/standards.mdc`*

#### Testing tools and commands

### Runners & Libraries
- Unit/Integration: Vitest / Jest + Testing Library
- E2E: Playwright (preferred) or Cypress
- Contract tests: Pact, OpenAPI validators, Zod/JSON Schema
### Suggested Commands
### Guardrails
- Lint/typecheck pre-commit; full suite pre-push
- Keep test output deterministic; avoid real clocks unless essential

*Source: `.cursor/rules/frameworks/testing/tools.mdc`*

### Ui

#### Tailwind CSS styling standards and Vibecode theme guidelines

### Light Theme Only (MANDATORY)
All components must use light theme only. Dark theme elements are prohibited.
### Color Palette (MUST USE)
### Background Colors
- `bg-gray-50` - Main page backgrounds
- `bg-white` - Cards and panels
- `bg-blue-50` - Info sections
- `bg-green-50` - Success sections
- `bg-yellow-50` - Warning sections
- `bg-red-50` - Error sections
### Text Colors
- `text-gray-900` - Headings and main text
- `text-gray-700` - Body text and labels
- `text-gray-600` - Secondary information
- `text-gray-500` - Placeholder and help text
- `text-blue-600` - Links and interactive elements
### Border Colors
- `border-gray-200` - All card and component borders
- `border-blue-200` - Info section borders
- `border-green-200` - Success section borders
- `border-yellow-200` - Warning section borders
- `border-red-200` - Error section borders
### Component Patterns
### Card Components
### Button Components
### Form Elements
### Interactive States
### Hover Effects
- `hover:shadow-md` - Enhanced shadow for cards
- `hover:bg-blue-700` - Button hover states
- `transition-shadow` - Smooth transitions
- `transition-colors` - Color transitions
### Focus States
- `focus:border-blue-500` - Form element focus
- `focus:ring-blue-500` - Focus ring
- `focus:ring-2` - Ring width
- `focus:outline-none` - Remove default outline
### Spacing System
### Vertical Spacing
- `space-y-6` - Large spacing between major sections
- `space-y-4` - Medium spacing between related elements
- `space-y-3` - Small spacing between grouped items
### Padding
- `p-6` - Card padding
- `p-4` - Section padding
- `p-3` - Component padding
### Prohibited Patterns
❌ **NEVER USE:**
- Dark theme elements (`bg-gray-900`, `text-white`)
- Mixed themes

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/frameworks/ui/tailwind-css.mdc`*

#### Tamagui property mappings, debugging, and component development guidelines

### Component Library Philosophy
- **ALWAYS prefer vanilla Tamagui components** when creating/updating UI
- **ALWAYS prefer Bento components** for complex UI patterns
- **TREAT packages/ui as a cross-platform, portable package**
- **MAKE components reusable, well-documented, and refactored**
### Tamagui Component Usage
- Use Tamagui primitives (`Button`, `Text`, `View`, `Stack`, `XStack`, `YStack`, etc.)
- Prefer Tamagui styling over custom CSS/styling
- Use Tamagui themes and design tokens
- Leverage Tamagui's responsive design capabilities
### Property Mappings
### Core Style Properties
- `borderColor` → `bc`
- `backgroundColor` → `bg` (use `$color1` to `$color12` or `$blue1` to `$blue12`)
- `borderRadius` → `rounded` (use `$1` to `$12` for consistent spacing)
- `alignItems` → `items`
- `justifyContent` → `justify`
### Spacing Properties
- `paddingHorizontal` → `px`
- `paddingVertical` → `py`
- `padding` → `p`
- `marginHorizontal` → `mx`
- `marginVertical` → `my`
- `margin` → `m`
### Size Properties
- `width` → `w`
- `height` → `h`
- `minWidth` → `minW`
- `maxWidth` → `maxW`
### Typography Properties
- `fontSize` → `fos`
- `fontWeight` → `fow`
- `color` → `col`
- `textAlign` → `text`
### Shadow Properties
- **DO NOT use** `shadowColor`, `shadowOffset`, `shadowOpacity`, `shadowRadius`
- **USE** `boxShadow` property instead
### Color Variables
- **Theme colors**: `$color1` to `$color12`
- **Semantic colors**: `$blue1` to `$blue12`, `$green1` to `$green12`, etc.
- **Surface colors**: `$background`, `$backgroundHover`, `$backgroundPress`
- **Text colors**: `$color`, `$colorHover`, `$colorPress`
### Examples
### ❌ Avoid - Standard React Native Properties
### ✅ Prefer - Tamagui Shorthand Properties
### Debugging
### Build-Time Debugging
- Add `// debug` to the top of any file for build-time analysis
- Add `// debug-verbose` for even more detailed information
### Runtime Debugging

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/frameworks/ui/tamagui.mdc`*

## Cross-Cutting Topics

These topics apply across different parts of the codebase:

### Accessibility

- **Accessibility standards and WCAG 2.1 AA compliance requirements**: See `.cursor/rules/topics/accessibility/standards.mdc` for details

*Source: `.cursor/rules/topics/accessibility/standards.mdc`*

### Api

- **API design standards, HTTP status codes, error handling, and client usage patterns**: See `.cursor/rules/topics/api/design-standards.mdc` for details

*Source: `.cursor/rules/topics/api/design-standards.mdc`*

### Deployment

#### Deployment workflow, environment management, and release procedures

### Environment Overview
### Development Environment
- **Branch**: `development`
- **Database**: Local or development database
- **Server**: Local development server
- **Purpose**: Feature development and testing
### Staging Environment
- **Branch**: `staging`
- **Database**: Dedicated staging database
- **Server**: Dedicated staging deployment
- **Purpose**: Pre-production testing and validation
### Production Environment
- **Branch**: `main`
- **Database**: Dedicated production database
- **Server**: Dedicated production deployment
- **Purpose**: Live application serving real users
### Deployment Workflow
### Feature Development Flow
### Environment Protection
### Branch Protection Rules
#### Development Branch
- Required: Pull request reviews
- Required: Status checks pass
- Required: No merge conflicts
- Forbidden: Direct pushes
#### Staging Branch
- Required: Pull request reviews
- Required: All tests pass
- Required: Build successful
- Required: Database migrations safe
- Forbidden: Direct pushes
- Forbidden: Merges from feature branches
#### Main Branch (Production)
- Required: Pull request reviews (2 approvals)
- Required: All staging tests pass
- Required: Staging deployment verified
- Required: Database backup completed
- Forbidden: Direct pushes
- Forbidden: Merges from development or feature branches
### Database Management
### Migration Safety
- **Development**: Test migrations locally
- **Staging**: Verify migrations in staging environment
- **Production**: Backup database before applying migrations
### Environment Variables
- Separate databases for each environment
- Different API keys for each environment
- Proper access control for production
### Deployment Checklist
### Staging Deployment
- [ ] All tests pass locally
- [ ] Build successful
- [ ] Database migrations tested
- [ ] Environment variables configured
- [ ] Deploy to staging
- [ ] Verify staging deployment
- [ ] Test critical functionality
- [ ] Check error monitoring
### Main Deployment
- [ ] Staging environment verified working

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/topics/deployment/environments.mdc`*

### Git

#### Git branching strategy, commit conventions, and pull request workflow

### Branching Strategy
### Feature Branches
- **Use feature branches for all new development**
- Never commit directly to `main` or `production`
- Always create feature branches from `main`
### Branch Naming Convention
### Syncing Before PR
### Commit Standards
### Conventional Commit Format
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
### Pull Request Workflow
### PR Flow
1. **Open a Draft PR early** to communicate your direction
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
### Release Workflow
### Semantic Versioning
- **Major (X.0.0):** Breaking changes
- **Minor (0.X.0):** New features, backwards compatible
- **Patch (0.0.X):** Bug fixes, backwards compatible
### Release Process
1. Create feature branch from main
### Release Notes
- Release notes should be written BEFORE creating the PR
- Include PR numbers in release notes for traceability
- Highlight breaking changes prominently
### Best Practices
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

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/topics/git/workflow.mdc`*

### Observability

- **Observability, monitoring, and logging patterns**: See `.cursor/rules/topics/observability/monitoring.mdc` for details

*Source: `.cursor/rules/topics/observability/monitoring.mdc`*

### Quality

#### Error handling patterns, quality gates, and zero-error policy

### Core Requirements
### Zero Error Policy
- **Never commit with errors**: Always fix issues before committing
- **No TypeScript errors**: `npm run type-check` must pass
- **No linting errors**: `npm run lint` must pass
- **No testing errors**: All tests must pass
- **Build must succeed**: `npm run build` must complete successfully
### Pre-commit Validation
- Use pre-commit hooks to catch errors early
- Run all checks locally before pushing
- Don't rely on CI to catch issues
- Fix errors immediately when they appear
### Error Categories
### TypeScript Errors
- Compilation errors must be resolved
- Type safety issues must be fixed
- Interface mismatches must be corrected
- Import/export errors must be resolved
### Linting Errors
- ESLint violations must be fixed
- Code style issues must be resolved
- Unused variables must be removed
- Import/export consistency must be maintained
### Testing Errors
- All unit tests must pass
- Integration tests must pass
- No test failures allowed
- Test coverage requirements must be met
### Error Resolution Workflow
1. **Identify the Error** - Read error message carefully, understand root cause
### Quality Gates
### Before Every Commit
- [ ] TypeScript compilation passes
- [ ] Linting passes
- [ ] Tests pass
- [ ] Build succeeds
- [ ] No console errors
### References
- **Quality Gates**: See `topics/quality/gates.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`

*Source: `.cursor/rules/topics/quality/error-handling.mdc`*

#### Quality gates and standards for code quality, testing, and production readiness

### Overview
Quality gates are mandatory checkpoints that ensure code quality, reliability, and maintainability. **NO EXCEPTIONS** - These quality gates must be passed before ANY commit or push.
### Pre-Commit Quality Gates
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
### Pre-Push Quality Gates
### Full Test Suite
- [ ] **All Test Phases** - Unit, integration, e2e tests pass
- [ ] **Build Verification** - Application builds without errors
- [ ] **Type Checking** - TypeScript compilation successful
- [ ] **Linting** - All linting rules pass
### Environment-Specific Quality Gates
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
### Quality Metrics
### Code Quality
- **TypeScript Coverage**: 100% of files typed
- **ESLint Compliance**: 0 warnings/errors
- **Test Coverage**: >80% for critical paths
- **Build Success Rate**: 100%
### Performance
- **API Response Time**: <500ms for most endpoints
- **Build Time**: <5 minutes
- **Test Execution**: <2 minutes
### Enforcement
### Automated Enforcement
- Pre-commit hooks prevent commits that fail quality gates
- Pre-push hooks prevent pushes that fail quality gates
- CI/CD pipelines enforce quality gates
### Manual Enforcement

*[Content truncated - see source rule file for full details]*

*Source: `.cursor/rules/topics/quality/gates.mdc`*

- **Logging standards and logger usage patterns**: See `.cursor/rules/topics/quality/logging.mdc` for details

*Source: `.cursor/rules/topics/quality/logging.mdc`*

### Security

- **Authentication boundaries, user identification, and security patterns**: See `.cursor/rules/topics/security/authentication.mdc` for details

*Source: `.cursor/rules/topics/security/authentication.mdc`*

#### Secrets management, environment variables, and secure configuration

### Core Principles
- **Never commit `.env*` files** to version control
- **Use secure secret management systems** (Azure Key Vault, AWS Secrets Manager, etc.)
- **All secrets via secure storage** (e.g., `kv://sites/<name>`)
- **Rotate keys regularly** (every 90 days recommended)
- **CI jobs check expiry** automatically
### Environment Variables
### Secure Storage
- Store secrets in secure vaults, not in code
- Use environment variables for configuration
- Reference secrets by path (e.g., `kv://sites/<name>`)
- Never hardcode secrets in application code
### Key Rotation
- Rotate keys every 90 days
- Use CI jobs to check key expiry
- Automate key rotation when possible
- Document key rotation procedures
### Secret Management Best Practices
### Storage
- Use Azure Key Vault or equivalent
- Reference secrets by path, not by value
- Use different secrets for different environments
- Never store secrets in database or logs
### Access
- Limit access to secrets (principle of least privilege)
- Use service principals for automated access
- Audit secret access
- Rotate secrets when compromised
### Development
- Use `.env.example` files (without real values)
- Document required environment variables
- Use local secrets for development only
- Never commit actual secrets
### Security Checklist
- [ ] No secrets in version control
- [ ] Secrets stored in secure vault
- [ ] Environment variables documented
- [ ] Key rotation schedule established
- [ ] CI checks for secret expiry
- [ ] Access controls configured
- [ ] Audit logging enabled
### References
- **Security**: See `general/security.mdc`
- **Authentication**: See `topics/security/authentication.mdc`

*Source: `.cursor/rules/topics/security/secrets.mdc`*

### Troubleshooting

- **Troubleshooting patterns and debugging guidelines**: See `.cursor/rules/topics/troubleshooting/debugging.mdc` for details

*Source: `.cursor/rules/topics/troubleshooting/debugging.mdc`*

## Package Management

Package management and reuse guidelines:

- **Package management rules for @bernierllc packages using ./manager CLI**: See `.cursor/rules/packages/package-management.mdc`

- **Guidelines for reusing existing @bernierllc packages before creating new ones**: See `.cursor/rules/packages/package-reuse.mdc`

## References

For the complete set of rules and detailed information, refer to the source rule files:

- `.cursor/rules/general/` - Core development principles
- `.cursor/rules/languages/` - Language-specific conventions
- `.cursor/rules/stacks/` - Technology stack patterns
- `.cursor/rules/frameworks/` - Framework-specific guidelines
- `.cursor/rules/topics/` - Cross-cutting concerns
- `.cursor/rules/packages/` - Package management rules

## Customization

This file can be extended with project-specific rules. When adding project-specific
instructions:

1. Keep them at the top or in a dedicated "Project-Specific" section
2. Reference relevant global rules where applicable
3. Avoid duplicating content from global rules
4. Update this file when project standards evolve

## Regenerating This File

This file is generated from `.cursor/rules/` using the script:

```bash
python3 scripts/generate-agent-files.py
```

To regenerate after rule updates, run the script from the repository root.
