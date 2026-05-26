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

# In-process registry of org-overlay pre-answers, keyed by prompt_id. Populated
# by the overlay applier (aec.lib.org_config.apply) before an install/setup run
# and cleared afterward. Empty by default, so absent any overlay the seam
# behaves exactly like a bare input() prompt.
_OVERLAY_ANSWERS: dict[str, Any] = {}


def set_overlay_answers(answers: dict[str, Any]) -> None:
    """Install org-overlay pre-answers consulted by ``prompt()``."""
    _OVERLAY_ANSWERS.clear()
    _OVERLAY_ANSWERS.update(answers)


def clear_overlay_answers() -> None:
    _OVERLAY_ANSWERS.clear()


def _coerce(value: Any, type: str) -> Any:  # noqa: A002 - matches doc surface
    if type == "bool" and isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    if type == "int" and not isinstance(value, bool):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def prompt(
    prompt_id: str,
    prompt_text: str,
    *,
    type: str = "string",  # noqa: A002 - intentional: matches doc surface
    default: Any = None,
    validator: Optional[Callable[[str], Any]] = None,
) -> str:
    """Read a line from the user, optionally pre-answered by an org overlay.

    If the overlay registry holds an answer for ``prompt_id``, it is coerced to
    ``type``, passed through ``validator`` (if any), announced, and returned
    without prompting. Otherwise this falls through to ``input(prompt_text)``
    (returning ``""`` on EOF, as before).

    Args:
        prompt_id: Stable dotted-path ID from ``aec.lib.prompt_ids``.
        prompt_text: Text shown when no overlay answer is available.
        type: Logical type (``"string"``/``"bool"``/``"int"``/``"enum"``/``"path"``).
        default: Default surfaced on empty input (callers still apply their own).
        validator: Optional callable run against the (pre-)answered value.
    """
    if prompt_id in _OVERLAY_ANSWERS:
        from .console import Console

        value = _coerce(_OVERLAY_ANSWERS[prompt_id], type)
        if validator is not None:
            value = validator(value if isinstance(value, str) else str(value))
        Console.info(f"Pre-answered by org config: {prompt_id}")
        return value

    _ = (default,)
    try:
        return input(prompt_text)
    except EOFError:
        return ""
