"""Git setup orchestration for aec repo setup."""

import json
import shutil
import subprocess
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
    supported_json = templates_dir / "gitignore" / "supported.json"
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


def write_git_essential(
    project_dir: Path,
    essential_key: str,
    provider_key: str,
    templates_dir: Path,
) -> bool:
    """Copy a bundled template into the project directory.

    Returns True if written, False if skipped (already exists).
    Does not overwrite existing files.
    """
    essential = GIT_PROVIDERS[provider_key]["essentials"][essential_key]
    template_rel = essential["template"]
    if template_rel is None:
        return False

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
                shutil.copy2(src_file, dest_file)
        return True
    else:
        src = templates_dir / "git" / template_rel
        dest = _resolve_dest(project_dir, provider_key, essential_key)
        if dest.exists():
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
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
