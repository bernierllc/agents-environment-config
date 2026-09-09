"""Hook installation orchestrator.

Pure merge helpers live here alongside the `install_item_hooks` /
`remove_item_hooks` entrypoints. The helpers operate on plain dicts with no
I/O so they can be tested in isolation — this file grows across Tasks 9a-9g.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Dict, List, Sequence

from ..atomic_write import atomic_write_json
from ..console import Console
from . import git_blocks, state as hook_state
from .fingerprint import fingerprint_hook
from .git_hooks_path import HUSKY_V8_BOOTSTRAP, resolve_hooks_dir
from .predicates import evaluate_when
from .schema import HooksFile, load_hooks_file
from .translator import translate_to_agent
from .validator import validate_hooks_file


_RUN_SCRIPT_PREFIX = "aec run-script"

# Per-agent config directory a hook write lands under. Cursor/Claude/Gemini all
# expect a *directory* here; a stray file at the same path (e.g. a hand-written
# `.cursor` JSON, which Cursor itself never reads — it uses a `.cursor/` dir)
# makes mkdir(exist_ok=True) raise [Errno 17]. We skip that agent rather than
# crash or clobber the user's file. `aec doctor` surfaces the same conflict.
_AGENT_CONFIG_DIR = {"claude": ".claude", "gemini": ".gemini", "cursor": ".cursor"}


def config_dir_blocked(repo_root: Path, agent: str) -> Path | None:
    """Return the conflicting path if `agent`'s config dir is occupied by a
    non-directory (a file where a directory is expected), else None."""
    rel = _AGENT_CONFIG_DIR.get(agent)
    if rel is None:
        return None
    path = repo_root / rel
    return path if path.exists() and not path.is_dir() else None


def _is_repo_local(script_path: Path, repo_root: Path) -> bool:
    """True if `script_path` lives inside `repo_root`."""
    try:
        script_path.relative_to(repo_root)
    except ValueError:
        return False
    return True


# How a resolved script path is written into each agent's config. Claude Code
# exports $CLAUDE_PROJECT_DIR, so a repo-local script can be addressed
# portably — the same settings.json then works in a clone, a worktree, or on a
# teammate's machine. Git hooks run with cwd at the repo root, so a plain
# relative path is enough there. gemini/cursor expose no verified project-dir
# variable, so they keep the absolute path.
# ponytail: per-agent rendering, not a plugin registry — add one when a fourth
# agent needs a third rendering.
def _render_script_path(script_path: Path, repo_root: Path, agent: str) -> str:
    """Render `script_path` the way `agent` should see it."""
    try:
        rel = script_path.relative_to(repo_root)
    except ValueError:
        # Global install (or otherwise outside the repo): absolute is the only
        # thing that resolves.
        return shlex.quote(str(script_path))
    if agent == "claude":
        return '"$CLAUDE_PROJECT_DIR"/' + shlex.quote(str(rel))
    if agent == "git":
        return shlex.quote(str(rel))
    return shlex.quote(str(script_path))


# Skill/agent/rule sources are frequently untracked (a repo may gitignore
# `.claude/`, or simply never have committed the installed skill), while
# settings.json IS tracked. A clone then wires a hook to a file that isn't
# there and every matching edit fails with 127. Guarding on the interpreter's
# own terms keeps the hook dormant instead of broken.
#
# `if ...; then ...; fi` rather than `[ -x P ] && P`: the latter exits 1 when
# the file is absent, which Claude Code reports as a failed hook.
GUARD_PREFIX = "if [ -x "

# Agents whose command string is evaluated by a POSIX shell. claude runs hooks
# through `sh -c`; git hooks ARE shell scripts. cursor/gemini render absolute
# paths (already checkout-specific) and their execution model isn't documented
# as shell, so they stay unguarded.
_SHELL_GUARD_AGENTS = frozenset({"claude", "git"})


def guard_script_command(rendered_path: str, command: str) -> str:
    """Wrap `command` so it only runs when `rendered_path` is executable."""
    return f"{GUARD_PREFIX}{rendered_path} ]; then {command}; fi"


def is_guarded(command: str) -> bool:
    """True if `command` already carries the missing-script guard."""
    return command.startswith(GUARD_PREFIX)


def _resolve_script_commands(
    hf, item_dir: Path, repo_root: Path, agent: str
) -> Dict[str, str]:
    """Rewrite `aec run-script <item> <script> [args...]` to a real path.

    Looks for `<item_dir>/scripts/<script>`. Raises FileNotFoundError if the
    referenced script does not exist. The rendering is agent-specific — see
    `_render_script_path`.
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
                # The rendered command execs the script directly, so it has to
                # carry its exec bit. `aec run-script` chmods on the way through;
                # this path has to do the same or a 0644 script (git only tracks
                # +x, and skills ship plenty of 0644 ones) fails with EACCES.
                if not os.access(script_path, os.X_OK):
                    try:
                        script_path.chmod(script_path.stat().st_mode | 0o111)
                    except OSError:
                        pass
                rendered = _render_script_path(script_path, repo_root, agent)
                pieces = [rendered]
                pieces += [shlex.quote(p) for p in extra]
                cmd = " ".join(pieces)
                if agent in _SHELL_GUARD_AGENTS and _is_repo_local(
                    script_path, repo_root
                ):
                    cmd = guard_script_command(rendered, cmd)
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

    st = hook_state.load_state(repo_root, item_type=item_type, item_key=item_key)

    # Retract whatever the previous install of this item put in the agent config
    # files before merging the new payloads. The merge only dedupes on an exact
    # content fingerprint, so without this a hook whose command changed (a
    # version bump in an argument, say) leaves the old entry behind AND appends
    # the new one — and the stale copy keeps firing.
    _remove_recorded_hooks(
        repo_root, st.hooks_installed, item_type=item_type, item_key=item_key,
    )

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
        blocked = config_dir_blocked(repo_root, agent)
        if blocked is not None:
            reason = f"{blocked} is a file, not the {agent} config directory"
            st.hooks_skipped.append({"agent": agent, "reason": reason})
            Console.warning(
                f"skipping {agent} hooks: {reason}. Move it aside "
                f"(e.g. `mv {blocked} {blocked}.bak`) to enable {agent} hooks."
            )
            continue
        resolved = _resolve_script_commands(hf, item_dir, repo_root, agent)
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


def _remove_recorded_hooks(
    repo_root: Path, hooks_installed: List[dict], *, item_type: str, item_key: str,
) -> None:
    """Delete every hook payload recorded in state from its agent config file."""
    for installed in hooks_installed:
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


def remove_item_hooks(
    *, item_type: str, item_key: str, repo_root: Path,
) -> None:
    """Remove an item's hooks from all recorded agents, then drop state."""
    st = hook_state.load_state(repo_root, item_type=item_type, item_key=item_key)
    _remove_recorded_hooks(
        repo_root, st.hooks_installed, item_type=item_type, item_key=item_key,
    )
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
    resolution = resolve_hooks_dir(repo_root)
    hooks_dir = resolution.hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)
    header_line = HUSKY_V8_BOOTSTRAP if resolution.needs_v8_bootstrap else ""
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
            header_line=header_line,
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
    hooks_dir = resolve_hooks_dir(repo_root).hooks_dir
    hook_file = hooks_dir / event_key
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
