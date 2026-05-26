"""`aec install --org-config` enrolls then applies org policy (A6/deferred)."""

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


def test_install_org_config_enrolls_and_applies(tmp_path):
    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG, encoding="utf-8")

    result = runner.invoke(
        app,
        ["install", "--org-config", str(src), "--allow-unsigned", "--yes"],
        env={"HOME": str(tmp_path)},
    )

    assert result.exit_code == 0, result.stdout
    assert (tmp_path / ".aec" / "orgs" / "acme.yaml").exists()


def test_install_without_type_name_errors(tmp_path):
    result = runner.invoke(app, ["install"], env={"HOME": str(tmp_path)})
    assert result.exit_code == 2
    assert "requires <type> <name>" in result.stdout
