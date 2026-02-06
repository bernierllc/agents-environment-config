# Documentation Rules

## Documentation Standards

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

## Documentation Types

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

## Documentation Maintenance

### Update Requirements
- **Functionality Changes**: Update docs when functionality changes
- **Mock Implementations**: Ensure implementation docs are added/updated for mocks
- **API Changes**: Update API documentation immediately
- **Architecture Changes**: Update architecture documentation

### Documentation Workflow
1. **Create**: Write documentation alongside code
2. **Review**: Review documentation for accuracy
3. **Update**: Keep documentation current with changes
4. **Validate**: Ensure links and references work
5. **Archive**: Move outdated docs to archive

## Code Documentation

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

## Planning Documentation

### Planning Structure
```
plans/
├── features/           # Feature planning
├── refactoring/        # Refactoring plans
├── architecture/       # Architecture changes
└── maintenance/        # Maintenance tasks
```

### Task List Format
```markdown
## Feature: User Authentication

### Tasks
- [ ] Design authentication flow
- [ ] Implement login endpoint
- [ ] Add password validation
- [x] Create user model
- [ ] Write tests

### Dependencies
- [ ] Database schema changes
- [ ] API documentation updates
```

### Cross-References
- **Related Features**: Link to related feature plans
- **Implementation Docs**: Link to implementation documentation
- **Architecture Docs**: Link to relevant architecture decisions
- **Code References**: Link to specific code files

## Documentation Tools

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

## Quality Assurance

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

## References
- **Architecture**: See `architecture.mdc`
- **Development Workflow**: See `development-workflow.mdc`
- **Port Management**: See `port-management.mdc`
- **CLI Tools**: See `project-setup-cli.mdc`