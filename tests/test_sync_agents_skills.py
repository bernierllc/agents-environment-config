"""generate_frontmatter must emit YAML-safe quoted scalars (agents-environment-config#113)."""

import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "sync_agents_skills",
    Path(__file__).resolve().parent.parent / "scripts" / "sync-agents-skills.py",
)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


def test_description_with_quotes_round_trips():
    desc = 'rejected with "commit-msg: subject must be" \\ and café'
    lines = sync.generate_frontmatter("x", desc, ["skill"]).splitlines()
    # A JSON string literal is a valid YAML double-quoted scalar.
    assert json.loads(lines[1].removeprefix("name: ")) == "x"
    assert json.loads(lines[2].removeprefix("description: ")) == desc
