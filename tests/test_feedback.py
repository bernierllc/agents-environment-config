"""AEC's feedback capture, `aec feedback` hand-off and the due notice."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec import cli
from aec.lib import feedback

REPO = Path(__file__).resolve().parent.parent
SKILL_SCRIPT = REPO / ".claude" / "skills" / "feedback-loop" / "scripts" / "feedback.py"


@pytest.fixture
def store(tmp_path, monkeypatch):
    home = tmp_path / "fb"
    monkeypatch.setenv("AGENT_FEEDBACK_HOME", str(home))
    monkeypatch.delenv("AGENT_FEEDBACK_BIN", raising=False)
    return home


def entries(home):
    path = home / "subjects" / "aec" / "aec" / "entries.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_capture_writes_an_entry_the_skill_reads(store):
    """Contract: AEC writes the store format directly; the skill's feedback.py must accept it."""
    if not SKILL_SCRIPT.is_file():
        if os.environ.get("CI"):
            pytest.fail(f"{SKILL_SCRIPT} missing: the skills submodule must include feedback-loop")
        pytest.skip("skills submodule not checked out or older than feedback-loop")
    feedback.capture("high", "`aec install` crashed: KeyError at aec.lib.x.y")
    feedback.capture("medium", "run stopped on unanswered prompt install.scope")
    env = {**os.environ, "AGENT_FEEDBACK_HOME": str(store)}
    out = subprocess.run([sys.executable, str(SKILL_SCRIPT), "status", "aec:aec", "--json"],
                         env=env, capture_output=True, text=True, check=True)
    [row] = json.loads(out.stdout)["subjects"]
    assert (row["total"], row["open"], row["due"]) == (2, 2, "1 high")
    review = subprocess.run([sys.executable, str(SKILL_SCRIPT), "review", "aec:aec", "--json"],
                            env=env, capture_output=True, text=True, check=True)
    assert {e["reporter"] for e in json.loads(review.stdout)["entries"]} == {"cli"}


def test_capture_respects_disable_and_opt_out(store):
    store.mkdir(parents=True)
    (store / "config.json").write_text(json.dumps({"enabled": True, "opt_out": ["aec:aec"]}))
    feedback.capture("high", "x")
    (store / "config.json").write_text(json.dumps({"enabled": False, "opt_out": []}))
    feedback.capture("high", "x")
    assert entries(store) == []


def test_crash_is_captured_without_arguments(store, monkeypatch):
    def boom():
        raise KeyError("/private/path/secret-value")

    monkeypatch.setattr(cli, "app", boom)
    monkeypatch.setattr(sys, "argv", ["aec", "install", "/private/path"])
    monkeypatch.setattr(feedback, "current_command", "install")
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    [e] = entries(store)
    assert (e["severity"], e["reporter"], e["kind"], e["name"]) == ("high", "cli", "aec", "aec")
    assert e["summary"].startswith("`aec install` crashed: KeyError")
    assert "private" not in e["summary"] and "secret" not in e["summary"]


def run_feedback(*args):
    return CliRunner().invoke(cli.app, ["feedback", *args])


def test_feedback_command_without_the_skill_says_how_to_install(store, monkeypatch):
    monkeypatch.setattr(feedback, "locate_script", lambda: None)
    monkeypatch.setattr("aec.commands.feedback_cmd.locate_script", lambda: None)
    result = run_feedback("status")
    assert result.exit_code == 1
    assert "aec install skill feedback-loop" in result.output


def test_feedback_command_passes_args_and_aliases_through(store, tmp_path, monkeypatch):
    fake = tmp_path / "feedback.py"
    record = tmp_path / "args.json"
    fake.write_text(f"import json, sys\njson.dump(sys.argv[1:], open({str(record)!r}, 'w'))\nsys.exit(3)\n")
    monkeypatch.setenv("AGENT_FEEDBACK_BIN", str(fake))
    cases = [
        (["opt-out", "skill:my-skill"], ["config", "--opt-out", "skill:my-skill"]),
        (["disable"], ["config", "--disable"]),
        (["review", "aec:aec", "--json"], ["review", "aec:aec", "--json"]),
        ([], ["--help"]),
    ]
    for given, expected in cases:
        result = run_feedback(*given)
        assert result.exit_code == 3, result.output
        assert json.loads(record.read_text()) == expected


