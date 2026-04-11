"""Similarity engine for AEC catalog discovery.

Stub module -- real implementation lives on a separate branch.
This provides type definitions and function signatures for dependent code.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MatchResult:
    """Result of comparing a local item against the AEC catalog."""
    local_name: str = ""
    local_path: Optional[Path] = None
    catalog_name: str = ""
    match_type: str = ""  # exact, modified, renamed, similar
    similarity: Optional[float] = None
    item_type: str = ""  # agents, skills, rules


def normalize_name(name: str) -> str:
    """Normalize an item name for comparison."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def scan_local_items(scope, item_type: str) -> list:
    """Find untracked local items in the given scope."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def scan(local_items: list, catalog: dict, catalog_hashes: dict = None, depth: int = 2) -> list:
    """Scan local items against catalog at the given depth."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
