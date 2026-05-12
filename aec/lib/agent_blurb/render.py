"""Pure renderer for the agent blurb block.

Determinism guarantees:
- Same inputs -> byte-identical output.
- No timestamps in body content; only stored in the JSON config.
- Lists are emitted in fixed-sorted order.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §4.
"""

import hashlib
from pathlib import Path
from typing import Dict

from aec.lib.agent_blurb.profile import (
    ITEM_TYPES,
    READ_ONLY_COMMANDS,
    DESTRUCTIVE_COMMANDS,
)

BLOCK_VERSION = "v1"
SCHEMA_VERSION = 1

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "blurb_v1.md.tmpl"

START_MARKER_PREFIX = "<!-- aec-blurb:start"
END_MARKER = "<!-- aec-blurb:end -->"


def sha256_short(text: str) -> str:
    """Return the first 16 hex chars of SHA256(text)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _read_template() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def shipped_template_hash() -> str:
    return sha256_short(_read_template())


def _format_auto_list(matrix: Dict[str, Dict[str, str]]) -> str:
    lines = []
    for cmd in sorted(READ_ONLY_COMMANDS):
        lines.append(f"- `aec {cmd}` — read-only (always auto)")
    for itype in ITEM_TYPES:
        if matrix[itype]["additive"] == "auto":
            lines.append(f"- `aec add {itype[:-1]} <name>` — install a {itype[:-1]} ({itype}: additive=auto)")
    return "\n".join(lines)


def _format_ask_list(matrix: Dict[str, Dict[str, str]]) -> str:
    lines = []
    for itype in ITEM_TYPES:
        if matrix[itype]["additive"] == "ask":
            lines.append(f"- `aec add {itype[:-1]} <name>` ({itype}: additive=ask)")
    for cmd in sorted(DESTRUCTIVE_COMMANDS):
        lines.append(f"- `aec {cmd}` — destructive (always ask)")
    return "\n".join(lines)


def _render_body(matrix: Dict[str, Dict[str, str]]) -> str:
    """Render the body content between start and end markers (excluding markers)."""
    tmpl = _read_template()
    return (
        tmpl
        .replace("{{AUTO_LIST}}", _format_auto_list(matrix))
        .replace("{{ASK_LIST}}", _format_ask_list(matrix))
    )


def content_hash_of(inner_body: str) -> str:
    return sha256_short(inner_body)


def render_block(
    scope: str, profile: str, matrix: Dict[str, Dict[str, str]], aec_version: str
) -> str:
    """Render the full block including start/end markers.

    The start marker contains: block-version, schema, aec version,
    template-hash, content-hash, profile, scope.
    """
    inner = _render_body(matrix)
    tmpl_hash = shipped_template_hash()
    content_hash = content_hash_of(inner)
    start = (
        f"{START_MARKER_PREFIX} {BLOCK_VERSION} "
        f"schema={SCHEMA_VERSION} aec={aec_version} "
        f"template-hash={tmpl_hash} content-hash={content_hash} "
        f"profile={profile} scope={scope} -->"
    )
    return f"{start}\n{inner}\n{END_MARKER}\n"


def extract_inner_body(block: str) -> str:
    """Given a full rendered block, return just the body between markers.

    Used to verify content-hash claims and for hashing on-disk blocks.
    """
    lines = block.splitlines()
    try:
        start_idx = next(i for i, ln in enumerate(lines) if ln.startswith(START_MARKER_PREFIX))
        end_idx = next(i for i, ln in enumerate(lines) if ln.strip() == END_MARKER)
    except StopIteration:
        raise ValueError("Block is missing start or end marker")
    return "\n".join(lines[start_idx + 1:end_idx])
