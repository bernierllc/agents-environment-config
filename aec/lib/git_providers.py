"""Git provider registry for aec repo setup."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

GIT_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "github": {
        "display_name": "GitHub",
        "detect_files": [".github/"],
        "detect_commands": ["gh"],
        "detect_env_vars": ["GITHUB_TOKEN", "GH_TOKEN"],
        "essentials": {
            ".gitignore": {
                "display": ".gitignore (language-aware, with AEC patterns)",
                "check": lambda d: (d / ".gitignore").exists(),
                "template": None,  # built dynamically from supported.json
            },
            "README.md": {
                "display": "README.md",
                "check": lambda d: (d / "README.md").exists(),
                "template": "github/README.md",
            },
            "dependabot": {
                "display": "Dependabot config (.github/dependabot.yml)",
                "check": lambda d: (d / ".github" / "dependabot.yml").exists(),
                "template": "github/.github/dependabot.yml",
            },
            "pr_template": {
                "display": "PR template (.github/PULL_REQUEST_TEMPLATE.md)",
                "check": lambda d: (d / ".github" / "PULL_REQUEST_TEMPLATE.md").exists(),
                "template": "github/.github/PULL_REQUEST_TEMPLATE.md",
            },
            "issue_templates": {
                "display": "Issue templates (.github/ISSUE_TEMPLATE/)",
                "check": lambda d: (d / ".github" / "ISSUE_TEMPLATE").exists(),
                "template": "github/.github/ISSUE_TEMPLATE/",
            },
            "ci_workflow": {
                "display": "CI workflow (.github/workflows/ci.yml)",
                "check": lambda d: (d / ".github" / "workflows").exists(),
                "template": "github/.github/workflows/ci.yml",
            },
            "license": {
                "display": "LICENSE file",
                "check": lambda d: any(d.glob("LICENSE*")),
                "template": "github/LICENSE",
            },
            "editorconfig": {
                "display": ".editorconfig",
                "check": lambda d: (d / ".editorconfig").exists(),
                "template": "github/.editorconfig",
            },
            "codeowners": {
                "display": "CODEOWNERS (.github/CODEOWNERS)",
                "check": lambda d: (d / ".github" / "CODEOWNERS").exists(),
                "template": "github/.github/CODEOWNERS",
            },
        },
    },
    # To add GitLab, Bitbucket, etc: add an entry here with the same shape.
}


def detect_git_provider(project_dir: Path) -> Optional[str]:
    """Detect the git provider for a project directory.

    Returns provider key (e.g. "github"), "unknown" if git exists but
    provider unrecognized, or None if no .git directory found.
    """
    if not (project_dir / ".git").exists():
        return None

    for provider_key, provider in GIT_PROVIDERS.items():
        for f in provider["detect_files"]:
            if (project_dir / f).exists():
                return provider_key
        for cmd in provider["detect_commands"]:
            if shutil.which(cmd) is not None:
                return provider_key
        for var in provider["detect_env_vars"]:
            if os.environ.get(var):
                return provider_key

    return "unknown"


def scan_git_essentials(project_dir: Path, provider_key: str) -> Dict[str, str]:
    """Scan which git essentials are present or missing.

    Returns dict mapping essential key -> "found" | "missing".
    """
    provider = GIT_PROVIDERS[provider_key]
    return {
        key: ("found" if essential["check"](project_dir) else "missing")
        for key, essential in provider["essentials"].items()
    }
