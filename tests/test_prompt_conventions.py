"""Prompt conventions: what a prompt *shows* must match how its answer is *parsed*.

Every bug this file guards against shipped because the question text and the
answer handling were written separately and nothing compared them:

  * a numbered "1) Yes / 2) No" menu routed through a yes/no parser, so "2"
    silently meant yes;
  * ``[a]ll, [s]elect, [S]kip`` lowercased before comparison, so "S" (skip)
    selected;
  * ``(Y/n)`` shown on a prompt whose default was False;
  * yes/no callsites comparing ``== "y"``, so a typed "yes" meant no.

Two layers:

1. Seam behavior -- a *typed* answer gets the same validation and
   normalization as a supplied one (the root cause of the last bug above).
2. Static conventions -- every ``prompt()`` callsite in ``aec/`` is read with
   ``ast`` and its text is checked against its declared type/default/choices,
   and against the catalog. New prompts are covered automatically.
"""

from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pytest

from aec.lib import prompts
from aec.lib.prompts import (
    PromptInvalidAnswer,
    parse_selection,
    prompt,
    selection_validator,
    yes_no_hint,
)

from tests.test_prompt_catalog_drift import PKG, SEAM_NAMES, SKIP, _module_name, _name_bindings


@pytest.fixture(autouse=True)
def _clean_prompt_state(monkeypatch):
    prompts.clear_answers()
    prompts.clear_overlay_answers()
    prompts.reset_mode()
    for key in list(__import__("os").environ):
        if key.startswith("AEC_ANSWER") or key in ("AEC_NONINTERACTIVE", "AEC_USE_DEFAULTS"):
            monkeypatch.delenv(key, raising=False)
    yield
    prompts.clear_answers()
    prompts.reset_mode()


def _typed(monkeypatch, *lines):
    it = iter(lines)
    monkeypatch.setattr(builtins, "input", lambda _text="": next(it))


# --- 1. Seam behavior for typed answers ------------------------------------


@pytest.mark.parametrize("typed,expected", [
    ("y", "y"), ("Y", "y"), ("yes", "y"), ("YES", "y"), (" Yes ", "y"),
    ("n", "n"), ("N", "n"), ("no", "n"), ("No", "n"),
])
def test_typed_yes_no_is_normalized(monkeypatch, typed, expected):
    _typed(monkeypatch, typed)
    assert prompt("q", "? [y/N]: ", type="yes_no", default=False) == expected


@pytest.mark.parametrize("default,expected", [(True, "y"), (False, "n")])
def test_enter_takes_the_declared_default(monkeypatch, default, expected):
    _typed(monkeypatch, "")
    assert prompt("q", "? ", type="yes_no", default=default) == expected


def test_invalid_yes_no_reasks_instead_of_defaulting(monkeypatch):
    # "2" used to fall through to the default (yes) without a word.
    _typed(monkeypatch, "2", "maybe", "n")
    assert prompt("q", "? [Y/n]: ", type="yes_no", default=True) == "n"


def test_choices_are_enforced_for_typed_answers(monkeypatch):
    _typed(monkeypatch, "7", "3")
    assert prompt("q", "Choice [1]: ", default="1", choices=["1", "2", "3"]) == "3"


def test_choices_fold_case_only_when_unambiguous(monkeypatch):
    _typed(monkeypatch, "A")
    assert prompt("q", "? ", default="k", choices=["a", "s", "k"]) == "a"
    _typed(monkeypatch, "S")
    assert prompt("q", "? ", default="s", choices=["s", "S"]) == "S"


def test_enter_on_a_choice_prompt_returns_the_default(monkeypatch):
    _typed(monkeypatch, "")
    assert prompt("q", "Choice [2]: ", default="2", choices=["1", "2"]) == "2"


def test_enter_without_default_is_checked_against_choices(monkeypatch):
    _typed(monkeypatch, "", "2")
    assert prompt("q", "Choice: ", choices=["1", "2"]) == "2"


def test_typed_int_is_validated(monkeypatch):
    _typed(monkeypatch, "thirty", "30")
    assert prompt("q", "Days [7]: ", type="int", default=7) == "30"


def test_typed_answer_runs_the_validator_and_reasks(monkeypatch):
    _typed(monkeypatch, "1,9", "1,2")
    assert prompt("q", "? [all]: ", default="all", validator=selection_validator(3)) == "1,2"


