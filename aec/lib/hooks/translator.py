"""Event-vocabulary translator — spec §1.3 matrix.

Produces per-agent payloads from a `HooksFile`. Does NOT write to disk; the
installer consumes the structured output. Per P1-D10, the `match` field is
silently dropped in P1 (parsed by schema for forward compatibility).
"""

from typing import Dict, List, Optional

from .schema import AgentOverride, GenericHook, HooksFile


# Map of (event, agent) -> (event_key, matcher_or_None). None anywhere means skip.
_MATRIX: Dict[tuple, Optional[tuple]] = {
    ("on_file_edit", "claude"): ("PostToolUse", "Edit|Write|MultiEdit"),
    ("on_file_edit", "gemini"): ("AfterTool", "write_file|replace"),
    ("on_file_edit", "cursor"): ("afterFileEdit", None),
    ("on_file_edit", "git"): None,

    ("on_file_read", "claude"): ("PostToolUse", "Read"),
    ("on_file_read", "gemini"): ("AfterTool", "read_file"),
    ("on_file_read", "cursor"): None,
    ("on_file_read", "git"): None,

    ("pre_tool_use", "claude"): ("PreToolUse", None),
    ("pre_tool_use", "gemini"): ("BeforeTool", None),
    ("pre_tool_use", "cursor"): None,
    ("pre_tool_use", "git"): None,

    ("session_start", "claude"): ("SessionStart", None),
    ("session_start", "gemini"): ("SessionStart", None),
    ("session_start", "cursor"): None,
    ("session_start", "git"): None,

    ("pre_commit", "claude"): None,
    ("pre_commit", "gemini"): None,
    ("pre_commit", "cursor"): None,
    ("pre_commit", "git"): ("pre-commit", None),

    ("pre_push", "claude"): None,
    ("pre_push", "gemini"): None,
    ("pre_push", "cursor"): None,
    ("pre_push", "git"): ("pre-push", None),
}


def _translate_generic(
    h: GenericHook, agent: str, resolved_commands: Dict[str, str]
) -> Optional[dict]:
    mapping = _MATRIX.get((h.event, agent))
    if mapping is None:
        return None
    event_key, matcher = mapping
    cmd = resolved_commands.get(h.id, h.command)

    if agent in ("claude", "gemini"):
        payload: dict = {}
        if matcher is not None:
            payload["matcher"] = matcher
        hook_entry: dict = {"type": "command", "command": cmd}
        if h.timeout_ms and h.timeout_ms != 5000:
            hook_entry["timeout"] = int(h.timeout_ms / 1000)
        payload["hooks"] = [hook_entry]
    elif agent == "cursor":
        # Cursor's hook format — single command per entry with event
        payload = {"event": event_key, "command": cmd}
    elif agent == "git":
        # Git hooks translate to a single command for the named git hook
        payload = {"hook_name": event_key, "command": cmd}
    else:
        return None

    return {
        "event_key": event_key,
        "payload": payload,
        "source_hook_id": h.id,
        "blocking": h.blocking,
    }


def _passthrough_override(ov: AgentOverride) -> dict:
    payload = ov.payload or {}
    event_key = (
        payload.get("hook_name")
        or payload.get("event")
        or payload.get("matcher")
        or ""
    )
    return {
        "event_key": event_key,
        "payload": payload,
        "source_hook_id": ov.id or "",
        "blocking": bool(payload.get("blocking", False)),
    }


def translate_to_agent(
    hf: HooksFile,
    agent: str,
    resolved_commands: Dict[str, str],
) -> List[dict]:
    """Translate a HooksFile to a list of agent-native hook entries.

    Each entry is a dict of shape:
        {"event_key": str, "payload": dict,
         "source_hook_id": str, "blocking": bool}

    Generic hooks that don't apply to the target agent are dropped.
    Per-agent overrides for the same `agent` are appended verbatim.
    """
    if agent not in ("claude", "gemini", "cursor", "git"):
        raise ValueError(f"unknown agent: {agent!r}")

    entries: List[dict] = []
    for h in hf.hooks:
        translated = _translate_generic(h, agent, resolved_commands)
        if translated is not None:
            entries.append(translated)

    for ov in getattr(hf, agent, []):
        entries.append(_passthrough_override(ov))

    return entries
