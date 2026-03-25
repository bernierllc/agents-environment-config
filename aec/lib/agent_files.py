"""Generate agent instruction files from .cursor/rules/ directory.

Reads rule files, parses frontmatter, and generates CLAUDE.md, GEMINI.md,
QWEN.md, AGENTS.md templates with rule references for each AI agent.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    frontmatter_str = parts[1].strip()
    body = parts[2].strip()

    if not HAS_YAML:
        return None, content

    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def organize_rules(rules_dir: Path) -> Dict[str, List[Tuple[str, Dict, str]]]:
    """Organize rules by category from .cursor/rules/ directory."""
    organized: Dict[str, List[Tuple[str, Dict, str]]] = {
        "general": [],
        "languages": [],
        "stacks": [],
        "frameworks": [],
        "topics": [],
        "packages": [],
    }

    for rule_file in sorted(rules_dir.rglob("*.mdc")):
        if rule_file.name == "README.mdc":
            continue

        relative_path = rule_file.relative_to(rules_dir)
        path_parts = relative_path.parts

        category = path_parts[0] if path_parts else "topics"
        if category not in organized:
            category = "topics"

        try:
            content = rule_file.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(content)

            if frontmatter:
                organized[category].append(
                    (str(relative_path), frontmatter, body)
                )
        except Exception as e:
            print(f"Warning: Could not parse {rule_file}: {e}")

    return organized


def generate_reference_content(
    organized_rules: Dict[str, List[Tuple[str, Dict, str]]],
    use_agent_rules: bool = False,
) -> str:
    """Generate a slim, reference-only rules section.

    Instead of inlining rule content, generates a categorized index
    that points to the source files. Rules are read on demand.
    """
    if use_agent_rules:
        rules_dir = "~/.agent-tools/rules/agents-environment-config"
        ext = ".md"
        dir_note = (
            "Rules live in `~/.agent-tools/rules/agents-environment-config/` "
            "(installed by `aec install`) and should be read on demand."
        )
    else:
        rules_dir = ".cursor/rules"
        ext = ".mdc"
        dir_note = (
            "Rules are organized in `.cursor/rules/` and should be "
            "read on demand when relevant."
        )

    essential_rules = {
        "testing": f"{rules_dir}/frameworks/testing/standards{ext}",
        "typescript": f"{rules_dir}/languages/typescript/typing-standards{ext}",
        "architecture": f"{rules_dir}/general/architecture{ext}",
        "git": f"{rules_dir}/topics/git/workflow{ext}",
        "quality": f"{rules_dir}/topics/quality/gates{ext}",
    }

    category_descriptions = {
        "general": "Core principles (architecture, workflow, documentation)",
        "languages": "Language conventions (Python, TypeScript)",
        "stacks": "Stack patterns (Next.js, FastAPI, React Native)",
        "frameworks": "Framework guides (databases, testing, UI)",
        "topics": "Cross-cutting (API, git, security, quality)",
        "packages": "Package management",
    }

    lines = [
        "## Rules Reference",
        "",
        dir_note,
        "Do NOT memorize all rules - read the specific rule file when working in that area.",
        "",
        "### Essential Rules (read when relevant)",
        "",
    ]

    for name, path in essential_rules.items():
        lines.append(f"- **{name.title()}**: `{path}`")

    lines.extend(["", "### All Rules by Category", ""])

    for category, description in category_descriptions.items():
        rules = organized_rules.get(category, [])
        if rules:
            lines.append(
                f"- **{category}/**: {description} ({len(rules)} rules)"
            )

    lines.extend([
        "",
        "### How to Use Rules",
        "",
        f"1. When working on TypeScript, read `{rules_dir}/languages/typescript/typing-standards{ext}`",
        f"2. When writing tests, read `{rules_dir}/frameworks/testing/standards{ext}`",
        f"3. When working with databases, read `{rules_dir}/frameworks/database/connection-management{ext}`",
        f"4. When setting up a project, read `{rules_dir}/general/architecture{ext}`",
        "5. For project-specific info, see `AGENTINFO.md`",
        "",
    ])

    return "\n".join(lines)


def generate_agent_file(
    agent_name: str,
    organized_rules: Dict[str, List[Tuple[str, Dict, str]]],
    use_agent_rules: bool = False,
) -> str:
    """Generate agent instruction file content.

    Args:
        agent_name: Display name of the AI agent
        organized_rules: Rules organized by category
        use_agent_rules: If True, reference ~/.agent-tools/rules/*.md
    """
    if use_agent_rules:
        rules_path = "~/.agent-tools/rules/agents-environment-config/*.md"
    else:
        rules_path = ".cursor/rules/*.mdc"

    lines = [
        f"# {agent_name} Agent Instructions",
        "",
        "> **Canonical Source**: Project-specific standards live in `AGENTINFO.md`.",
        "> Read that file first. This file provides rule references.",
        "",
        "## Quick Start",
        "",
        "1. Read `AGENTINFO.md` for project-specific info",
        f"2. Read relevant `{rules_path}` files on demand",
        "3. Do NOT memorize all rules - reference them when needed",
        "",
    ]

    lines.append(
        generate_reference_content(organized_rules, use_agent_rules=use_agent_rules)
    )

    lines.extend([
        "## Regenerating This File",
        "",
        "```bash",
        "aec files generate",
        "```",
        "",
    ])

    return "\n".join(lines)


def generate_all(
    repo_root: Path,
    agents: Optional[Dict[str, Tuple[str, bool]]] = None,
) -> Dict[str, str]:
    """Generate all agent instruction files.

    Args:
        repo_root: Repository root path
        agents: Optional {filename: (display_name, use_agent_rules)} dict.
                If None, loaded from agents.json via registry.

    Returns:
        Dict of {filename: content} for all generated files.
    """
    rules_dir = repo_root / ".cursor" / "rules"
    if not rules_dir.exists():
        raise FileNotFoundError(f"Rules directory not found at {rules_dir}")

    organized_rules = organize_rules(rules_dir)

    if agents is None:
        from .registry import get_generation_agents
        agents = get_generation_agents()

    results = {}
    for filename, (agent_name, use_agent_rules) in agents.items():
        content = generate_agent_file(
            agent_name, organized_rules, use_agent_rules=use_agent_rules
        )
        results[filename] = content

    return results
