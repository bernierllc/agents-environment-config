import shutil
from pathlib import Path

import pytest

from aec.lib.org_config.discovery import discover_enrolled_orgs
from aec.lib.org_config.errors import OrgConfigMultiOrgRejectedError
from aec.lib.org_config.paths import OrgPaths


FIXTURES = Path(__file__).parent / "fixtures"


def test_discovery_finds_no_orgs_when_dir_empty(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    assert discover_enrolled_orgs(paths) == []


def test_discovery_finds_no_orgs_when_dir_missing(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    assert discover_enrolled_orgs(paths) == []


def test_discovery_loads_single_org(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "valid-minimal.yaml", paths.orgs_dir / "minimal.yaml")

    orgs = discover_enrolled_orgs(paths)
    assert len(orgs) == 1
    assert orgs[0].config.org_id == "minimal"
    assert orgs[0].content_hash.startswith("sha256:")
    assert orgs[0].source_path == paths.orgs_dir / "minimal.yaml"


def test_discovery_rejects_multiple_orgs_in_phase_1(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    shutil.copy(FIXTURES / "valid-minimal.yaml", paths.orgs_dir / "minimal.yaml")
    shutil.copy(FIXTURES / "valid-full.yaml", paths.orgs_dir / "full.yaml")

    with pytest.raises(OrgConfigMultiOrgRejectedError, match="phase 3"):
        discover_enrolled_orgs(paths)
