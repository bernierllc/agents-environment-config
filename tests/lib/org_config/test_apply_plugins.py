"""Org-config plugin governance: items.plugins is validated, applied via the
loadout engine, and never dropped or crashed on."""

import json

import pytest

import aec.lib.config as config_mod
import aec.lib.preferences as prefs_mod
from aec.lib.manifest_v2 import get_installed, load_manifest, record_plugin_install, save_manifest
from aec.lib.org_config.apply import (
    apply_plugins,
    blocked_item_keys,
    compile_desired_items,
)
from aec.lib.org_config.effective import EffectivePolicy
from aec.lib.org_config.errors import OrgConfigValidationError
from aec.lib.org_config.parser import parse_org_config_text
from aec.lib.org_config.schema import ITEM_TYPES, ItemPolicy, Stance
from aec.lib.org_config.validator import validate_org_config


def _policy(items):
    return EffectivePolicy(
        items=items, preferences={}, prompts={}, default_sources={},
        custom_sources=[], install_mode=None, held=(),
    )


def _item(name, stance, org="acme"):
    return {
        f"plugins/{name}": (
            org, ItemPolicy(source="aec.default.plugins", stance=Stance(stance), version=None)
        )
    }


def _config(item_yaml: str):
    text = f"""---
schema_version: "1.0"
org_id: "acme"
org_name: "Acme"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom: []

items:
  plugins:
{item_yaml}
"""
    return validate_org_config(*parse_org_config_text(text))


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    """A one-plugin catalog whose install command touches a marker file."""
    marker = tmp_path / "ran"
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "schema": "loadout/v1", "item_type": "plugin", "name": "demo",
        "version": "1.2.3", "description": "d", "source": "https://example.com/demo",
        "supports": ["claude"], "install_type": "per-tool",
        "install": {"tools": {"claude": {"run": ["touch", str(marker)]}}},
        "uninstall": {"tools": {"claude": {"run": ["touch", str(marker) + ".removed"]}}},
    }))
    monkeypatch.setattr(config_mod, "detect_agents", lambda: {"claude": {}})
    monkeypatch.setattr(prefs_mod, "get_setting", lambda key, *a, **k: None)
    return {
        "marker": marker,
        "source_dirs": {"plugins": tmp_path / "plugins"},
        "manifest_path": tmp_path / "installed-manifest.json",
    }


def test_plugins_is_a_known_item_type():
    assert "plugins" in ITEM_TYPES


def test_plugin_block_is_validated_not_dropped():
    cfg = _config("    demo: { source: aec.default.plugins, stance: required }")
    assert cfg.items["plugins"]["demo"].stance is Stance.REQUIRED


@pytest.mark.parametrize("line, field", [
    ("    demo: { source: aec.default.plugins, stance: pinned }", "stance"),
    ("    demo: { source: aec.default.plugins, stance: required, version: '1.0.0' }", "version"),
])
def test_plugin_pin_and_version_are_rejected(line, field):
    with pytest.raises(OrgConfigValidationError) as exc:
        _config(line)
    assert exc.value.field_path.endswith(field)


def test_plugin_policies_do_not_reach_the_file_copy_pipeline():
    items = {**_item("demo", "required"), **_item("gone", "blocked")}
    pol = _policy(items)
    assert compile_desired_items(pol, "global") == []
    assert blocked_item_keys(pol) == []


def test_required_plugin_installs_and_is_recorded(catalog):
    installed, removed = apply_plugins(
        _policy(_item("demo", "required")), "global",
        source_dirs=catalog["source_dirs"], manifest_path=catalog["manifest_path"],
    )
    assert installed == ["demo"] and removed == []
    assert catalog["marker"].exists()
    rec = get_installed(load_manifest(catalog["manifest_path"]), "global", "plugins")
    assert rec["demo"]["version"] == "1.2.3"


def test_instructions_only_never_runs_commands(catalog, monkeypatch):
    monkeypatch.setattr(prefs_mod, "get_setting", lambda key, *a, **k: "instructions-only")
    apply_plugins(
        _policy(_item("demo", "required")), "global",
        source_dirs=catalog["source_dirs"], manifest_path=catalog["manifest_path"],
    )
    assert not catalog["marker"].exists()


def test_blocked_plugin_is_uninstalled(catalog, monkeypatch):
    manifest = load_manifest(catalog["manifest_path"])
    record_plugin_install(manifest, "global", "demo", "1.2.3",
                          install_type="per-tool", targets=["claude"])
    save_manifest(manifest, catalog["manifest_path"])
    called = []
    import aec.lib.org_config.apply as apply_mod
    monkeypatch.setattr(apply_mod, "_uninstall_blocked",
                        lambda item_type, name, scope: called.append((item_type, name, scope)))
    _, removed = apply_plugins(
        _policy(_item("demo", "blocked")), "global",
        source_dirs=catalog["source_dirs"], manifest_path=catalog["manifest_path"],
    )
    assert removed == ["demo"] and called == [("plugin", "demo", "global")]
