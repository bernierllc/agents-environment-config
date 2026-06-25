# tests/test_plugin_install.py
import pytest
from aec.lib.plugin_install import resolve_targets


def test_intersects_supports_with_detected():
    m = {"install_type": "per-tool", "supports": ["claude", "cursor", "gemini"]}
    assert resolve_targets(m, {"claude": {}, "cursor": {}}) == ["claude", "cursor"]


def test_omitted_supports_means_all_detected():
    m = {"install_type": "per-tool"}
    assert resolve_targets(m, {"claude": {}, "qwen": {}}) == ["claude", "qwen"]


def test_marketplace_is_claude_only():
    m = {"install_type": "marketplace", "supports": ["claude", "cursor"]}
    assert resolve_targets(m, {"claude": {}, "cursor": {}}) == ["claude"]


def test_marketplace_without_claude_is_empty():
    m = {"install_type": "marketplace"}
    assert resolve_targets(m, {"cursor": {}}) == []


from aec.lib.plugin_install import effective_policy, install_marketplace


def test_policy_external_always_instructions():
    assert effective_policy("external", has_run=False, pref=None) == "instructions"


def test_policy_marketplace_runs_by_default():
    assert effective_policy("marketplace", has_run=True, pref=None) == "run"


def test_policy_pref_downgrades_to_instructions():
    assert effective_policy("marketplace", has_run=True, pref="instructions-only") == "instructions"


def test_marketplace_handler_runs_two_commands():
    calls = []
    m = {"install_type": "marketplace",
         "install": {"marketplace": "DietrichGebert/ponytail", "plugin": "ponytail"}}
    install_marketplace(m, runner=lambda cmd: calls.append(cmd), confirm=lambda _: True)
    assert calls == [
        ["claude", "plugin", "marketplace", "add", "DietrichGebert/ponytail"],
        ["claude", "plugin", "install", "ponytail"],
    ]


def test_marketplace_handler_respects_declined_confirm():
    calls = []
    m = {"install_type": "marketplace",
         "install": {"marketplace": "x", "plugin": "y"}}
    install_marketplace(m, runner=lambda cmd: calls.append(cmd), confirm=lambda _: False)
    assert calls == []
