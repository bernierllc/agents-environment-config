"""Git setup orchestration for aec repo setup."""

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from .git_providers import GIT_PROVIDERS, detect_git_provider, scan_git_essentials

AEC_GITIGNORE_PATTERNS = [
    ".aec.json",
    ".aec-local/",
]

_TEMPLATES_ROOT: Optional[Path] = None


def get_templates_root() -> Path:
    """Return the absolute path to aec/templates/."""
    global _TEMPLATES_ROOT
    if _TEMPLATES_ROOT is None:
        _TEMPLATES_ROOT = Path(__file__).parent.parent / "templates"
    return _TEMPLATES_ROOT


def build_composite_gitignore(
    languages: List[str],
    frameworks: List[str],
    templates_dir: Path,
) -> str:
    """Build a composite .gitignore from detected languages and frameworks.

    Reads templates from the gitignore submodule (github/gitignore), deduplicates
    lines, and appends AEC-specific patterns. Falls back to AEC patterns only if
    the submodule is not initialized.
    """
    # supported.json lives in our repo (one level up from the submodule), not inside it
    supported_json = templates_dir / "gitignore_supported.json"
    # Templates are at submodule root (github/gitignore), NOT in a 'templates/' subdirectory
    gitignore_templates_dir = templates_dir / "gitignore"

    template_files: List[str] = []

    if supported_json.exists() and gitignore_templates_dir.exists():
        supported = json.loads(supported_json.read_text())
        seen_templates: set = set()

        for lang in languages:
            for tpl in supported.get("languages", {}).get(lang, []):
                if tpl not in seen_templates:
                    template_files.append(tpl)
                    seen_templates.add(tpl)

        for fw in frameworks:
            for tpl in supported.get("frameworks", {}).get(fw, []):
                if tpl not in seen_templates:
                    template_files.append(tpl)
                    seen_templates.add(tpl)
    elif languages or frameworks:
        print(
            "  Warning: gitignore template submodule not initialized.\n"
            "  Run `aec install` to initialize it for language-aware .gitignore generation.\n"
            "  Falling back to AEC patterns only."
        )

    sections: List[str] = []
    seen_lines: set = set()

    for tpl_name in template_files:
        tpl_path = gitignore_templates_dir / tpl_name
        if not tpl_path.exists():
            continue
        name = tpl_name.replace(".gitignore", "")
        section_lines = [f"### {name} ###"]
        for line in tpl_path.read_text(encoding="utf-8").splitlines():
            if line not in seen_lines:
                seen_lines.add(line)
                section_lines.append(line)
        sections.append("\n".join(section_lines))

    aec_section = "\n### AEC ###\n" + "\n".join(AEC_GITIGNORE_PATTERNS)
    sections.append(aec_section)

    return "\n\n".join(sections) + "\n"


# --- Template context ---------------------------------------------------------
#
# Templates carry ``{{name}}`` placeholders that are always filled from a
# context, and dependabot/CI are generated from what the project actually
# uses. Nothing AEC writes may still say "YEAR AUTHOR" or "@your-username".

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# (marker files, dependabot ecosystem) -- first match wins per ecosystem.
_DEPENDABOT_ECOSYSTEMS = [
    (("package.json",), "npm"),
    (("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"), "pip"),
    (("go.mod",), "gomod"),
    (("Cargo.toml",), "cargo"),
    (("Gemfile",), "bundler"),
    (("composer.json",), "composer"),
    (("Dockerfile",), "docker"),
]


