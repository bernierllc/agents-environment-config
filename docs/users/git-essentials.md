# Git essentials phase

During `aec setup`, AEC detects your git provider and checks for missing essentials. For GitHub projects it offers a multi-select checklist:

| Essential | What gets created |
|---|---|
| `.gitignore` | Language-aware, built from the `github/gitignore` templates + AEC patterns |
| `README.md` | Starter readme |
| `dependabot.yml` | `.github/dependabot.yml` with weekly update schedule |
| PR template | `.github/PULL_REQUEST_TEMPLATE.md` |
| Issue templates | `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md` |
| CI workflow | `.github/workflows/ci.yml` |
| `LICENSE` | MIT license |
| `.editorconfig` | Consistent editor settings |
| `CODEOWNERS` | `.github/CODEOWNERS` stub |

AEC skips any essential that already exists, so it's safe to run on established projects. After creating files you choose a commit strategy: one commit, incremental per file, stage-only, or none.

The gitignore builder pulls templates from the bundled `github/gitignore` submodule and maps your detected languages (TypeScript, Python, Rust, Go, Ruby) and frameworks to the right template files.

To add support for a new git provider (GitLab, Bitbucket, etc.), see [Adding git provider support](../contributors/adding-git-provider-support.md).
