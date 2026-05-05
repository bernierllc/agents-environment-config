"""Content hashing for org-config files.

sha256 with explicit prefix so the algorithm is recoverable from the hash
string alone (forward-compat if we ever migrate).
"""
from __future__ import annotations

import hashlib
from pathlib import Path


HASH_PREFIX = "sha256:"


def hash_config_bytes(data: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(data).hexdigest()


def hash_config_file(path: Path) -> str:
    return hash_config_bytes(path.read_bytes())
