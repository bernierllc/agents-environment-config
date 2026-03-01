"""Files commands: aec files {generate}"""

from pathlib import Path

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console, get_repo_root

if HAS_TYPER:
    app = typer.Typer(help="Manage agent instruction files")
else:
    app = None


def generate() -> None:
    """Generate agent instruction files (CLAUDE.md, GEMINI.md, etc.) in templates/.

    Reads .cursor/rules/*.mdc, parses frontmatter, and generates
    reference-only instruction files for each agent defined in agents.json.
    """
    Console.header("Generate Agent Instruction Files")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    templates_dir = repo_root / "templates"
    if not templates_dir.exists():
        Console.error("templates/ directory not found in repo root")
        raise SystemExit(1)

    from ..lib.agent_files import generate_all

    try:
        results = generate_all(repo_root)
    except FileNotFoundError as e:
        Console.error(str(e))
        raise SystemExit(1)

    Console.print(f"Writing to {Console.path(templates_dir)}\n")

    for filename, content in results.items():
        output_path = templates_dir / filename
        output_path.write_text(content, encoding="utf-8")
        Console.success(f"Generated {filename}")

    Console.print()
    Console.success(f"Generated {len(results)} agent instruction files in templates/")


# Typer command decorators (if available)
if HAS_TYPER:
    @app.command("generate")
    def generate_cmd():
        """Generate agent instruction files in templates/ from .cursor/rules/."""
        generate()
