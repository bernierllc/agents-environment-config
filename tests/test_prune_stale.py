"""Tests for tracking.prune_stale: dead paths leave both tracking stores."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def stores(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    live = temp_dir / "projects" / "live"
    live.mkdir(parents=True)
    dead_txt = temp_dir / "projects" / "gone-txt"
    dead_json = temp_dir / "projects" / "gone-json"  # tracked only in JSON
    log = aec_home / "setup-repo-locations.txt"
    log.write_text(
        f"2026-04-04T00:00:00Z|2.5.4|{live}\n2026-04-04T00:00:00Z|2.5.4|{dead_txt}\n"
    )
    repos = {
        str(p): {"aecJsonPath": f"{p}/.aec.json", "trackedAt": "2026-04-04T00:00:00Z", "aecVersion": "2.5.4"}
        for p in (live, dead_txt, dead_json)
    }
    store = aec_home / "tracked-repos.json"
    store.write_text(json.dumps({"schemaVersion": 1, "repos": repos}))
    import aec.lib.tracking as tracking_mod
    monkeypatch.setattr(tracking_mod, "AEC_SETUP_LOG", log)
    return {"live": live, "dead": {dead_txt, dead_json}, "log": log, "store": store}


def test_dry_run_reports_dead_paths_from_both_stores(stores):
    from aec.lib.tracking import prune_stale

    assert {r.path for r in prune_stale(dry_run=True)} == stores["dead"]
    assert len(json.loads(stores["store"].read_text())["repos"]) == 3


def test_prune_removes_dead_paths_from_both_stores(stores):
    from aec.lib.tracking import prune_stale

    assert {r.path for r in prune_stale()} == stores["dead"]
    assert list(json.loads(stores["store"].read_text())["repos"]) == [str(stores["live"])]
    assert stores["log"].read_text().strip().endswith(f"|{stores['live']}")
    assert prune_stale() == []




def test_dry_run_does_not_migrate_legacy_txt(stores):
    from aec.lib.tracking import prune_stale

    stores["store"].unlink()  # only the legacy txt exists: load would migrate it
    assert {r.path for r in prune_stale(dry_run=True)} == {p for p in stores["dead"] if "txt" in p.name}
    assert not stores["store"].exists()
def test_prune_drops_manifest_scopes_of_removed_worktrees(stores, monkeypatch):
    import aec.lib.config as config_mod
    from aec.lib.manifest_v2 import load_manifest, save_manifest
    from aec.lib.tracking import prune_stale

    path = stores["store"].parent / "installed-manifest.json"
    monkeypatch.setattr(config_mod, "INSTALLED_MANIFEST_V2", path)
    manifest = load_manifest(path)
    gone = stores["live"] / ".worktrees" / "topic"  # never tracked, now removed
    for repo in (stores["live"], gone):
        manifest["repos"][str(repo)] = {"skills": {}, "rules": {}, "agents": {}}
    save_manifest(manifest, path)

    assert gone in {r.path for r in prune_stale(dry_run=True)}  # previewed
    assert str(gone) in load_manifest(path)["repos"]
    assert gone in {r.path for r in prune_stale()}  # reported
    assert list(load_manifest(path)["repos"]) == [str(stores["live"])]
