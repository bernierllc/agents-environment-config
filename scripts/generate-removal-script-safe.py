#!/usr/bin/env python3
"""Generate a safer removal script with validation checks."""

import os
from pathlib import Path
import re

# Read the audit report
audit_file = Path('plans/cursor/project-rules-audit.md')
if not audit_file.exists():
    print("Audit file not found. Run audit script first.")
    exit(1)

content = audit_file.read_text()

# Extract files to remove
files_to_remove = []
current_project = None
in_remove_section = False
in_keep_section = False
in_review_section = False

for line in content.split('\n'):
    line_stripped = line.strip()
    
    if line.startswith('## '):
        current_project = line.replace('## ', '').strip()
        in_remove_section = False
        in_keep_section = False
        in_review_section = False
    elif line.startswith('### Can Remove'):
        in_remove_section = True
        in_keep_section = False
        in_review_section = False
    elif line.startswith('### Keep'):
        in_remove_section = False
        in_keep_section = True
        in_review_section = False
    elif line.startswith('### Review'):
        in_remove_section = False
        in_keep_section = False
        in_review_section = True
    elif in_remove_section and line_stripped.startswith('- `'):
        # Extract file path
        file_part = line.split('`')[1]
        if current_project:
            # Reconstruct full path
            project_path = '/Users/mattbernier/projects/' + current_project.replace('.cursor', '.cursor/rules')
            full_path = os.path.join(project_path, file_part)
            files_to_remove.append(full_path)

# Safety checks
safe_files = []
unsafe_files = []

for file_path in files_to_remove:
    p = Path(file_path)
    
    # Check 1: Must be in .cursor/rules directory
    if '.cursor/rules' not in str(p):
        unsafe_files.append((file_path, 'Not in .cursor/rules directory'))
        continue
    
    # Check 2: Must NOT be in agents-environment-config (global repo)
    if 'agents-environment-config' in str(p):
        unsafe_files.append((file_path, 'In global rules repository'))
        continue
    
    # Check 3: Must be under /Users/mattbernier/projects
    if not str(p).startswith('/Users/mattbernier/projects'):
        unsafe_files.append((file_path, 'Outside projects directory'))
        continue
    
    # Check 4: Must be a .mdc file
    if not p.name.endswith('.mdc'):
        unsafe_files.append((file_path, 'Not a .mdc file'))
        continue
    
    # Check 5: File must exist
    if not p.exists():
        unsafe_files.append((file_path, 'File does not exist'))
        continue
    
    # Check 6: Must be a file, not directory
    if not p.is_file():
        unsafe_files.append((file_path, 'Is a directory, not a file'))
        continue
    
    safe_files.append(file_path)

# Report unsafe files
if unsafe_files:
    print("WARNING: Found unsafe files that will be skipped:")
    for file_path, reason in unsafe_files:
        print(f"  {file_path}: {reason}")
    print()

# Generate removal script with safety checks
script_lines = ['#!/bin/bash', '# Files to remove - covered by global rules', '# Generated with safety checks', '']
script_lines.append('# Note: set -e and set -u disabled to allow flexibility')
script_lines.append('')
script_lines.append('# Check for dry-run flag')
script_lines.append('DRY_RUN=false')
script_lines.append('if [[ "${1:-}" == "--dry-run" ]] || [[ "${1:-}" == "-n" ]]; then')
script_lines.append('  DRY_RUN=true')
script_lines.append('  echo "DRY RUN MODE - No files will be removed"')
script_lines.append('  echo "========================================"')
script_lines.append('fi')
script_lines.append('')
script_lines.append('if [ "$DRY_RUN" = false ]; then')
script_lines.append('  echo "Removing project-specific rule files covered by global rules..."')
script_lines.append('else')
script_lines.append('  echo "Dry run: Would remove project-specific rule files covered by global rules..."')
script_lines.append('fi')
script_lines.append('echo "Safety checks enabled - only removing files in .cursor/rules directories"')
script_lines.append('')
script_lines.append('removed_count=0')
script_lines.append('skipped_count=0')
script_lines.append('')

removed_count = 0
skipped_count = 0

for file_path in safe_files:
    script_lines.append(f'# Removing: {file_path}')
    script_lines.append(f'if [ -f "{file_path}" ] && [[ "{file_path}" == *".cursor/rules"* ]] && [[ "{file_path}" != *"agents-environment-config"* ]]; then')
    script_lines.append(f'  if [ "$DRY_RUN" = true ]; then')
    script_lines.append(f'    echo "✓ Would remove: {file_path}"')
    script_lines.append(f'  else')
    script_lines.append(f'    rm "{file_path}"')
    script_lines.append(f'    echo "✓ Removed: {file_path}"')
    script_lines.append(f'  fi')
    script_lines.append(f'  ((removed_count++))')
    script_lines.append('else')
    script_lines.append(f'  echo "✗ Skipped (safety check failed): {file_path}"')
    script_lines.append(f'  ((skipped_count++))')
    script_lines.append('fi')
    script_lines.append('')

script_lines.append('echo ""')
script_lines.append('if [ "$DRY_RUN" = true ]; then')
script_lines.append('  echo "Dry run complete!"')
script_lines.append('  echo "Would remove: $removed_count files"')
script_lines.append('else')
script_lines.append('  echo "Done!"')
script_lines.append('  echo "Removed: $removed_count files"')
script_lines.append('fi')
script_lines.append('echo "Skipped: $skipped_count files"')

script_content = '\n'.join(script_lines)
script_path = Path('scripts/remove-duplicate-rules.sh')
script_path.write_text(script_content)
script_path.chmod(0o755)

print(f"Generated removal script: {script_path}")
print(f"Safe files to remove: {len(safe_files)}")
if unsafe_files:
    print(f"Unsafe files skipped: {len(unsafe_files)}")
print(f"\nReview the script before running:")
print(f"  cat {script_path}")
print(f"\nTo test (dry run):")
print(f"  bash {script_path} --dry-run")
print(f"\nTo execute:")
print(f"  bash {script_path}")

