#!/usr/bin/env python3
"""Generate removal commands for files that can be removed."""

import os
from pathlib import Path

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

for line in content.split('\n'):
    if line.startswith('## '):
        current_project = line.replace('## ', '').strip()
        in_remove_section = False
    elif line.startswith('### Can Remove'):
        in_remove_section = True
    elif line.startswith('### Keep') or line.startswith('### Review'):
        in_remove_section = False
    elif in_remove_section and line.strip().startswith('- `'):
        # Extract file path
        file_part = line.split('`')[1]
        if current_project:
            # Reconstruct full path
            project_path = '/Users/mattbernier/projects/' + current_project.replace('.cursor', '.cursor/rules')
            full_path = os.path.join(project_path, file_part)
            files_to_remove.append(full_path)

# Generate removal script
script_lines = ['#!/bin/bash', '# Files to remove - covered by global rules', '']
script_lines.append('echo "Removing project-specific rule files covered by global rules..."')
script_lines.append('')

for file_path in files_to_remove:
    if os.path.exists(file_path):
        script_lines.append(f'rm "{file_path}"')
        script_lines.append(f'echo "Removed: {file_path}"')

script_lines.append('')
script_lines.append('echo "Done!"')

script_content = '\n'.join(script_lines)
script_path = Path('scripts/remove-duplicate-rules.sh')
script_path.write_text(script_content)
script_path.chmod(0o755)

print(f"Generated removal script: {script_path}")
print(f"Total files to remove: {len(files_to_remove)}")
print(f"\nReview the script before running:")
print(f"  cat {script_path}")
print(f"\nTo execute:")
print(f"  bash {script_path}")

