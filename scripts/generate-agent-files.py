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
    """Extract key content from rule body, limiting length."""
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
    rules_dir: Path
) -> str:
    """Generate agent instruction file content."""
    
    # Determine agent-specific pointer text
    if agent_name == "Codex":
        pointer_text = [
            "> 🚨 **Canonical Source**: All project-specific standards now live in `AGENTINFO.md`. Always update/read that file first; this document contains global rules and is a pointer to project-specific info.",
            "",
            "**Maintaining AGENTINFO.md:**",
            "- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately",
            "- `AGENTINFO.md` should contain all project-specific information (structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, documentation)",
            "- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`",
            "- If you notice drift between this repo's behavior and `AGENTINFO.md`, fix `AGENTINFO.md` immediately",
        ]
    elif agent_name == "Claude Code":
        pointer_text = [
            "> 🚨 **Canonical Source**: All project-specific standards live in `AGENTINFO.md`. Read/update that file first; this profile only highlights Claude-specific reminders.",
            "",
            "**Maintaining AGENTINFO.md:**",
            "- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately",
            "- Mirror every expectation from `AGENTINFO.md` (project structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, documentation)",
            "- Keep responses crisp but cite `AGENTINFO.md` when referencing project rules so humans know the authoritative file",
            "- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`",
            "- If new constraints arise, edit `AGENTINFO.md` first—never duplicate details here",
        ]
    elif agent_name == "Gemini CLI":
        pointer_text = [
            "> 🚨 **Canonical Source**: All project-specific guidance now lives in `AGENTINFO.md`. Read/update that file first. This document only carries Gemini-specific reminders.",
            "",
            "**Maintaining AGENTINFO.md:**",
            "- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately",
            "- Treat `AGENTINFO.md` as the single source of truth for project structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, and documentation",
            "- Mirror the requirements spelled out in `AGENTINFO.md` in all responses",
            "- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`",
            "- Update `AGENTINFO.md` whenever new standards emerge; do **not** duplicate the details here",
        ]
    elif agent_name == "Qwen Code":
        pointer_text = [
            "> 🚨 **Canonical Source**: All project-specific context now lives in `AGENTINFO.md`. Read/update that file first; this profile only adds Qwen-specific reminders.",
            "",
            "**Maintaining AGENTINFO.md:**",
            "- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately",
            "- Mirror every requirement from `AGENTINFO.md` (project structure, build/test commands, coding style, testing guidance, commit/PR standards, security/config, documentation)",
            "- When responding, cite the relevant sections of `AGENTINFO.md` rather than restating them—this avoids stale guidance",
            "- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`",
            "- If you discover new constraints, update `AGENTINFO.md` instead of duplicating details here",
        ]
    else:
        # Generic fallback for other agents
        pointer_text = [
            "> 🚨 **Canonical Source**: All project-specific standards now live in `AGENTINFO.md`. Always update/read that file first; this document contains global rules and is a pointer to project-specific info.",
            "",
            "**Maintaining AGENTINFO.md:**",
            "- When project-specific processes, structure, or standards change, update `AGENTINFO.md` immediately",
            "- Do NOT duplicate project-specific information in this file or in `.cursor/rules/` - keep it in `AGENTINFO.md`",
        ]
    
    lines = [
        f"# {agent_name} Agent Instructions",
        "",
    ]
    lines.extend(pointer_text)
    lines.extend([
        "",
        "## Overview",
        "",
        f"This file contains development rules and standards for the {agent_name} AI coding assistant.",
        "These instructions are generated from `.cursor/rules/` and incorporate essential development",
        "principles, coding standards, and best practices. This file can be committed to git repositories",
        "so that anyone cloning the project will have consistent coding standards even without access",
        "to the global agents-environment-config repository.",
        "",
        "> **Note**: For detailed information and the latest updates, see the source rule files in",
        "> `.cursor/rules/` if available in this repository. For project-specific information, see `AGENTINFO.md`.",
        "",
        "---",
        "",
    ])
    
    # Core Development Principles (from general/)
    general_rules = organized_rules.get('general', [])
    if general_rules:
        lines.extend([
            "## Core Development Principles",
            "",
            "These principles apply universally across all projects:",
            "",
        ])
        
        for rule_path, frontmatter, body in general_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            always_apply = frontmatter.get('alwaysApply', False)
            
            # Include full content for always-apply general rules
            if always_apply:
                # Extract key content (headers and main points)
                key_content = extract_key_content(body, max_lines=80)
                
                lines.append(f"### {rule_name}")
                lines.append("")
                lines.append(key_content)
                lines.append("")
                lines.append(f"*Source: `.cursor/rules/{rule_path}`*")
                lines.append("")
            else:
                # Brief summary for non-always-apply general rules
                lines.append(f"- **{rule_name}**: See `.cursor/rules/{rule_path}`")
                lines.append("")
    
    # Language-Specific Rules
    lang_rules = organized_rules.get('languages', [])
    if lang_rules:
        lines.extend([
            "## Language-Specific Rules",
            "",
            "These rules apply when working with specific languages. They are conditionally relevant",
            "based on the file types being edited:",
            "",
        ])
        
        for rule_path, frontmatter, body in lang_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            globs = frontmatter.get('globs', [])
            
            lines.append(f"### {rule_name}")
            if globs:
                lines.append(f"*Applies to: {', '.join(globs[:3])}{'...' if len(globs) > 3 else ''}*")
            lines.append("")
            
            key_content = extract_key_content(body, max_lines=60)
            lines.append(key_content)
            lines.append("")
            lines.append(f"*Source: `.cursor/rules/{rule_path}`*")
            lines.append("")
    
    # Stack-Specific Rules
    stack_rules = organized_rules.get('stacks', [])
    if stack_rules:
        lines.extend([
            "## Stack-Specific Rules",
            "",
            "These rules apply when using specific technology stacks:",
            "",
        ])
        
        for rule_path, frontmatter, body in stack_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            globs = frontmatter.get('globs', [])
            
            lines.append(f"### {rule_name}")
            if globs:
                lines.append(f"*Applies to: {', '.join(globs[:3])}{'...' if len(globs) > 3 else ''}*")
            lines.append("")
            
            key_content = extract_key_content(body, max_lines=60)
            lines.append(key_content)
            lines.append("")
            lines.append(f"*Source: `.cursor/rules/{rule_path}`*")
            lines.append("")
    
    # Framework-Specific Rules
    framework_rules = organized_rules.get('frameworks', [])
    if framework_rules:
        lines.extend([
            "## Framework-Specific Rules",
            "",
            "These rules apply when using specific frameworks or tools:",
            "",
        ])
        
        # Group by subcategory
        frameworks_by_category = {}
        for rule_path, frontmatter, body in framework_rules:
            path_parts = Path(rule_path).parts
            if len(path_parts) > 1:
                subcat = path_parts[1]  # e.g., 'database', 'testing', 'ui'
                if subcat not in frameworks_by_category:
                    frameworks_by_category[subcat] = []
                frameworks_by_category[subcat].append((rule_path, frontmatter, body))
            else:
                if 'other' not in frameworks_by_category:
                    frameworks_by_category['other'] = []
                frameworks_by_category['other'].append((rule_path, frontmatter, body))
        
        for subcat, rules in sorted(frameworks_by_category.items()):
            lines.append(f"### {subcat.title()}")
            lines.append("")
            
            for rule_path, frontmatter, body in rules:
                rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
                lines.append(f"#### {rule_name}")
                lines.append("")
                
                key_content = extract_key_content(body, max_lines=50)
                lines.append(key_content)
                lines.append("")
                lines.append(f"*Source: `.cursor/rules/{rule_path}`*")
                lines.append("")
    
    # Cross-Cutting Topics
    topic_rules = organized_rules.get('topics', [])
    if topic_rules:
        lines.extend([
            "## Cross-Cutting Topics",
            "",
            "These topics apply across different parts of the codebase:",
            "",
        ])
        
        # Group by subcategory
        topics_by_category = {}
        for rule_path, frontmatter, body in topic_rules:
            path_parts = Path(rule_path).parts
            if len(path_parts) > 1:
                subcat = path_parts[1]  # e.g., 'quality', 'security', 'api'
                if subcat not in topics_by_category:
                    topics_by_category[subcat] = []
                topics_by_category[subcat].append((rule_path, frontmatter, body))
            else:
                if 'other' not in topics_by_category:
                    topics_by_category['other'] = []
                topics_by_category['other'].append((rule_path, frontmatter, body))
        
        for subcat, rules in sorted(topics_by_category.items()):
            lines.append(f"### {subcat.title()}")
            lines.append("")
            
            for rule_path, frontmatter, body in rules:
                rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
                always_apply = frontmatter.get('alwaysApply', False)
                
                if always_apply:
                    lines.append(f"#### {rule_name}")
                    lines.append("")
                    key_content = extract_key_content(body, max_lines=60)
                    lines.append(key_content)
                    lines.append("")
                else:
                    # Brief summary for conditional topics
                    lines.append(f"- **{rule_name}**: See `.cursor/rules/{rule_path}` for details")
                    lines.append("")
                
                lines.append(f"*Source: `.cursor/rules/{rule_path}`*")
                lines.append("")
    
    # Packages (brief mention)
    package_rules = organized_rules.get('packages', [])
    if package_rules:
        lines.extend([
            "## Package Management",
            "",
            "Package management and reuse guidelines:",
            "",
        ])
        
        for rule_path, frontmatter, body in package_rules:
            rule_name = frontmatter.get('description', Path(rule_path).stem.replace('-', ' ').title())
            lines.append(f"- **{rule_name}**: See `.cursor/rules/{rule_path}`")
            lines.append("")
    
    # References section
    lines.extend([
        "## References",
        "",
        "For the complete set of rules and detailed information, refer to the source rule files:",
        "",
        "- `.cursor/rules/general/` - Core development principles",
        "- `.cursor/rules/languages/` - Language-specific conventions",
        "- `.cursor/rules/stacks/` - Technology stack patterns",
        "- `.cursor/rules/frameworks/` - Framework-specific guidelines",
        "- `.cursor/rules/topics/` - Cross-cutting concerns",
        "- `.cursor/rules/packages/` - Package management rules",
        "",
        "## Customization",
        "",
        "This file can be extended with project-specific rules. When adding project-specific",
        "instructions:",
        "",
        "1. Keep them at the top or in a dedicated \"Project-Specific\" section",
        "2. Reference relevant global rules where applicable",
        "3. Avoid duplicating content from global rules",
        "4. Update this file when project standards evolve",
        "",
        "## Regenerating This File",
        "",
        "This file is generated from `.cursor/rules/` using the script:",
        "",
        "```bash",
        "python3 scripts/generate-agent-files.py",
        "```",
        "",
        "To regenerate after rule updates, run the script from the repository root.",
        "",
    ])
    
    return '\n'.join(lines)


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

