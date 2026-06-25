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
