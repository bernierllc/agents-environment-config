# tests/test_loadout.py
import json
from pathlib import Path

import pytest

from aec.lib.loadout import load_loadout, validate_loadout, LoadoutError

VALID = {
    "schema": "loadout/v1", "item_type": "plugin", "name": "ponytail",
    "version": "1.0.0", "description": "x", "source": "https://example.com",
    "install_type": "external",
    "install": {"external": {"download": "https://x", "instructions": "do it"}},
}


def _write(d: Path, name: str, data: dict) -> Path:
    p = d / name
    p.write_text(json.dumps(data))
    return p


class TestValidate:
    def test_valid_passes(self) -> None:
        validate_loadout(VALID)  # no raise

    def test_missing_required_field_raises(self) -> None:
        bad = {k: v for k, v in VALID.items() if k != "source"}
        with pytest.raises(LoadoutError, match="source"):
            validate_loadout(bad)

    def test_bad_install_type_raises(self) -> None:
        with pytest.raises(LoadoutError, match="install_type"):
            validate_loadout({**VALID, "install_type": "nope"})

    def test_wrong_schema_version_raises(self) -> None:
        with pytest.raises(LoadoutError, match="schema"):
            validate_loadout({**VALID, "schema": "loadout/v2"})


class TestLoad:
    def test_loads_plugin_json(self, tmp_path: Path) -> None:
        _write(tmp_path, "plugin.json", VALID)
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_json_wins_over_yaml(self, tmp_path: Path) -> None:
        _write(tmp_path, "plugin.json", VALID)
        (tmp_path / "plugin.yaml").write_text("name: other\n")
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_loadout_subdir(self, tmp_path: Path) -> None:
        sub = tmp_path / ".loadout"
        sub.mkdir()
        _write(sub, "plugin.json", VALID)
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_missing_returns_error(self, tmp_path: Path) -> None:
        with pytest.raises(LoadoutError, match="no loadout"):
            load_loadout(tmp_path)

    def test_loads_plugin_yaml(self, tmp_path: Path) -> None:
        yaml = pytest.importorskip("yaml")
        (tmp_path / "plugin.yaml").write_text(yaml.safe_dump(VALID))
        assert load_loadout(tmp_path)["name"] == "ponytail"

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        pytest.importorskip("yaml")
        (tmp_path / "plugin.yaml").write_text("name: [unbalanced\n  bad: :\n")
        with pytest.raises(LoadoutError, match="parse"):
            load_loadout(tmp_path)
