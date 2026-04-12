"""Tests for aec.lib.tracked_repos and dual-write in aec.lib.tracking."""

import json
from pathlib import Path

import pytest

from aec.lib.tracked_repos import (
    add_tracked_repo,
    get_all_tracked_paths,
    is_tracked,
    load_tracked_repos,
    migrate_from_txt,
    remove_tracked_repo,
    save_tracked_repos,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_path(home: Path) -> Path:
    return home / ".agents-environment-config" / "tracked-repos.json"


def _txt_path(home: Path) -> Path:
    return home / ".agents-environment-config" / "setup-repo-locations.txt"


def _ensure_aec_home(home: Path) -> Path:
    aec_home = home / ".agents-environment-config"
    aec_home.mkdir(parents=True, exist_ok=True)
    return aec_home


# ---------------------------------------------------------------------------
# load_tracked_repos
# ---------------------------------------------------------------------------

class TestLoadTrackedRepos:
    """Tests for load_tracked_repos."""

    def test_returns_empty_store_when_no_files(self, mock_home: Path) -> None:
        """Returns default schema when neither JSON nor txt exist."""
        data = load_tracked_repos()
        assert data == {"schemaVersion": 1, "repos": {}}

    def test_returns_empty_store_on_corrupt_json(self, mock_home: Path) -> None:
        """Returns default schema when JSON file is corrupt."""
        _ensure_aec_home(mock_home)
        _json_path(mock_home).write_text("not json at all", encoding="utf-8")
        data = load_tracked_repos()
        assert data == {"schemaVersion": 1, "repos": {}}

    def test_returns_empty_store_on_missing_repos_key(self, mock_home: Path) -> None:
        """Returns default schema when JSON lacks 'repos' key."""
        _ensure_aec_home(mock_home)
        _json_path(mock_home).write_text('{"schemaVersion": 1}', encoding="utf-8")
        data = load_tracked_repos()
        assert data == {"schemaVersion": 1, "repos": {}}

    def test_reads_valid_json(self, mock_home: Path) -> None:
        """Reads well-formed JSON store correctly."""
        _ensure_aec_home(mock_home)
        store = {
            "schemaVersion": 1,
            "repos": {
                "/tmp/project-a": {
                    "aecJsonPath": "/tmp/project-a/.aec.json",
                    "trackedAt": "2026-04-08T00:00:00Z",
                    "aecVersion": "2.18.2",
                }
            },
        }
        _json_path(mock_home).write_text(json.dumps(store), encoding="utf-8")
        data = load_tracked_repos()
        assert data == store

    def test_auto_migrates_from_txt(self, mock_home: Path) -> None:
        """When JSON doesn't exist but txt does, auto-migrates."""
        aec_home = _ensure_aec_home(mock_home)
        txt = _txt_path(mock_home)
        txt.write_text("2026-04-01T00:00:00Z|2.17.0|/tmp/proj\n")

        data = load_tracked_repos()
        # Path.resolve() may expand /tmp -> /private/tmp on macOS
        resolved = str(Path("/tmp/proj").resolve())
        assert resolved in data["repos"]
        # JSON file should now exist
        assert _json_path(mock_home).exists()


# ---------------------------------------------------------------------------
# add_tracked_repo / remove_tracked_repo
# ---------------------------------------------------------------------------

class TestAddRemoveRepo:
    """Tests for add_tracked_repo and remove_tracked_repo."""

    def test_add_and_retrieve(self, mock_home: Path) -> None:
        """Added repo appears in the store."""
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "myapp"
        repo.mkdir(parents=True)

        add_tracked_repo(repo, "2.18.2")

        data = load_tracked_repos()
        abs_path = str(repo.resolve())
        assert abs_path in data["repos"]
        entry = data["repos"][abs_path]
        assert entry["aecVersion"] == "2.18.2"
        assert entry["aecJsonPath"] == str(repo.resolve() / ".aec.json")
        assert "trackedAt" in entry

    def test_add_overwrites_existing(self, mock_home: Path) -> None:
        """Adding an already-tracked repo updates the entry."""
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "myapp"
        repo.mkdir(parents=True)

        add_tracked_repo(repo, "2.17.0")
        add_tracked_repo(repo, "2.18.2")

        data = load_tracked_repos()
        abs_path = str(repo.resolve())
        assert data["repos"][abs_path]["aecVersion"] == "2.18.2"

    def test_remove_repo(self, mock_home: Path) -> None:
        """Removing a repo deletes it from the store."""
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "myapp"
        repo.mkdir(parents=True)

        add_tracked_repo(repo, "2.18.2")
        remove_tracked_repo(repo)

        data = load_tracked_repos()
        assert str(repo.resolve()) not in data["repos"]

    def test_remove_nonexistent_is_noop(self, mock_home: Path) -> None:
        """Removing a repo that isn't tracked doesn't raise."""
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "ghost"
        repo.mkdir(parents=True)

        remove_tracked_repo(repo)  # should not raise

        data = load_tracked_repos()
        assert data["repos"] == {}


# ---------------------------------------------------------------------------
# is_tracked
# ---------------------------------------------------------------------------

class TestIsTracked:
    """Tests for is_tracked."""

    def test_returns_true_for_tracked(self, mock_home: Path) -> None:
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "myapp"
        repo.mkdir(parents=True)

        add_tracked_repo(repo, "2.18.2")
        assert is_tracked(repo) is True

    def test_returns_false_for_untracked(self, mock_home: Path) -> None:
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "unknown"
        repo.mkdir(parents=True)
        assert is_tracked(repo) is False

    def test_returns_false_when_no_store(self, mock_home: Path) -> None:
        repo = mock_home / "projects" / "unknown"
        repo.mkdir(parents=True)
        assert is_tracked(repo) is False


# ---------------------------------------------------------------------------
# get_all_tracked_paths
# ---------------------------------------------------------------------------

class TestGetAllTrackedPaths:
    """Tests for get_all_tracked_paths."""

    def test_filters_nonexistent(self, mock_home: Path) -> None:
        """Paths that don't exist on disk are excluded."""
        _ensure_aec_home(mock_home)
        real_repo = mock_home / "projects" / "real"
        real_repo.mkdir(parents=True)

        add_tracked_repo(real_repo, "2.18.2")

        # Manually add a fake path that doesn't exist
        data = load_tracked_repos()
        data["repos"]["/nonexistent/fake"] = {
            "aecJsonPath": "/nonexistent/fake/.aec.json",
            "trackedAt": "2026-04-08T00:00:00Z",
            "aecVersion": "2.18.2",
        }
        save_tracked_repos(data)

        paths = get_all_tracked_paths()
        assert real_repo.resolve() in paths
        assert Path("/nonexistent/fake") not in paths

    def test_returns_empty_when_no_store(self, mock_home: Path) -> None:
        assert get_all_tracked_paths() == []


# ---------------------------------------------------------------------------
# migrate_from_txt
# ---------------------------------------------------------------------------

class TestMigrateFromTxt:
    """Tests for migrate_from_txt."""

    def test_migrates_entries(self, mock_home: Path) -> None:
        """Reads legacy txt format and writes to JSON."""
        aec_home = _ensure_aec_home(mock_home)
        txt = _txt_path(mock_home)
        txt.write_text(
            "2026-04-01T10:00:00Z|2.17.0|/tmp/alpha\n"
            "2026-04-02T11:00:00Z|2.18.0|/tmp/beta\n"
        )

        count = migrate_from_txt()
        assert count == 2

        data = load_tracked_repos()
        alpha = str(Path("/tmp/alpha").resolve())
        beta = str(Path("/tmp/beta").resolve())
        assert alpha in data["repos"]
        assert beta in data["repos"]
        assert data["repos"][alpha]["aecVersion"] == "2.17.0"
        assert data["repos"][alpha]["trackedAt"] == "2026-04-01T10:00:00Z"

    def test_returns_zero_when_no_txt(self, mock_home: Path) -> None:
        assert migrate_from_txt() == 0

    def test_returns_zero_for_empty_txt(self, mock_home: Path) -> None:
        _ensure_aec_home(mock_home)
        _txt_path(mock_home).write_text("")
        assert migrate_from_txt() == 0

    def test_skips_malformed_lines(self, mock_home: Path) -> None:
        """Lines with fewer than 3 pipe-delimited parts are skipped."""
        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "good"
        repo.mkdir(parents=True)
        txt = _txt_path(mock_home)
        txt.write_text(
            "malformed-line\n"
            f"2026-04-01T10:00:00Z|2.17.0|{repo}\n"
        )
        count = migrate_from_txt()
        assert count == 1


# ---------------------------------------------------------------------------
# Dual-write: tracking.log_setup writes to both files
# ---------------------------------------------------------------------------

class TestDualWrite:
    """Tests that tracking.log_setup writes to both txt and JSON."""

    def test_log_setup_writes_both(self, mock_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """log_setup should write to both setup-repo-locations.txt and tracked-repos.json."""
        import aec.lib.tracking as tracking_mod

        aec_home = _ensure_aec_home(mock_home)

        # Monkeypatch the names as seen by tracking.py (it uses
        # `from .config import AEC_HOME, AEC_SETUP_LOG, AEC_README`).
        monkeypatch.setattr(tracking_mod, "AEC_HOME", aec_home)
        monkeypatch.setattr(tracking_mod, "AEC_SETUP_LOG", _txt_path(mock_home))
        monkeypatch.setattr(tracking_mod, "AEC_README", aec_home / "README.md")

        readme = aec_home / "README.md"
        readme.write_text("# test")
        txt = _txt_path(mock_home)
        txt.touch()

        repo = mock_home / "projects" / "dualtest"
        repo.mkdir(parents=True)

        tracking_mod.log_setup(repo)

        # Check txt file
        txt_content = txt.read_text()
        assert str(repo.resolve()) in txt_content

        # Check JSON file (uses dynamic Path.home(), already mocked)
        data = load_tracked_repos()
        assert str(repo.resolve()) in data["repos"]

    def test_is_logged_checks_json_first(self, mock_home: Path) -> None:
        """is_logged should find repos in JSON even if txt is empty."""
        from aec.lib.tracking import is_logged

        _ensure_aec_home(mock_home)
        repo = mock_home / "projects" / "jsononly"
        repo.mkdir(parents=True)

        # Write only to JSON
        add_tracked_repo(repo, "2.18.2")

        assert is_logged(repo) is True

    def test_is_logged_falls_back_to_txt(self, mock_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """is_logged should find repos in txt if JSON has no match."""
        import aec.lib.tracking as tracking_mod

        _ensure_aec_home(mock_home)

        # Monkeypatch the precomputed AEC_SETUP_LOG so the txt fallback
        # reads from the mocked home directory.
        monkeypatch.setattr(tracking_mod, "AEC_SETUP_LOG", _txt_path(mock_home))

        repo = mock_home / "projects" / "txtonly"
        repo.mkdir(parents=True)

        # Write only to txt
        txt = _txt_path(mock_home)
        txt.write_text(f"2026-04-01T00:00:00Z|2.17.0|{repo.resolve()}\n")

        assert tracking_mod.is_logged(repo) is True
