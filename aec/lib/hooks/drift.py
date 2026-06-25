"""Reconciliation between recorded hook state and the actual agent settings.

State records a `target_json_pointer` like `/hooks/PostToolUse/0`, but that
index is only a cache — when another tool (a tsc bootstrap, an older pipeline,
a hand edit) inserts or removes entries, the index shifts while the hook itself
is still present. So identity is the **content fingerprint**, never the index.

`classify_hook` locates a recorded hook in its settings file by fingerprint and
reports OK / MISSING. `verify_repo` runs that over every recorded hook in a repo.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .fingerprint import fingerprint_hook
from .state import list_installed_items, load_state

# Settings-file agents store entries under data["hooks"][<event_key>].
_AGENT_SETTINGS = {
    "claude": ".claude/settings.json",
    "gemini": ".gemini/settings.json",
    "cursor": ".cursor/hooks.json",
}


class Drift(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    # ponytail: MODIFIED/ORPHAN need a stable identity marker in the written
    # payload, which AEC doesn't write yet — add when the payload carries one.


@dataclass
class HookStatus:
    item_type: str
    item_key: str
    hook_id: str
    agent: str
    status: Drift
    recorded_pointer: str
    found_index: Optional[int] = None


def _event_key(pointer: str) -> str:
    # "/hooks/PostToolUse/0" -> "PostToolUse"; "/git/pre-commit/<id>" -> "pre-commit"
    return pointer.split("/")[2]


def _locate_settings(repo_root: Path, agent: str, event_key: str, fp: str):
    settings_path = repo_root / _AGENT_SETTINGS[agent]
    if not settings_path.exists():
        return None
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    arr = data.get("hooks", {}).get(event_key, [])
    for i, entry in enumerate(arr):
        if fingerprint_hook(entry) == fp:
            return i
    return None


def _git_present(repo_root: Path, event_key: str, item_type: str,
                 item_key: str, hook_id: str) -> bool:
    from .git_blocks import block_present
    from .git_hooks_path import resolve_hooks_dir

    hook_file = resolve_hooks_dir(repo_root).hooks_dir / event_key
    return block_present(hook_file, item_key=f"{item_type}:{item_key}",
                         hook_id=hook_id)


def classify_hook(repo_root: Path, installed: dict, *,
                  item_type: str, item_key: str) -> HookStatus:
    """Classify a single recorded hook against its settings file."""
    agent = installed["agent"]
    pointer = installed["target_json_pointer"]
    event_key = _event_key(pointer)
    hook_id = installed["hook_id"]

    if agent == "git":
        present = _git_present(repo_root, event_key, item_type, item_key, hook_id)
        status, idx = (Drift.OK, None) if present else (Drift.MISSING, None)
    else:
        idx = _locate_settings(repo_root, agent, event_key,
                               installed["content_fingerprint"])
        status = Drift.OK if idx is not None else Drift.MISSING

    return HookStatus(
        item_type=item_type, item_key=item_key, hook_id=hook_id,
        agent=agent, status=status, recorded_pointer=pointer, found_index=idx,
    )


def verify_repo(repo_root: Path) -> List[HookStatus]:
    """Classify every recorded hook across every installed item in a repo."""
    statuses: List[HookStatus] = []
    for item_type, item_key in list_installed_items(repo_root):
        st = load_state(repo_root, item_type=item_type, item_key=item_key)
        for installed in st.hooks_installed:
            statuses.append(
                classify_hook(repo_root, installed,
                              item_type=item_type, item_key=item_key)
            )
    return statuses
