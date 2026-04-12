"""Tests for aec.lib.dismissals module."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest


@dataclass
class FakeScope:
    """Minimal scope for testing without importing real Scope."""

    is_global: bool
    repo_path: Optional[Path] = None

    @property
    def is_local(self) -> bool:
        return not self.is_global


def _make_record(
    catalog_item: str = "engineering-code-reviewer",
    catalog_hash: str = "sha256:abc123",
    local_hash: str = "sha256:def456",
    match_type: str = "similar",
    similarity: Optional[float] = 0.87,
) -> dict:
    """Build a dismissal record for tests."""
    rec = {
        "dismissedAt": "2026-04-10T18:00:00Z",
        "matchedCatalogItem": catalog_item,
        "matchedCatalogVersion": "1.0.0",
        "matchedCatalogHash": catalog_hash,
        "localHash": local_hash,
        "matchType": match_type,
        "scanDepth": 3,
    }
    if similarity is not None:
        rec["similarity"] = similarity
    return rec


class TestGlobalDismissedPath:
    """Test _global_dismissed_path."""

    def test_returns_plural_filename(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import _global_dismissed_path

        assert _global_dismissed_path("agent") == tmp_path / "dismissed-agents.json"
        assert _global_dismissed_path("skill") == tmp_path / "dismissed-skills.json"
        assert _global_dismissed_path("rule") == tmp_path / "dismissed-rules.json"


class TestLoadGlobalDismissed:
    """Test _load_global_dismissed."""

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import _load_global_dismissed

        result = _load_global_dismissed("agent")
        assert result == {"schemaVersion": 1, "items": {}}

    def test_corrupt_json_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        (tmp_path / "dismissed-agents.json").write_text("not json{{{", encoding="utf-8")
        from aec.lib.dismissals import _load_global_dismissed

        result = _load_global_dismissed("agent")
        assert result == {"schemaVersion": 1, "items": {}}

    def test_malformed_structure_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        (tmp_path / "dismissed-agents.json").write_text(
            json.dumps({"no_items_key": True}), encoding="utf-8"
        )
        from aec.lib.dismissals import _load_global_dismissed

        result = _load_global_dismissed("agent")
        assert result == {"schemaVersion": 1, "items": {}}

    def test_valid_file_loaded(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        data = {"schemaVersion": 1, "items": {"foo.md": _make_record()}}
        (tmp_path / "dismissed-agents.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        from aec.lib.dismissals import _load_global_dismissed

        result = _load_global_dismissed("agent")
        assert result["items"]["foo.md"]["matchedCatalogItem"] == "engineering-code-reviewer"


class TestSaveAndReloadGlobal:
    """Test save and reload cycle for global dismissals."""

    def test_save_and_reload(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import _load_global_dismissed, _save_global_dismissed

        record = _make_record()
        data = {"schemaVersion": 1, "items": {"custom-reviewer.md": record}}
        _save_global_dismissed("agent", data)

        reloaded = _load_global_dismissed("agent")
        assert reloaded["items"]["custom-reviewer.md"]["matchedCatalogItem"] == "engineering-code-reviewer"
        assert reloaded["schemaVersion"] == 1

    def test_atomic_write_produces_no_tmp_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import _save_global_dismissed

        _save_global_dismissed("agent", {"schemaVersion": 1, "items": {}})
        assert (tmp_path / "dismissed-agents.json").exists()
        assert not (tmp_path / "dismissed-agents.json.tmp").exists()


class TestRepoDismissals:
    """Test repo-level dismissals via .aec.json."""

    def test_load_missing_aec_json_returns_empty(self, tmp_path):
        from aec.lib.dismissals import _load_repo_dismissed

        result = _load_repo_dismissed("agent", tmp_path)
        assert result == {}

    def test_aec_json_without_dismissed_key_returns_empty(self, tmp_path):
        (tmp_path / ".aec.json").write_text(
            json.dumps({"version": "1.0.0", "installed": {}}, indent=2) + "\n",
            encoding="utf-8",
        )
        from aec.lib.dismissals import _load_repo_dismissed

        result = _load_repo_dismissed("agent", tmp_path)
        assert result == {}

    def test_save_and_reload_repo_dismissal(self, tmp_path):
        # Create initial .aec.json
        (tmp_path / ".aec.json").write_text(
            json.dumps({"version": "1.0.0", "installed": {}}, indent=2) + "\n",
            encoding="utf-8",
        )
        from aec.lib.dismissals import _load_repo_dismissed, _save_repo_dismissal

        record = _make_record()
        _save_repo_dismissal("agent", tmp_path, "custom-reviewer.md", record)

        reloaded = _load_repo_dismissed("agent", tmp_path)
        assert "custom-reviewer.md" in reloaded
        assert reloaded["custom-reviewer.md"]["matchType"] == "similar"

    def test_save_preserves_existing_aec_json_fields(self, tmp_path):
        original = {"version": "1.0.0", "installed": {"skills": {"foo": {}}}}
        (tmp_path / ".aec.json").write_text(
            json.dumps(original, indent=2) + "\n", encoding="utf-8"
        )
        from aec.lib.dismissals import _save_repo_dismissal

        _save_repo_dismissal("agent", tmp_path, "bar.md", _make_record())

        data = json.loads((tmp_path / ".aec.json").read_text(encoding="utf-8"))
        assert data["installed"]["skills"]["foo"] == {}
        assert "bar.md" in data["dismissed"]["agents"]


class TestLoadDismissed:
    """Test the dispatching load_dismissed function."""

    def test_global_scope(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import save_dismissal, load_dismissed

        scope = FakeScope(is_global=True)
        save_dismissal("agent", scope, "foo.md", _make_record())

        result = load_dismissed("agent", scope)
        assert "foo.md" in result

    def test_repo_scope(self, tmp_path):
        (tmp_path / ".aec.json").write_text(
            json.dumps({"version": "1.0.0"}, indent=2) + "\n", encoding="utf-8"
        )
        from aec.lib.dismissals import save_dismissal, load_dismissed

        scope = FakeScope(is_global=False, repo_path=tmp_path)
        save_dismissal("skill", scope, "my-skill/", _make_record(catalog_item="web-testing"))

        result = load_dismissed("skill", scope)
        assert "my-skill/" in result


class TestIsDismissed:
    """Test is_dismissed function."""

    def test_returns_true_for_dismissed_item(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import is_dismissed, save_dismissal

        scope = FakeScope(is_global=True)
        save_dismissal("agent", scope, "custom.md", _make_record())

        assert is_dismissed("agent", scope, "custom.md") is True

    def test_returns_false_for_non_dismissed_item(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import is_dismissed

        scope = FakeScope(is_global=True)
        assert is_dismissed("agent", scope, "nonexistent.md") is False

    def test_repo_scope_dismissed(self, tmp_path):
        (tmp_path / ".aec.json").write_text(
            json.dumps({"version": "1.0.0"}, indent=2) + "\n", encoding="utf-8"
        )
        from aec.lib.dismissals import is_dismissed, save_dismissal

        scope = FakeScope(is_global=False, repo_path=tmp_path)
        save_dismissal("rule", scope, "my-rule.md", _make_record())

        assert is_dismissed("rule", scope, "my-rule.md") is True
        assert is_dismissed("rule", scope, "other.md") is False


class TestClearDismissals:
    """Test clear_dismissals function."""

    def test_clears_global_dismissals(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import clear_dismissals, is_dismissed, save_dismissal

        scope = FakeScope(is_global=True)
        save_dismissal("agent", scope, "a.md", _make_record())
        save_dismissal("agent", scope, "b.md", _make_record())

        assert is_dismissed("agent", scope, "a.md") is True
        clear_dismissals("agent", scope)
        assert is_dismissed("agent", scope, "a.md") is False
        assert is_dismissed("agent", scope, "b.md") is False

    def test_clears_repo_dismissals(self, tmp_path):
        (tmp_path / ".aec.json").write_text(
            json.dumps({"version": "1.0.0"}, indent=2) + "\n", encoding="utf-8"
        )
        from aec.lib.dismissals import clear_dismissals, is_dismissed, save_dismissal

        scope = FakeScope(is_global=False, repo_path=tmp_path)
        save_dismissal("skill", scope, "s1/", _make_record())
        save_dismissal("skill", scope, "s2/", _make_record())

        assert is_dismissed("skill", scope, "s1/") is True
        clear_dismissals("skill", scope)
        assert is_dismissed("skill", scope, "s1/") is False
        assert is_dismissed("skill", scope, "s2/") is False

    def test_clear_on_missing_aec_json_is_noop(self, tmp_path):
        from aec.lib.dismissals import clear_dismissals

        scope = FakeScope(is_global=False, repo_path=tmp_path)
        # Should not raise
        clear_dismissals("agent", scope)


class TestPruneStale:
    """Test prune_stale function."""

    def test_removes_dangling_refs_global(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import is_dismissed, prune_stale, save_dismissal

        scope = FakeScope(is_global=True)
        save_dismissal("agent", scope, "a.md", _make_record(catalog_item="item-a"))
        save_dismissal("agent", scope, "b.md", _make_record(catalog_item="item-b"))
        save_dismissal("agent", scope, "c.md", _make_record(catalog_item="item-c"))

        # Only item-a and item-c exist in catalog
        catalog = {"item-a": {}, "item-c": {}}
        pruned = prune_stale("agent", scope, catalog)

        assert pruned == 1
        assert is_dismissed("agent", scope, "a.md") is True
        assert is_dismissed("agent", scope, "b.md") is False
        assert is_dismissed("agent", scope, "c.md") is True

    def test_removes_dangling_refs_repo(self, tmp_path):
        (tmp_path / ".aec.json").write_text(
            json.dumps({"version": "1.0.0"}, indent=2) + "\n", encoding="utf-8"
        )
        from aec.lib.dismissals import is_dismissed, prune_stale, save_dismissal

        scope = FakeScope(is_global=False, repo_path=tmp_path)
        save_dismissal("skill", scope, "s1/", _make_record(catalog_item="web-testing"))
        save_dismissal("skill", scope, "s2/", _make_record(catalog_item="removed-skill"))

        catalog = {"web-testing": {}}
        pruned = prune_stale("skill", scope, catalog)

        assert pruned == 1
        assert is_dismissed("skill", scope, "s1/") is True
        assert is_dismissed("skill", scope, "s2/") is False

    def test_returns_zero_when_nothing_stale(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import prune_stale, save_dismissal

        scope = FakeScope(is_global=True)
        save_dismissal("agent", scope, "a.md", _make_record(catalog_item="item-a"))

        catalog = {"item-a": {}}
        pruned = prune_stale("agent", scope, catalog)
        assert pruned == 0

    def test_returns_zero_on_empty_dismissals(self, monkeypatch, tmp_path):
        monkeypatch.setattr("aec.lib.dismissals.AEC_HOME", tmp_path)
        from aec.lib.dismissals import prune_stale

        scope = FakeScope(is_global=True)
        pruned = prune_stale("agent", scope, {"item-a": {}})
        assert pruned == 0


class TestShouldResurface:
    """Test should_resurface function."""

    def test_manual_policy_always_false(self):
        from aec.lib.dismissals import should_resurface

        record = _make_record(catalog_hash="sha256:old")
        catalog_hashes = {"engineering-code-reviewer": "sha256:new"}
        assert should_resurface(record, catalog_hashes, "manual") is False

    def test_auto_unchanged_hashes_returns_false(self):
        from aec.lib.dismissals import should_resurface

        record = _make_record(catalog_hash="sha256:abc123")
        catalog_hashes = {"engineering-code-reviewer": "sha256:abc123"}
        assert should_resurface(record, catalog_hashes, "auto") is False

    def test_auto_changed_catalog_hash_returns_true(self):
        from aec.lib.dismissals import should_resurface

        record = _make_record(catalog_hash="sha256:old-hash")
        catalog_hashes = {"engineering-code-reviewer": "sha256:new-hash"}
        assert should_resurface(record, catalog_hashes, "auto") is True

    def test_auto_changed_local_hash_returns_true(self):
        from aec.lib.dismissals import should_resurface

        record = _make_record(
            catalog_hash="sha256:abc123",
            local_hash="sha256:original",
        )
        record["currentLocalHash"] = "sha256:modified"
        catalog_hashes = {"engineering-code-reviewer": "sha256:abc123"}
        assert should_resurface(record, catalog_hashes, "auto") is True

    def test_auto_missing_catalog_item_returns_false(self):
        from aec.lib.dismissals import should_resurface

        record = _make_record(catalog_item="removed-item")
        catalog_hashes = {"other-item": "sha256:xyz"}
        assert should_resurface(record, catalog_hashes, "auto") is False

    def test_auto_no_matched_catalog_item_returns_false(self):
        from aec.lib.dismissals import should_resurface

        record = {"localHash": "sha256:abc"}
        catalog_hashes = {"something": "sha256:xyz"}
        assert should_resurface(record, catalog_hashes, "auto") is False
