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
