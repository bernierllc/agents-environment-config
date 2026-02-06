# Plans and Checklists Rules

## Planning Workflow

### When to Create Plans
- Every new feature, tool, or improvement should begin with a plans/ document
- If a `./plans/` doc for the topic does not exist, create one named after the task or feature
- Use `./plans/` or `./plans/<category>/` folders for organization

### Plan File Structure
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

## References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **Documentation**: See `general/documentation.mdc`
