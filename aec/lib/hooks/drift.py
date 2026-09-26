"""Reconciliation between recorded hook state and the actual agent settings.

State records a `target_json_pointer` like `/hooks/PostToolUse/0`, but that
index is only a cache — when another tool (a tsc bootstrap, an older pipeline,
a hand edit) inserts or removes entries, the index shifts while the hook itself
is still present. So identity is the **content fingerprint**, never the index.

`classify_hook` locates a recorded hook by fingerprint (git: by its block) and
reports MISSING if it's gone, STALE if it differs from what the item's source
renders today, else OK. `verify_repo` runs that over every recorded hook in a repo.
"""

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .fingerprint import fingerprint_hook
from .installer import _resolve_script_commands
from .predicates import evaluate_when
from .schema import load_hooks_file
from .state import list_installed_items, load_state
from .translator import translate_to_agent

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


def _rendered(repo_root: Path, item_type: str, item_key: str,
              agent: str) -> Optional[Dict[Tuple[str, str], Set[str]]]:
    """(hook_id, event_key) -> the entries this item's source renders for `agent` today.

    Settings agents map to payload fingerprints (what install records); git maps
    to command lines (what the block holds). None when the source can't be
    rendered — missing hooks.json, a script gone — so drift has no opinion.
    """
    src = _item_source_dir(repo_root, item_type, item_key)
    if src is None or not (src / "hooks.json").exists():
        return None
    try:
        hf = load_hooks_file(src / "hooks.json")
        # Drop what install would skip, so a hook whose `when` turned false is
        # retracted. A custom_check is never run here — verify and doctor must
        # not execute item shell — so those hooks count as applicable.
        applied = replace(hf, hooks=[
            h for h in hf.hooks
            if (h.when and h.when.custom_check)
            or evaluate_when(h.when, repo_root).applied
        ])
        entries = translate_to_agent(
            applied, agent,
            resolved_commands=_resolve_script_commands(
                applied, src, repo_root, agent),
        )
    # Broad on purpose: item content is untrusted input, and verify/doctor must
    # report on every other hook rather than crash on one bad file. Install
    # (and so repair) surfaces the real error.
    except Exception:
        return None
    out: Dict[Tuple[str, str], Set[str]] = {}
    for e in entries:
        key = (e["payload"]["command"] if agent == "git"
               else fingerprint_hook(e["payload"]))
        out.setdefault((e["source_hook_id"], e["event_key"]), set()).add(key)
    return out


def _is_stale(expected: Optional[Dict[Tuple[str, str], Set[str]]],
              hook_id: str, event_key: str, actual: str) -> bool:
    """True if the installed hook isn't what its source renders today.

    Covers every older rendering at once — absolute paths, the unguarded
    project-dir path, the `-x` exec-bit guard, gemini/cursor exec'ing the bare
    path — and a hook whose source changed since install: its command, its
    event, or its removal from hooks.json altogether. Repair reinstalls the
    current rendering, so a flagged hook is always fixable: a hand-written
    command renders verbatim and never differs.
    """
    if expected is None:
        return False
    return actual not in expected.get((hook_id, event_key), ())


def _git_block(repo_root: Path, event_key: str, item_type: str,
               item_key: str, hook_id: str) -> Optional[str]:
    from .git_blocks import read_block
    from .git_hooks_path import resolve_hooks_dir

    hook_file = resolve_hooks_dir(repo_root).hooks_dir / event_key
    return read_block(hook_file, item_key=f"{item_type}:{item_key}",
                      hook_id=hook_id)


def classify_hook(repo_root: Path, installed: dict, *,
                  item_type: str, item_key: str) -> HookStatus:
    """Classify a single recorded hook against its settings file."""
    agent = installed["agent"]
    pointer = installed["target_json_pointer"]
    event_key = _event_key(pointer)
    hook_id = installed["hook_id"]

    expected = _rendered(repo_root, item_type, item_key, agent)
    if agent == "git":
        block = _git_block(repo_root, event_key, item_type, item_key, hook_id)
        idx = None
        if block is None:
            status = Drift.MISSING
        else:
            # The block is marker, command line(s), END marker.
            actual = "\n".join(block.rstrip("\n").split("\n")[1:-1])
            status = (Drift.STALE if _is_stale(expected, hook_id, event_key, actual)
                      else Drift.OK)
    else:
        fp = installed["content_fingerprint"]
        found = _locate_settings(repo_root, agent, event_key, fp)
        if found is None:
            status, idx = Drift.MISSING, None
        else:
            idx = found[0]
            status = (Drift.STALE if _is_stale(expected, hook_id, event_key, fp)
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
        # One broken item must not abort the rest of this repo or the
        # remaining repos; the caller reports it and exits non-zero.
        try:
            # The repo-local source is the truth repair converges on, version
            # included: an item updated in place (new hooks.json, bumped
            # version) is drift the recorded version would refuse to install.
            install_hooks_for_item(
                item_type=item_type, item_key=item_key,
                item_version=load_hooks_file(src / "hooks.json").version,
                item_dir=src, repo_root=repo_root, agents=agents,
                allow_custom_check=st.allow_custom_check,
            )
        except Exception as exc:
            results.append(RepairResult(item_type, item_key, repaired=False,
                                        detail=f"{type(exc).__name__}: {exc}"))
            continue
        results.append(RepairResult(item_type, item_key, repaired=True))
    return results
