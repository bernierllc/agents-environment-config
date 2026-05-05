"""Prompt helper that provides a single seam for org-config pre-answering.

Phase 1 of the org-config overlay only establishes the interface. The
overlay applier that actually pre-answers prompts arrives in a later phase.
For now `prompt()` simply delegates to ``input()``, but every interactive
callsite in install/setup/preferences has been refactored to call through
this helper with a stable ``prompt_id``. That stability is what later
phases rely on to look up overlay answers.

The helper is intentionally minimal in Phase 1; later phases will:
  1) consult an in-process registry populated by the overlay loader,
  2) run the supplied ``validator`` against any pre-answered value, and
  3) emit ``Console.info("Pre-answered by org config: ...")``.

The signature already accepts ``prompt_id``, expected ``type``, ``default``,
and ``validator`` so downstream phases need not touch every callsite again.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


def prompt(
    prompt_id: str,
    prompt_text: str,
    *,
    type: str = "string",  # noqa: A002 - intentional: matches doc surface
    default: Any = None,
    validator: Optional[Callable[[str], Any]] = None,
) -> str:
    """Read a line from the user, optionally pre-answered by an org overlay.

    Phase 1 behaviour:
      - Always falls through to ``input(prompt_text)``.
      - On EOF, returns ``""`` (callers handle defaults — same as the
        pre-refactor inline ``try/except EOFError`` blocks).

    Args:
        prompt_id: Stable dotted-path ID from ``aec.lib.prompt_ids``. The
            overlay applier (later phase) uses this ID to look up a pre-
            answered value.
        prompt_text: The text shown to the user when no overlay answer is
            available.
        type: Expected logical type of the answer (``"string"``, ``"bool"``,
            ``"int"``, ``"enum"``, ``"path"``). Phase 1 records this on the
            interface but does not act on it.
        default: Default value to surface if the user just presses Enter.
            Callers continue to apply their own default logic in Phase 1;
            this argument exists so later phases can centralize it.
        validator: Optional callable that the overlay applier (later phase)
            will run against pre-answered values before returning them.
            Phase 1 does not invoke it.

    Returns:
        The raw user input as a string. Callers convert/validate it the
        same way they did before the refactor — Phase 1 deliberately does
        not change observable behaviour.
    """
    # Reference the parameters so static checkers don't flag them as unused;
    # later phases consume them.
    _ = (prompt_id, type, default, validator)
    try:
        return input(prompt_text)
    except EOFError:
        return ""
