#!/usr/bin/env python3
"""Audit project .cursor/rules directories and identify files that can be removed."""

import os
import json
from pathlib import Path
from collections import defaultdict

# Global rules mapping - files that exist in global rules
GLOBAL_RULES = {
    # General
    'architecture': 'general/architecture.mdc',
    'development-workflow': 'general/development-workflow.mdc',
    'documentation': 'general/documentation.mdc',
    'security': 'general/security.mdc',
    'port-management': 'general/port-management.mdc',
    'project-setup-cli': 'general/project-setup-cli.mdc',
    'plans-checklists': 'general/plans-checklists.mdc',
    'plans-and-checklists': 'general/plans-checklists.mdc',
    'rules-about-rules': 'general/rules-about-rules.mdc',
    'cursor-rules': 'general/rules-about-rules.mdc',
    'rules': 'general/rules-about-rules.mdc',
    
    # Languages
    'typescript-typing': 'languages/typescript/typing-standards.mdc',
    'typescript': 'languages/typescript/typing-standards.mdc',
    'strict-typing': 'languages/typescript/typing-standards.mdc',
    'linting-type-safety': 'languages/typescript/typing-standards.mdc',
    'typescript-strict': 'languages/typescript/typing-standards.mdc',
    'python-style': 'languages/python/style.mdc',
    'python': 'languages/python/style.mdc',
    'flake8-formatting': 'languages/python/style.mdc',
    'python-server-apis': 'stacks/python-backend/fastapi.mdc',
    
    # Stacks
    'nextjs': 'stacks/nextjs/app-router.mdc',
    'nextjs-react': 'stacks/nextjs/app-router.mdc',
    'react-native': 'stacks/react-native/expo-development.mdc',
    'fastapi': 'stacks/python-backend/fastapi.mdc',
    
    # Frameworks - Database
    'supabase': 'frameworks/database/supabase.mdc',
    'sqlalchemy': 'frameworks/database/sqlalchemy.mdc',
    'alembic': 'frameworks/database/alembic.mdc',
    'database': 'frameworks/database/prisma.mdc',  # May be Prisma or Supabase
    
    # Frameworks - UI
    'styling': 'frameworks/ui/tailwind-css.mdc',
    'tailwind': 'frameworks/ui/tailwind-css.mdc',
    'tamagui': 'frameworks/ui/tamagui.mdc',
    'tamagui-debugging': 'frameworks/ui/tamagui.mdc',
    'tamagui-properties': 'frameworks/ui/tamagui.mdc',
    'ui-development': 'frameworks/ui/tamagui.mdc',
    
    # Frameworks - Testing
    'testing': 'frameworks/testing/standards.mdc',
    'testing-standards': 'frameworks/testing/standards.mdc',
    'testing-changes': 'frameworks/testing/standards.mdc',
    
    # Topics - API
    'api-standards': 'topics/api/design-standards.mdc',
    'api': 'topics/api/design-standards.mdc',
    'api-testing': 'topics/api/design-standards.mdc',
    'api-client-ui': 'topics/api/design-standards.mdc',
    'api-integration': 'topics/api/design-standards.mdc',
    'api-request-flow': 'topics/api/design-standards.mdc',
    
    # Topics - Git
    'git': 'topics/git/workflow.mdc',
    'git-workflow': 'topics/git/workflow.mdc',
    'branching': 'topics/git/workflow.mdc',
    'pull-requests': 'topics/git/workflow.mdc',
    'commits': 'topics/git/workflow.mdc',
    
    # Topics - Security
    'authentication-boundaries': 'topics/security/authentication.mdc',
    'auth': 'topics/security/authentication.mdc',
    'security': 'topics/security/authentication.mdc',
    'security-vulnerabilities': 'topics/security/authentication.mdc',
    'secrets': 'topics/security/secrets.mdc',
    'security_secrets': 'topics/security/secrets.mdc',
    'rbac': 'topics/security/authentication.mdc',
    'rbac_okta': 'topics/security/authentication.mdc',
    
    # Topics - Quality
    'quality-gates': 'topics/quality/gates.mdc',
    'code-quality': 'topics/quality/gates.mdc',
    'production-ready': 'topics/quality/gates.mdc',
    'build-quality': 'topics/quality/gates.mdc',
    'errors': 'topics/quality/error-handling.mdc',
    'error-handling': 'topics/quality/error-handling.mdc',
    'logging': 'topics/quality/logging.mdc',
    'coding/quality-gates': 'topics/quality/gates.mdc',
    'coding/documentation': 'general/documentation.mdc',
    'coding/testing': 'frameworks/testing/standards.mdc',
    'coding/linting-type-safety': 'languages/typescript/typing-standards.mdc',
    
    # Topics - Other
    'accessibility': 'topics/accessibility/standards.mdc',
    'accessibility-admin': 'topics/accessibility/standards.mdc',
    'deployment': 'topics/deployment/environments.mdc',
    'environment': 'topics/deployment/environments.mdc',
    'monitoring': 'topics/observability/monitoring.mdc',
    'observability': 'topics/observability/monitoring.mdc',
    'debugging': 'topics/troubleshooting/debugging.mdc',
    
    # Packages
    'package-management': 'packages/package-management.mdc',
    'package-reuse': 'packages/package-reuse.mdc',
    'npm-publish': 'packages/package-management.mdc',
    'publishing': 'packages/package-management.mdc',
    'bernierllc-packages': 'packages/package-management.mdc',
}

