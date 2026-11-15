"""The one check that a path AEC writes stays inside its repo.

Every repo file AEC changes (migrate, tidy, setup, rollback) goes through
`escapes()`, so a symlinked file or directory can never redirect a write to a
shared location outside the repo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List


def escapes(root: Path, paths: Iterable[Path]) -> List[str]:
    """Why each path could lead outside `root`; empty when every path is confined.

    A path is confined when it sits lexically under `root` (after `..` is
    collapsed) and no component from just below `root` down to the file
    itself is a symlink. `root` itself may live under a symlink (e.g. macOS
    /var -> /private/var): only what is inside the repo matters.
    """
    base = Path(os.path.abspath(root))
    problems: List[str] = []
    for p in paths:
        full = Path(os.path.abspath(p))
        if base not in full.parents:
            problems.append(f"{p} is outside {base}")
            continue
        node = base
        for part in full.relative_to(base).parts:
            node = node / part
            if node.is_symlink():
                problems.append(f"{node} is a symlink")
                break
    return problems
