"""Tests for agent-blurb decline state (separate sibling file)."""

from aec.lib.agent_blurb.decline import (
    DECLINE_FILENAME,
    is_declined,
    record_decline,
    clear_decline,
    should_reprompt,
)


class TestDecline:
    def test_decline_filename_constant(self):
        assert DECLINE_FILENAME == "agent-blurb-decline.json"

    def test_not_declined_by_default(self, tmp_path):
        assert is_declined(scope="project", root=tmp_path) is False

    def test_record_then_is_declined(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert is_declined(scope="project", root=tmp_path) is True

    def test_clear_removes_decline(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        clear_decline(scope="project", root=tmp_path)
        assert is_declined(scope="project", root=tmp_path) is False

    def test_should_reprompt_on_major_version_bump(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert should_reprompt(scope="project", root=tmp_path, current_version="3.0.0") is True

    def test_should_not_reprompt_on_minor_bump(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert should_reprompt(scope="project", root=tmp_path, current_version="2.38.0") is False

    def test_should_not_reprompt_on_patch_bump(self, tmp_path):
        record_decline(scope="project", root=tmp_path, aec_version="2.37.4")
        assert should_reprompt(scope="project", root=tmp_path, current_version="2.37.5") is False

    def test_should_reprompt_if_never_declined(self, tmp_path):
        assert should_reprompt(scope="project", root=tmp_path, current_version="2.37.4") is True
