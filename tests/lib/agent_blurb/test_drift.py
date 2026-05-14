"""Tests for drift detection (spec §6.1)."""

from aec.lib.agent_blurb.drift import DriftState, compute_drift
from aec.lib.agent_blurb.render import sha256_short


_BODY = "body content"
_BODY_HASH = sha256_short(_BODY)
_EDITED_BODY = "edited body content"


def _make_block(template: str, body: str = _BODY) -> str:
    # The marker's content-hash field is informational only; drift detection
    # re-hashes the body between markers.
    return (
        f"<!-- aec-blurb:start v1 schema=1 aec=2.37.4 "
        f"template-hash={template} content-hash=ignored "
        f"profile=balanced scope=project -->\n"
        f"{body}\n"
        f"<!-- aec-blurb:end -->\n"
    )


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
            on_disk_content=_make_block(template="abc"),
            stored_template_hash="abc",
            stored_content_hash=_BODY_HASH,
            shipped_template_hash="abc",
        )
        assert state == DriftState.CLEAN

    def test_upstream_update_when_template_changed(self):
        state = compute_drift(
            on_disk_content=_make_block(template="0ad"),
            stored_template_hash="0ad",
            stored_content_hash=_BODY_HASH,
            shipped_template_hash="4ee",
        )
        assert state == DriftState.UPSTREAM_UPDATE

    def test_manual_edit_when_on_disk_differs(self):
        state = compute_drift(
            on_disk_content=_make_block(template="abc", body=_EDITED_BODY),
            stored_template_hash="abc",
            stored_content_hash=_BODY_HASH,
            shipped_template_hash="abc",
        )
        assert state == DriftState.MANUAL_EDIT

    def test_conflict_when_both_changed(self):
        state = compute_drift(
            on_disk_content=_make_block(template="0ad", body=_EDITED_BODY),
            stored_template_hash="0ad",
            stored_content_hash=_BODY_HASH,
            shipped_template_hash="4ee",
        )
        assert state == DriftState.CONFLICT
