"""Tests for profile model and command classification."""

import pytest
from aec.lib.agent_blurb.profile import (
    PROFILES,
    DEFAULT_PROFILE,
    READ_ONLY_COMMANDS,
    DESTRUCTIVE_COMMANDS,
    ITEM_TYPES,
    expand_profile,
    classify_command,
    CommandClass,
)


class TestProfiles:
    def test_default_profile_is_balanced(self):
        assert DEFAULT_PROFILE == "balanced"

    def test_three_named_profiles_exist(self):
        assert set(PROFILES.keys()) == {"conservative", "balanced", "permissive"}

    def test_balanced_matrix(self):
        assert PROFILES["balanced"] == {
            "agents":   {"additive": "ask"},
            "skills":   {"additive": "auto"},
            "rules":    {"additive": "auto"},
            "packages": {"additive": "ask"},
            "plugins":  {"additive": "ask"},
        }

    def test_conservative_is_all_ask(self):
        for itype in ITEM_TYPES:
            assert PROFILES["conservative"][itype]["additive"] == "ask"

    def test_permissive_is_all_auto(self):
        for itype in ITEM_TYPES:
            assert PROFILES["permissive"][itype]["additive"] == "auto"

    def test_item_types_match_spec(self):
        assert ITEM_TYPES == ("agents", "skills", "rules", "packages", "plugins")


class TestExpandProfile:
    def test_named_profile_returns_matrix(self):
        m = expand_profile("balanced")
        assert m == PROFILES["balanced"]

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            expand_profile("nope")

    def test_returned_matrix_is_copy_not_reference(self):
        m = expand_profile("balanced")
        m["agents"]["additive"] = "auto"
        assert PROFILES["balanced"]["agents"]["additive"] == "ask"


class TestClassifyCommand:
    @pytest.mark.parametrize("cmd", ["list", "doctor", "search", "info", "outdated"])
    def test_read_only(self, cmd):
        assert classify_command(cmd) == CommandClass.READ_ONLY

    @pytest.mark.parametrize("cmd", ["install"])
    def test_additive(self, cmd):
        assert classify_command(cmd) == CommandClass.ADDITIVE

    @pytest.mark.parametrize("cmd", ["uninstall", "update", "upgrade", "untrack", "prune"])
    def test_destructive(self, cmd):
        assert classify_command(cmd) == CommandClass.DESTRUCTIVE

    def test_unknown_command_defaults_destructive(self):
        """Unknown commands are conservatively classified as destructive."""
        assert classify_command("hypothetical-future-command") == CommandClass.DESTRUCTIVE


class TestReadOnlyAndDestructiveSets:
    def test_untrack_is_destructive(self):
        assert "untrack" in DESTRUCTIVE_COMMANDS
        assert "untrack" not in READ_ONLY_COMMANDS

    def test_update_is_destructive(self):
        assert "update" in DESTRUCTIVE_COMMANDS
