"""`when` predicate evaluator — spec §1.4.

Evaluates a `WhenPredicate` against a repository root. `custom_check` runs
actual subprocess (no mocks per global testing rule). Installer is responsible
for obtaining explicit user consent before invoking this with a hooks.json
that contains `custom_check` (P1-D8).
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .schema import WhenPredicate


@dataclass
class WhenResult:
    applied: bool
    reason: str = ""


def evaluate_when(
    pred: Optional[WhenPredicate],
    repo_root: Path,
    timeout_s: int = 5,
) -> WhenResult:
    if pred is None:
        return WhenResult(True, "")

    for rel in pred.repo_has:
        if not (repo_root / rel).exists():
            return WhenResult(False, f"missing required path: {rel}")

    if pred.repo_has_any:
        if not any((repo_root / rel).exists() for rel in pred.repo_has_any):
            return WhenResult(
                False,
                f"none of repo_has_any present: {pred.repo_has_any}",
            )

    for rel in pred.repo_lacks:
        if (repo_root / rel).exists():
            return WhenResult(False, f"repo_lacks violated: {rel} exists")

    if pred.custom_check:
        try:
            r = subprocess.run(
                pred.custom_check,
                shell=True,
                cwd=str(repo_root),
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return WhenResult(False, f"custom_check timeout after {timeout_s}s")
        if r.returncode != 0:
            return WhenResult(False, f"custom_check exit {r.returncode}")

    return WhenResult(True, "")
