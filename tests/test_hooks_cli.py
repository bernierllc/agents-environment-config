"""Tests for `aec hooks` Typer sub-app."""

import json

from typer.testing import CliRunner


class TestHooksValidateCLI:
    def setup_method(self):
        from aec.cli import app
        self.app = app
        self.runner = CliRunner()

    def test_validate_passes_minimal_file(self, tmp_path):
        p = tmp_path / "hooks.json"
        p.write_text(json.dumps({"$schema": "x", "version": "1.0.0", "hooks": []}))
        result = self.runner.invoke(
            self.app, ["hooks", "validate", str(p), "--item-version", "1.0.0"],
        )
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_fails_on_version_mismatch(self, tmp_path):
        p = tmp_path / "hooks.json"
        p.write_text(json.dumps({"$schema": "x", "version": "1.0.0", "hooks": []}))
        result = self.runner.invoke(
            self.app, ["hooks", "validate", str(p), "--item-version", "2.0.0"],
        )
        assert result.exit_code != 0

    def test_validate_warns_but_succeeds_on_mirror_override(self, tmp_path):
        data = {
            "$schema": "x", "version": "1.0.0", "hooks": [],
            "claude": [{
                "id": "mirror", "matcher": "Edit|Write",
                "hooks": [{"type": "command", "command": "x"}],
            }],
        }
        p = tmp_path / "hooks.json"
        p.write_text(json.dumps(data))
        result = self.runner.invoke(
            self.app, ["hooks", "validate", str(p), "--item-version", "1.0.0"],
        )
        assert result.exit_code == 0
        text = (result.stdout + (result.output or "")).lower()
        assert "warn" in text or "mirror" in text

    def test_validate_reports_missing_file(self, tmp_path):
        result = self.runner.invoke(
            self.app,
            ["hooks", "validate", str(tmp_path / "does-not-exist.json"),
             "--item-version", "1.0.0"],
        )
        assert result.exit_code == 2


def _seed_repo(tmp_path):
    """Install one claude hook into a fresh repo; return its root."""
    from aec.lib.hooks.installer import install_item_hooks

    item_dir = tmp_path / "item"
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "hooks.json").write_text(json.dumps({
        "$schema": "x", "version": "1.0.0", "hooks": [{
            "id": "lint", "event": "on_file_edit",
            "command": "echo hi", "description": "lint",
        }],
    }))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    install_item_hooks(
        item_type="skill", item_key="demo", item_version="1.0.0",
        item_dir=item_dir, repo_root=repo_root, agents=["claude"],
    )
    return repo_root


class TestHooksVerifyCLI:
    def setup_method(self):
        from aec.cli import app
        self.app = app
        self.runner = CliRunner()

    def test_healthy_repo_exits_zero(self, tmp_path):
        repo_root = _seed_repo(tmp_path)
        result = self.runner.invoke(self.app, ["hooks", "verify", str(repo_root)])
        assert result.exit_code == 0
        assert "ok" in result.stdout.lower()

    def test_clobbered_repo_exits_one_and_names_drift(self, tmp_path):
        repo_root = _seed_repo(tmp_path)
        (repo_root / ".claude/settings.json").write_text(json.dumps({"hooks": {}}))
        result = self.runner.invoke(self.app, ["hooks", "verify", str(repo_root)])
        assert result.exit_code == 1
        text = result.stdout.lower()
        assert "missing" in text
        assert "demo" in text and "lint" in text

    def test_repo_without_hooks_exits_zero(self, tmp_path):
        repo_root = tmp_path / "empty"
        repo_root.mkdir()
        result = self.runner.invoke(self.app, ["hooks", "verify", str(repo_root)])
        assert result.exit_code == 0
