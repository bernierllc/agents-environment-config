"""Tests for compiling/applying org-policy items (A4)."""

import aec.lib.org_config.apply as apply_mod
from aec.lib.org_config.apply import (
    blocked_item_keys,
    compile_desired_items,
    remove_blocked_items,
)
from aec.lib.org_config.effective import EffectivePolicy
from aec.lib.org_config.schema import ItemPolicy, Stance


def _policy(items):
    return EffectivePolicy(
        items=items,
        preferences={},
        prompts={},
        default_sources={},
        custom_sources=[],
        install_mode=None,
        held=(),
    )


def _item(subject, stance, version=None, org="acme"):
    plural = subject.split("/", 1)[0]
    source = f"aec.default.{plural}"
    return {subject: (org, ItemPolicy(source=source, stance=Stance(stance), version=version))}


def test_compile_required_item():
    pol = _policy(_item("skills/foo", "required"))
    desired = compile_desired_items(pol, "global")
    assert len(desired) == 1
    assert desired[0].item_type == "skill"
    assert desired[0].name == "foo"
    assert desired[0].scope == "global"


def test_compile_pinned_uses_version():
    pol = _policy(_item("skills/foo", "pinned", version="2.1.0"))
    desired = compile_desired_items(pol, "global")
    assert desired[0].version_spec == "2.1.0"


def test_blocked_and_silent_excluded_from_desired():
    items = {}
    items.update(_item("skills/foo", "blocked"))
    items.update(_item("skills/bar", "silent"))
    items.update(_item("skills/baz", "required"))
    pol = _policy(items)
    names = {d.name for d in compile_desired_items(pol, "global")}
    assert names == {"baz"}


def test_blocked_item_keys():
    items = {}
    items.update(_item("rules/r1", "blocked"))
    items.update(_item("skills/foo", "required"))
    pol = _policy(items)
    assert blocked_item_keys(pol) == [("rule", "r1")]


def test_remove_blocked_items_removes_installed_blocked(tmp_path, monkeypatch):
    # rules/r1 is "installed" so it gets removed.
    manifest_path = tmp_path / "manifest.json"

    # Manifest reports r1 installed at global scope so blocked removal triggers.
    from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest

    m = load_manifest(manifest_path)
    record_install(m, "global", "rules", "r1", "1.0.0")
    save_manifest(m, manifest_path)

    removed_calls = []
    monkeypatch.setattr(
        apply_mod, "_uninstall_blocked", lambda t, n, s: removed_calls.append((t, n, s))
    )
    items = {}
    items.update(_item("rules/r1", "blocked"))
    pol = _policy(items)
    removed, errors = remove_blocked_items(pol, "global", manifest_path=manifest_path)
    assert errors == []
    assert removed == [("rule", "r1")]
    assert removed_calls == [("rule", "r1", "global")]
