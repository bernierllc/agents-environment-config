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
    local_path: str = ""
    catalog_item: str = ""
    catalog_version: str = ""
    catalog_hash: str = ""
    local_hash: str = ""
    match_type: str = ""  # exact, modified, renamed, similar
    similarity: Optional[float] = None
    scan_depth: int = 1
    item_type: str = ""  # agents, skills, rules


def normalize_name(name: str) -> str:
    """Normalize an item name for comparison."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def scan_local_items(scope_dir: Path, item_type: str, installed: dict) -> list:
    """Find untracked local items in the given scope directory.

    Returns list[dict] with keys: name, path, is_dir.
    """
    raise NotImplementedError("Stub -- real implementation on feature branch")


def scan(local_items: list, catalog: dict, catalog_hashes: dict = None, depth: int = 2) -> list:
    """Scan local items against catalog at the given depth."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
