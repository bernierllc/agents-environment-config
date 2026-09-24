"""Single seam every interactive AEC prompt goes through.

A human and an agent get the same contract: a typed answer is validated
exactly like a supplied one. Yes/no answers accept y/yes/n/no in any case and
come back as ``"y"``/``"n"``; Enter takes the declared default; an answer that
is not a valid yes/no, int, or one of ``choices`` re-asks instead of silently
falling through to whatever branch the callsite happens to use for "other".

What this module also adds is a way for an *agent* to drive AEC unattended:

  1. Discover the questions ahead of time — every callsite declares a stable
     ``prompt_id`` catalogued in :mod:`aec.lib.prompt_catalog`, surfaced by
     ``aec prompts list``.
  2. Answer them — via an org-config overlay, an ``--answers`` JSON file, or
     ``AEC_ANSWER_<ID>`` environment variables.
  3. Fail loudly when an answer is missing rather than silently taking a
     default and performing a side effect nobody approved.

Answer precedence, highest first:

  1. Org-config overlay answers (``set_overlay_answers``)
  2. Explicit answers (``set_answers`` / ``--answers`` / ``AEC_ANSWERS`` /
     ``AEC_ANSWER_<ID>``)
  3. Interactive ``input()`` — only when attached to a TTY
  4. The declared default — only when ``--defaults``/``--yes`` was passed

``prompt()`` always returns a ``str``, already normalized: callsites compare
against canonical values (``"y"``, ``"n"``, a choice) and never see "" for a
prompt that declares a default.

Hint conventions (enforced by ``tests/test_prompt_conventions.py``): yes/no
prompts end with ``yes_no_hint(default)`` (``[Y/n]`` / ``[y/N]``), and every
prompt with a default shows it in brackets, e.g. ``Choice [1]:``.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional


class PromptUnanswered(Exception):
    """Raised when a prompt cannot be answered without a human.

    Carries the prompt ID so the CLI can tell an agent exactly which key to
    add to its answers file.
    """

    def __init__(self, prompt_id: str, reason: str, *, sensitive: bool = False):
        self.prompt_id = prompt_id
        self.reason = reason
        self.sensitive = sensitive
        super().__init__(f"{prompt_id}: {reason}")


class PromptInvalidAnswer(Exception):
    """Raised when a supplied answer does not satisfy the prompt's type."""

    def __init__(self, prompt_id: str, value: Any, expected: str):
        self.prompt_id = prompt_id
        self.value = value
        self.expected = expected
        super().__init__(f"{prompt_id}: {value!r} is not a valid {expected}")


# --- Answer registries ------------------------------------------------------
#
# Two registries, deliberately separate: the org overlay is policy pushed by an
# administrator and outranks the answers a local caller supplies.

_OVERLAY_ANSWERS: dict[str, Any] = {}
_ANSWERS: dict[str, Any] = {}

# Runtime mode, set once by the CLI entry point from global options.
_NON_INTERACTIVE: Optional[bool] = None
_USE_DEFAULTS: bool = False


def set_overlay_answers(answers: dict[str, Any]) -> None:
    """Install org-overlay pre-answers consulted by ``prompt()``."""
    _OVERLAY_ANSWERS.clear()
    _OVERLAY_ANSWERS.update(answers)


def clear_overlay_answers() -> None:
    _OVERLAY_ANSWERS.clear()


def set_answers(answers: dict[str, Any]) -> None:
    """Install caller-supplied answers (``--answers`` file or API use)."""
    _ANSWERS.clear()
    _ANSWERS.update(answers)


def clear_answers() -> None:
    _ANSWERS.clear()


def set_mode(*, non_interactive: Optional[bool] = None, use_defaults: Optional[bool] = None) -> None:
    """Set the process-wide prompting mode from CLI global options."""
    global _NON_INTERACTIVE, _USE_DEFAULTS
    if non_interactive is not None:
        _NON_INTERACTIVE = non_interactive
    if use_defaults is not None:
        _USE_DEFAULTS = use_defaults


def reset_mode() -> None:
    global _NON_INTERACTIVE, _USE_DEFAULTS
    _NON_INTERACTIVE = None
    _USE_DEFAULTS = False


def is_non_interactive() -> bool:
    """True when we must not call ``input()`` at all.

    Only an explicit signal counts — ``--non-interactive`` or
    ``AEC_NONINTERACTIVE``. We deliberately do *not* infer this from
    ``stdin.isatty()``: piping answers in (``printf 'y\n' | aec install``) is a
    legitimate way to drive AEC, and a non-TTY stdin still has answers to read.
    A genuinely closed stdin surfaces as ``EOFError``, which ``prompt()``
    routes to the same strict-failure path as this flag.
    """
    if _NON_INTERACTIVE is not None:
        return _NON_INTERACTIVE
    return _env_flag("AEC_NONINTERACTIVE")


