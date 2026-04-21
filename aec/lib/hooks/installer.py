"""Hook installation orchestrator.

Pure merge helpers live here alongside the `install_item_hooks` /
`remove_item_hooks` entrypoints. The helpers operate on plain dicts with no
I/O so they can be tested in isolation — this file grows across Tasks 9a-9g.
"""

import json
import shlex
from pathlib import Path
from typing import Dict, List, Sequence

from ..atomic_write import atomic_write_json
from . import git_blocks, state as hook_state
from .fingerprint import fingerprint_hook
from .predicates import evaluate_when
from .schema import HooksFile, load_hooks_file
from .translator import translate_to_agent
from .validator import validate_hooks_file


_RUN_SCRIPT_PREFIX = "aec run-script"


def _resolve_script_commands(hf, item_dir: Path) -> Dict[str, str]:
    """Rewrite `aec run-script <item> <script> [args...]` to an absolute path.

    Looks for `<item_dir>/scripts/<script>`. Raises FileNotFoundError if the
    referenced script does not exist.
    """
    resolved: Dict[str, str] = {}
    for h in hf.hooks:
        cmd = h.command
        if cmd.startswith(_RUN_SCRIPT_PREFIX):
            parts = shlex.split(cmd)
            if len(parts) >= 4 and parts[:2] == ["aec", "run-script"]:
                script_name = parts[3]
                extra = parts[4:]
                script_path = item_dir / "scripts" / script_name
                if not script_path.exists():
                    raise FileNotFoundError(
                        f"hook {h.id!r}: script not found: {script_path}"
                    )
                pieces = [str(script_path), *extra]
                cmd = shlex.join(pieces) if hasattr(shlex, "join") else " ".join(
                    shlex.quote(p) for p in pieces
                )
        resolved[h.id] = cmd
    return resolved


def _merge_claude_entries(config: dict, entries: List[dict]) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        new_payload = entry["payload"]
        fp_new = fingerprint_hook(new_payload)
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(new_payload)
    return settings


def _merge_gemini_entries(config: dict, entries: List[dict]) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        new_payload = entry["payload"]
        fp_new = fingerprint_hook(new_payload)
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(new_payload)
    return settings


def _merge_cursor_entries(config: dict, entries: List[dict]) -> dict:
    cfg = dict(config) if config else {}
    hooks = cfg.setdefault("hooks", {})
    for entry in entries:
        arr = hooks.setdefault(entry["event_key"], [])
        fp_new = fingerprint_hook(entry["payload"])
        if any(fingerprint_hook(existing) == fp_new for existing in arr):
            continue
        arr.append(entry["payload"])
    return cfg


def _remove_from_claude(config: dict, event_key: str, fingerprint: str) -> dict:
    settings = dict(config) if config else {}
    hooks = settings.get("hooks", {})
    if event_key not in hooks:
        return settings
    hooks[event_key] = [e for e in hooks[event_key] if fingerprint_hook(e) != fingerprint]
    if not hooks[event_key]:
        del hooks[event_key]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def _remove_from_gemini(config: dict, event_key: str, fingerprint: str) -> dict:
    return _remove_from_claude(config, event_key, fingerprint)


def _remove_from_cursor(config: dict, event_key: str, fingerprint: str) -> dict:
    return _remove_from_claude(config, event_key, fingerprint)


def install_item_hooks(
    *,
    item_type: str,
    item_key: str,
    item_version: str,
    item_dir: Path,
    repo_root: Path,
    agents: Sequence[str],
    allow_custom_check: bool = False,
) -> None:
    """End-to-end install: load → validate → translate → merge → record state.

    Only `claude` is handled in this slice; other agents land in later tasks.
    """
    hooks_json = item_dir / "hooks.json"
    if not hooks_json.exists():
        return
    hf = load_hooks_file(hooks_json)
    errs, _warns = validate_hooks_file(hf, expected_version=item_version)
    if errs:
        messages = "; ".join(
            f"{e.hook_id + ': ' if e.hook_id else ''}{e.message}" for e in errs
        )
        raise ValueError(f"hooks.json validation failed: {messages}")

    if any(h.when and h.when.custom_check for h in hf.hooks) and not allow_custom_check:
        raise PermissionError(
            "hooks.json contains when.custom_check; re-run with "
            "allow_custom_check=True to consent to running custom shell"
        )

    resolved = _resolve_script_commands(hf, item_dir)

    st = hook_state.load_state(repo_root, item_type=item_type, item_key=item_key)
    st.item_version = item_version
    st.hooks_file_hash = fingerprint_hook(json.loads(hooks_json.read_text()))
    st.agents_targeted = list(agents)
    st.hooks_installed = []
    st.hooks_skipped = []
    if allow_custom_check:
        st.allow_custom_check = True

    kept: List = []
    for h in hf.hooks:
        result = evaluate_when(h.when, repo_root)
        if result.applied:
            kept.append(h)
        else:
            st.hooks_skipped.append({"hook_id": h.id, "reason": result.reason})

    filtered = HooksFile(
        version=hf.version,
        hooks=kept,
        claude=hf.claude,
        cursor=hf.cursor,
        gemini=hf.gemini,
        git=hf.git,
        schema_url=hf.schema_url,
        source_path=hf.source_path,
    )

    for agent in agents:
        entries = translate_to_agent(filtered, agent, resolved_commands=resolved)
        if agent == "claude":
            _install_claude(repo_root, entries, st, item_version)
        elif agent == "gemini":
            _install_gemini(repo_root, entries, st, item_version)
        elif agent == "cursor":
            _install_cursor(repo_root, entries, st, item_version)
        elif agent == "git":
            _install_git(repo_root, entries, st, item_type, item_key, item_version)
        else:
            raise NotImplementedError(f"agent {agent!r} handled in later task")

    hook_state.save_state(repo_root, st)


