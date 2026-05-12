"""Tests for drift detection (spec §6.1)."""

from aec.lib.agent_blurb.drift import DriftState, compute_drift


class TestCompute:
    def test_not_installed_when_marker_missing(self):
        state = compute_drift(
            on_disk_content="# CLAUDE.md\n",
            stored_template_hash=None,
            stored_content_hash=None,
            shipped_template_hash="abc",
        )
        assert state == DriftState.NOT_INSTALLED

    def test_clean_when_all_match(self):
        state = compute_drift(
            on_disk_content=_make_block(template="abc", content="def"),
            stored_template_hash="abc",
            stored_content_hash="def",
            shipped_template_hash="abc",
        )
        assert state == DriftState.CLEAN

    def test_upstream_update_when_template_changed(self):
        state = compute_drift(
            on_disk_content=_make_block(template="0ad", content="def"),
            stored_template_hash="0ad",
            stored_content_hash="def",
            shipped_template_hash="4ee",
        )
        assert state == DriftState.UPSTREAM_UPDATE

    def test_manual_edit_when_on_disk_differs(self):
        state = compute_drift(
            on_disk_content=_make_block(template="abc", content="ed17ed"),
            stored_template_hash="abc",
            stored_content_hash="def",
            shipped_template_hash="abc",
        )
        assert state == DriftState.MANUAL_EDIT

    def test_conflict_when_both_changed(self):
        state = compute_drift(
            on_disk_content=_make_block(template="0ad", content="ed17ed"),
            stored_template_hash="0ad",
            stored_content_hash="def",
            shipped_template_hash="4ee",
        )
        assert state == DriftState.CONFLICT


def _make_block(template: str, content: str) -> str:
    return (
        f"<!-- aec-blurb:start v1 schema=1 aec=2.37.4 "
        f"template-hash={template} content-hash={content} "
        f"profile=balanced scope=project -->\n"
        f"body\n"
        f"<!-- aec-blurb:end -->\n"
    )
