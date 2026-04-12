"""Three-level similarity scan engine: Quick (name), Normal (hash), Deep (content)."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .skills_manifest import hash_skill_directory

# Common division prefixes stripped during name normalization.
_DIVISION_PREFIXES = (
    "engineering-",
    "design-",
    "security-",
    "testing-",
    "marketing-",
    "sales-",
    "academic-",
    "paid-media-",
)


@dataclass
class MatchResult:
    """Result of comparing a local item against the AEC catalog."""

    local_path: str  # absolute path to local file
    local_name: str  # filename stem
    catalog_item: str  # matched catalog item name
    match_type: str  # "exact", "modified", "renamed", "similar"
    similarity: float  # 1.0 for exact/modified/renamed, 0.0-1.0 for similar
    catalog_version: str  # version of matched catalog item
    catalog_hash: str  # hash of matched catalog item
    local_hash: str  # hash of local file
    scan_depth: int  # 1, 2, or 3


def normalize_name(filename: str) -> str:
    """Normalize a filename for comparison.

    Strips .md extension, strips common division prefixes, and lowercases.
    Hyphens are preserved; no underscore conversion is applied.
    """
    name = filename.lower()
    # Strip .md extension
    if name.endswith(".md"):
        name = name[:-3]
    # Strip known division prefixes
    for prefix in _DIVISION_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name


def scan_local_items(
    scope_dir: Path, item_type: str, installed: dict
) -> list[dict]:
    """Enumerate files in a scope directory, excluding already-installed items.

    Args:
        scope_dir: Directory to scan (e.g. .claude/agents/).
        item_type: One of 'agents', 'skills', 'rules'.
        installed: Dict of installed item names (keys are canonical names).

    Returns:
        List of dicts with keys: name (stem), path (abs str), is_dir (bool).
    """
    if not scope_dir.is_dir():
        return []

    items: list[dict] = []
    for entry in sorted(scope_dir.iterdir()):
        if entry.name.startswith("."):
            continue

        stem = entry.stem if entry.is_file() else entry.name
        if stem in installed:
            continue

        items.append(
            {
                "name": stem,
                "path": str(entry.resolve()),
                "is_dir": entry.is_dir(),
            }
        )
    return items


def _hash_file(path: Path) -> str:
    """Compute sha256 hash of a single file."""
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return f"sha256:{hasher.hexdigest()}"


def _hash_local_item(item: dict) -> str:
    """Hash a local item — file or directory."""
    path = Path(item["path"])
    if item["is_dir"]:
        return hash_skill_directory(path)
    return _hash_file(path)


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity on normalized line sets.

    Normalizes whitespace within each line, splits into line sets, then
    returns ``len(intersection) / len(union)``.  Returns 0.0 when both
    inputs are empty.
    """
    def _to_line_set(text: str) -> set[str]:
        lines: set[str] = set()
        for raw_line in text.splitlines():
            normalized = " ".join(raw_line.split())
            if normalized:
                lines.add(normalized)
        return lines

    set_a = _to_line_set(text_a)
    set_b = _to_line_set(text_b)

    if not set_a and not set_b:
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _size_prefilter(size_a: int, size_b: int) -> bool:
    """Return True if the two sizes are within a 5x ratio of each other."""
    if size_a == 0 or size_b == 0:
        return False
    ratio = max(size_a, size_b) / min(size_a, size_b)
    return ratio <= 5.0


def _read_path_text(path: Path) -> Optional[str]:
    """Read text content from a file or directory path.

    For directories, concatenates all non-hidden file contents (sorted).
    Returns None if unreadable or empty.
    """
    try:
        if path.is_dir():
            parts: list[str] = []
            for filepath in sorted(path.rglob("*")):
                if filepath.is_file() and not any(
                    p.startswith(".") for p in filepath.relative_to(path).parts
                ):
                    try:
                        parts.append(filepath.read_text(encoding="utf-8"))
                    except (UnicodeDecodeError, OSError):
                        pass
            return "\n".join(parts) if parts else None
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _read_item_text(item: dict) -> Optional[str]:
    """Read text content from a local item."""
    return _read_path_text(Path(item["path"]))


def _read_catalog_text(catalog_item_name: str, catalog: dict) -> Optional[str]:
    """Read text content for a catalog item.

    Catalog entries are expected to have a ``source_path`` key pointing to the
    file on disk.  If absent or unreadable, returns None.
    """
    entry = catalog.get(catalog_item_name, {})
    source_path = entry.get("source_path")
    if not source_path:
        return None
    return _read_path_text(Path(source_path))


