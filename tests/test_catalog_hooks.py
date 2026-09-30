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
