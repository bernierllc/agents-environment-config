#!/usr/bin/env python3
"""
Generate .agent-rules/ directory from .cursor/rules/

Creates a parallel directory structure with .md files (no Cursor frontmatter)
from the .cursor/rules/*.mdc files. This allows non-Cursor agents to use
the rules without being polluted by Cursor-specific metadata.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from markdown content.

    Args:
        content: File content that may have YAML frontmatter

    Returns:
        Content without frontmatter (body only)
    """
    if not content.startswith('---'):
        return content

    # Find the closing ---
    parts = content.split('---', 2)
    if len(parts) < 3:
        return content

    # Return everything after the second ---
    body = parts[2].strip()
    return body


def mdc_to_md_path(mdc_path: Path, cursor_rules_dir: Path, agent_rules_dir: Path) -> Path:
    """Convert .cursor/rules/*.mdc path to .agent-rules/*.md path.

    Args:
        mdc_path: Path to the .mdc file
        cursor_rules_dir: Path to .cursor/rules/ directory
        agent_rules_dir: Path to .agent-rules/ directory

    Returns:
        Corresponding .md path in .agent-rules/
    """
    # Get relative path from .cursor/rules/
    relative = mdc_path.relative_to(cursor_rules_dir)

    # Change extension from .mdc to .md
    md_relative = relative.with_suffix('.md')

    # Return full path in .agent-rules/
    return agent_rules_dir / md_relative


def process_rule_file(mdc_path: Path, md_path: Path) -> Tuple[bool, Optional[str]]:
    """Process a single rule file, stripping frontmatter.

    Args:
        mdc_path: Source .mdc file
        md_path: Target .md file

    Returns:
        Tuple of (success, error_message)
    """
    try:
        content = mdc_path.read_text(encoding='utf-8')
        body = strip_frontmatter(content)

        # Ensure parent directory exists
        md_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the stripped content
        md_path.write_text(body, encoding='utf-8')

        return True, None
    except Exception as e:
        return False, str(e)


def generate_agent_rules(repo_root: Path, verbose: bool = True) -> int:
    """Generate .agent-rules/ directory from .cursor/rules/.

    Args:
        repo_root: Repository root directory
        verbose: Print progress messages

    Returns:
        0 on success, 1 on error
    """
    cursor_rules_dir = repo_root / '.cursor' / 'rules'
    agent_rules_dir = repo_root / '.agent-rules'

    if not cursor_rules_dir.exists():
        print(f"Error: .cursor/rules/ directory not found at {cursor_rules_dir}")
        return 1

    # Find all .mdc files (excluding README.mdc files)
    mdc_files = [
        f for f in cursor_rules_dir.rglob('*.mdc')
        if f.name != 'README.mdc'
    ]

    if verbose:
        print(f"Found {len(mdc_files)} rule files in .cursor/rules/")

    # Process each file
    errors = []
    created = 0

    for mdc_path in sorted(mdc_files):
        md_path = mdc_to_md_path(mdc_path, cursor_rules_dir, agent_rules_dir)

        success, error = process_rule_file(mdc_path, md_path)

        if success:
            created += 1
            if verbose:
                relative_md = md_path.relative_to(repo_root)
                print(f"  ✓ {relative_md}")
        else:
            relative_mdc = mdc_path.relative_to(repo_root)
            errors.append(f"{relative_mdc}: {error}")
            if verbose:
                print(f"  ✗ {relative_mdc}: {error}")

    if verbose:
        print(f"\nGenerated {created} files in .agent-rules/")

    if errors:
        print(f"\n{len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1

    return 0


def main() -> int:
    """Main entry point."""
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    print(f"Generating .agent-rules/ from .cursor/rules/...\n")

    return generate_agent_rules(repo_root)


if __name__ == '__main__':
    sys.exit(main())
