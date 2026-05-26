"""Tests for the org-overlay pre-answering in the prompt() seam."""

import pytest

from aec.lib import prompts


@pytest.fixture(autouse=True)
def _clear():
    prompts.clear_overlay_answers()
    yield
    prompts.clear_overlay_answers()


def test_unregistered_id_falls_through_to_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _t: "typed")
    assert prompts.prompt("some.id", "Q? ") == "typed"


def test_registered_id_returns_preanswer_without_input(monkeypatch):
    def boom(_t):
        raise AssertionError("input() must not be called when pre-answered")

    monkeypatch.setattr("builtins.input", boom)
    prompts.set_overlay_answers({"install.settings.projects_dir": "~/work"})
    assert prompts.prompt("install.settings.projects_dir", "Q? ") == "~/work"


def test_bool_coercion():
    prompts.set_overlay_answers({"x": "yes"})
    assert prompts.prompt("x", "Q? ", type="bool") is True
    prompts.set_overlay_answers({"x": "no"})
    assert prompts.prompt("x", "Q? ", type="bool") is False


def test_int_coercion():
    prompts.set_overlay_answers({"x": "42"})
    assert prompts.prompt("x", "Q? ", type="int") == 42


def test_validator_applied_to_preanswer():
    prompts.set_overlay_answers({"x": "value"})
    assert prompts.prompt("x", "Q? ", validator=str.upper) == "VALUE"


def test_clear_restores_input(monkeypatch):
    prompts.set_overlay_answers({"x": "pre"})
    prompts.clear_overlay_answers()
    monkeypatch.setattr("builtins.input", lambda _t: "typed")
    assert prompts.prompt("x", "Q? ") == "typed"
