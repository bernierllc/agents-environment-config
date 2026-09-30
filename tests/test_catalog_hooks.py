"""Tests for hooks on items used in place in the aec repo (catalog_hooks)."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


def _skill(repo: Path, version: str, when: dict = None, hooks_version: str = None) -> Path:
    skill = repo / ".claude" / "skills" / "my-skill"
    (skill / "scripts").mkdir(parents=True, exist_ok=True)
    (skill / "scripts" / "guard.py").write_text("print('ok')\n")
    (skill / "SKILL.md").write_text(
        f"---\nname: my-skill\nversion: {version}\ndescription: t\nauthor: t\n---\n"
    )
    hook = {
        "id": "my-guard",
        "event": "pre_tool_use",
        "command": "aec run-script skill:my-skill guard.py",
        "description": "test guard",
        "blocking": True,
        "timeout_ms": 1000,
    }
    if when:
        hook["when"] = when
    (skill / "hooks.json").write_text(json.dumps({"version": hooks_version or version, "hooks": [hook]}))
    return skill


@pytest.fixture
def catalog(temp_dir):
    repo = temp_dir / "aec-repo"
    _skill(repo, "1.0.0")
    with patch(
        "aec.lib.catalog_hooks.get_source_dirs",
        return_value={"skills": repo / ".claude" / "skills", "rules": repo / ".agent-rules"},
    ):
        yield repo


def test_refresh_rewires_when_catalog_version_moves(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks.state import load_state

    assert catalog_hooks.wire(catalog, "skill", "my-skill")
    assert catalog_hooks.refresh(catalog) == []

    _skill(catalog, "1.1.0")  # a submodule bump
    assert catalog_hooks.refresh(catalog) == ["my-skill: 1.0.0 -> 1.1.0"]
    assert load_state(catalog, "skill", "my-skill").item_version == "1.1.0"
    assert "my-skill" in (catalog / ".claude" / "settings.json").read_text()


def test_refresh_unwires_items_that_left_the_catalog(catalog):
    from aec.lib import catalog_hooks

    catalog_hooks.wire(catalog, "skill", "my-skill")
    shutil.rmtree(catalog / ".claude" / "skills" / "my-skill")

    assert catalog_hooks.refresh(catalog) == ["my-skill: removed from catalog, hooks unwired"]
    assert "my-skill" not in (catalog / ".claude" / "settings.json").read_text()


def test_unwire_never_touches_item_files(catalog):
    from aec.lib import catalog_hooks

    catalog_hooks.wire(catalog, "skill", "my-skill")
    assert catalog_hooks.unwire(catalog, "skill", "my-skill")
    assert (catalog / ".claude" / "skills" / "my-skill" / "hooks.json").exists()
    assert not catalog_hooks.unwire(catalog, "skill", "my-skill")


def test_refresh_dry_run_reports_without_rewiring(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks.state import load_state

    catalog_hooks.wire(catalog, "skill", "my-skill")
    _skill(catalog, "1.1.0")
    assert catalog_hooks.refresh(catalog, dry_run=True) == ["my-skill: 1.0.0 -> 1.1.0"]
    assert load_state(catalog, "skill", "my-skill").item_version == "1.0.0"


def test_refresh_keeps_custom_check_consent(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks.state import load_state

    _skill(catalog, "1.0.0", when={"custom_check": "true"})
    catalog_hooks.wire(catalog, "skill", "my-skill", allow_custom_check=True)
    _skill(catalog, "1.1.0", when={"custom_check": "true"})

    # a plain `aec upgrade` (no --yes) still honours consent given at install
    assert catalog_hooks.refresh(catalog) == ["my-skill: 1.0.0 -> 1.1.0"]
    assert load_state(catalog, "skill", "my-skill").item_version == "1.1.0"
    assert "my-skill" in (catalog / ".claude" / "settings.json").read_text()


def test_failed_refresh_keeps_previous_hooks(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks.state import load_state

    catalog_hooks.wire(catalog, "skill", "my-skill")
    _skill(catalog, "1.1.0", hooks_version="9.9.9")  # hooks.json fails validation

    [line] = catalog_hooks.refresh(catalog)
    assert "not refreshed, previous hooks kept" in line
    assert load_state(catalog, "skill", "my-skill").hooks_installed
    assert "my-skill" in (catalog / ".claude" / "settings.json").read_text()



def test_refresh_with_missing_script_keeps_previous_hooks(catalog):
    from aec.lib import catalog_hooks

    catalog_hooks.wire(catalog, "skill", "my-skill")
    before = (catalog / ".claude" / "settings.json").read_text()
    skill = _skill(catalog, "1.1.0")
    (skill / "scripts" / "guard.py").unlink()  # valid hooks.json, fails at render

    [line] = catalog_hooks.refresh(catalog)
    assert "not refreshed, previous hooks kept" in line
    assert (catalog / ".claude" / "settings.json").read_text() == before


def test_refresh_write_failure_restores_every_agent(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks import installer

    catalog_hooks.wire(catalog, "skill", "my-skill")
    settings = catalog / ".claude" / "settings.json"
    before = settings.read_text()
    _skill(catalog, "1.1.0")

    # Retraction has already rewritten settings.json when the install write fails.
    with patch.object(installer, "_install_claude", side_effect=OSError("disk full")):
        [line] = catalog_hooks.refresh(catalog)
    assert "not refreshed, previous hooks kept" in line
    assert settings.read_text() == before


def test_wire_unwires_when_item_no_longer_ships_hooks(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks.state import STATE_DIR

    skill = catalog / ".claude" / "skills" / "my-skill"
    catalog_hooks.wire(catalog, "skill", "my-skill")
    (skill / "hooks.json").unlink()

    assert catalog_hooks.wire(catalog, "skill", "my-skill") is False
    assert not list((catalog / STATE_DIR).glob("*.json"))
    assert "my-skill" not in (catalog / ".claude" / "settings.json").read_text()


def test_refresh_state_write_failure_restores_configs(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks import installer

    catalog_hooks.wire(catalog, "skill", "my-skill")
    settings = catalog / ".claude" / "settings.json"
    before = settings.read_text()
    skill = _skill(catalog, "1.1.0")
    (skill / "scripts" / "guard2.py").write_text("print('ok')\n")
    hooks = skill / "hooks.json"
    hooks.write_text(hooks.read_text().replace("guard.py", "guard2.py"))  # new payload

    with patch.object(installer.hook_state, "save_state", side_effect=OSError("read-only")):
        [line] = catalog_hooks.refresh(catalog)
    assert "not refreshed, previous hooks kept" in line
    assert settings.read_text() == before


def test_refresh_isolates_one_items_failure(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks.state import STATE_DIR, load_state

    catalog_hooks.wire(catalog, "skill", "my-skill")
    state_dir = catalog / STATE_DIR
    (state_dir / "skill.aaa-broken.json").write_text((state_dir / "skill.my-skill.json").read_text())
    _skill(catalog, "1.1.0")

    real = catalog_hooks._catalog_item
    def lookup(item_type, name):
        if name == "aaa-broken":
            raise OSError("unreadable source")
        return real(item_type, name)

    with patch.object(catalog_hooks, "_catalog_item", side_effect=lookup):
        lines = catalog_hooks.refresh(catalog)
    assert lines[0].startswith("aaa-broken: not refreshed")
    assert "my-skill: 1.0.0 -> 1.1.0" in lines
    assert load_state(catalog, "skill", "my-skill").item_version == "1.1.0"


def test_failed_unwire_restores_hooks_and_state(catalog):
    from aec.lib import catalog_hooks
    from aec.lib.hooks import installer
    from aec.lib.hooks.state import load_state

    catalog_hooks.wire(catalog, "skill", "my-skill")
    settings = catalog / ".claude" / "settings.json"
    before = settings.read_text()
    shutil.rmtree(catalog / ".claude" / "skills" / "my-skill")  # left the catalog

    with patch.object(installer.hook_state, "remove_state", side_effect=OSError("busy")):
        [line] = catalog_hooks.refresh(catalog)
    assert "not refreshed" in line
    assert settings.read_text() == before
    assert load_state(catalog, "skill", "my-skill").hooks_installed


def test_rollback_leaves_a_directory_in_the_way_alone(catalog):
    from aec.lib.hooks import installer

    blocker = catalog / ".gemini" / "settings.json"
    blocker.mkdir(parents=True)
    settings = catalog / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{}")

    snap = installer._snapshot_configs(catalog, [], [])
    settings.write_text('{"changed": true}')
    installer._restore_configs(snap)
    assert settings.read_text() == "{}"
    assert blocker.is_dir()

def test_directory_form_rule_wires_from_its_directory(catalog):
    from aec.lib import catalog_hooks

    rule = catalog / ".agent-rules" / "my-rule"
    (rule / "scripts").mkdir(parents=True)
    (rule / "scripts" / "guard.py").write_text("print('ok')\n")
    (rule / "rule.md").write_text("---\nname: my-rule\nversion: 1.0.0\ndescription: t\n---\n")
    (rule / "hooks.json").write_text(json.dumps({"version": "1.0.0", "hooks": [{
        "id": "rule-guard", "event": "pre_tool_use",
        "command": "aec run-script rule:my-rule guard.py",
        "description": "t", "blocking": True, "timeout_ms": 1000,
    }]}))
    assert catalog_hooks.wire(catalog, "rule", "my-rule")


def test_refresh_unwires_when_new_version_drops_hooks_json(catalog):
    from aec.lib import catalog_hooks

    catalog_hooks.wire(catalog, "skill", "my-skill")
    skill = _skill(catalog, "1.1.0")
    (skill / "hooks.json").unlink()

    assert catalog_hooks.refresh(catalog) == ["my-skill: 1.0.0 -> 1.1.0: no hooks.json, hooks unwired"]
    assert "my-skill" not in (catalog / ".claude" / "settings.json").read_text()
    assert catalog_hooks.refresh(catalog) == []
