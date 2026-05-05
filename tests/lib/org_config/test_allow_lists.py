"""Tests for the org-config overlay allow-lists.

These tests fence the contract that:
  - Each allow-listed preference key is a real preference (in
    ``KNOWN_PREFERENCE_KEYS``).
  - Each allow-listed prompt ID matches a constant in ``aec.lib.prompt_ids``.
  - Excluded keys/IDs really are excluded from the positive lists.
"""
from __future__ import annotations

import pytest

from aec.lib.org_config.allow_lists import (
    PREFERENCES_ALLOW_LIST,
    PREFERENCES_DYNAMIC_NAMESPACES,
    PREFERENCES_EXCLUDED_KEYS,
    PROMPTS_ALLOW_LIST,
    PROMPTS_DYNAMIC_PREFIXES,
    PROMPTS_EXCLUDED_IDS,
)


# --- Preferences ------------------------------------------------------------


def test_preferences_allow_list_is_non_empty():
    assert len(PREFERENCES_ALLOW_LIST) > 0


def test_preferences_allow_list_keys_are_known_preferences():
    """Every allow-listed pref key must be a real preference writer target."""
    from aec.lib.preferences import KNOWN_PREFERENCE_KEYS

    for key in PREFERENCES_ALLOW_LIST:
        assert key in KNOWN_PREFERENCE_KEYS, (
            f"Allow-listed preference {key!r} is not in KNOWN_PREFERENCE_KEYS"
        )


def test_preferences_allow_list_does_not_include_excluded_keys():
    for excluded in PREFERENCES_EXCLUDED_KEYS:
        assert excluded not in PREFERENCES_ALLOW_LIST


def test_preferences_excluded_keys_are_known():
    """Excluded keys must still be real preference targets — otherwise we
    are excluding a key that doesn't exist (likely a typo)."""
    from aec.lib.preferences import KNOWN_PREFERENCE_KEYS

    for key in PREFERENCES_EXCLUDED_KEYS:
        assert key in KNOWN_PREFERENCE_KEYS


def test_preferences_optional_rules_match_registry():
    """The five optional_rules.* entries must mirror OPTIONAL_FEATURES."""
    from aec.lib.preferences import OPTIONAL_FEATURES

    for feature_key in OPTIONAL_FEATURES:
        assert feature_key in PREFERENCES_ALLOW_LIST, (
            f"OPTIONAL_FEATURES key {feature_key!r} is not allow-listed"
        )


def test_preferences_dynamic_namespace_is_configurable_instructions():
    assert PREFERENCES_DYNAMIC_NAMESPACES == ("configurable_instructions",)


# --- Prompts ----------------------------------------------------------------


def test_prompts_allow_list_is_non_empty():
    assert len(PROMPTS_ALLOW_LIST) > 0


def test_prompts_allow_list_matches_static_prompt_ids():
    """Every static prompt ID emitted by callsites must be in the allow-list,
    and the allow-list must not contain stray IDs not declared in
    aec.lib.prompt_ids.
    """
    from aec.lib.prompt_ids import ALL_STATIC_PROMPT_IDS

    static_ids = set(ALL_STATIC_PROMPT_IDS)
    allow_keys = set(PROMPTS_ALLOW_LIST.keys())
    assert static_ids == allow_keys, (
        f"Drift between prompt_ids and allow-list:\n"
        f"  in code only: {static_ids - allow_keys}\n"
        f"  in allow-list only: {allow_keys - static_ids}"
    )


def test_prompts_dynamic_prefixes_match_prompt_ids_module():
    from aec.lib.prompt_ids import DYNAMIC_PROMPT_ID_PREFIXES

    assert set(PROMPTS_DYNAMIC_PREFIXES.keys()) == set(DYNAMIC_PROMPT_ID_PREFIXES)


def test_prompts_excluded_ids_are_disjoint_from_allow_list():
    for excluded in PROMPTS_EXCLUDED_IDS:
        assert excluded not in PROMPTS_ALLOW_LIST


# --- Type tag sanity --------------------------------------------------------


@pytest.mark.parametrize("key,tag", list(PREFERENCES_ALLOW_LIST.items()))
def test_every_preferences_entry_has_a_type_tag(key, tag):
    assert isinstance(tag, str) and tag, f"{key} has empty type tag"


@pytest.mark.parametrize("pid,tag", list(PROMPTS_ALLOW_LIST.items()))
def test_every_prompt_entry_has_a_type_tag(pid, tag):
    assert isinstance(tag, str) and tag, f"{pid} has empty type tag"