def test_endless_invalid_answers_give_up(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _text="": "garbage")
    with pytest.raises(PromptInvalidAnswer):
        prompt("q", "? [y/N]: ", type="yes_no", default=False)


@pytest.mark.parametrize("text,count,expected", [
    ("all", 3, [1, 2, 3]), ("a", 2, [1, 2]), ("none", 3, []), ("n", 3, []),
    ("1,3", 3, [1, 3]), ("2-3", 3, [2, 3]), ("3,1,1", 3, [1, 3]),
])
def test_parse_selection(text, count, expected):
    assert parse_selection(text, count) == expected


@pytest.mark.parametrize("bad", ["0", "4", "x", "1,,2", "2-9", "-1"])
def test_selection_validator_rejects(bad):
    with pytest.raises(ValueError):
        selection_validator(3)(bad)


# --- 2. Static conventions over every callsite -----------------------------


@dataclass
class Site:
    where: str
    prompt_id: Optional[str]
    text: Optional[str]  # f-string holes rendered as "{}"; None if not static
    hint_call: bool  # text interpolates yes_no_hint(...)
    type: str
    default: Any  # _DYNAMIC when not a literal
    has_default: bool
    choices: Any  # list, None, or _DYNAMIC
    has_validator: bool = False


_DYNAMIC = object()


def _render(node) -> tuple[Optional[str], bool]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if isinstance(node, ast.JoinedStr):
        parts, hint = [], False
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v.value)
            else:
                call = v.value
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                        and call.func.id == "yes_no_hint"):
                    hint = True
                parts.append("{}")
        return "".join(parts), hint
    return None, False


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return _DYNAMIC


def _enclosing_functions(tree) -> dict:
    """{id(node): innermost enclosing FunctionDef} for every node in ``tree``."""
    owner = {}

    def visit(node, fn):
        for child in ast.iter_child_nodes(node):
            inner = child if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            owner[id(child)] = fn
            visit(child, inner)

    visit(tree, None)
    return owner


def _text_variants(node, fn) -> list:
    """The static texts ``node`` can evaluate to: a literal/f-string, either arm
    of a conditional, or whatever a local variable was assigned."""
    if isinstance(node, ast.IfExp):
        return _text_variants(node.body, fn) + _text_variants(node.orelse, fn)
    if isinstance(node, ast.Name) and fn is not None:
        found = []
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == node.id for t in sub.targets
            ):
                found += _text_variants(sub.value, fn)
        return found
    text, hint = _render(node)
    return [(text, hint)] if text is not None else []


def _site(path, node, pid, text, hint, kw) -> Site:
    return Site(
        where=f"{path.relative_to(PKG.parent)}:{node.lineno}",
        prompt_id=pid,
        text=text,
        hint_call=hint,
        type=_literal(kw["type"]) if "type" in kw else "string",
        default=_literal(kw["default"]) if "default" in kw else None,
        has_default="default" in kw,
        choices=_literal(kw["choices"]) if "choices" in kw else None,
        has_validator="validator" in kw,
    )


def _sites() -> list[Site]:
    out = []
    for path in sorted(PKG.rglob("*.py")):
        if path in SKIP or any(p in SKIP for p in path.parents):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bindings = _name_bindings(tree, _module_name(path))
        owner = _enclosing_functions(tree)
        # name -> (index of the text parameter, seam keywords) for local
        # wrappers like ``def _confirm(prompt_id, text): return prompt(..., text, ...)``
        wrappers = {}
        seam_calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in SEAM_NAMES and len(n.args) >= 2
        ]
        for node in seam_calls:
            arg0 = node.args[0]
            pid = (arg0.value if isinstance(arg0, ast.Constant)
                   else bindings.get(arg0.id) if isinstance(arg0, ast.Name) else None)
            kw = {k.arg: k.value for k in node.keywords}
            fn = owner.get(id(node))
            text_arg = node.args[1]
            params = [a.arg for a in fn.args.args] if fn is not None else []
            if isinstance(text_arg, ast.Name) and text_arg.id in params:
                wrappers[fn.name] = (params.index(text_arg.id), kw)
                continue
            variants = _text_variants(text_arg, fn) or [(None, False)]
            for text, hint in variants:
                out.append(_site(path, node, pid, text, hint, kw))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in wrappers):
                idx, kw = wrappers[node.func.id]
                if len(node.args) > idx:
                    for text, hint in _text_variants(node.args[idx], owner.get(id(node))) or [(None, False)]:
                        out.append(_site(path, node, None, text, hint, kw))
    return out


