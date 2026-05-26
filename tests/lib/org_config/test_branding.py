"""Tests for branding schema/validation (Phase 4d)."""
from __future__ import annotations

from pathlib import Path

from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.schema import Branding
from aec.lib.org_config.validator import validate_org_config

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return parse_org_config_text((FIXTURES / name).read_text())


def test_branding_absent_is_none():
    fm, body = _load("valid-minimal.yaml")
    cfg = validate_org_config(fm, body)
    assert cfg.branding is None


def test_branding_block_populates_all_fields():
    fm, body = _load("valid-minimal.yaml")
    body["branding"] = {
        "display_name": "Acme Engineering",
        "welcome_message": "Welcome to Acme!",
        "doctor_footer": "Acme org config v1",
    }
    cfg = validate_org_config(fm, body)
    assert isinstance(cfg.branding, Branding)
    assert cfg.branding.display_name == "Acme Engineering"
    assert cfg.branding.welcome_message == "Welcome to Acme!"
    assert cfg.branding.doctor_footer == "Acme org config v1"


def test_partial_branding_block_populates_what_is_present():
    fm, body = _load("valid-minimal.yaml")
    body["branding"] = {"welcome_message": "hi"}
    cfg = validate_org_config(fm, body)
    assert cfg.branding.welcome_message == "hi"
    assert cfg.branding.display_name is None
    assert cfg.branding.doctor_footer is None


def test_valid_full_fixture_has_branding():
    fm, body = _load("valid-full.yaml")
    cfg = validate_org_config(fm, body)
    assert cfg.branding is not None
    assert cfg.branding.display_name == "Acme Engineering Standard"


def test_perform_enroll_prints_welcome_message(tmp_path, monkeypatch, capsys):
    import aec.commands.org as org_cmd

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    src = tmp_path / "acme.yaml"
    src.write_text(
        """---
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

branding:
  welcome_message: "Welcome to Acme!"
""",
        encoding="utf-8",
    )
    org_cmd.perform_enroll(str(src), allow_unsigned=True)
    assert "Welcome to Acme!" in capsys.readouterr().out
