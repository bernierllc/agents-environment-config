"""Tests for hooks on items used in place in the aec repo (catalog_hooks)."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


def _skill(repo: Path, version: str) -> Path:
    skill = repo / ".claude" / "skills" / "my-skill"
    (skill / "scripts").mkdir(parents=True, exist_ok=True)
    (skill / "scripts" / "guard.py").write_text("print('ok')\n")
    (skill / "SKILL.md").write_text(
        f"---\nname: my-skill\nversion: {version}\ndescription: t\nauthor: t\n---\n"
    )
    (skill / "hooks.json").write_text(json.dumps({
        "version": version,
        "hooks": [{
            "id": "my-guard",
            "event": "pre_tool_use",
            "command": "aec run-script skill:my-skill guard.py",
            "description": "test guard",
            "blocking": True,
            "timeout_ms": 1000,
        }],
    }))
    return skill


@pytest.fixture
def catalog(temp_dir):
    repo = temp_dir / "aec-repo"
    _skill(repo, "1.0.0")
    with patch(
        "aec.lib.catalog_hooks.get_source_dirs",
        return_value={"skills": repo / ".claude" / "skills"},
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
