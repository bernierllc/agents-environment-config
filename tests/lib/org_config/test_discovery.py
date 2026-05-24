import shutil
from pathlib import Path

from aec.lib.org_config.discovery import discover_enrolled_orgs
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


def test_discovery_loads_multiple_orgs_sorted_by_id(tmp_path: Path):
    paths = OrgPaths(home_dir=tmp_path)
    paths.orgs_dir.mkdir(parents=True)
    # File names intentionally not in org_id order to prove sorting is by id.
    shutil.copy(FIXTURES / "valid-full.yaml", paths.orgs_dir / "zzz.yaml")  # org_id "acme"
    shutil.copy(FIXTURES / "valid-minimal.yaml", paths.orgs_dir / "aaa.yaml")  # org_id "minimal"

    orgs = discover_enrolled_orgs(paths)
    assert [e.config.org_id for e in orgs] == ["acme", "minimal"]
