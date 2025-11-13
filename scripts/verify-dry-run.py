#!/usr/bin/env python3
"""Verify dry-run doesn't remove files marked as Keep."""
import re
from pathlib import Path

# Read audit report to get files marked as 'Keep'
audit = Path('plans/cursor/project-rules-audit.md').read_text()

# Extract files from 'Keep' sections
keep_files = []
current_project = None
in_keep_section = False

for line in audit.split('\n'):
    if line.startswith('## '):
        current_project = line.replace('## ', '').strip()
        in_keep_section = False
    elif line.startswith('### Keep'):
        in_keep_section = True
    elif line.startswith('### Can Remove') or line.startswith('### Review'):
        in_keep_section = False
    elif in_keep_section and line.strip().startswith('- `'):
        file_part = line.split('`')[1]
        if current_project:
            project_path = '/Users/mattbernier/projects/' + current_project.replace('.cursor', '.cursor/rules')
            full_path = Path(project_path) / file_part
            keep_files.append(str(full_path))

# Read dry-run output
output = Path('/tmp/dry-run-output.txt').read_text()
would_remove = re.findall(r'✓ Would remove: (.+)', output)

# Check for conflicts
keep_set = set(keep_files)
remove_set = set(would_remove)
conflicts = keep_set & remove_set

print(f'Files marked as KEEP in audit: {len(keep_files)}')
print(f'Files that WOULD BE REMOVED: {len(would_remove)}')
print(f'Conflicts (keep files that would be removed): {len(conflicts)}')

if conflicts:
    print('\n⚠️  CONFLICT DETECTED - Files marked as KEEP but would be removed:')
    for conflict in list(conflicts)[:10]:
        print(f'  {conflict}')
else:
    print('\n✓ No conflicts - all files marked as KEEP are safe')