# Project-specific patterns that should stay
PROJECT_SPECIFIC_KEYWORDS = [
    'project-guardrails',
    'project-structure',
    'vibe-kanban',
    'workspace-commands',
    'route-constants',
    'route-naming-convention',
    'avoid-barrel-files',
    'browser-server-management',
    'email_templates',
    'forms',
    'sycophancy',
    'agent-guidelines',
    'ai-agent-operations',
    'cursor-execution-rules',
    'privacy-hipaa',
    'clarifying-questions',
    'docs-updates',
    'github-rule',
    'ideas',
    'development',
    'npm-run',
    'browser',
    'docs',
    'general',
    'workflow',
    'plans',
    'global',
    'principles',
    'core',
    'shared',
    'atomic-package-identification',
    'partial-package-matches',
    'min-requirements',
    'version-management',
    'licensing',
    'readme',
    'index',
    'scripts',
    'util',
    'service',
    'suite',
    'separation-of-concerns',
    'markdown-rules',
    'coding',
]

def normalize_filename(filename):
    """Normalize filename for comparison."""
    return filename.replace('.mdc', '').lower().replace('_', '-').replace(' ', '-')


def check_global_match(filename):
    """Check if filename matches a global rule."""
    normalized = normalize_filename(filename)
    
    # Check exact matches first
    if normalized in GLOBAL_RULES:
        return GLOBAL_RULES[normalized]
    
    # Check partial matches
    for key, global_path in GLOBAL_RULES.items():
        if key in normalized or normalized in key:
            return global_path
    
    return None


def is_project_specific(filename):
    """Check if filename suggests project-specific content."""
    normalized = normalize_filename(filename)
    
    # Check if it matches a global rule first (don't mark as project-specific if it's a duplicate)
    if check_global_match(filename):
        return False
    
    for keyword in PROJECT_SPECIFIC_KEYWORDS:
        if keyword in normalized or normalized in keyword:
            return True
    
    return False


