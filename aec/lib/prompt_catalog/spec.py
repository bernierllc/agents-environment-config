"""The declarative shape of a single prompt.

Prompt *text* stays at the callsite — it carries runtime context (repo names,
detected viewers) that no static table can hold. What lives here is everything
an agent needs to answer the prompt without seeing it: its type, default,
choices, and whether it may be auto-answered at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class PromptSpec:
    """One catalogued prompt.

    Attributes:
        prompt_id: Stable dotted-path ID, matching the callsite.
        command: The ``aec`` command that asks it (e.g. ``"install"``).
        summary: One line describing what the answer controls.
        type: Type tag from the allow-list vocabulary (``yes_no``, ``path``,
            ``int[1..3650]``, ``enum[a,b]``, ...).
        default: Value used when ``--defaults`` is in play. ``None`` means the
            prompt has no safe default and must be answered explicitly.
        choices: Valid values for enum-typed prompts, when statically known.
        sensitive: True when the answer must always be explicit — destructive
            or security-relevant prompts that ``--defaults``/``--yes`` must not
            silently satisfy.
    """

    prompt_id: str
    command: str
    summary: str
    type: str = "string"
    default: Any = None
    choices: Optional[tuple] = None
    sensitive: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.prompt_id,
            "command": self.command,
            "summary": self.summary,
            "type": self.type,
            "default": self.default,
            "choices": list(self.choices) if self.choices else None,
            "sensitive": self.sensitive,
        }


@dataclass
class DynamicPromptFamily:
    """A prompt family whose concrete IDs depend on runtime registries.

    ``expand`` is called at listing time to produce concrete specs; it is kept
    lazy so importing the catalog never touches preferences on disk.
    """

    prefix: str
    command: str
    summary: str
    type: str = "yes_no"
    expander: Any = field(default=None)

    def expand(self) -> list:
        if self.expander is None:
            return []
        return list(self.expander(self))
