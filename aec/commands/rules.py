"""Rules commands: aec rules {generate|validate}"""

import re
from pathlib import Path
from typing import List, Tuple

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console, get_repo_root, ensure_directory

if HAS_TYPER:
    app = typer.Typer(help="Manage agent rules")
else:
    app = None


def _strip_frontmatter(content: str) -> str:
    """
    Strip YAML frontmatter from markdown content.

    Frontmatter is delimited by --- at the start and end.
    """
    lines = content.split("\n")

    if not lines or lines[0].strip() != "---":
        return content

    # Find the closing ---
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            # Return everything after the frontmatter
            return "\n".join(lines[i + 1:]).lstrip("\n")

    # No closing ---, return original
    return content


def _get_cursor_rules(repo_root: Path) -> List[Path]:
    """Get all .mdc files in .cursor/rules/, excluding README.mdc."""
    cursor_rules = repo_root / ".cursor" / "rules"
    if not cursor_rules.exists():
        return []

    rules = []
    for mdc_file in cursor_rules.rglob("*.mdc"):
        if mdc_file.name != "README.mdc":
            rules.append(mdc_file)

    return sorted(rules)


def _mdc_to_md_path(mdc_path: Path, repo_root: Path) -> Path:
    """Convert a .cursor/rules/*.mdc path to .agent-rules/*.md path."""
    relative = mdc_path.relative_to(repo_root / ".cursor" / "rules")
    md_name = relative.with_suffix(".md")
    return repo_root / ".agent-rules" / md_name


def generate() -> None:
    """Generate .agent-rules/ from .cursor/rules/ (strips frontmatter)."""
    Console.header("Generate Agent Rules")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    Console.print(f"Repository: {Console.path(repo_root)}")

    cursor_rules = _get_cursor_rules(repo_root)
    if not cursor_rules:
        Console.warning("No .mdc files found in .cursor/rules/")
        return

    Console.print(f"Found {len(cursor_rules)} rule files\n")

    agent_rules_dir = repo_root / ".agent-rules"
    generated = 0
    errors = 0

    for mdc_file in cursor_rules:
        md_file = _mdc_to_md_path(mdc_file, repo_root)

        try:
            # Read and strip frontmatter
            content = mdc_file.read_text()
            stripped = _strip_frontmatter(content)

            # Ensure directory exists
            ensure_directory(md_file.parent)

            # Write stripped content
            md_file.write_text(stripped)

            relative_md = md_file.relative_to(repo_root)
            Console.success(f"{relative_md}")
            generated += 1

        except Exception as e:
            Console.error(f"Failed to process {mdc_file.name}: {e}")
            errors += 1

    Console.print()
    if errors == 0:
        Console.success(f"Generated {generated} rule files in .agent-rules/")
    else:
        Console.warning(f"Generated {generated} files, {errors} errors")


def validate() -> Tuple[bool, List[str]]:
    """
    Validate .agent-rules/ matches .cursor/rules/ (sans frontmatter).

    Returns:
        Tuple of (success, list of error messages)
    """
    Console.header("Validate Rule Parity")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        return False, ["Repository not found"]

    cursor_rules = _get_cursor_rules(repo_root)
    if not cursor_rules:
        Console.warning("No .mdc files found in .cursor/rules/")
        return True, []

    errors: List[str] = []

    for mdc_file in cursor_rules:
        md_file = _mdc_to_md_path(mdc_file, repo_root)
        relative_mdc = mdc_file.relative_to(repo_root)
        relative_md = md_file.relative_to(repo_root)

        # Check if corresponding .md file exists
        if not md_file.exists():
            errors.append(f"Missing: {relative_md} (source: {relative_mdc})")
            continue

        # Compare content (stripped frontmatter vs .md)
        mdc_content = mdc_file.read_text()
        mdc_stripped = _strip_frontmatter(mdc_content).strip()
        md_content = md_file.read_text().strip()

        if mdc_stripped != md_content:
            errors.append(f"Content mismatch: {relative_mdc} vs {relative_md}")

    if errors:
        Console.error(f"Rule parity check failed - {len(errors)} issue(s):\n")
        for error in errors:
            Console.print(f"  - {error}")
        Console.print()
        Console.print(f"Run {Console.cmd('python -m aec rules generate')} to fix.")
        return False, errors
    else:
        Console.success(f"Rule parity check passed - .agent-rules/ matches .cursor/rules/")
        Console.print(f"  Validated {len(cursor_rules)} rule files")
        return True, []


# Typer command decorators (if available)
if HAS_TYPER:
    @app.command("generate")
    def generate_cmd():
        """Generate .agent-rules/ from .cursor/rules/ (strips frontmatter)."""
        generate()

    @app.command("validate")
    def validate_cmd():
        """Validate .agent-rules/ parity with .cursor/rules/."""
        success, _ = validate()
        if not success:
            raise typer.Exit(1)
