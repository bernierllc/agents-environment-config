"""Resolve the directory where git-hook scripts must live for a given repo.

Most repos use the default `.git/hooks/`, but projects that adopt husky
relocate hooks via `core.hooksPath`. Husky v8 points it at `.husky/` and
requires each hook to source `_/husky.sh`; husky v9 points it at `.husky/_/`
(wrappers) and user hooks live unwrapped at `.husky/<name>`.

`resolve_hooks_dir` returns the directory we should write user-visible hook
scripts into, plus whether the husky v8 bootstrap source-line needs to be
injected.
"""

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


def _read_core_hooks_path(repo_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "core.hooksPath"],
            capture_output=True, text=True, check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _detect_husky(repo_root: Path) -> Optional[str]:
    husky_dir = repo_root / ".husky"
    if not husky_dir.is_dir():
        return None
    underscore = husky_dir / "_"
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
      2. If `core.hooksPath` is configured, honor it.
      3. Default to `.git/hooks/`.
    """
    husky_version = _detect_husky(repo_root)
    if husky_version is not None:
        return HooksDirResolution(
            hooks_dir=repo_root / ".husky",
            husky_version=husky_version,
            needs_v8_bootstrap=(husky_version == "v8"),
        )

    configured = _read_core_hooks_path(repo_root)
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = repo_root / path
        return HooksDirResolution(
            hooks_dir=path,
            husky_version=None,
            needs_v8_bootstrap=False,
        )

    return HooksDirResolution(
        hooks_dir=repo_root / ".git" / "hooks",
        husky_version=None,
        needs_v8_bootstrap=False,
    )
