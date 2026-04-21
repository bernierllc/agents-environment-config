"""Idempotent delimited-block writer for `.git/hooks/<name>` scripts.

Wraps each installed command in a clearly delimited block keyed by
`item_key` + `hook_id` so upgrades replace in place and removals leave user
content untouched. See spec §1.7.
"""

import re
import stat
from pathlib import Path

SHEBANG = "#!/usr/bin/env bash"


def _begin_marker(item_key: str, hook_id: str) -> str:
    return f"# >>> AEC:BEGIN item={item_key} hook_id={hook_id}"


END_MARKER = "# <<< AEC:END"


def _block_regex(item_key: str, hook_id: str) -> re.Pattern:
    begin = re.escape(_begin_marker(item_key, hook_id))
    end = re.escape(END_MARKER)
    # Match from marker line through the END line (inclusive), including a
    # trailing newline if present. DOTALL so `.` spans newlines.
    return re.compile(
        rf"{begin}[^\n]*\n.*?{end}\n?",
        flags=re.DOTALL,
    )


def _render_block(item_key: str, hook_id: str, version: str, command: str) -> str:
    return (
        f"{_begin_marker(item_key, hook_id)} version={version}\n"
        f"{command}\n"
        f"{END_MARKER}\n"
    )


def _ensure_shebang(text: str) -> str:
    if not text:
        return SHEBANG + "\n"
    first_line = text.splitlines()[0] if text else ""
    if first_line.startswith("#!"):
        return text if text.endswith("\n") else text + "\n"
    prefix = SHEBANG + "\n"
    return prefix + (text if text.endswith("\n") else text + "\n")


def _try_chmod_exec(path: Path) -> None:
    try:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except (AttributeError, NotImplementedError, PermissionError, OSError):
        pass


def write_block(
    hook_file: Path,
    *,
    item_key: str,
    hook_id: str,
    version: str,
    command: str,
) -> None:
    """Idempotently install a delimited block for (item_key, hook_id).

    If a block with the same item_key+hook_id already exists, it is replaced.
    Otherwise the new block is appended. User content outside AEC blocks is
    preserved. Ensures a shebang and sets the executable bit (best-effort).
    """
    existing = hook_file.read_text(encoding="utf-8") if hook_file.exists() else ""
    existing = _ensure_shebang(existing)

    block = _render_block(item_key, hook_id, version, command)
    pattern = _block_regex(item_key, hook_id)

    if pattern.search(existing):
        new_text = pattern.sub(block, existing, count=1)
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        new_text = existing + block

    if new_text != existing or not hook_file.exists():
        hook_file.parent.mkdir(parents=True, exist_ok=True)
        hook_file.write_text(new_text, encoding="utf-8")

    _try_chmod_exec(hook_file)


def remove_block(hook_file: Path, *, item_key: str, hook_id: str) -> None:
    """Remove the matching delimited block. No-op if absent or file missing."""
    if not hook_file.exists():
        return
    text = hook_file.read_text(encoding="utf-8")
    pattern = _block_regex(item_key, hook_id)
    if not pattern.search(text):
        return
    new_text = pattern.sub("", text, count=1)
    hook_file.write_text(new_text, encoding="utf-8")