def _optional_feature_sites() -> list[Site]:
    from aec.lib.preferences import OPTIONAL_FEATURES

    return [
        Site(f"preferences.OPTIONAL_FEATURES[{key!r}]", None, e["prompt"], False,
             "yes_no", e["default"], True, None)
        for key, e in OPTIONAL_FEATURES.items()
    ]


SITES = _sites()
ALL = SITES + _optional_feature_sites()
# The optional-features loop passes feature["prompt"]; its text is checked
# through _optional_feature_sites() instead.
TABLE_DRIVEN = {"aec/lib/preferences.py"}


def _base(type_) -> str:
    return type_.split("[", 1)[0] if isinstance(type_, str) else ""


def _ids(site):
    return site.where


LETTER_OPTION = re.compile(r"(?<![/\w])\w*\[([A-Za-z])\]\w*")
YN_HINT = re.compile(r"[\[(]\s*[yY]\s*/\s*[nN]")


def test_scanner_finds_the_callsites():
    assert len(SITES) > 50


def test_every_prompt_text_is_statically_checkable():
    unchecked = [s.where for s in SITES if s.text is None
                 and not any(s.where.startswith(t) for t in TABLE_DRIVEN)]
    assert not unchecked, (
        "prompt text must be a literal or f-string so conventions can be "
        f"checked: {unchecked}"
    )


def _checkable(sites):
    return [s for s in sites if s.text is not None]


@pytest.mark.parametrize("site", [s for s in _checkable(ALL) if s.type == "yes_no"], ids=_ids)
def test_yes_no_hint_matches_default(site):
    if site.hint_call:
        return  # yes_no_hint(default) is correct by construction
    assert site.default is not _DYNAMIC, (
        f"{site.where}: dynamic default -- build the hint with yes_no_hint(default)"
    )
    expected = yes_no_hint(bool(site.default))
    assert expected in site.text, f"{site.where}: yes/no prompt must show {expected}"


@pytest.mark.parametrize("site", [s for s in _checkable(ALL) if s.type == "yes_no"], ids=_ids)
def test_yes_no_prompt_offers_no_other_options(site):
    """A yes/no parser cannot honor a numbered or lettered menu."""
    assert not re.search(r"^\s*\d+[.)]\s", site.text, re.M), (
        f"{site.where}: numbered menu on a yes/no prompt -- ask [Y/n] or use choices"
    )
    assert not re.search(r"\[[yY]/[nN]/", site.text), (
        f"{site.where}: extra options beyond y/n on a yes/no prompt -- use choices"
    )


@pytest.mark.parametrize("site", _checkable(ALL), ids=_ids)
def test_hints_use_square_brackets(site):
    assert not re.search(r"\(\s*[yY]\s*/\s*[nN]", site.text), (
        f"{site.where}: use [Y/n] / [y/N], not parentheses"
    )


@pytest.mark.parametrize("site", [s for s in _checkable(ALL) if s.type != "yes_no"], ids=_ids)
def test_non_yes_no_prompt_showing_yn_declares_choices(site):
    if YN_HINT.search(site.text):
        assert site.choices is not None, (
            f"{site.where}: shows a y/n hint but is not type='yes_no' and declares "
            "no choices, so any answer is accepted"
        )


@pytest.mark.parametrize("site", _checkable(ALL), ids=_ids)
def test_letter_options_are_distinct_ignoring_case(site):
    letters = LETTER_OPTION.findall(site.text)
    lowered = [c.lower() for c in letters]
    assert len(lowered) == len(set(lowered)), (
        f"{site.where}: options {letters} collide when case is ignored "
        "(answers are matched case-insensitively)"
    )


@pytest.mark.parametrize("site", _checkable(ALL), ids=_ids)
def test_letter_options_mark_only_the_default_uppercase(site):
    letters = LETTER_OPTION.findall(site.text)
    if not letters:
        return
    upper = [c for c in letters if c.isupper()]
    if isinstance(site.default, str) and len(site.default) == 1:
        assert upper == [site.default.upper()], (
            f"{site.where}: default {site.default!r} must be the only uppercase option, got {letters}"
        )
    else:
        assert not upper, f"{site.where}: uppercase marks a default, but none is declared"


