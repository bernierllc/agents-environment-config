from pathlib import Path
from aec.lib.org_config.paths import OrgPaths


def test_org_paths_exposes_canonical_locations(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)

    assert paths.aec_dir == tmp_path / ".aec"
    assert paths.orgs_dir == tmp_path / ".aec" / "orgs"
    assert paths.conflict_resolutions == tmp_path / ".aec" / "conflict-resolutions.json"
    assert paths.conflict_resolutions_history == tmp_path / ".aec" / "conflict-resolutions.history.json"
    assert paths.trusted_orgs == tmp_path / ".aec" / "trusted-orgs.json"


def test_org_paths_per_org_helpers(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)

    assert paths.config_for("acme") == tmp_path / ".aec" / "orgs" / "acme.yaml"
    assert paths.state_for("acme") == tmp_path / ".aec" / "orgs" / "acme.state.json"
    assert paths.state_lock_for("acme") == tmp_path / ".aec" / "orgs" / "acme.state.json.lock"


def test_org_paths_default_uses_real_home():
    paths = OrgPaths.default()
    assert paths.home_dir == Path.home()
