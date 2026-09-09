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
from .installer import CLAUDE_PROJECT_DIR_PREFIX, is_guarded
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
    STALE = "STALE"
    # ponytail: MODIFIED/ORPHAN need a stable identity marker in the written
    # payload, which AEC doesn't write yet — add when the payload carries one.


# Where a repo-scoped item's source (incl. hooks.json) lives, by item type.
_REPO_ITEM_DIR = {
    "skill": Path(".claude") / "skills",
    "agent": Path(".claude") / "agents",
    "rule": Path(".agent-rules"),
}


@dataclass
class RepairResult:
    item_type: str
    item_key: str
    repaired: bool
    detail: Optional[str] = None


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
    """Return (index, entry) for the recorded hook, or None if it's gone."""
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
            return i, entry
    return None


def _entry_commands(entry: dict) -> List[str]:
    """Every command string in a settings entry, whatever the nesting."""
    cmds: List[str] = []
    if isinstance(entry.get("command"), str):
        cmds.append(entry["command"])
    for inner in entry.get("hooks", []) or []:
        if isinstance(inner, dict) and isinstance(inner.get("command"), str):
            cmds.append(inner["command"])
    return cmds


def _is_stale(repo_root: Path, agent: str, entry: dict) -> bool:
    """True if the entry runs, but not in anyone else's checkout.

    Two generations of that:

    1. Installs before the `$CLAUDE_PROJECT_DIR` rendering baked the machine's
       absolute repo path into settings.json.
    2. Installs before the missing-script guard pointed a portable path at a
       `.claude/skills/**` script that is typically untracked — settings.json
       IS tracked, so a clone wires the hook and every matching edit exits 127.
       Keyed on the generated shape — the command STARTS with the project-dir
       prefix — not on the variable appearing anywhere: repair only guards paths
       it resolves, so flagging a hand-written hook that merely mentions
       `$CLAUDE_PROJECT_DIR` would leave it STALE forever.

    Either way the command still runs here, so it isn't MISSING. Flagging it
    STALE lets `hooks verify --repair` upgrade it in place: the reinstall
    retracts the old entry and writes the current rendering. Only claude has a
    project-dir variable, so only claude can be stale.
    """
    if agent != "claude":
        return False
    # Claude entries nest the command under a matcher object; scan the whole
    # serialized entry rather than reaching into a shape that may grow.
    if str(repo_root) in json.dumps(entry):
        return True
    return any(
        cmd.startswith(CLAUDE_PROJECT_DIR_PREFIX) and not is_guarded(cmd)
        for cmd in _entry_commands(entry)
    )


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
        found = _locate_settings(repo_root, agent, event_key,
                                 installed["content_fingerprint"])
        if found is None:
            status, idx = Drift.MISSING, None
        else:
            idx, entry = found
            status = (Drift.STALE if _is_stale(repo_root, agent, entry)
                      else Drift.OK)

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


def _item_source_dir(repo_root: Path, item_type: str, item_key: str) -> Optional[Path]:
    sub = _REPO_ITEM_DIR.get(item_type)
    if sub is None:
        return None
    return repo_root / sub / item_key


def repair_repo(repo_root: Path) -> List[RepairResult]:
    """Re-wire any drifted hooks from each item's repo-local source.

    Reuses the installer, which merges (never clobbers) into settings and
    rebuilds the state pointers from the freshly-located indices. Only items
    with MISSING drift are touched; healthy items are reported as no-ops.
    """
    from .lifecycle import install_hooks_for_item

    results: List[RepairResult] = []
    drifted_items = {
        (s.item_type, s.item_key)
        for s in verify_repo(repo_root)
        if s.status is not Drift.OK
    }
    for item_type, item_key in list_installed_items(repo_root):
        if (item_type, item_key) not in drifted_items:
            results.append(RepairResult(item_type, item_key, repaired=False,
                                        detail="no drift"))
            continue
        src = _item_source_dir(repo_root, item_type, item_key)
        if src is None or not (src / "hooks.json").exists():
            results.append(RepairResult(
                item_type, item_key, repaired=False,
                detail=f"source hooks.json not found at {src}",
            ))
            continue
        st = load_state(repo_root, item_type=item_type, item_key=item_key)
        agents = st.agents_targeted or ["claude", "gemini", "cursor", "git"]
        install_hooks_for_item(
            item_type=item_type, item_key=item_key,
            item_version=st.item_version or "0.0.0",
            item_dir=src, repo_root=repo_root, agents=agents,
            allow_custom_check=st.allow_custom_check,
        )
        results.append(RepairResult(item_type, item_key, repaired=True))
    return results
