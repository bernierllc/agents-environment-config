# Package Management Rules

## Use the project's own package tooling

Before running any package command, find how this repository manages its packages and use that, not an ad-hoc command:

1. **Look for project scripts first**: `package.json` `scripts`, a `Makefile`, a `scripts/` directory, or a repo CLI (e.g. `./manager`, `./scripts/release`). If one exists for building, testing, versioning or publishing, it is the only supported path.
2. **Identify the workspace tool**: npm/pnpm/yarn workspaces, Turborepo, Nx, Lerna, Changesets. Run commands through it so the whole workspace stays consistent.
3. **Never publish by hand** (`npm publish` straight from a package directory) when the repo defines a release flow; hand publishing skips its version, changelog and validation steps.
4. **If there is no tooling**, use the package manager the lockfile implies (`package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn) and do not mix managers.

ecks

## Package Design

Follow the architecture this repository already uses; do not impose one.

- **Read the repo's conventions first**: its README, CONTRIBUTING, or package docs. If packages are layered (for example core → service → suite), keep dependencies pointing one way and put code in the layer the repo defines for it.
- **Match the language setup**: in a TypeScript repo, follow its `tsconfig` strictness; do not add types to a JavaScript package or change strictness as a side effect.
- **Keep each package focused**: one clear responsibility and a public API documented in its README.

## Package Reuse Guidelines

### Before Creating New Packages
1. **Search existing packages**: Check if functionality already exists (see `package-reuse.mdc`)
2. **Evaluate partial matches**: Consider extending existing packages
3. **Use composition**: Combine existing packages rather than recreating
4. **Document decisions**: Record the rationale where the repo keeps design notes

## Quality Gates

### Before Publishing
- [ ] Validation/lint passes (the project's validate or lint script)
- [ ] Build succeeds (the project's build script)
- [ ] Tests pass (the project's test script)
- [ ] Version bump and changelog follow the project's release flow
- [ ] Documentation complete: README.md, API docs, examples

### Package Requirements
- **README.md**: Purpose, usage, examples
- **API documentation**: Clear interface definitions
- **Types**: Whatever the repo's language setup requires (e.g. its `tsconfig` strictness)
- **Tests**: Cover the package's public behavior and edge cases
- **Error handling**: Follow the repo's error conventions

## References
- **Architecture**: See `general/architecture.mdc`
- **Development Workflow**: See `general/development-workflow.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
