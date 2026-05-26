"""Wiring: perform_enroll runs the org's enrollment_script."""
from __future__ import annotations

from pathlib import Path

import pytest

import aec.commands.org as org_cmd

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

items:
  skills: {}
  rules: {}
  agents: {}
  mcps: {}

install:
  enrollment_script:
    - { action: "run_doctor" }
"""


def test_perform_enroll_runs_enrollment_script(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(
        "aec.lib.org_config.enrollment._do_run_doctor",
        lambda doctor: (
            calls.append("ran")
            or __import__(
                "aec.lib.org_config.enrollment", fromlist=["StepResult"]
            ).StepResult("run_doctor", True, "ok")
        ),
    )
    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG, encoding="utf-8")

    org_cmd.perform_enroll(str(src), allow_unsigned=True)
    assert calls == ["ran"]
    out = capsys.readouterr().out
    assert "run_doctor" in out


def test_perform_enroll_exits_on_script_failure(tmp_path, monkeypatch):
    import typer

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from aec.lib.org_config.enrollment import StepResult

    monkeypatch.setattr(
        "aec.lib.org_config.enrollment._do_run_doctor",
        lambda doctor: StepResult("run_doctor", False, "broken"),
    )
    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG, encoding="utf-8")
    with pytest.raises(typer.Exit):
        org_cmd.perform_enroll(str(src), allow_unsigned=True)
