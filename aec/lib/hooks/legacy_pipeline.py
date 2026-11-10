"""Ownership of pre-declarative verification pipeline Git hook blocks."""

import re
from pathlib import Path

from ..console import Console
from .git_hooks_path import resolve_hooks_dir

_HOOK_SOURCE_LINE = "source scripts/verification-playwright/hooks/{hook}.sh 2>/dev/null || true"
_HOOK_BEGIN = "# BEGIN verification-playwright"
_HOOK_END = "# END verification-playwright"


def unwire_git_hooks(repo_path: Path) -> None:
    """Remove only legacy pipeline blocks; generic hooks have their own state."""
    pattern = re.compile(
        rf"^{re.escape(_HOOK_BEGIN)}\n.*?^{re.escape(_HOOK_END)}(?:\n|$)",
        re.MULTILINE | re.DOTALL,
    )
    # Check both destinations the legacy writer can use; Husky may coexist
    # with previously wired raw hooks after a framework change.
    for directory in {repo_path / ".husky", resolve_hooks_dir(repo_path).hooks_dir}:
        for name in ("pre-commit", "pre-push"):
            path = directory / name
            if path.is_file():
                original = path.read_text()
                updated = pattern.sub("", original)
                if updated != original:
                    path.write_text(updated)


def wire_git_hooks(repo_path: Path) -> None:
    """Wire verification-playwright into the project's git hook framework."""
    for hook_name in ("pre-commit", "pre-push"):
        source_line = _HOOK_SOURCE_LINE.format(hook=hook_name)
        block = f"{_HOOK_BEGIN}\n{source_line}\n{_HOOK_END}\n"

        # Husky
        husky_hook = repo_path / ".husky" / hook_name
        if husky_hook.exists():
            content = husky_hook.read_text()
            if _HOOK_BEGIN not in content:
                husky_hook.write_text(content.rstrip() + "\n\n" + block)
            continue

        # Lefthook
        for lefthook_file in (".lefthookrc.yml", ".lefthookrc.yaml", "lefthook.yml"):
            lefthook_path = repo_path / lefthook_file
            if lefthook_path.exists():
                # Don't auto-edit YAML — just inform
                Console.info(f"  Add verification-playwright to {lefthook_file} manually")
                break
        else:
            # Raw git hooks dir (honors core.hooksPath and linked worktrees)
            git_hook = resolve_hooks_dir(repo_path).hooks_dir / hook_name
            if git_hook.exists():
                content = git_hook.read_text()
                if _HOOK_BEGIN not in content:
                    git_hook.write_text(content.rstrip() + "\n\n" + block)
            else:
                git_hook.parent.mkdir(parents=True, exist_ok=True)
                git_hook.write_text(f"#!/usr/bin/env bash\n\n{block}")
                git_hook.chmod(0o755)
