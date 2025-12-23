#!/usr/bin/env python3
"""
Automated sync system for agents and skills between submodule repos and cursor commands.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil
import re

# Configuration
REPO_ROOT = Path(__file__).parent.parent
CONFIG_FILE = REPO_ROOT / "scripts" / "sync-config.json"
CLAUDE_AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
CLAUDE_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
CURSOR_AGENTS_DIR = REPO_ROOT / ".cursor" / "commands" / "agents"
CURSOR_SKILLS_DIR = REPO_ROOT / ".cursor" / "commands" / "skills"


def check_skip_flag() -> bool:
    """Check if sync should be skipped via SKIP_SYNC environment variable."""
    return os.environ.get("SKIP_SYNC", "").lower() in ("1", "true", "yes")


def validate_submodules() -> Tuple[bool, str]:
    """
    Validate that submodules are initialized and on correct branch.
    Returns: (is_valid, error_message)
    """
    try:
        # Check if submodule directories exist
        if not CLAUDE_AGENTS_DIR.exists():
            return False, "Submodule not initialized: run 'git submodule update --init --recursive'"
        
        if not CLAUDE_SKILLS_DIR.exists():
            return False, "Submodule not initialized: run 'git submodule update --init --recursive'"
        
        # Check if agents submodule is on detached HEAD
        result = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            cwd=CLAUDE_AGENTS_DIR,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, "Agents submodule on detached HEAD: checkout a branch first"
        
        # Check if skills submodule is on detached HEAD
        result = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            cwd=CLAUDE_SKILLS_DIR,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, "Skills submodule on detached HEAD: checkout a branch first"
        
        return True, ""
    except Exception as e:
        return False, f"Error validating submodules: {str(e)}"


def validate_github_cli() -> Tuple[bool, str]:
    """
    Check if GitHub CLI is installed and authenticated.
    Returns: (is_valid, error_message)
    """
    try:
        # Check if gh is installed
        result = subprocess.run(
            ["which", "gh"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, "GitHub CLI not installed: install from https://cli.github.com/"
        
        # Check if authenticated
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return False, "GitHub CLI not authenticated: run 'gh auth login'"
        
        return True, ""
    except Exception as e:
        return False, f"Error checking GitHub CLI: {str(e)}"


def load_config() -> Dict:
    """Load configuration from sync-config.json."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Config file not found at {CONFIG_FILE}, using defaults")
        return {
            "submodules": {
                "agents": {
                    "path": ".claude/agents",
                    "repo": "bernierllc/agency-agents",
                    "cursor_target": ".cursor/commands/agents"
                },
                "skills": {
                    "path": ".claude/skills",
                    "repo": "bernierllc/skills",
                    "cursor_target": ".cursor/commands/skills",
                    "skill_file_pattern": ["Skill.md", "SKILL.md"]
                }
            },
            "pr_settings": {
                "base_branch": "main",
                "title_template": "Sync {type}: {filename}",
                "body_template": "Automated sync from agents-environment-config"
            }
        }


def map_agent_path(source_path: Path) -> Path:
    """
    Convert .claude/agents path to .cursor/commands/agents path.
    """
    relative_path = source_path.relative_to(CLAUDE_AGENTS_DIR)
    return CURSOR_AGENTS_DIR / relative_path


def map_skill_path(source_path: Path) -> Path:
    """
    Convert .claude/skills/dir/SKILL.md to .cursor/commands/skills/dir.md.
    Parent directory name becomes the filename.
    """
    # Get parent directory of SKILL.md
    skill_dir = source_path.parent
    # Get relative path from skills dir
    relative_path = skill_dir.relative_to(CLAUDE_SKILLS_DIR)
    # Create target path with directory name as filename
    return CURSOR_SKILLS_DIR / f"{relative_path}.md"


def parse_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """
    Parse frontmatter from markdown content.
    Returns: (frontmatter_dict, content_without_frontmatter)
    """
    if not content.startswith("---"):
        return None, content
    
    try:
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None, content
        
        # Parse YAML-like frontmatter (simple key: value pairs)
        frontmatter = {}
        for line in parts[1].strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")
        
        return frontmatter, parts[2]
    except Exception as e:
        print(f"Warning: Could not parse frontmatter: {e}")
        return None, content


def generate_frontmatter(name: str, description: str = "", tags: List[str] = None) -> str:
    """Generate frontmatter for cursor command file."""
    if tags is None:
        tags = []
    
    frontmatter = f"""---
name: "{name}"
description: "{description}"
tags: {json.dumps(tags)}
---

"""
    return frontmatter


