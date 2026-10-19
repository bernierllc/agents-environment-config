"""Resolve the directory where git-hook scripts must live for a given repo.

Most repos use the default `.git/hooks/`, but projects that adopt husky
relocate hooks via `core.hooksPath`. Husky v8 points it at `.husky/` and
requires each hook to source `_/husky.sh`; husky v9 points it at `.husky/_/`
(wrappers) and user hooks live unwrapped at `.husky/<name>`.

`resolve_hooks_dir` returns the directory we should write user-visible hook
scripts into, plus whether the husky v8 bootstrap source-line needs to be
injected.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


HUSKY_V8_BOOTSTRAP = '. "$(dirname -- "$0")/_/husky.sh"'


@dataclass(frozen=True)
class HooksDirResolution:
    hooks_dir: Path
    husky_version: Optional[str]  # "v8", "v9", or None
    needs_v8_bootstrap: bool


def _git_hooks_path(repo_root: Path) -> Optional[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse",
             "--path-format=absolute", "--git-path", "hooks"],
            capture_output=True, text=True, check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return Path(value) if value else None


def _husky_major_from_package_json(repo_root: Path) -> Optional[int]:
    try:
        pkg = json.loads((repo_root / "package.json").read_text())
    except (OSError, ValueError):
        return None
    for section in ("devDependencies", "dependencies"):
        spec = (pkg.get(section) or {}).get("husky")
        if isinstance(spec, str):
            m = re.search(r"\d+", spec)
            if m:
                return int(m.group())
    return None


def _detect_husky(repo_root: Path) -> Optional[str]:
    husky_dir = repo_root / ".husky"
    if not husky_dir.is_dir():
        return None
    underscore = husky_dir / "_"
    # v9 always writes `_/h`; it also writes a `_/husky.sh` deprecation stub,
    # so husky.sh alone does not mean v8. `_/` is gitignored, so a fresh
    # clone or worktree has none: fall back to the declared husky version.
    if (underscore / "h").is_file():
        return "v9"
    major = _husky_major_from_package_json(repo_root)
    if major is not None and major >= 9:
        return "v9"
    if not underscore.is_dir():
        # `.husky/` exists but no `_/` — likely v8 pre-install state.
        return "v8"
    if (underscore / "husky.sh").is_file():
        return "v8"
    # v9 ships per-event wrappers in _/ but no husky.sh shim.
    if any(underscore.iterdir()):
        return "v9"
    return "v8"


def resolve_hooks_dir(repo_root: Path) -> HooksDirResolution:
    """Decide where to write user-visible hook scripts for this repo.

    Order of precedence:
      1. If `.husky/` exists, target `.husky/<name>` regardless of
         `core.hooksPath` (husky v9 sets it to `.husky/_/` but user hooks
         belong at `.husky/<name>`).
      2. Otherwise git's own hooks dir: `core.hooksPath` if set, else the
         (common) `.git/hooks/`, which also covers linked worktrees.
      3. Not a git repo: `.git/hooks/`.
    """
    husky_version = _detect_husky(repo_root)
    if husky_version is not None:
        return HooksDirResolution(
            hooks_dir=repo_root / ".husky",
            husky_version=husky_version,
            needs_v8_bootstrap=(husky_version == "v8"),
        )

    # `--git-path hooks` honors core.hooksPath and resolves a linked
    # worktree (where `.git` is a file) to the common hooks dir.
    hooks = _git_hooks_path(repo_root)
    if hooks is not None:
        return HooksDirResolution(
            hooks_dir=hooks,
            husky_version=None,
            needs_v8_bootstrap=False,
        )

    return HooksDirResolution(
        hooks_dir=repo_root / ".git" / "hooks",
        husky_version=None,
        needs_v8_bootstrap=False,
    )
