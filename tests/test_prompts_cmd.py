"""``aec prompts list|template|check`` — the agent-facing discovery surface."""
import json

import pytest

from aec.commands.prompts_cmd import (
    run_prompts_check,
    run_prompts_list,
    run_prompts_template,
)
from aec.lib.prompt_catalog import all_specs


def test_list_json_covers_the_whole_catalog(capsys):
    run_prompts_list(json_out=True)
    payload = json.loads(capsys.readouterr().out)
    assert {p["id"] for p in payload["prompts"]} == {
        s.prompt_id for s in all_specs(expand_dynamic=True)
    }
    assert payload["dynamic_families"], "dynamic families must be discoverable too"


def test_list_filters_by_command(capsys):
    run_prompts_list(command="upgrade", json_out=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["prompts"]
    assert all("upgrade" in p["command"] for p in payload["prompts"])


def test_list_human_output_names_the_env_var(capsys):
    run_prompts_list(command="agent-tools")
    out = capsys.readouterr().out
    assert "agent_tools.rollback.confirm" in out
    assert "AEC_ANSWER_AGENT_TOOLS_ROLLBACK_CONFIRM" in out


def test_template_maps_every_id_to_its_default(capsys):
    run_prompts_template(command="upgrade")
    template = json.loads(capsys.readouterr().out)
    assert template["upgrade.run_update_first"] is True
    assert template["upgrade.other_repos"] == "n"


def test_template_writes_a_file(tmp_path):
    out = tmp_path / "answers.json"
    run_prompts_template(command="upgrade", output=str(out))
    assert json.loads(out.read_text())["upgrade.other_repos"] == "n"


def test_check_accepts_valid_answers(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps({"upgrade.run_update_first": False}))
    assert run_prompts_check(str(path)) == 0


@pytest.mark.parametrize(
    "answers,needle",
    [
        ({"bogus.prompt": "x"}, "not a known prompt ID"),
        ({"upgrade.run_update_first": "maybe"}, "not a valid yes_no"),
        ({"install.settings.projects_dir": None}, "no default"),
    ],
)
def test_check_rejects_bad_answers(tmp_path, capsys, answers, needle):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(answers))
    assert run_prompts_check(str(path)) == 1
    assert needle in capsys.readouterr().out


def test_check_accepts_dynamic_family_members(tmp_path):
    """Concrete IDs only exist at run time; the prefix is all we can validate."""
    path = tmp_path / "answers.json"
    path.write_text(json.dumps({"upgrade.overwrite_local.my-skill": True}))
    assert run_prompts_check(str(path)) == 0


def test_check_reports_a_missing_file(tmp_path, capsys):
    assert run_prompts_check(str(tmp_path / "nope.json")) == 1
    assert "nope.json" in capsys.readouterr().out
