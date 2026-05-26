"""Tests for the enrollment_script runner (Phase 4c)."""
from __future__ import annotations

import textwrap

import pytest

import aec.lib.preferences as preferences_mod
from aec.lib.org_config.enrollment import EnrollmentResult, run_enrollment_script
from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.validator import validate_org_config


def _cfg(script_actions, *, items=None, custom_sources=None):
    custom_block = ""
    if custom_sources:
        items_lines = []
        for cs in custom_sources:
            items_lines.append(
                f"    - {{ id: '{cs['id']}', url: '{cs['url']}', "
                f"ref: '{cs['ref']}', contributes: {cs['contributes']} }}"
            )
        custom_block = "\n".join(items_lines)
    items_block = items or {
        "skills": {}, "rules": {}, "agents": {}, "mcps": {},
    }
    items_yaml = ""
    for t in ("skills", "rules", "agents", "mcps"):
        items_yaml += f"  {t}:\n"
        for name, pol in items_block.get(t, {}).items():
            items_yaml += f"    \"{name}\":\n"
            for k, v in pol.items():
                items_yaml += f"      {k}: {v!r}\n"

    text = textwrap.dedent(
        """\
        ---
        schema_version: "1.0"
        org_id: "acme"
        org_name: "acme"
        config_version: "1.0.0"
        trust:
          mode: "unsigned"
        ---

        sources:
          default: { skills: keep, rules: keep, agents: keep, mcps: keep }
          custom:
        """
    ) + (custom_block + "\n" if custom_block else "    []\n")
    text += "\nitems:\n" + items_yaml + "\ninstall:\n  enrollment_script:\n"
    for a in script_actions:
        text += f"    - {a!r}\n"
    fm, body = parse_org_config_text(text)
    return validate_org_config(fm, body)


def _paths(tmp_path):
    return OrgPaths(home_dir=tmp_path)


def test_run_doctor_success(tmp_path):
    cfg = _cfg([{"action": "run_doctor"}])
    result = run_enrollment_script(
        cfg, _paths(tmp_path), doctor=lambda: (True, ["ok"])
    )
    assert isinstance(result, EnrollmentResult)
    assert result.ok is True
    assert result.steps[0].action == "run_doctor"
    assert result.steps[0].success is True


def test_failing_action_halts_script(tmp_path):
    cfg = _cfg([{"action": "run_doctor"}, {"action": "run_doctor"}])
    calls = []

    def doctor():
        calls.append("call")
        return False, ["broken"]

    result = run_enrollment_script(cfg, _paths(tmp_path), doctor=doctor)
    assert result.ok is False
    assert len(result.steps) == 1  # second run_doctor never reached
    assert calls == ["call"]


def test_add_source_failure_does_not_halt(tmp_path):
    cfg = _cfg(
        [
            {"action": "add_source", "source_id": "broken"},
            {"action": "run_doctor"},
        ],
        custom_sources=[
            {"id": "broken", "url": "https://x/y.git", "ref": "main", "contributes": ["skills"]}
        ],
    )

    def boom(url, dest, ref):
        raise PermissionError("denied")

    doctor_calls = []
    result = run_enrollment_script(
        cfg,
        _paths(tmp_path),
        cloner=boom,
        doctor=lambda: (doctor_calls.append("x") or (True, [])),
    )
    assert result.steps[0].action == "add_source"
    assert result.steps[0].success is False
    assert result.failed_sources == ("broken",)
    # The script continued to run_doctor despite the add_source failure.
    assert doctor_calls == ["x"]
    # add_source failures don't poison ok — other actions decide that.
    assert result.ok is True


def test_set_pref_writes_setting(tmp_path, monkeypatch):
    written: dict = {}
    monkeypatch.setattr(preferences_mod, "set_setting", lambda k, v: written.update({k: v}))
    monkeypatch.setattr(preferences_mod, "get_setting", lambda k: None)
    cfg = _cfg([{"action": "set_pref", "key": "hook_mode", "value": "auto"}])
    result = run_enrollment_script(cfg, _paths(tmp_path))
    assert result.ok is True
    assert written == {"hook_mode": "auto"}


def test_set_pref_if_unset_skips_when_set(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_mod, "get_setting", lambda k: "per-repo")
    monkeypatch.setattr(
        preferences_mod, "set_setting", lambda k, v: pytest.fail("must not write")
    )
    cfg = _cfg(
        [{"action": "set_pref", "key": "hook_mode", "value": "auto", "if_unset": True}]
    )
    result = run_enrollment_script(cfg, _paths(tmp_path))
    assert result.ok is True
    assert "skipped" in result.steps[0].message


def test_set_hooks_writes_hook_mode(tmp_path, monkeypatch):
    written: dict = {}
    monkeypatch.setattr(preferences_mod, "set_setting", lambda k, v: written.update({k: v}))
    cfg = _cfg([{"action": "set_hooks", "policy": "per-repo"}])
    result = run_enrollment_script(cfg, _paths(tmp_path))
    assert result.ok is True
    assert written == {"hook_mode": "per-repo"}


def test_install_items_skips_failed_sources(tmp_path, monkeypatch):
    cfg = _cfg(
        [
            {"action": "add_source", "source_id": "broken"},
            {"action": "install_items"},
        ],
        items={
            "skills": {
                "ok-skill": {"source": "aec.default.skills", "stance": "required"},
                "doomed": {"source": "broken", "stance": "required"},
            }
        },
        custom_sources=[
            {"id": "broken", "url": "https://x.git", "ref": "main", "contributes": ["skills"]}
        ],
    )

    seen_policies = []

    class _Result:
        applied = ["ok-skill"]

    def fake_apply_items(policy, scope, **kwargs):
        seen_policies.append(policy)
        return _Result(), []

    monkeypatch.setattr("aec.lib.org_config.apply.apply_items", fake_apply_items)
    monkeypatch.setattr(
        "aec.lib.org_config.apply._catalog", lambda scope: ({}, {}, tmp_path / "m.json")
    )

    def boom(url, dest, ref):
        raise PermissionError("denied")

    result = run_enrollment_script(cfg, _paths(tmp_path), cloner=boom)
    assert result.failed_sources == ("broken",)
    install_step = result.steps[1]
    assert install_step.success is True
    assert "skipped" in install_step.message
    assert len(seen_policies) == 1
    # Only the non-failed-source item is in the install policy.
    keys = set(seen_policies[0].items.keys())
    assert "skills/ok-skill" in keys
    assert "skills/doomed" not in keys
