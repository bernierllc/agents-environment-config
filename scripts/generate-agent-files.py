#!/usr/bin/env python3
"""
Generate agent instruction files (AGENTS.md, GEMINI.md, QWEN.md, CLAUDE.md) 
from .cursor/rules/ directory.

These files incorporate essential rules so they can be committed to git repos
and used by anyone cloning the repository without requiring the global 
agents-environment-config setup.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml


def parse_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return None, content
    
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, content
    
    frontmatter_str = parts[1].strip()
    body = parts[2].strip()
    
    try:
        frontmatter = yaml.safe_load(frontmatter_str) or {}
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def extract_key_content(body: str, max_lines: int = 50) -> str:
    """Extract key content from rule body, limiting length.

    NOTE: This function is kept for backwards compatibility but is no longer
    used in the optimized reference-only generation mode.
    """
    lines = body.split('\n')

    # Skip code blocks and main title (first # header)
    in_code_block = False
    content_lines = []
    skip_code = False
    first_header_seen = False

    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            # Don't include code blocks in summaries - too verbose
            skip_code = True
            continue

        if in_code_block:
            continue

        # Skip the first main title (single #)
        stripped = line.strip()
        if stripped.startswith('# ') and not first_header_seen:
            first_header_seen = True
            continue

        # Include subheaders (##, ###, etc.) and key points
        if stripped.startswith('##'):
            # Convert headers to one level deeper for better nesting
            if stripped.startswith('###'):
                content_lines.append(stripped)
            else:
                content_lines.append('##' + stripped[1:])  # Make ### from ##
            skip_code = False
        elif stripped and not skip_code:
            # Include bullet points and important statements
            if stripped.startswith('-') or stripped.startswith('*') or stripped.startswith('1.'):
                content_lines.append(line)
            elif any(keyword in stripped.lower() for keyword in ['must', 'never', 'always', 'required', 'critical', 'prefer', 'avoid']):
                content_lines.append(line)
            elif stripped.startswith('**') and stripped.endswith('**'):  # Bold statements
                content_lines.append(line)

    # Limit total lines
    result = '\n'.join(content_lines[:max_lines])

    # If we cut it off, add a note
    if len(content_lines) > max_lines:
        result += '\n\n*[Content truncated - see source rule file for full details]*'

    return result


def generate_reference_only_content(
    organized_rules: Dict[str, List[Tuple[str, Dict, str]]]
) -> str:
    """Generate a slim, reference-only rules section.

    Instead of inlining rule content, this generates a categorized index
    that points to the source .mdc files. Rules are read on demand.
    """
    lines = []

    # Essential rules that should always be mentioned (read on demand)
    essential_rules = {
        'testing': '.cursor/rules/frameworks/testing/standards.mdc',
        'typescript': '.cursor/rules/languages/typescript/typing-standards.mdc',
        'architecture': '.cursor/rules/general/architecture.mdc',
        'git': '.cursor/rules/topics/git/workflow.mdc',
        'quality': '.cursor/rules/topics/quality/gates.mdc',
    }

    lines.extend([
        "## Rules Reference",
        "",
        "Rules are organized in `.cursor/rules/` and should be read on demand when relevant.",
        "Do NOT memorize all rules - read the specific rule file when working in that area.",
        "",
        "### Essential Rules (read when relevant)",
        "",
    ])

    for name, path in essential_rules.items():
        lines.append(f"- **{name.title()}**: `{path}`")

    lines.extend([
        "",
        "### All Rules by Category",
        "",
    ])

    category_descriptions = {
        'general': 'Core principles (architecture, workflow, documentation)',
        'languages': 'Language conventions (Python, TypeScript)',
        'stacks': 'Stack patterns (Next.js, FastAPI, React Native)',
        'frameworks': 'Framework guides (databases, testing, UI)',
        'topics': 'Cross-cutting (API, git, security, quality)',
        'packages': 'Package management',
    }

    for category, description in category_descriptions.items():
        rules = organized_rules.get(category, [])
        if rules:
            lines.append(f"- **{category}/**: {description} ({len(rules)} rules)")

    lines.extend([
        "",
        "### How to Use Rules",
        "",
        "1. When working on TypeScript, read `languages/typescript/typing-standards.mdc`",
        "2. When writing tests, read `frameworks/testing/standards.mdc`",
        "3. When setting up a project, read `general/architecture.mdc`",
        "4. For project-specific info, see `AGENTINFO.md`",
        "",
    ])

    return '\n'.join(lines)


def organize_rules(rules_dir: Path) -> Dict[str, List[Tuple[str, Dict, str]]]:
    """Organize rules by category."""
    organized = {
        'general': [],
        'languages': [],
        'stacks': [],
        'frameworks': [],
        'topics': [],
        'packages': []
    }
    
    for rule_file in sorted(rules_dir.rglob('*.mdc')):
        # Skip README files
        if rule_file.name == 'README.mdc':
            continue
        
        relative_path = rule_file.relative_to(rules_dir)
        path_parts = relative_path.parts
        
        # Determine category from path
        if len(path_parts) > 0:
            category = path_parts[0]
            if category not in organized:
                category = 'topics'  # Default fallback
        
        try:
            content = rule_file.read_text(encoding='utf-8')
            frontmatter, body = parse_frontmatter(content)
            
            if frontmatter:
                organized[category].append((
                    str(relative_path),
                    frontmatter,
                    body
                ))
        except Exception as e:
            print(f"Warning: Could not parse {rule_file}: {e}")
    
    return organized


def generate_agent_file(
    agent_name: str,
    organized_rules: Dict[str, List[Tuple[str, Dict, str]]],
    rules_dir: Path,
    slim_mode: bool = True
) -> str:
    """Generate agent instruction file content.

    Args:
        agent_name: Name of the AI agent
        organized_rules: Rules organized by category
        rules_dir: Path to rules directory
        slim_mode: If True, generate reference-only content (recommended).
                   If False, inline rule content (legacy, context-heavy).
    """
    lines = [
        f"# {agent_name} Agent Instructions",
        "",
        "> **Canonical Source**: Project-specific standards live in `AGENTINFO.md`.",
        "> Read that file first. This file provides rule references.",
        "",
        "## Quick Start",
        "",
        "1. Read `AGENTINFO.md` for project-specific info",
        "2. Read relevant `.cursor/rules/*.mdc` files on demand",
        "3. Do NOT memorize all rules - reference them when needed",
        "",
    ]

    if slim_mode:
        # Generate reference-only content
        lines.append(generate_reference_only_content(organized_rules))
    else:
        # Legacy mode - inline content (kept for backwards compatibility)
        lines.extend(_generate_inline_content(agent_name, organized_rules))

    lines.extend([
        "## Regenerating This File",
        "",
        "```bash",
        "python3 scripts/generate-agent-files.py",
        "```",
        "",
    ])

    return '\n'.join(lines)


def _generate_inline_content(
    agent_name: str,
    organized_rules: Dict[str, List[Tuple[str, Dict, str]]]
) -> List[str]:
    """Generate inline content (legacy mode). Returns list of lines."""
    lines = []

    # Core Development Principles (from general/)
    general_rules = organized_rules.get('general', [])
    if general_rules:
        lines.extend([
            "## Core Development Principles",
            "",
        ])

        for rule_path, frontmatter, body in general_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            always_apply = frontmatter.get('alwaysApply', False)

            if always_apply:
                key_content = extract_key_content(body, max_lines=40)
                lines.append(f"### {rule_name}")
                lines.append("")
                lines.append(key_content)
                lines.append("")
                lines.append(f"*Source: `.cursor/rules/{rule_path}`*")
                lines.append("")
            else:
                lines.append(f"- **{rule_name}**: `.cursor/rules/{rule_path}`")

    # Language-Specific Rules
    lang_rules = organized_rules.get('languages', [])
    if lang_rules:
        lines.extend([
            "",
            "## Language Rules",
            "",
        ])
        for rule_path, frontmatter, body in lang_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            lines.append(f"- **{rule_name}**: `.cursor/rules/{rule_path}`")

    # Stack-Specific Rules
    stack_rules = organized_rules.get('stacks', [])
    if stack_rules:
        lines.extend([
            "",
            "## Stack Rules",
            "",
        ])
        for rule_path, frontmatter, body in stack_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            lines.append(f"- **{rule_name}**: `.cursor/rules/{rule_path}`")

    # Framework Rules
    framework_rules = organized_rules.get('frameworks', [])
    if framework_rules:
        lines.extend([
            "",
            "## Framework Rules",
            "",
        ])
        for rule_path, frontmatter, body in framework_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            lines.append(f"- **{rule_name}**: `.cursor/rules/{rule_path}`")

    # Topics
    topic_rules = organized_rules.get('topics', [])
    if topic_rules:
        lines.extend([
            "",
            "## Topic Rules",
            "",
        ])
        for rule_path, frontmatter, body in topic_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            lines.append(f"- **{rule_name}**: `.cursor/rules/{rule_path}`")

    lines.append("")
    return lines


def main():
    """Main execution function."""
    # Determine repository root (assume script is in scripts/)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    rules_dir = repo_root / '.cursor' / 'rules'
    
    if not rules_dir.exists():
        print(f"Error: Rules directory not found at {rules_dir}")
        return 1
    
    print(f"Reading rules from {rules_dir}...")
    organized_rules = organize_rules(rules_dir)
    
    # Count rules
    total_rules = sum(len(rules) for rules in organized_rules.values())
    print(f"Found {total_rules} rule files")
    
    # Generate files for each agent
    agents = {
        'AGENTS.md': 'Codex',
        'GEMINI.md': 'Gemini CLI',
        'QWEN.md': 'Qwen Code',
        'CLAUDE.md': 'Claude Code'
    }
    
    for filename, agent_name in agents.items():
        print(f"Generating {filename} for {agent_name}...")
        content = generate_agent_file(agent_name, organized_rules, rules_dir)
        
        output_path = repo_root / filename
        output_path.write_text(content, encoding='utf-8')
        print(f"  Written to {output_path}")
    
    print("\nDone! Generated agent instruction files:")
    for filename in agents.keys():
        print(f"  - {filename}")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

