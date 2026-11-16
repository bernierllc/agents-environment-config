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


def test_bool_normalization():
    """prompt() always returns the string a user would have typed.

    Callsites chain ``.strip().lower()`` on the result, so returning a real
    bool here would blow up with AttributeError the moment an overlay
    pre-answered the prompt.
    """
    prompts.set_overlay_answers({"x": "yes"})
    assert prompts.prompt("x", "Q? ", type="yes_no") == "y"
    prompts.set_overlay_answers({"x": False})
    assert prompts.prompt("x", "Q? ", type="yes_no") == "n"


def test_int_normalization():
    prompts.set_overlay_answers({"x": 42})
    assert prompts.prompt("x", "Q? ", type="int") == "42"


def test_validator_applied_to_preanswer():
    prompts.set_overlay_answers({"x": "value"})
    assert prompts.prompt("x", "Q? ", validator=str.upper) == "VALUE"


def test_clear_restores_input(monkeypatch):
    prompts.set_overlay_answers({"x": "pre"})
    prompts.clear_overlay_answers()
    monkeypatch.setattr("builtins.input", lambda _t: "typed")
    assert prompts.prompt("x", "Q? ") == "typed"


def test_enrolled_org_prompt_answers_load_in_a_fresh_process(tmp_path):
    """`aec org apply` stores policy; a later command must still see its prompt answers."""
    from aec.lib.org_config import OrgPaths
    from aec.lib.org_config.apply import load_enrolled_prompt_answers

    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    (paths.orgs_dir / "my-org.yaml").write_text(
        "---\n"
        'schema_version: "1.0"\n'
        "org_id: my-org\n"
        "org_name: my-org\n"
        'config_version: "1.0.0"\n'
        "trust:\n"
        '  mode: "unsigned"\n'
        "---\n\n"
        "install:\n"
        "  prompts:\n"
        "    repo.git.license_kind: proprietary\n"
    )
    assert load_enrolled_prompt_answers(paths) == 1
    assert prompts.prompt("repo.git.license_kind", "Q? ", type="enum", choices=["mit", "proprietary"]) == "proprietary"


def test_no_enrolled_orgs_loads_nothing(tmp_path):
    from aec.lib.org_config import OrgPaths
    from aec.lib.org_config.apply import load_enrolled_prompt_answers

    assert load_enrolled_prompt_answers(OrgPaths(home_dir=tmp_path)) == 0


def test_cli_startup_loads_org_answers_and_survives_a_broken_org_config(monkeypatch):
    from aec import cli
    from aec.lib.org_config import apply

    calls = []
    monkeypatch.setattr(apply, "load_enrolled_prompt_answers", lambda paths: calls.append(paths) or 1)
    cli._load_org_prompt_answers()
    assert len(calls) == 1

    def broken(_paths):
        raise ValueError("bad org config")

    warnings = []
    monkeypatch.setattr(apply, "load_enrolled_prompt_answers", broken)
    monkeypatch.setattr(cli.Console, "warning", lambda msg: warnings.append(msg))
    cli._load_org_prompt_answers()  # must not raise
    assert "bad org config" in warnings[0]
