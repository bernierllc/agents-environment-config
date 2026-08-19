"""Prompt seam: answer sources, precedence, normalization, strict failure."""
import json

import pytest

from aec.lib import prompts
from aec.lib.prompts import (
    PromptInvalidAnswer,
    PromptUnanswered,
    env_var_name,
    load_answers_file,
    prompt,
)


@pytest.fixture(autouse=True)
def _clean_prompt_state(monkeypatch):
    prompts.clear_answers()
    prompts.clear_overlay_answers()
    prompts.reset_mode()
    for var in list(__import__("os").environ):
        if var.startswith("AEC_ANSWER") or var in ("AEC_NONINTERACTIVE", "AEC_USE_DEFAULTS"):
            monkeypatch.delenv(var, raising=False)
    # Default every test to headless; interactive tests opt back in explicitly.
    prompts.set_mode(non_interactive=True)
    yield
    prompts.clear_answers()
    prompts.clear_overlay_answers()
    prompts.reset_mode()


# --- Precedence -------------------------------------------------------------

def test_overlay_outranks_answers_and_env(monkeypatch):
    prompts.set_overlay_answers({"a.b": "overlay"})
    prompts.set_answers({"a.b": "file"})
    monkeypatch.setenv(env_var_name("a.b"), "env")
    assert prompt("a.b", "? ") == "overlay"


def test_answers_file_outranks_env(monkeypatch):
    prompts.set_answers({"a.b": "file"})
    monkeypatch.setenv(env_var_name("a.b"), "env")
    assert prompt("a.b", "? ") == "file"


def test_env_answer_used_when_nothing_else(monkeypatch):
    monkeypatch.setenv("AEC_ANSWER_A_B", "env")
    assert prompt("a.b", "? ") == "env"


def test_env_var_name_shape():
    assert env_var_name("install.settings.plans_dir") == "AEC_ANSWER_INSTALL_SETTINGS_PLANS_DIR"


# --- Normalization: prompt() always returns a str ---------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "y"), (False, "n"), ("yes", "y"), ("N", "n"), ("true", "y"), ("0", "n")],
)
def test_yes_no_answers_normalize_to_typed_string(value, expected):
    prompts.set_answers({"q": value})
    result = prompt("q", "? ", type="yes_no")
    assert result == expected
    # Callsites chain .strip().lower() — this must not explode.
    assert result.strip().lower() == expected


def test_int_answer_normalizes_to_decimal_string():
    prompts.set_answers({"q": 30})
    result = prompt("q", "? ", type="int")
    assert result == "30"
    assert int(result.strip()) == 30


def test_bool_for_int_prompt_is_rejected():
    prompts.set_answers({"q": True})
    with pytest.raises(PromptInvalidAnswer):
        prompt("q", "? ", type="int")


def test_non_yes_no_string_rejected_for_yes_no():
    prompts.set_answers({"q": "maybe"})
    with pytest.raises(PromptInvalidAnswer) as exc:
        prompt("q", "? ", type="yes_no")
    assert exc.value.prompt_id == "q"


def test_choices_are_enforced():
    prompts.set_answers({"q": "3"})
    with pytest.raises(PromptInvalidAnswer):
        prompt("q", "? ", type="enum", choices=["1", "2"])


def test_validator_runs_on_supplied_answer():
    prompts.set_answers({"q": " spaced "})
    assert prompt("q", "? ", validator=lambda v: v.strip()) == "spaced"


# --- Strict failure ---------------------------------------------------------

def test_unanswered_without_defaults_raises_naming_the_id():
    with pytest.raises(PromptUnanswered) as exc:
        prompt("install.settings.plans_dir", "? ", type="enum", default="1")
    assert exc.value.prompt_id == "install.settings.plans_dir"
    assert "--defaults" in str(exc.value)


def test_unanswered_without_default_raises_even_with_defaults_flag():
    prompts.set_mode(use_defaults=True)
    with pytest.raises(PromptUnanswered):
        prompt("q", "? ", type="path", default=None)


def test_defaults_flag_supplies_declared_default():
    prompts.set_mode(use_defaults=True)
    assert prompt("q", "? ", type="yes_no", default=True) == "y"
    assert prompt("q2", "? ", type="int", default=30) == "30"


def test_sensitive_prompt_refuses_defaults():
    prompts.set_mode(use_defaults=True)
    with pytest.raises(PromptUnanswered) as exc:
        prompt("danger", "Delete everything? ", type="yes_no", default=False, sensitive=True)
    assert exc.value.sensitive is True


def test_sensitive_prompt_still_accepts_an_explicit_answer():
    prompts.set_answers({"danger": "y"})
    assert prompt("danger", "? ", type="yes_no", sensitive=True) == "y"


# --- Interactive parity -----------------------------------------------------

def test_tty_user_is_still_prompted(monkeypatch):
    prompts.set_mode(non_interactive=False)
    monkeypatch.setattr("builtins.input", lambda text: "typed")
    assert prompt("q", "? ", type="string", default="unused") == "typed"


def test_closed_stdin_mid_prompt_fails_instead_of_returning_empty(monkeypatch):
    prompts.set_mode(non_interactive=False)

    def _eof(_text):
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    with pytest.raises(PromptUnanswered):
        prompt("q", "? ", type="yes_no", default=True)


def test_non_tty_stdin_is_still_interactive(monkeypatch):
    """Piped stdin (`printf 'y\\n' | aec install`) must still be read."""
    prompts.reset_mode()
    monkeypatch.setattr("sys.stdin", type("S", (), {"isatty": staticmethod(lambda: False)})())
    assert prompts.is_non_interactive() is False
    monkeypatch.setattr("builtins.input", lambda _="": "y")
    assert prompts.prompt("t.piped", "go? ", type="yes_no") == "y"


def test_non_interactive_env_flag(monkeypatch):
    prompts.reset_mode()
    monkeypatch.setenv("AEC_NONINTERACTIVE", "1")
    assert prompts.is_non_interactive() is True


# --- Answers file loading ---------------------------------------------------

def test_load_answers_file_roundtrip(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps({"a.b": True, "c.d": 30}))
    assert load_answers_file(path) == {"a.b": True, "c.d": 30}


def test_load_answers_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_answers_file(tmp_path / "nope.json")


def test_load_answers_file_rejects_non_object(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text("[1, 2]")
    with pytest.raises(ValueError):
        load_answers_file(path)


def test_load_answers_file_rejects_bad_json(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text("{nope")
    with pytest.raises(ValueError):
        load_answers_file(path)


# --- Catalog ----------------------------------------------------------------

def test_catalog_covers_every_declared_static_prompt_id():
    from aec.lib.prompt_catalog import catalog_ids
    from aec.lib.prompt_ids import ALL_STATIC_PROMPT_IDS

    assert catalog_ids() == set(ALL_STATIC_PROMPT_IDS)


def test_catalog_lookup_and_dynamic_expansion():
    from aec.lib.prompt_catalog import all_specs, get_spec
    from aec.lib.prompt_ids import SETUP_TRACK_CURRENT_REPO

    spec = get_spec(SETUP_TRACK_CURRENT_REPO)
    assert spec is not None and spec.type == "yes_no"
    assert get_spec("nope.not.a.prompt") is None
    assert len(all_specs(expand_dynamic=True)) > len(all_specs())


def test_catalog_specs_serialize():
    from aec.lib.prompt_catalog import all_specs

    for spec in all_specs():
        payload = spec.to_dict()
        assert payload["id"] and payload["command"] and payload["summary"]
