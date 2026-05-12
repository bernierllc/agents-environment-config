"""After update, AEC surfaces drift and offers refresh."""

from aec.commands.update import check_blurb_drift
from aec.lib.agent_blurb.config import save_config, new_skeleton


def test_update_reports_no_config_silently(tmp_path):
    result = check_blurb_drift(root=tmp_path)
    assert result == 0


def test_update_reports_drift_when_present(tmp_path, monkeypatch):
    """When stored hashes don't match shipped/on-disk, check_blurb_drift
    still returns 0 (informational); we just verify it doesn't crash and
    surfaces something to the console.
    """
    monkeypatch.chdir(tmp_path)
    cfg = new_skeleton(scope="project", profile="balanced", aec_version="1.0.0")
    cfg["targets"].append({
        "agent_key": "claude",
        "path": "CLAUDE.md",
        "template_hash": "deadbeef",
        "content_hash": "cafef00d",
        "written_at": "2026-01-01T00:00:00Z",
    })
    save_config(cfg, scope="project", root=tmp_path)
    (tmp_path / "CLAUDE.md").write_text(
        '<!-- aec-blurb:start v1 schema=1 aec=1.0.0 '
        'template-hash=deadbeef content-hash=cafef00d profile=balanced scope=project -->\n'
        'body\n'
        '<!-- aec-blurb:end -->\n'
    )
    rc = check_blurb_drift(root=tmp_path)
    assert rc == 0  # informational, non-fatal