def generate_cursor_command(source_path: Path, target_path: Path, content_type: str = "agent"):
    """
    Create or update cursor command file with frontmatter and source content.
    Preserves existing frontmatter if it exists, creates default if not.
    Extracts content from source file (removing its frontmatter if present).
    """
    try:
        # Read source content
        with open(source_path, 'r', encoding='utf-8') as f:
            source_content = f.read()
        
        # Extract content from source (remove source frontmatter if present)
        _, source_content_only = parse_frontmatter(source_content)
        
        # Check if target exists and has frontmatter to preserve
        existing_frontmatter = None
        if target_path.exists():
            with open(target_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
                existing_frontmatter, _ = parse_frontmatter(existing_content)
        
        # Generate new content
        if existing_frontmatter:
            # Preserve existing frontmatter
            frontmatter_lines = ["---"]
            for key, value in existing_frontmatter.items():
                if isinstance(value, list):
                    frontmatter_lines.append(f'{key}: {json.dumps(value)}')
                else:
                    frontmatter_lines.append(f'{key}: "{value}"')
            frontmatter_lines.append("---\n")
            frontmatter = "\n".join(frontmatter_lines)
        else:
            # Create default frontmatter from source
            source_frontmatter, _ = parse_frontmatter(source_content)
            if source_frontmatter:
                # Use source frontmatter as base
                name = source_frontmatter.get("name", source_path.stem.replace("-", " ").title())
                description = source_frontmatter.get("description", f"{'Skill' if content_type == 'skill' else 'Agent'} command")
                tags = [content_type]
            else:
                # Create default
                name = source_path.stem.replace("-", " ").title()
                description = f"{'Skill' if content_type == 'skill' else 'Agent'} command"
                tags = [content_type]
            frontmatter = generate_frontmatter(name, description, tags)
        
        # Combine frontmatter with source content (without source frontmatter)
        new_content = frontmatter + "\n" + source_content_only.strip() + "\n"
        
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to target
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
    except Exception as e:
        print(f"Error generating cursor command for {source_path}: {e}")
        return False


def sync_to_cursor_commands(source_type: str = "agents") -> Tuple[int, int, int]:
    """
    Sync files from source directory to cursor commands directory.
    Returns: (files_synced, files_created, files_deleted)
    """
    files_synced = 0
    files_created = 0
    files_deleted = 0
    
    try:
        if source_type == "agents":
            source_dir = CLAUDE_AGENTS_DIR
            target_dir = CURSOR_AGENTS_DIR
            content_type = "agent"
            
            # Find all .md files in agents directory
            source_files = list(source_dir.rglob("*.md"))
            # Exclude README, CONTRIBUTING, LICENSE files
            source_files = [f for f in source_files if f.name not in ["README.md", "CONTRIBUTING.md", "LICENSE.md"]]
            
            # Sync each file
            for source_file in source_files:
                target_file = map_agent_path(source_file)
                
                # Check if we need to update
                needs_update = False
                if not target_file.exists():
                    needs_update = True
                    files_created += 1
                elif source_file.stat().st_mtime > target_file.stat().st_mtime:
                    needs_update = True
                    files_synced += 1
                
                if needs_update:
                    generate_cursor_command(source_file, target_file, content_type)
            
            # Check for deleted files
            if target_dir.exists():
                for target_file in target_dir.rglob("*.md"):
                    source_file = CLAUDE_AGENTS_DIR / target_file.relative_to(target_dir)
                    if not source_file.exists():
                        target_file.unlink()
                        files_deleted += 1
        
        elif source_type == "skills":
            source_dir = CLAUDE_SKILLS_DIR
            target_dir = CURSOR_SKILLS_DIR
            content_type = "skill"
            
            # Find all SKILL.md and Skill.md files
            source_files = []
            for pattern in ["SKILL.md", "Skill.md"]:
                source_files.extend(source_dir.rglob(pattern))
            
            # Sync each file
            for source_file in source_files:
                target_file = map_skill_path(source_file)
                
                # Check if we need to update
                needs_update = False
                if not target_file.exists():
                    needs_update = True
                    files_created += 1
                elif source_file.stat().st_mtime > target_file.stat().st_mtime:
                    needs_update = True
                    files_synced += 1
                
                if needs_update:
                    generate_cursor_command(source_file, target_file, content_type)
            
            # Check for deleted files
            if target_dir.exists():
                for target_file in target_dir.rglob("*.md"):
                    # Reconstruct potential source paths
                    skill_name = target_file.stem
                    relative_path = target_file.relative_to(target_dir).parent
                    potential_source_dir = source_dir / relative_path / skill_name
                    
                    source_exists = False
                    for pattern in ["SKILL.md", "Skill.md"]:
                        if (potential_source_dir / pattern).exists():
                            source_exists = True
                            break
                    
                    if not source_exists:
                        target_file.unlink()
                        files_deleted += 1
        
        return files_synced, files_created, files_deleted
    except Exception as e:
        print(f"Error syncing {source_type}: {e}")
        return files_synced, files_created, files_deleted


def detect_changes(submodule_path: Path) -> List[str]:
    """
    Detect changed files in submodule using git.
    Returns list of changed file paths.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=submodule_path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []
    except Exception as e:
        print(f"Error detecting changes in {submodule_path}: {e}")
        return []


def sync_to_submodule_repo(submodule_path: Path, repo_name: str, changed_files: List[str], config: Dict) -> bool:
    """
    Push changes to submodule repo as PR via GitHub CLI.
    Returns: success status
    """
    try:
        # Validate GitHub CLI
        is_valid, error_msg = validate_github_cli()
        if not is_valid:
            print(f"Warning: {error_msg} - Skipping PR creation")
            return False
        
        pr_settings = config.get("pr_settings", {})
        base_branch = pr_settings.get("base_branch", "main")
        
        # Create branch name
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"sync-{timestamp}"
        
        # Create and checkout new branch
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=submodule_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error creating branch: {result.stderr}")
            return False
        
        # Stage changes
        for file in changed_files:
            subprocess.run(
                ["git", "add", file],
                cwd=submodule_path,
                capture_output=True
            )
        
        # Commit changes
        commit_msg = f"Sync changes from agents-environment-config"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=submodule_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"No changes to commit or error: {result.stderr}")
            # Checkout back to original branch
            subprocess.run(["git", "checkout", "-"], cwd=submodule_path)
            return False
        
        # Push branch
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=submodule_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error pushing branch: {result.stderr}")
            subprocess.run(["git", "checkout", "-"], cwd=submodule_path)
            return False
        
        # Create PR
        pr_title = f"Sync changes from agents-environment-config"
        pr_body = pr_settings.get("body_template", "Automated sync")
        
        result = subprocess.run(
            ["gh", "pr", "create", "--title", pr_title, "--body", pr_body, "--base", base_branch],
            cwd=submodule_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error creating PR: {result.stderr}")
            subprocess.run(["git", "checkout", "-"], cwd=submodule_path)
            return False
        
        print(f"✓ Created PR in {repo_name}: {result.stdout.strip()}")
        
        # Checkout back to original branch
        subprocess.run(["git", "checkout", "-"], cwd=submodule_path)
        
        return True
    except Exception as e:
        print(f"Error creating PR for {repo_name}: {e}")
        # Try to checkout back
        try:
            subprocess.run(["git", "checkout", "-"], cwd=submodule_path, capture_output=True)
        except:
            pass
        return False


def sync_from_submodule_repo(submodule_path: Path) -> bool:
    """
    Pull latest changes from submodule repo.
    Returns: success status
    """
    try:
        result = subprocess.run(
            ["git", "submodule", "update", "--remote", str(submodule_path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error updating submodule {submodule_path}: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error pulling from submodule {submodule_path}: {e}")
        return False


def main():
    """Main sync function."""
    # Check skip flag
    if check_skip_flag():
        print("SKIP_SYNC is set, skipping sync operations")
        return 0
    
    # Load config
    config = load_config()
    
    # Validate submodules
    is_valid, error_msg = validate_submodules()
    if not is_valid:
        print(f"Warning: {error_msg}")
        print("Continuing with available operations...")
    
    # Sync agents to cursor commands
    print("\nSyncing agents to cursor commands...")
    agent_synced, agent_created, agent_deleted = sync_to_cursor_commands("agents")
    print(f"  Synced: {agent_synced}, Created: {agent_created}, Deleted: {agent_deleted}")
    
    # Sync skills to cursor commands
    print("\nSyncing skills to cursor commands...")
    skill_synced, skill_created, skill_deleted = sync_to_cursor_commands("skills")
    print(f"  Synced: {skill_synced}, Created: {skill_created}, Deleted: {skill_deleted}")
    
    print("\n✓ Sync complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