def remove_item_hooks(
    *, item_type: str, item_key: str, repo_root: Path,
) -> None:
    """Remove an item's hooks from all recorded agents, then drop state."""
    st = hook_state.load_state(repo_root, item_type=item_type, item_key=item_key)
    for installed in st.hooks_installed:
        agent = installed["agent"]
        event_key = installed["target_json_pointer"].split("/")[2]
        fp = installed["content_fingerprint"]
        if agent == "claude":
            _remove_claude(repo_root, event_key, fp)
        elif agent == "gemini":
            _remove_gemini(repo_root, event_key, fp)
        elif agent == "cursor":
            _remove_cursor(repo_root, event_key, fp)
        elif agent == "git":
            _remove_git(repo_root, event_key, installed, item_type, item_key)
    hook_state.remove_state(repo_root, item_type=item_type, item_key=item_key)


def _remove_claude(repo_root: Path, event_key: str, fp: str) -> None:
    settings_path = repo_root / ".claude/settings.json"
    if not settings_path.exists():
        return
    existing = json.loads(settings_path.read_text())
    updated = _remove_from_claude(existing, event_key, fp)
    atomic_write_json(settings_path, updated)


def _remove_gemini(repo_root: Path, event_key: str, fp: str) -> None:
    settings_path = repo_root / ".gemini/settings.json"
    if not settings_path.exists():
        return
    existing = json.loads(settings_path.read_text())
    updated = _remove_from_gemini(existing, event_key, fp)
    atomic_write_json(settings_path, updated)


def _remove_cursor(repo_root: Path, event_key: str, fp: str) -> None:
    settings_path = repo_root / ".cursor/hooks.json"
    if not settings_path.exists():
        return
    existing = json.loads(settings_path.read_text())
    updated = _remove_from_cursor(existing, event_key, fp)
    atomic_write_json(settings_path, updated)


def _install_git(
    repo_root: Path,
    entries: List[dict],
    st,
    item_type: str,
    item_key: str,
    item_version: str,
) -> None:
    item_ref = f"{item_type}:{item_key}"
    hooks_dir = repo_root / ".git/hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        event_key = entry["event_key"]
        payload = entry["payload"]
        command = payload["command"]
        hook_id = entry["source_hook_id"]
        hook_file = hooks_dir / event_key
        git_blocks.write_block(
            hook_file,
            item_key=item_ref,
            hook_id=hook_id,
            version=item_version,
            command=command,
        )
        fp = fingerprint_hook({"command": command, "hook_name": event_key})
        st.hooks_installed.append({
            "hook_id": hook_id,
            "agent": "git",
            "target_json_pointer": f"/git/{event_key}/{hook_id}",
            "content_fingerprint": fp,
            "version": item_version,
        })


def _remove_git(
    repo_root: Path, event_key: str, installed: dict,
    item_type: str, item_key: str,
) -> None:
    hook_file = repo_root / ".git/hooks" / event_key
    git_blocks.remove_block(
        hook_file,
        item_key=f"{item_type}:{item_key}",
        hook_id=installed["hook_id"],
    )


def _install_claude(
    repo_root: Path, entries: List[dict], st, item_version: str
) -> None:
    settings_path = repo_root / ".claude/settings.json"
    existing = (
        json.loads(settings_path.read_text()) if settings_path.exists() else {}
    )
    updated = _merge_claude_entries(existing, entries)
    atomic_write_json(settings_path, updated)
    _record_entries(st, entries, updated, agent="claude", item_version=item_version)


def _install_gemini(
    repo_root: Path, entries: List[dict], st, item_version: str
) -> None:
    settings_path = repo_root / ".gemini/settings.json"
    existing = (
        json.loads(settings_path.read_text()) if settings_path.exists() else {}
    )
    updated = _merge_gemini_entries(existing, entries)
    atomic_write_json(settings_path, updated)
    _record_entries(st, entries, updated, agent="gemini", item_version=item_version)


def _install_cursor(
    repo_root: Path, entries: List[dict], st, item_version: str
) -> None:
    settings_path = repo_root / ".cursor/hooks.json"
    existing = (
        json.loads(settings_path.read_text()) if settings_path.exists() else {}
    )
    updated = _merge_cursor_entries(existing, entries)
    atomic_write_json(settings_path, updated)
    _record_entries(st, entries, updated, agent="cursor", item_version=item_version)


def _record_entries(
    st, entries: List[dict], updated: dict, *, agent: str, item_version: str
) -> None:
    for entry in entries:
        fp = fingerprint_hook(entry["payload"])
        arr = updated.get("hooks", {}).get(entry["event_key"], [])
        idx = next(
            (i for i, e in enumerate(arr) if fingerprint_hook(e) == fp),
            -1,
        )
        st.hooks_installed.append({
            "hook_id": entry["source_hook_id"],
            "agent": agent,
            "target_json_pointer": f"/hooks/{entry['event_key']}/{idx}",
            "content_fingerprint": fp,
            "version": item_version,
        })
