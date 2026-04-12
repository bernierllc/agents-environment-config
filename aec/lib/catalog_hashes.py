"""Generate and load catalog-hashes.json with pre-computed SHA-256 hashes."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from aec.lib.config import VERSION
from aec.lib.skills_manifest import hash_skill_directory
from aec.lib.sources import discover_available, get_source_dirs


def hash_single_file(path: Path) -> str:
    """Compute SHA-256 of a single file, return 'sha256:<hexdigest>'."""
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return f"sha256:{hasher.hexdigest()}"


def generate_catalog_hashes(source_dirs: dict = None) -> dict:
    """Walk each source dir and build a catalog-hashes dict.

    For agents: hash each .md file individually using hash_single_file.
    For skills: hash each skill directory using hash_skill_directory.
    For rules: hash each .md file individually using hash_single_file.

    Args:
        source_dirs: Optional dict of item_type -> Path. If None, uses
            get_source_dirs() to discover them from the AEC repo.

    Returns:
        Dict matching the catalog-hashes.json schema.
    """
    if source_dirs is None:
        source_dirs = get_source_dirs()

    catalog: dict = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "aecVersion": VERSION,
        "agents": {},
        "skills": {},
        "rules": {},
    }

    for item_type in ("agents", "skills", "rules"):
        src = source_dirs.get(item_type)
        if src is None:
            continue

        items = discover_available(src, item_type)

        for name, meta in items.items():
            rel_path = meta.get("path", name)
            full_path = src / rel_path

            if item_type == "skills":
                if full_path.is_dir():
                    content_hash = hash_skill_directory(full_path)
                else:
                    continue
            else:
                # agents and rules — hash individual .md files
                if full_path.is_file():
                    content_hash = hash_single_file(full_path)
                else:
                    continue

            catalog[item_type][name] = {
                "version": meta.get("version", "0.0.0"),
                "contentHash": content_hash,
            }

    return catalog


def load_catalog_hashes(path: Path) -> dict:
    """Load catalog-hashes.json from path.

    Returns empty structure on missing or corrupt file.
    """
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "agents" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"agents": {}, "skills": {}, "rules": {}}


def regenerate_if_missing(catalog_path: Path, source_dirs: dict = None) -> dict:
    """If file missing or corrupt, regenerate and save; otherwise load existing.

    Args:
        catalog_path: Path to the catalog-hashes.json file.
        source_dirs: Optional dict of item_type -> Path.

    Returns:
        The catalog hashes dict (loaded or freshly generated).
    """
    existing = load_catalog_hashes(catalog_path)
    if existing.get("generatedAt"):
        return existing

    catalog = generate_catalog_hashes(source_dirs)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return catalog