def use_defaults() -> bool:
    return _USE_DEFAULTS or _env_flag("AEC_USE_DEFAULTS")


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def env_var_name(prompt_id: str) -> str:
    """``install.settings.plans_dir`` -> ``AEC_ANSWER_INSTALL_SETTINGS_PLANS_DIR``."""
    return "AEC_ANSWER_" + prompt_id.replace(".", "_").replace("-", "_").upper()


def load_answers_file(path) -> dict[str, Any]:
    """Read an answers JSON file: a flat ``{prompt_id: value}`` mapping."""
    import json
    from pathlib import Path

    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Answers file not found: {p}")
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Answers file is not valid JSON: {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Answers file must be a JSON object of prompt_id -> value: {p}")
    return data


def _lookup_answer(prompt_id: str) -> tuple[bool, Any, str]:
    """Find an answer for ``prompt_id``. Returns ``(found, value, source)``."""
    if prompt_id in _OVERLAY_ANSWERS:
        return True, _OVERLAY_ANSWERS[prompt_id], "org config"
    if prompt_id in _ANSWERS:
        return True, _ANSWERS[prompt_id], "answers file"
    env_value = os.environ.get(env_var_name(prompt_id))
    if env_value is not None:
        return True, env_value, "environment"
    return False, None, ""


# --- Normalization ----------------------------------------------------------
#
# Callsites parse the return value as if the user had typed it (`.strip()`,
# `.lower()`, `in ("y", "yes")`, `int(...)`). So every answer — whatever its
# JSON type — is normalized back into the string a user would have typed.

_TRUTHY = ("1", "true", "yes", "y", "on")
_FALSY = ("0", "false", "no", "n", "off")


def normalize(value: Any, type: str) -> str:  # noqa: A002 - matches doc surface
    """Render an answer as the string an interactive user would have typed."""
    base = (type or "string").split("[", 1)[0]

    if base in ("yes_no", "bool"):
        if isinstance(value, bool):
            return "y" if value else "n"
        text = str(value).strip().lower()
        if text in _TRUTHY:
            return "y"
        if text in _FALSY:
            return "n"
        raise PromptInvalidAnswer("", value, "yes/no")

    if base == "int":
        if isinstance(value, bool):
            raise PromptInvalidAnswer("", value, "int")
        try:
            return str(int(str(value).strip()))
        except (TypeError, ValueError) as exc:
            raise PromptInvalidAnswer("", value, "int") from exc

    if isinstance(value, bool):
        return "y" if value else "n"
    return str(value)


# Re-asks before giving up on a human who keeps typing invalid answers (also
# bounds a pipe that feeds the same bad line forever).
_MAX_TYPED_ATTEMPTS = 5


def yes_no_hint(default: bool) -> str:
    """The standard hint for a yes/no prompt: ``[Y/n]`` or ``[y/N]``."""
    return "[Y/n]" if default else "[y/N]"


def selection_validator(count: int, *, allow_empty: bool = False) -> Callable[[str], str]:
    """Validator for "comma-separated numbers, 'all', or 'none'" menus.

    Accepts ``all``/``a``, ``none``/``n``, and comma-separated numbers or
    ranges (``1,3,5-8``) within ``1..count``. Returns the answer lowercased;
    raises ``ValueError`` naming the bad token so the user is re-asked rather
    than having typos silently dropped.
    """

    def _validate(value: str) -> str:
        text = value.strip().lower()
        if text in ("all", "a", "none", "n") or (allow_empty and text == ""):
            return text
        if text == "":
            raise ValueError("enter numbers, 'all', or 'none'")
        for part in text.split(","):
            part = part.strip()
            bounds = part.split("-", 1) if "-" in part else [part, part]
            try:
                lo, hi = int(bounds[0]), int(bounds[1])
            except ValueError:
                raise ValueError(f"{part!r} is not a number, range, 'all', or 'none'") from None
            if not (1 <= lo <= hi <= count):
                raise ValueError(f"{part!r} is out of range (1-{count})")
        return text

    return _validate


def parse_selection(text: str, count: int) -> list:
    """Parse an answer accepted by ``selection_validator`` into sorted 1-based
    indices. ``all``/``a`` selects everything; ``none``/``n``/"" selects nothing."""
    text = text.strip().lower()
    if text in ("all", "a"):
        return list(range(1, count + 1))
    if text in ("none", "n", ""):
        return []
    picked = set()
    for part in text.split(","):
        part = part.strip()
        lo, _, hi = part.partition("-")
        try:
            span = range(int(lo), int(hi or lo) + 1)
        except ValueError:
            continue  # unreachable after selection_validator; tolerated for direct callers
        picked.update(i for i in span if 1 <= i <= count)
    return sorted(picked)


def _coerce_typed(raw: str, type: str, default: Any, choices: Optional[list]) -> str:  # noqa: A002
    """Turn a line a human typed into the canonical answer, or raise
    ``PromptInvalidAnswer`` with a message fit to show before re-asking."""
    text = raw.strip()
    if text == "":
        if default is None:
            return ""
        text = normalize(default, type)
    else:
        text = normalize(text, type)
    if choices:
        allowed = [str(c) for c in choices]
        if text in allowed:
            return text
        folded = [c for c in allowed if c.lower() == text.lower()]
        if len(folded) == 1:
            return folded[0]
        shown = ", ".join(c for c in allowed if c != "")
        raise PromptInvalidAnswer("", text, f"choice (one of {shown})")
    return text


def prompt(
    prompt_id: str,
    prompt_text: str,
    *,
    type: str = "string",  # noqa: A002 - intentional: matches doc surface
    default: Any = None,
    validator: Optional[Callable[[str], Any]] = None,
    sensitive: bool = False,
    choices: Optional[list] = None,
) -> str:
    """Ask ``prompt_text``, or return a pre-supplied answer for ``prompt_id``.

    Args:
        prompt_id: Stable dotted-path ID, catalogued in ``aec.lib.prompt_catalog``.
        prompt_text: Text shown when a human answers.
        type: Logical type (``"string"``/``"yes_no"``/``"int"``/``"enum"``/``"path"``).
        default: Value used when the user submits an empty line, and the value
            ``--defaults`` falls back to. ``None`` means the prompt has no
            default and must be answered explicitly.
        validator: Optional callable run against the answer.
        sensitive: When True the answer must be supplied explicitly — never
            satisfied by ``--defaults``/``--yes``. Used for destructive actions
            and security acknowledgements.
        choices: Valid values for enum-typed prompts.

    Raises:
        PromptUnanswered: No human is available and no answer was supplied.
        PromptInvalidAnswer: A supplied answer does not satisfy ``type``.
    """
    found, raw, source = _lookup_answer(prompt_id)

    if found:
        try:
            value = normalize(raw, type)
        except PromptInvalidAnswer as exc:
            raise PromptInvalidAnswer(prompt_id, exc.value, exc.expected) from exc
        _check_choices(prompt_id, value, choices)
        value = _run_validator(prompt_id, value, validator)
        from .console import Console

        Console.info(f"Pre-answered by {source}: {prompt_id}")
        return value

    if not is_non_interactive():
        from .console import Console

        for _attempt in range(_MAX_TYPED_ATTEMPTS):
            try:
                raw = input(prompt_text)
            except EOFError:
                # stdin closed mid-run. Treat exactly like the non-interactive
                # path rather than silently returning "" and defaulting.
                return _unanswered(prompt_id, type, default, sensitive, validator, choices)
            try:
                value = _coerce_typed(raw, type, default, choices)
                return validator(value) if validator is not None else value
            except PromptInvalidAnswer as exc:
                Console.warning(f"{exc.value!r} is not a valid {exc.expected}. Try again.")
            except ValueError as exc:
                Console.warning(f"{exc}. Try again.")
        raise PromptInvalidAnswer(prompt_id, raw, f"answer after {_MAX_TYPED_ATTEMPTS} attempts")

    return _unanswered(prompt_id, type, default, sensitive, validator, choices)


def _unanswered(prompt_id, type, default, sensitive, validator, choices) -> str:  # noqa: A002
    """No human, no supplied answer: use the default or fail with a usable message."""
    if sensitive:
        raise PromptUnanswered(
            prompt_id,
            "this prompt is marked sensitive and must be answered explicitly "
            "(--defaults and --yes will not answer it)",
            sensitive=True,
        )
    if default is None:
        raise PromptUnanswered(prompt_id, "no answer supplied and this prompt has no default")
    if not use_defaults():
        raise PromptUnanswered(
            prompt_id,
            f"no answer supplied (default would be {default!r}); "
            "pass --defaults to accept defaults",
        )

    value = normalize(default, type)
    _check_choices(prompt_id, value, choices)
    value = _run_validator(prompt_id, value, validator)
    from .console import Console

    Console.info(f"Defaulted: {prompt_id} = {value}")
    return value


def _run_validator(prompt_id: str, value: str, validator: Optional[Callable[[str], Any]]) -> Any:
    """Run ``validator``; a ``ValueError`` becomes ``PromptInvalidAnswer``."""
    if validator is None:
        return value
    try:
        return validator(value)
    except PromptInvalidAnswer:
        raise
    except ValueError as exc:
        raise PromptInvalidAnswer(prompt_id, value, str(exc) or "answer") from exc


def _check_choices(prompt_id: str, value: str, choices: Optional[list]) -> None:
    if not choices:
        return
    allowed = [str(c) for c in choices]
    if value not in allowed:
        raise PromptInvalidAnswer(prompt_id, value, f"one of {', '.join(allowed)}")
