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


from aec.lib.plugin_install import install_per_tool


def _manifest():
    return {"install_type": "per-tool", "install": {"tools": {
        "claude": {"run": ["bash", "-c", "echo hi"]},
        "gemini": {"steps": "copy X to ~/.gemini"},
    }}}


def test_per_tool_runs_run_tools_and_prints_steps_tools():
    ran, printed = [], []
    summary = install_per_tool(
        _manifest(), ["claude", "gemini"],
        runner=lambda c: ran.append(c), confirm=lambda *_: True,
        printer=lambda s: printed.append(s), pref=None)
    assert ran == [["bash", "-c", "echo hi"]]
    assert any("gemini" in p or "~/.gemini" in p for p in printed)
    assert summary["claude"] == "run"
    assert summary["gemini"] == "instructions"


def test_per_tool_pref_downgrades_run_to_instructions():
    ran, printed = [], []
    install_per_tool(
        _manifest(), ["claude"],
        runner=lambda c: ran.append(c), confirm=lambda *_: True,
        printer=lambda s: printed.append(s), pref="instructions-only")
    assert ran == []
    assert printed  # claude's command was printed, not executed


def test_per_tool_declined_confirm_does_not_run():
    ran = []
    summary = install_per_tool(
        _manifest(), ["claude"],
        runner=lambda c: ran.append(c), confirm=lambda *_: False,
        printer=lambda s: None, pref=None)
    assert ran == []
    assert summary["claude"] == "declined"


from aec.lib.plugin_install import install_external


def test_external_prints_and_never_runs():
    ran, printed = [], []
    m = {"install_type": "external", "install": {"external": {
        "download": "https://impeccable.style/#downloads",
        "instructions": "1. download 2. run /impeccable setup"}}}
    install_external(m, runner=lambda c: ran.append(c), printer=lambda s: printed.append(s))
    assert ran == []
    assert any("impeccable.style" in p for p in printed)
    assert any("/impeccable setup" in p for p in printed)


from aec.lib.plugin_install import install_plugin


def test_install_plugin_external_returns_result_and_prints_usage():
    printed = []
    m = {"schema": "loadout/v1", "item_type": "plugin", "name": "imp",
         "version": "1.0.0", "description": "x", "source": "https://x",
         "install_type": "external", "usage": "run /imp setup",
         "install": {"external": {"download": "https://x", "instructions": "go"}}}
    result = install_plugin(m, {"claude": {}}, runner=lambda c: None,
                            confirm=lambda *_: True, printer=lambda s: printed.append(s),
                            pref=None)
    assert result["install_type"] == "external"
    assert result["executed"] is False
    assert any("run /imp setup" in p for p in printed)


def test_install_plugin_marketplace_without_claude_is_skipped():
    m = {"schema": "loadout/v1", "item_type": "plugin", "name": "p",
         "version": "1.0.0", "description": "x", "source": "https://x",
         "install_type": "marketplace",
         "install": {"marketplace": "a/b", "plugin": "b"}}
    result = install_plugin(m, {"cursor": {}}, runner=lambda c: None,
                            confirm=lambda *_: True, printer=lambda s: None, pref=None)
    assert result["targets"] == []
    assert result["executed"] is False


from aec.lib.plugin_install import uninstall_plugin


def test_uninstall_plugin_no_block_prints_manual_cleanup():
    # marketplace plugin with no uninstall block: must punt to manual cleanup,
    # never fabricate/run a marketplace-uninstall command.
    ran, printed = [], []
    m = {"install_type": "marketplace",
         "install": {"marketplace": "a/b", "plugin": "b"}}
    result = uninstall_plugin(m, {"claude": {}}, runner=lambda c: ran.append(c),
                              confirm=lambda *_: True, printer=lambda s: printed.append(s),
                              pref=None)
    assert ran == []
    assert result["executed"] is False
    assert any("manual cleanup may be required" in p for p in printed)