def test_notice_prints_once_a_day_when_due(store, tmp_path, monkeypatch, capsys):
    fake = tmp_path / "feedback.py"
    fake.write_text('import json\nprint(json.dumps({"subjects": [{"subject": "aec:aec", "due": "1 high"}]}))\n')
    monkeypatch.setenv("AGENT_FEEDBACK_BIN", str(fake))
    monkeypatch.delenv("AEC_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("aec.lib.config.AEC_HOME", tmp_path / "aec-home")
    feedback.maybe_notify()
    assert "aec feedback review aec:aec" in capsys.readouterr().err
    feedback.maybe_notify()
    assert capsys.readouterr().err == ""


def test_notice_is_off_under_no_update_check(store, tmp_path, monkeypatch, capsys):
    fake = tmp_path / "feedback.py"
    fake.write_text("raise SystemExit('must not run')\n")
    monkeypatch.setenv("AGENT_FEEDBACK_BIN", str(fake))
    monkeypatch.setenv("AEC_NO_UPDATE_CHECK", "1")
    feedback.maybe_notify()
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("config", ["null", "[]", '{"enabled": true, "opt_out": null}', "{bad json"])
def test_malformed_config_never_escapes_capture(store, config):
    store.mkdir(parents=True)
    (store / "config.json").write_text(config)
    feedback.capture("high", "x")  # must not raise into main()'s error handler
    assert entries(store) == []


def test_unanswered_dynamic_prompt_records_its_family_not_the_path(store, monkeypatch):
    from aec.lib.prompt_catalog.lifecycle_area import UNTRACK_CONFIRM_PREFIX
    from aec.lib.prompts import PromptUnanswered

    def unanswered():
        raise PromptUnanswered(f"{UNTRACK_CONFIRM_PREFIX}./private/customer/secret-project", "no answer")

    monkeypatch.setattr(cli, "app", unanswered)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    [e] = entries(store)
    assert e["summary"] == f"run stopped on unanswered prompt {UNTRACK_CONFIRM_PREFIX}.*"


def test_feedback_works_in_the_dependency_free_cli(store, tmp_path):
    """The base install has no Typer, so `aec feedback` must exist in the argparse CLI too."""
    fake = tmp_path / "feedback.py"
    record = tmp_path / "args.json"
    fake.write_text(f"import json, sys\njson.dump(sys.argv[1:], open({str(record)!r}, 'w'))\n")
    code = ("import sys; sys.modules['typer'] = None; "
            "sys.argv = ['aec', 'feedback', 'opt-out', 'skill:my-skill']; "
            "from aec import cli; assert not cli.HAS_TYPER; cli.main()")
    env = {**os.environ, "AGENT_FEEDBACK_BIN": str(fake), "AGENT_FEEDBACK_HOME": str(store),
           "HOME": str(tmp_path), "AEC_NO_UPDATE_CHECK": "1"}
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(record.read_text()) == ["config", "--opt-out", "skill:my-skill"]


@pytest.mark.parametrize("config", [{"enabled": False, "opt_out": []}, {"enabled": True, "opt_out": ["aec:aec"]}])
def test_notice_is_silent_when_feedback_is_off(store, tmp_path, monkeypatch, capsys, config):
    store.mkdir(parents=True)
    (store / "config.json").write_text(json.dumps(config))
    fake = tmp_path / "feedback.py"
    fake.write_text("raise SystemExit('must not run')\n")
    monkeypatch.setenv("AGENT_FEEDBACK_BIN", str(fake))
    monkeypatch.delenv("AEC_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr("aec.lib.config.AEC_HOME", tmp_path / "aec-home")
    feedback.maybe_notify()
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("stamp", ['{"last": "2020-01-01T00:00:00"}', '"not an object"'])
def test_bad_notice_stamp_is_treated_as_never_noticed(store, tmp_path, monkeypatch, capsys, stamp):
    fake = tmp_path / "feedback.py"
    fake.write_text('import json\nprint(json.dumps({"subjects": [{"subject": "aec:aec", "due": "1 high"}]}))\n')
    monkeypatch.setenv("AGENT_FEEDBACK_BIN", str(fake))
    monkeypatch.delenv("AEC_NO_UPDATE_CHECK", raising=False)
    home = tmp_path / "aec-home"
    home.mkdir()
    (home / "feedback-notice.json").write_text(stamp)
    monkeypatch.setattr("aec.lib.config.AEC_HOME", home)
    feedback.maybe_notify()
    assert "aec feedback review aec:aec" in capsys.readouterr().err
