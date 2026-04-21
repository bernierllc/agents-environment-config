"""hooks.json schema — dataclasses and loader.

Provides strongly-typed dataclasses for the hooks.json authoring surface and
a loader that parses JSON into them. Validation beyond basic shape/type checks
lives in validator.py.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional


class HooksSchemaError(ValueError):
    """Raised when a hooks.json file cannot be parsed into the schema."""


GENERIC_EVENTS = frozenset({
    "on_file_edit",
    "on_file_read",
    "pre_tool_use",
    "session_start",
    "pre_commit",
    "pre_push",
})


@dataclass
class WhenPredicate:
    repo_has: List[str] = field(default_factory=list)
    repo_has_any: List[str] = field(default_factory=list)
    repo_lacks: List[str] = field(default_factory=list)
    custom_check: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["WhenPredicate"]:
        if data is None:
            return None
        return cls(
            repo_has=list(data.get("repo_has", []) or []),
            repo_has_any=list(data.get("repo_has_any", []) or []),
            repo_lacks=list(data.get("repo_lacks", []) or []),
            custom_check=data.get("custom_check"),
        )


@dataclass
class GenericHook:
    id: str
    event: str
    command: str
    description: str
    # Reserved for v2: a glob whose interpretation depends on event. Parsed but
    # NOT surfaced by the P1 translator. See plan decision P1-D10.
    match: Optional[str] = None
    blocking: bool = False
    timeout_ms: int = 5000
    when: Optional[WhenPredicate] = None

    @classmethod
    def from_dict(cls, data: dict) -> "GenericHook":
        try:
            return cls(
                id=data["id"],
                event=data["event"],
                command=data["command"],
                description=data["description"],
                match=data.get("match"),
                blocking=bool(data.get("blocking", False)),
                timeout_ms=int(data.get("timeout_ms", 5000)),
                when=WhenPredicate.from_dict(data.get("when")),
            )
        except KeyError as e:
            raise HooksSchemaError(f"GenericHook missing required field: {e}") from e


@dataclass
class AgentOverride:
    """Raw per-agent hook payload, passed through verbatim by the translator."""
    agent: str  # "claude" | "cursor" | "gemini" | "git"
    payload: dict
    id: Optional[str] = None


@dataclass
class HooksFile:
    version: str
    hooks: List[GenericHook] = field(default_factory=list)
    claude: List[AgentOverride] = field(default_factory=list)
    cursor: List[AgentOverride] = field(default_factory=list)
    gemini: List[AgentOverride] = field(default_factory=list)
    git: List[AgentOverride] = field(default_factory=list)
    schema_url: Optional[str] = None
    source_path: Optional[Path] = None


def load_hooks_file(path: Path) -> HooksFile:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HooksSchemaError(f"{path}: invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise HooksSchemaError(f"{path}: top-level must be an object")
    if "version" not in data:
        raise HooksSchemaError(f"{path}: missing required field 'version'")

    generic = [GenericHook.from_dict(h) for h in data.get("hooks", []) or []]

    def _overrides(key: str) -> List[AgentOverride]:
        raw_list = data.get(key, []) or []
        return [
            AgentOverride(agent=key, payload=item, id=item.get("id"))
            for item in raw_list
        ]

    return HooksFile(
        version=str(data["version"]),
        hooks=generic,
        claude=_overrides("claude"),
        cursor=_overrides("cursor"),
        gemini=_overrides("gemini"),
        git=_overrides("git"),
        schema_url=data.get("$schema"),
        source_path=path,
    )