def audit_project_rules():
    """Audit all project .cursor/rules directories."""
    projects_dir = Path('/Users/mattbernier/projects')
    results = defaultdict(lambda: {
        'can_remove': [],
        'review_needed': [],
        'keep_project_specific': [],
        'total_files': 0
    })
    
    for rules_dir in projects_dir.rglob('.cursor/rules'):
        # Skip agents-environment-config itself
        if 'agents-environment-config' in str(rules_dir):
            continue
        
        # Skip .git directories
        if '.git' in str(rules_dir):
            continue
        
        project_name = str(rules_dir.relative_to(projects_dir).parent)
        
        # Handle both root and subdirectories
        for rule_file in rules_dir.rglob('*.mdc'):
            results[project_name]['total_files'] += 1
            # Get relative path from rules directory
            rel_path = rule_file.relative_to(rules_dir)
            filename = rule_file.name
            # Use relative path if in subdirectory
            if rel_path.parent != Path('.'):
                filename = str(rel_path)
            
            # Check if it's project-specific
            if is_project_specific(filename):
                results[project_name]['keep_project_specific'].append({
                    'file': filename,
                    'path': str(rule_file),
                    'reason': 'Project-specific pattern'
                })
                continue
            
            # Check if it matches a global rule
            global_match = check_global_match(filename)
            if global_match:
                results[project_name]['can_remove'].append({
                    'file': filename,
                    'path': str(rule_file),
                    'global_rule': global_match,
                    'reason': f'Covered by global rule: {global_match}'
                })
            else:
                results[project_name]['review_needed'].append({
                    'file': filename,
                    'path': str(rule_file),
                    'reason': 'No clear match - needs manual review'
                })
    
    return results


def generate_report(results):
    """Generate markdown report."""
    report = []
    report.append("# Project Rules Audit Report\n")
    report.append("This report identifies which project-specific rule files can be removed because they're covered by global rules.\n")
    
    total_files = sum(r['total_files'] for r in results.values())
    total_can_remove = sum(len(r['can_remove']) for r in results.values())
    total_keep = sum(len(r['keep_project_specific']) for r in results.values())
    total_review = sum(len(r['review_needed']) for r in results.values())
    
    report.append("## Summary\n")
    report.append(f"- **Total projects audited**: {len(results)}\n")
    report.append(f"- **Total rule files**: {total_files}\n")
    report.append(f"- **Can remove (covered by global)**: {total_can_remove}\n")
    report.append(f"- **Keep (project-specific)**: {total_keep}\n")
    report.append(f"- **Review needed**: {total_review}\n\n")
    
    report.append("## Recommendations\n\n")
    report.append("1. **Remove files** marked as 'Can Remove' - they're covered by global rules\n")
    report.append("2. **Keep files** marked as 'Project-Specific' - they contain unique project patterns\n")
    report.append("3. **Review files** marked as 'Review Needed' - manually check if they're duplicates\n\n")
    
    # Sort projects alphabetically
    for project_name in sorted(results.keys()):
        data = results[project_name]
        
        if data['total_files'] == 0:
            continue
        
        report.append(f"## {project_name}\n")
        report.append(f"**Total files**: {data['total_files']}\n\n")
        
        if data['can_remove']:
            report.append("### Can Remove (Covered by Global Rules)\n")
            for item in data['can_remove']:
                report.append(f"- `{item['file']}` → {item['global_rule']}\n")
            report.append("\n")
        
        if data['keep_project_specific']:
            report.append("### Keep (Project-Specific)\n")
            for item in data['keep_project_specific']:
                report.append(f"- `{item['file']}` - {item['reason']}\n")
            report.append("\n")
        
        if data['review_needed']:
            report.append("### Review Needed\n")
            for item in data['review_needed']:
                report.append(f"- `{item['file']}` - {item['reason']}\n")
            report.append("\n")
        
        report.append("---\n\n")
    
    return '\n'.join(report)


if __name__ == '__main__':
    print("Auditing project rules...")
    results = audit_project_rules()
    
    report = generate_report(results)
    
    report_path = Path('plans/cursor/project-rules-audit.md')
    report_path.write_text(report)
    
    print(f"Report generated: {report_path}")
    print(f"\nSummary:")
    print(f"  Projects: {len(results)}")
    print(f"  Total files: {sum(r['total_files'] for r in results.values())}")
    print(f"  Can remove: {sum(len(r['can_remove']) for r in results.values())}")
    print(f"  Keep: {sum(len(r['keep_project_specific']) for r in results.values())}")
    print(f"  Review: {sum(len(r['review_needed']) for r in results.values())}")