def scan(
    local_items: list[dict],
    catalog: dict,
    catalog_hashes: Optional[dict] = None,
    depth: int = 2,
) -> list[MatchResult]:
    """Run the similarity scan pipeline at the given depth.

    Args:
        local_items: Output of ``scan_local_items``.
        catalog: Dict of catalog_name -> {version, ...}.
        catalog_hashes: Dict of catalog_name -> hash string.
            Required for depth >= 2.
        depth: Scan depth — 1 (Quick), 2 (Normal), or 3 (Deep).

    Returns:
        List of MatchResult objects sorted by local_name.
    """
    if depth not in (1, 2, 3):
        raise ValueError(f"depth must be 1, 2, or 3, got {depth}")

    if catalog_hashes is None:
        catalog_hashes = {}

    # Build normalized catalog name lookup: normalized -> catalog_name
    catalog_norm: dict[str, str] = {}
    for cname in catalog:
        catalog_norm[normalize_name(cname)] = cname

    # --- Level 1: Quick (name matching) ---
    results: list[MatchResult] = []
    name_matched_locals: set[int] = set()  # indices into local_items
    name_matched_catalog: set[str] = set()  # catalog item names

    for idx, item in enumerate(local_items):
        norm_local = normalize_name(item["name"])
        if norm_local in catalog_norm:
            cname = catalog_norm[norm_local]
            centry = catalog.get(cname, {})
            results.append(
                MatchResult(
                    local_path=item["path"],
                    local_name=item["name"],
                    catalog_item=cname,
                    match_type="exact",  # provisional at depth 1
                    similarity=1.0,
                    catalog_version=centry.get("version", ""),
                    catalog_hash=catalog_hashes.get(cname, ""),
                    local_hash="",
                    scan_depth=1,
                )
            )
            name_matched_locals.add(idx)
            name_matched_catalog.add(cname)

    if depth == 1:
        return sorted(results, key=lambda r: r.local_name)

    # --- Level 2: Normal (hash comparison) ---
    items_by_path = {i["path"]: i for i in local_items}

    for result in results:
        item = items_by_path[result.local_path]
        result.local_hash = _hash_local_item(item)
        result.scan_depth = 2

        catalog_hash = catalog_hashes.get(result.catalog_item, "")
        result.catalog_hash = catalog_hash

        if catalog_hash and result.local_hash == catalog_hash:
            result.match_type = "exact"
        else:
            result.match_type = "modified"

    # Check for renamed items: hash remaining local items and compare
    # against all catalog hashes
    hash_to_catalog: dict[str, str] = {}
    for cname, chash in catalog_hashes.items():
        if cname not in name_matched_catalog:
            hash_to_catalog[chash] = cname

    for idx, item in enumerate(local_items):
        if idx in name_matched_locals:
            continue
        local_hash = _hash_local_item(item)
        if local_hash in hash_to_catalog:
            cname = hash_to_catalog[local_hash]
            centry = catalog.get(cname, {})
            results.append(
                MatchResult(
                    local_path=item["path"],
                    local_name=item["name"],
                    catalog_item=cname,
                    match_type="renamed",
                    similarity=1.0,
                    catalog_version=centry.get("version", ""),
                    catalog_hash=catalog_hashes.get(cname, ""),
                    local_hash=local_hash,
                    scan_depth=2,
                )
            )
            name_matched_locals.add(idx)
            name_matched_catalog.add(cname)

    # At depth 2, name+hash mismatches stay as "modified". We cannot
    # distinguish "modified" from "completely different" without content
    # analysis, which is deferred to depth 3.
    if depth == 2:
        return sorted(results, key=lambda r: r.local_name)

    # --- Level 3: Deep (content similarity) ---
    unmatched_locals: list[tuple[int, dict]] = []
    for idx, item in enumerate(local_items):
        if idx not in name_matched_locals:
            unmatched_locals.append((idx, item))

    unmatched_catalog: list[str] = [
        cname for cname in catalog if cname not in name_matched_catalog
    ]

    for idx, item in unmatched_locals:
        local_text = _read_item_text(item)
        if local_text is None:
            continue
        local_size = len(local_text)

        local_hash = _hash_local_item(item)
        best_sim = 0.0
        best_cname: Optional[str] = None

        for cname in unmatched_catalog:
            catalog_text = _read_catalog_text(cname, catalog)
            if catalog_text is None:
                continue

            # Size pre-filter
            if not _size_prefilter(local_size, len(catalog_text)):
                continue

            sim = _jaccard_similarity(local_text, catalog_text)
            if sim > best_sim:
                best_sim = sim
                best_cname = cname

        if best_sim >= 0.70 and best_cname is not None:
            centry = catalog.get(best_cname, {})
            results.append(
                MatchResult(
                    local_path=item["path"],
                    local_name=item["name"],
                    catalog_item=best_cname,
                    match_type="similar",
                    similarity=round(best_sim, 4),
                    catalog_version=centry.get("version", ""),
                    catalog_hash=catalog_hashes.get(best_cname, ""),
                    local_hash=local_hash,
                    scan_depth=3,
                )
            )

    return sorted(results, key=lambda r: r.local_name)
