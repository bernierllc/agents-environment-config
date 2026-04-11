"""Catalog hash management for AEC discovery.

Stub module -- real implementation lives on a separate branch.
"""

from pathlib import Path


def load_catalog_hashes(path: Path) -> dict:
    """Load pre-computed catalog hashes."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def regenerate_if_missing(catalog_path: Path, source_dirs: dict = None) -> dict:
    """Regenerate catalog hashes if missing."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def generate_catalog_hashes() -> dict:
    """Generate catalog hashes from source."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