def _git(project_dir: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=project_dir, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def github_owner(project_dir: Path) -> str:
    """GitHub owner of the ``origin`` remote (``bernierllc`` for
    ``git@github.com:bernierllc/repo.git``), or "" when not on GitHub."""
    url = _git(project_dir, "remote", "get-url", "origin")
    match = re.search(r"github\.com[:/]([^/]+)/", url)
    return match.group(1) if match else ""


def _gh_api(path: str, jq: str) -> str:
    """One ``gh api`` lookup, or "" when gh is missing, offline, or unauthenticated."""
    try:
        out = subprocess.run(
            ["gh", "api", path, "-q", jq], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def github_account_type(login: str) -> str:
    """``"User"``, ``"Organization"``, or "" when it cannot be determined."""
    return _gh_api(f"users/{login}", ".type") if login else ""


def default_codeowner(project_dir: Path) -> str:
    """A CODEOWNERS owner GitHub will honor, or "" if none can be inferred.

    An organization alone is not a valid owner (it must be a user or an
    ``@org/team``), so the origin owner is used only when it is a user;
    otherwise the signed-in ``gh`` user.
    """
    owner = github_owner(project_dir)
    if owner and github_account_type(owner) == "User":
        return owner
    return _gh_api("user", ".login")


def default_copyright_holder(project_dir: Path) -> str:
    """Best guess for the LICENSE holder: git ``user.name``, else the GitHub
    owner, else "The <project> Authors"."""
    return (
        _git(project_dir, "config", "user.name")
        or github_owner(project_dir)
        or f"The {project_dir.name} Authors"
    )


def detect_dependabot_ecosystems(project_dir: Path, *, with_actions: bool = False) -> List[str]:
    """Dependabot ecosystems for the manifests present in ``project_dir``."""
    found = [
        eco for markers, eco in _DEPENDABOT_ECOSYSTEMS
        if any((project_dir / m).exists() for m in markers)
    ]
    if with_actions or (project_dir / ".github" / "workflows").exists():
        found.append("github-actions")
    return found


def render_dependabot(ecosystems: List[str]) -> str:
    lines = ["version: 2", "updates:"]
    for eco in ecosystems:
        lines += [
            f'  - package-ecosystem: "{eco}"',
            '    directory: "/"',
            "    schedule:",
            '      interval: "weekly"',
        ]
    if not ecosystems:
        lines[-1] = "updates: []"
    return "\n".join(lines) + "\n"


def _python_install_command(project_dir: Path) -> str:
    if (project_dir / "requirements.txt").exists():
        return "pip install -r requirements.txt"
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*dev\s*=", text, re.M) and "optional-dependencies" in text:
            return 'pip install -e ".[dev]"'
        return "pip install -e ."
    return "pip install pytest"


def _node_install_command(project_dir: Path) -> str:
    if (project_dir / "pnpm-lock.yaml").exists():
        return "corepack enable && pnpm install --frozen-lockfile"
    if (project_dir / "yarn.lock").exists():
        return "yarn install --frozen-lockfile"
    if (project_dir / "package-lock.json").exists():
        return "npm ci"
    return "npm install"


def render_ci_workflow(project_dir: Path, test_commands: List[str]) -> str:
    """A CI workflow that runs the project's detected test commands.

    With no known command the test step emits a GitHub warning annotation
    rather than a silent always-green ``echo``.
    """
    head = [
        "name: CI", "", "on:", "  push:", "    branches: [main]",
        "  pull_request:", "    branches: [main]", "", "jobs:", "  test:",
        "    runs-on: ubuntu-latest", "    steps:", "      - uses: actions/checkout@v4",
    ]
    steps: List[str] = []
    test_commands = ci_safe_commands(test_commands)
    if not test_commands:
        steps += [
            "      - name: Run tests",
            '        run: echo "::warning title=CI not configured::Add your test command '
            'to .github/workflows/ci.yml"',
        ]
        return "\n".join(head + steps) + "\n"

    runtimes = {_runtime(cmd) for cmd in test_commands}
    if "python" in runtimes:
        steps += [
            "      - uses: actions/setup-python@v5",
            "        with:",
            '          python-version: "3.12"',
            "      - name: Install Python dependencies",
            f"        run: {_python_install_command(project_dir)}",
        ]
    if "node" in runtimes:
        steps += [
            "      - uses: actions/setup-node@v4",
            "        with:",
            '          node-version: "lts/*"',
            "      - name: Install Node dependencies",
            f"        run: {_node_install_command(project_dir)}",
        ]
    if "go" in runtimes:
        steps += [
            "      - uses: actions/setup-go@v5",
            "        with:",
            "          go-version-file: go.mod",
        ]
    for cmd in test_commands:
        steps += [f"      - name: {yaml_quote(f'Test ({cmd})')}", f"        run: {yaml_quote(cmd)}"]
    return "\n".join(head + steps) + "\n"


def ci_safe_commands(test_commands: List[str]) -> List[str]:
    """Commands that can go into a workflow ``run:`` line. A command spanning
    lines is not something detection produces for a well-formed project, so it
    is left out (and reported by the caller) rather than written."""
    return [c for c in test_commands if c.strip() and not re.search(r"[\r\n]", c)]


# Characters YAML does not allow literally inside a double-quoted scalar (or
# would fold as a line break); all are in the BMP, so \uXXXX escapes them.
_YAML_UNSAFE = re.compile("[\x7f-\x9f\u2028\u2029\ufeff\ud800-\udfff\ufffe\uffff]")


def yaml_quote(value: str) -> str:
    """``value`` as a YAML double-quoted scalar that parses back identically.

    ``json.dumps`` already escapes quotes, backslashes and C0 controls in a
    YAML-compatible way. It is used with ``ensure_ascii=False`` because JSON's
    surrogate-pair escape for non-BMP characters is not understood by YAML;
    the few characters YAML rejects literally are escaped afterwards.
    """
    quoted = json.dumps(value, ensure_ascii=False)
    return _YAML_UNSAFE.sub(lambda m: "\\u%04x" % ord(m.group()), quoted)


def _runtime(command: str) -> str:
    first = command.split()[0] if command.split() else ""
    if first in ("npm", "npx", "yarn", "pnpm", "node", "bun"):
        return "node"
    if first in ("python", "python3", "pytest", "uv", "poetry", "tox"):
        return "python"
    if first == "go":
        return "go"
    return ""


def default_git_context(
    project_dir: Path,
    *,
    test_commands: Optional[List[str]] = None,
    copyright_holder: Optional[str] = None,
    codeowner: Optional[str] = None,
    with_ci: bool = False,
) -> dict:
    """Everything needed to render the git-essential templates for a project."""
    owner = default_codeowner(project_dir) if codeowner is None else codeowner.lstrip("@")
    return {
        "year": str(date.today().year),
        "project_name": project_dir.name,
        "copyright_holder": copyright_holder or default_copyright_holder(project_dir),
        "codeowners_rule": f"* @{owner}" if owner else "# * @your-username",
        "generated": {
            "dependabot": render_dependabot(
                detect_dependabot_ecosystems(project_dir, with_actions=with_ci)
            ),
            "ci_workflow": render_ci_workflow(project_dir, list(test_commands or [])),
        },
    }


def render_template(text: str, context: dict) -> str:
    """Fill ``{{name}}`` placeholders; an unknown name is a bug, not a silent pass."""

    def sub(match):
        key = match.group(1)
        if key not in context:
            raise KeyError(f"template placeholder {{{{{key}}}}} has no value")
        return str(context[key])

    return _PLACEHOLDER.sub(sub, text)


def _write_rendered(src: Path, dest: Path, context: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_template(src.read_text(encoding="utf-8"), context), encoding="utf-8")


def write_git_essential(
    project_dir: Path,
    essential_key: str,
    provider_key: str,
    templates_dir: Path,
    context: Optional[dict] = None,
) -> bool:
    """Write a git essential into the project directory, rendered for it.

    Templates are filled from ``context`` (see ``default_git_context``, used
    when none is given); dependabot and CI are generated from the project.

    Returns True if written, False if skipped (already exists).
    Does not overwrite existing files.
    """
    essential = GIT_PROVIDERS[provider_key]["essentials"][essential_key]
    template_rel = essential["template"]
    if template_rel is None:
        return False
    if context is None:
        context = default_git_context(project_dir)

    is_dir = template_rel.endswith("/")

    if is_dir:
        src_dir = templates_dir / "git" / template_rel.rstrip("/")
        if not src_dir.exists():
            return False
        dest_dir = _resolve_dest(project_dir, provider_key, essential_key)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src_file in src_dir.iterdir():
            dest_file = dest_dir / src_file.name
            if not dest_file.exists():
                _write_rendered(src_file, dest_file, context)
        return True
    else:
        src = templates_dir / "git" / template_rel
        dest = _resolve_dest(project_dir, provider_key, essential_key)
        if dest.exists():
            return False
        generated = context.get("generated", {}).get(essential_key)
        if generated is not None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(generated, encoding="utf-8")
        else:
            _write_rendered(src, dest, context)
        return True


def _resolve_dest(project_dir: Path, provider_key: str, essential_key: str) -> Path:
    """Resolve the destination path for an essential from its template path."""
    essential = GIT_PROVIDERS[provider_key]["essentials"][essential_key]
    template_rel = essential["template"]
    if template_rel is None:
        raise ValueError(f"No template for {essential_key}")
    rel = template_rel[len(f"{provider_key}/"):]
    return project_dir / rel


def execute_commit_strategy(
    project_dir: Path,
    files: List[str],
    strategy: str,
    agent_name: str = "your AI agent",
) -> None:
    """Execute the user's chosen commit strategy for created files.

    strategy: "one_commit" | "incremental" | "stage_only" | "none"
    """
    if strategy == "none" or not files:
        return

    def _stage(f: str) -> bool:
        result = subprocess.run(
            ["git", "add", f], cwd=project_dir, capture_output=True, text=True
        )
        return result.returncode == 0

    def _commit(msg: str) -> bool:
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=project_dir, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"\n  Git commit failed: {result.stderr.strip()}")
            print(f"  Ask {agent_name} to help troubleshoot.")
        return result.returncode == 0

    if strategy == "stage_only":
        for f in files:
            _stage(f)

    elif strategy == "one_commit":
        for f in files:
            _stage(f)
        _commit("chore: add git essentials via aec setup")

    elif strategy == "incremental":
        for f in files:
            if _stage(f):
                _commit(f"chore: add {f} via aec setup")
