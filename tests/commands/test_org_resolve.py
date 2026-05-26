"""Command-level tests for `aec org resolve` (Phase 2d.4)."""

from pathlib import Path

from typer.testing import CliRunner

from aec.cli import app

runner = CliRunner()

TEMPLATE = """---
schema_version: "1.0"
org_id: "{org_id}"
org_name: "{org_id}"
config_version: "{version}"
trust:
  mode: "unsigned"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom: []

items:
  skills:
    "foo":
      source: "aec.default.skills"
      stance: {stance}
  rules: {{}}
  agents: {{}}
  mcps: {{}}
"""


def _run(args, home, **kwargs):
    return runner.invoke(app, args, env={"HOME": str(home)}, **kwargs)


def _write_org(home, org_id, stance, version="1.0.0"):
    orgs_dir = home / ".aec" / "orgs"
    orgs_dir.mkdir(parents=True, exist_ok=True)
    (orgs_dir / f"{org_id}.yaml").write_text(
        TEMPLATE.format(org_id=org_id, stance=stance, version=version), encoding="utf-8"
    )


def _setup_conflict(home):
    _write_org(home, "acme", "required")
    _write_org(home, "globex", "blocked")


def test_resolve_no_conflicts(tmp_path):
    result = _run(["org", "resolve"], tmp_path)
    assert result.exit_code == 0
    assert "no unresolved org conflicts" in result.stdout


def test_resolve_list_shows_open_conflicts(tmp_path):
    _setup_conflict(tmp_path)
    result = _run(["org", "resolve", "--list"], tmp_path)
    assert result.exit_code == 0
    assert "skills/foo" in result.stdout
    assert "stance" in result.stdout


def test_resolve_interactive_persists_decision(tmp_path):
    _setup_conflict(tmp_path)
    # Choice "1" honors the first participant (acme, sorted first).
    result = _run(["org", "resolve"], tmp_path, input="1\n")
    assert result.exit_code == 0
    assert "resolved skills/foo: honor:acme" in result.stdout

    # Now no open conflicts remain.
    after = _run(["org", "resolve", "--list"], tmp_path)
    assert "no unresolved org conflicts" in after.stdout


def test_resolve_unknown_id_errors(tmp_path):
    _setup_conflict(tmp_path)
    result = _run(["org", "resolve", "conf-doesnotexist"], tmp_path)
    assert result.exit_code == 13


def test_resolution_invalidated_when_config_changes(tmp_path):
    _setup_conflict(tmp_path)
    _run(["org", "resolve"], tmp_path, input="1\n")
    assert "no unresolved" in _run(["org", "resolve", "--list"], tmp_path).stdout

    # One org's config changes -> input hash changes -> resolution goes stale.
    _write_org(tmp_path, "acme", "required", version="2.0.0")
    result = _run(["org", "resolve", "--list"], tmp_path)
    assert "skills/foo" in result.stdout


def test_resolve_defer_keeps_conflict_open(tmp_path):
    _setup_conflict(tmp_path)
    # Options: 1=honor acme, 2=honor globex, 3=skip, 4=defer.
    result = _run(["org", "resolve"], tmp_path, input="4\n")
    assert result.exit_code == 0
    assert "deferred" in result.stdout
    assert "skills/foo" in _run(["org", "resolve", "--list"], tmp_path).stdout
