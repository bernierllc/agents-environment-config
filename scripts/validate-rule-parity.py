#!/usr/bin/env python3
"""
Validate parity between .cursor/rules/*.mdc and .agent-rules/*.md files.

This script ensures that every .mdc file in .cursor/rules/ has a corresponding
.md file in .agent-rules/ with matching content (minus frontmatter).

Used as a pre-commit hook to prevent content drift between the two directories.
"""

import sys
from pathlib import Path
from typing import List, Tuple


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
    """Convert .cursor/rules/*.mdc path to .agent-rules/*.md path."""
    relative = mdc_path.relative_to(cursor_rules_dir)
    md_relative = relative.with_suffix('.md')
    return agent_rules_dir / md_relative


def validate_rule_parity(repo_root: Path) -> Tuple[List[str], List[str]]:
    """Validate parity between .cursor/rules/ and .agent-rules/.

    Args:
        repo_root: Repository root directory

    Returns:
        Tuple of (missing_files, content_mismatches)
    """
    cursor_rules_dir = repo_root / '.cursor' / 'rules'
    agent_rules_dir = repo_root / '.agent-rules'

    if not cursor_rules_dir.exists():
        return [f".cursor/rules/ directory not found"], []

    if not agent_rules_dir.exists():
        return [".agent-rules/ directory not found - run: python3 scripts/generate-agent-rules.py"], []

    missing_files = []
    content_mismatches = []

    # Find all .mdc files (excluding README.mdc)
    mdc_files = [
        f for f in cursor_rules_dir.rglob('*.mdc')
        if f.name != 'README.mdc'
    ]

    for mdc_path in sorted(mdc_files):
        md_path = mdc_to_md_path(mdc_path, cursor_rules_dir, agent_rules_dir)
        relative_mdc = mdc_path.relative_to(repo_root)
        relative_md = md_path.relative_to(repo_root)

        # Check if .md file exists
        if not md_path.exists():
            missing_files.append(f"Missing: {relative_md} (source: {relative_mdc})")
            continue

        # Compare content (strip frontmatter from .mdc)
        try:
            mdc_content = mdc_path.read_text(encoding='utf-8')
            md_content = md_path.read_text(encoding='utf-8')

            mdc_body = strip_frontmatter(mdc_content)

            if mdc_body.strip() != md_content.strip():
                content_mismatches.append(
                    f"Content mismatch: {relative_mdc} vs {relative_md}"
                )
        except Exception as e:
            content_mismatches.append(f"Error reading {relative_mdc} or {relative_md}: {e}")

    return missing_files, content_mismatches


def main() -> int:
    """Main entry point for pre-commit validation."""
    # Determine repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    missing, mismatches = validate_rule_parity(repo_root)

    if not missing and not mismatches:
        print("✓ Rule parity check passed - .agent-rules/ matches .cursor/rules/")
        return 0

    print("✗ Rule parity check FAILED\n")

    if missing:
        print("Missing files in .agent-rules/:")
        for msg in missing:
            print(f"  - {msg}")
        print()

    if mismatches:
        print("Content mismatches:")
        for msg in mismatches:
            print(f"  - {msg}")
        print()

    print("To fix: run 'python3 scripts/generate-agent-rules.py'")
    return 1


if __name__ == '__main__':
    sys.exit(main())
