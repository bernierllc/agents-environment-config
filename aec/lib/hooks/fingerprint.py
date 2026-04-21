"""Deterministic content fingerprint for drift detection.

SHA-256 of canonical JSON (sorted keys, tight separators, UTF-8). Stable
across dict-insertion order and Python versions.
"""

import hashlib
import json


def fingerprint_hook(payload: dict) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
