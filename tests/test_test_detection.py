"""Tests for aec.lib.test_detection module."""

import json
from pathlib import Path

import pytest


class TestFrameworkHooksRegistry:
    """Test the TEST_FRAMEWORK_HOOKS registry is well-formed."""

    def test_registry_has_expected_frameworks(self):
        """Registry should contain all expected test frameworks."""
        from aec.lib.test_detection import TEST_FRAMEWORK_HOOKS

        expected = {
            "jest", "vitest", "pytest", "playwright",
            "cargo_test", "go_test", "rspec",
        }
        assert set(TEST_FRAMEWORK_HOOKS.keys()) == expected

    def test_each_framework_has_required_keys(self):
        """Each framework must have required configuration keys."""
        from aec.lib.test_detection import TEST_FRAMEWORK_HOOKS

        required_keys = {
            "display_name", "languages", "detect_files",
            "default_command", "default_cleanup",
        }
        for key, fw in TEST_FRAMEWORK_HOOKS.items():
            for rk in required_keys:
                assert rk in fw, f"{key} missing {rk}"
            assert isinstance(fw["detect_files"], list), (
                f"{key} detect_files must be a list"
            )
            assert len(fw["detect_files"]) > 0, (
                f"{key} must have at least one detect_file"
            )
            assert isinstance(fw["languages"], list), (
                f"{key} languages must be a list"
            )


class TestDetectTestFrameworks:
    """Test detect_test_frameworks function."""

    def test_detects_jest_via_config_file(self, temp_dir: Path):
        """Should detect Jest when jest.config.ts exists."""
        (temp_dir / "jest.config.ts").write_text("module.exports = {};")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "jest" in keys
        jest = next(r for r in result if r["key"] == "jest")
        assert jest["detected_by"] == "jest.config.ts"
        assert jest["display_name"] == "Jest"

    def test_detects_vitest_via_config_file(self, temp_dir: Path):
        """Should detect Vitest when vitest.config.ts exists."""
        (temp_dir / "vitest.config.ts").write_text("export default {};")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "vitest" in keys
        vitest = next(r for r in result if r["key"] == "vitest")
        assert vitest["detected_by"] == "vitest.config.ts"

    def test_detects_pytest_via_conftest(self, temp_dir: Path):
        """Should detect pytest when conftest.py exists."""
        (temp_dir / "conftest.py").write_text("import pytest")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "pytest" in keys
        pt = next(r for r in result if r["key"] == "pytest")
        assert pt["detected_by"] == "conftest.py"

    def test_detects_pytest_via_pytest_ini(self, temp_dir: Path):
        """Should detect pytest when pytest.ini exists."""
        (temp_dir / "pytest.ini").write_text("[pytest]")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "pytest" in keys
        pt = next(r for r in result if r["key"] == "pytest")
        assert pt["detected_by"] == "pytest.ini"

    def test_detects_playwright_via_config_file(self, temp_dir: Path):
        """Should detect Playwright when playwright.config.ts exists."""
        (temp_dir / "playwright.config.ts").write_text("export default {};")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "playwright" in keys
        pw = next(r for r in result if r["key"] == "playwright")
        assert pw["detected_by"] == "playwright.config.ts"

    def test_detects_cargo_test_via_cargo_toml(self, temp_dir: Path):
        """Should detect Cargo Test when Cargo.toml exists."""
        (temp_dir / "Cargo.toml").write_text("[package]")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "cargo_test" in keys

    def test_detects_go_test_via_go_mod(self, temp_dir: Path):
        """Should detect Go Test when go.mod exists."""
        (temp_dir / "go.mod").write_text("module example.com/foo")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "go_test" in keys

    def test_detects_rspec_via_dot_rspec(self, temp_dir: Path):
        """Should detect RSpec when .rspec exists."""
        (temp_dir / ".rspec").write_text("--color")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "rspec" in keys

    def test_detects_multiple_frameworks(self, temp_dir: Path):
        """Should detect multiple frameworks in a monorepo."""
        (temp_dir / "jest.config.ts").write_text("module.exports = {};")
        (temp_dir / "playwright.config.ts").write_text("export default {};")
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "jest" in keys
        assert "playwright" in keys

    def test_returns_empty_list_when_no_frameworks(self, temp_dir: Path):
        """Should return empty list for a bare directory."""
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        assert result == []

    def test_detects_jest_via_package_json_dev_dependencies(self, temp_dir: Path):
        """Should detect Jest via package.json devDependencies."""
        pkg = {"devDependencies": {"jest": "^29.0.0"}}
        (temp_dir / "package.json").write_text(json.dumps(pkg))
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "jest" in keys
        jest = next(r for r in result if r["key"] == "jest")
        assert "devDependencies" in jest["detected_by"]

    def test_does_not_detect_jest_from_scripts_test_alone(self, temp_dir: Path):
        """Should NOT detect Jest solely because a test script exists.

        The scripts:test detection is a weak signal and should only be
        used when jest is also found in devDependencies.
        """
        pkg = {"scripts": {"test": "jest"}}
        (temp_dir / "package.json").write_text(json.dumps(pkg))
        from aec.lib.test_detection import detect_test_frameworks

        result = detect_test_frameworks(temp_dir)
        keys = [r["key"] for r in result]
        assert "jest" not in keys


class TestScanTestScripts:
    """Test scan_test_scripts function."""

    def test_finds_test_scripts_in_package_json(self, temp_dir: Path):
        """Should find test scripts in package.json."""
        pkg = {"scripts": {"test": "jest", "build": "tsc"}}
        (temp_dir / "package.json").write_text(json.dumps(pkg))
        from aec.lib.test_detection import scan_test_scripts

        result = scan_test_scripts(temp_dir)
        assert len(result) == 1
        assert result[0]["name"] == "test"
        assert result[0]["command"] == "jest"
        assert result[0]["source"] == "package.json"

    def test_finds_multiple_test_scripts(self, temp_dir: Path):
        """Should find test:unit, test:integration, test:e2e scripts."""
        pkg = {
            "scripts": {
                "test": "jest",
                "test:unit": "jest --testPathPattern=unit",
                "test:integration": "jest --testPathPattern=integration",
                "test:e2e": "playwright test",
                "build": "tsc",
            }
        }
        (temp_dir / "package.json").write_text(json.dumps(pkg))
        from aec.lib.test_detection import scan_test_scripts

        result = scan_test_scripts(temp_dir)
        names = [r["name"] for r in result]
        assert "test" in names
        assert "test:unit" in names
        assert "test:integration" in names
        assert "test:e2e" in names
        assert "build" not in names

    def test_returns_empty_for_no_package_json(self, temp_dir: Path):
        """Should return empty list when no package.json exists."""
        from aec.lib.test_detection import scan_test_scripts

        result = scan_test_scripts(temp_dir)
        assert result == []

    def test_handles_malformed_package_json(self, temp_dir: Path):
        """Should handle malformed package.json gracefully."""
        (temp_dir / "package.json").write_text("not valid json {{{")
        from aec.lib.test_detection import scan_test_scripts

        result = scan_test_scripts(temp_dir)
        assert result == []
