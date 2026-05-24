"""Command-level tests for `aec org apply` (A6)."""

from pathlib import Path

from typer.testing import CliRunner

from aec.cli import app

runner = CliRunner()

CONFIG = """---
schema_version: "1.0"
org_id: "acme"
org_name: "acme"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

install:
  mode: "managed"

items:
  skills:
    "foo":
      source: "aec.default.skills"
      stance: required
  rules: {}
  agents: {}
  mcps: {}
"""


def _run(args, home, **kw):
    return runner.invoke(app, args, env={"HOME": str(home)}, **kw)


def _enroll(home):
    orgs = home / ".aec" / "orgs"
    orgs.mkdir(parents=True, exist_ok=True)
    (orgs / "acme.yaml").write_text(CONFIG, encoding="utf-8")


def test_apply_dry_run_prints_plan(tmp_path):
    _enroll(tmp_path)
    result = _run(["org", "apply", "--dry-run"], tmp_path)
    assert result.exit_code == 0
    assert "Org policy plan" in result.stdout
    assert "skills/foo" in result.stdout


def test_apply_enroll_then_dry_run(tmp_path):
    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG, encoding="utf-8")
    result = _run(["org", "apply", "--enroll", str(src), "--allow-unsigned", "--dry-run"], tmp_path)
    assert result.exit_code == 0
    assert (tmp_path / ".aec" / "orgs" / "acme.yaml").exists()
    assert "Org policy plan" in result.stdout


def test_apply_dry_run_no_orgs(tmp_path):
    result = _run(["org", "apply", "--dry-run"], tmp_path)
    assert result.exit_code == 0