@pytest.mark.parametrize("site", _checkable(ALL), ids=_ids)
def test_letter_options_are_accepted(site):
    letters = LETTER_OPTION.findall(site.text)
    if letters and isinstance(site.choices, list):
        missing = [c for c in letters if c.lower() not in [str(x).lower() for x in site.choices]]
        assert not missing, f"{site.where}: shows options {missing} that choices reject"


@pytest.mark.parametrize("site", [s for s in _checkable(ALL) if s.type != "yes_no"], ids=_ids)
def test_menu_prompts_declare_choices(site):
    """A "Choice [1]:" prompt without choices accepts any typo and routes it
    to whatever branch the callsite uses for "other"."""
    if re.search(r"\bChoo?(se|ice)\b", site.text):
        assert site.choices is not None or site.has_validator, (
            f"{site.where}: menu prompt must pass choices=[...] or a validator"
        )


@pytest.mark.parametrize(
    "site",
    [s for s in _checkable(ALL) if s.type != "yes_no" and isinstance(s.default, (str, int))
     and s.default != ""],
    ids=_ids,
)
def test_default_is_shown(site):
    shown = str(site.default)
    in_slash_list = re.search(
        r"\[(?:[^\]]*/)?" + re.escape(shown.upper()) + r"(?:/[^\]]*)?\]", site.text
    )
    assert re.search(r"\[" + re.escape(shown) + r"\]", site.text, re.I) or in_slash_list or \
        f"[{shown.upper()}]" in site.text, (
        f"{site.where}: default {shown!r} is not shown, e.g. '[{shown}]'"
    )


@pytest.mark.parametrize(
    "site", [s for s in SITES if s.has_default and s.default is _DYNAMIC and s.type != "yes_no"],
    ids=_ids,
)
def test_dynamic_default_is_interpolated_in_brackets(site):
    if site.text is None:
        return
    assert "[{}]" in site.text or "[Enter=" in site.text, (
        f"{site.where}: interpolate the default into the hint, e.g. f'... [{{default}}]: '"
    )


# --- 3. Callsite agrees with the catalog ----------------------------------


def _catalog_pairs():
    from aec.lib.prompt_catalog import get_spec

    pairs = []
    for s in SITES:
        spec = get_spec(s.prompt_id) if s.prompt_id else None
        if spec is not None:
            pairs.append((s, spec))
    return pairs


CATALOG_PAIRS = _catalog_pairs()


def test_catalog_pairs_found():
    assert len(CATALOG_PAIRS) > 30


@pytest.mark.parametrize("site,spec", CATALOG_PAIRS, ids=[s.where for s, _ in CATALOG_PAIRS])
def test_callsite_yes_no_matches_catalog(site, spec):
    assert (site.type == "yes_no") == (_base(spec.type) == "yes_no"), (
        f"{site.where}: callsite type {site.type!r} vs catalog {spec.type!r} for {spec.prompt_id}"
    )


@pytest.mark.parametrize("site,spec", CATALOG_PAIRS, ids=[s.where for s, _ in CATALOG_PAIRS])
def test_callsite_default_matches_catalog(site, spec):
    if site.default is _DYNAMIC or spec.default is None or not site.has_default:
        return
    norm = lambda v: prompts.normalize(v, site.type if isinstance(site.type, str) else "string")
    assert norm(site.default) == norm(spec.default), (
        f"{site.where}: default {site.default!r} vs catalog {spec.default!r} for {spec.prompt_id}"
    )


@pytest.mark.parametrize("site,spec", CATALOG_PAIRS, ids=[s.where for s, _ in CATALOG_PAIRS])
def test_catalog_choices_are_enforced_at_callsite(site, spec):
    """The catalog tells agents the valid answers; the callsite must enforce
    the same set for humans."""
    if not spec.choices:
        return
    assert site.choices is not None, (
        f"{site.where}: catalog declares choices {spec.choices} for {spec.prompt_id} "
        "but the callsite accepts anything"
    )
    if isinstance(site.choices, list):
        assert {str(c) for c in site.choices} - {""} == {str(c) for c in spec.choices} - {""}, (
            f"{site.where}: choices {site.choices} vs catalog {spec.choices}"
        )
