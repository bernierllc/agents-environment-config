"""Test framework detection for AI agent repo setup."""

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

TEST_FRAMEWORK_HOOKS: Dict[str, Dict[str, Any]] = {
    "jest": {
        "display_name": "Jest",
        "languages": ["typescript", "javascript"],
        "detect_files": [
            "jest.config.js",
            "jest.config.ts",
            "jest.config.mjs",
            "jest.config.cjs",
        ],
        "detect_package_json": {"devDependencies": ["jest"], "scripts": ["test"]},
        "default_command": "npx jest",
        "default_cleanup": None,
    },
    "vitest": {
        "display_name": "Vitest",
        "languages": ["typescript", "javascript"],
        "detect_files": ["vitest.config.ts", "vitest.config.js", "vitest.config.mts"],
        "detect_package_json": {"devDependencies": ["vitest"]},
        "default_command": "npx vitest run",
        "default_cleanup": None,
    },
    "pytest": {
        "display_name": "pytest",
        "languages": ["python"],
        "detect_files": ["pytest.ini", "conftest.py"],
        "detect_pyproject": {
            "tool.pytest": True,
            "project.optional-dependencies": ["pytest"],
        },
        "default_command": "python -m pytest",
        "default_cleanup": None,
    },
    "playwright": {
        "display_name": "Playwright",
        "languages": ["typescript", "javascript", "python"],
        "detect_files": ["playwright.config.ts", "playwright.config.js"],
        "detect_package_json": {"devDependencies": ["@playwright/test"]},
        "default_command": "npx playwright test",
        "default_cleanup": None,
    },
    "cargo_test": {
        "display_name": "Cargo Test",
        "languages": ["rust"],
        "detect_files": ["Cargo.toml"],
        "default_command": "cargo test",
        "default_cleanup": None,
    },
    "go_test": {
        "display_name": "Go Test",
        "languages": ["go"],
        "detect_files": ["go.mod"],
        "default_command": "go test ./...",
        "default_cleanup": None,
    },
    "rspec": {
        "display_name": "RSpec",
        "languages": ["ruby"],
        "detect_files": [".rspec", "spec/spec_helper.rb"],
        "default_command": "bundle exec rspec",
        "default_cleanup": None,
    },
}


def _parse_package_json(project_dir: Path) -> Dict[str, Any]:
    """Parse package.json from a project directory.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        Parsed package.json dict, or empty dict on failure.
    """
    pkg_path = project_dir / "package.json"
    if not pkg_path.exists():
        return {}
    try:
        return json.loads(pkg_path.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


def _parse_pyproject_toml(project_dir: Path) -> Dict[str, Any]:
    """Parse pyproject.toml from a project directory.

    Uses tomllib (stdlib 3.11+) with fallback to tomli.
    Returns empty dict if file missing or unparseable.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        Parsed pyproject.toml dict, or empty dict on failure.
    """
    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    if tomllib is not None:
        try:
            with open(pyproject_path, "rb") as f:
                return tomllib.load(f)  # type: ignore[no-any-return]
        except Exception:
            return {}

    # Fallback: no toml library available — do simple string parsing
    # for the keys we care about
    return _simple_parse_pyproject(pyproject_path)


def _simple_parse_pyproject(path: Path) -> Dict[str, Any]:
    """Minimal string-based pyproject.toml parser for key sections.

    Only detects [tool.pytest] and pytest in optional-dependencies.

    Args:
        path: Path to pyproject.toml file.

    Returns:
        Dict with 'tool' key if tool.pytest section found.
    """
    try:
        text = path.read_text()
    except OSError:
        return {}

    result: Dict[str, Any] = {}

    # Check for [tool.pytest] or [tool.pytest.ini_options]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("[tool.pytest]", "[tool.pytest.ini_options]"):
            result.setdefault("tool", {})["pytest"] = {}
            break

    return result


def _check_package_json(
    framework_config: Dict[str, Any],
    pkg_data: Dict[str, Any],
) -> str | None:
    """Check if a framework is detected via package.json.

    Args:
        framework_config: The framework's hook config dict.
        pkg_data: Parsed package.json data.

    Returns:
        Detection reason string, or None if not detected.
    """
    detect_pkg = framework_config.get("detect_package_json")
    if not detect_pkg or not pkg_data:
        return None

    dev_deps = pkg_data.get("devDependencies", {})
    dep_names = detect_pkg.get("devDependencies", [])

    for dep in dep_names:
        if dep in dev_deps:
            return f"package.json devDependencies ({dep})"

    return None


def _check_pyproject(
    framework_config: Dict[str, Any],
    pyproject_data: Dict[str, Any],
) -> str | None:
    """Check if a framework is detected via pyproject.toml.

    Args:
        framework_config: The framework's hook config dict.
        pyproject_data: Parsed pyproject.toml data.

    Returns:
        Detection reason string, or None if not detected.
    """
    detect_pyproject = framework_config.get("detect_pyproject")
    if not detect_pyproject or not pyproject_data:
        return None

    # Check for tool.pytest section
    if detect_pyproject.get("tool.pytest"):
        tool = pyproject_data.get("tool", {})
        if "pytest" in tool:
            return "pyproject.toml [tool.pytest]"

    # Check for pytest in optional-dependencies
    opt_deps_check = detect_pyproject.get("project.optional-dependencies", [])
    if opt_deps_check:
        opt_deps = pyproject_data.get("project", {}).get(
            "optional-dependencies", {}
        )
        for group_deps in opt_deps.values() if isinstance(opt_deps, dict) else []:
            for dep in group_deps if isinstance(group_deps, list) else []:
                dep_name = dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip()
                if dep_name in opt_deps_check:
                    return f"pyproject.toml optional-dependencies ({dep_name})"

    return None


def detect_test_frameworks(project_dir: Path) -> List[Dict[str, Any]]:
    """Detect test frameworks in a project directory.

    Scans for framework-specific config files, package.json entries,
    and pyproject.toml sections.

    Detection order per framework:
    1. Check detect_files -- if any exist, framework is detected
    2. Check detect_package_json -- parse package.json for devDependencies
    3. Check detect_pyproject -- parse pyproject.toml for tool sections

    Args:
        project_dir: Path to the project root directory.

    Returns:
        List of dicts with keys: key, display_name, detected_by.
    """
    detected: List[Dict[str, Any]] = []
    pkg_data = _parse_package_json(project_dir)
    pyproject_data = _parse_pyproject_toml(project_dir)

    for fw_key, fw_config in TEST_FRAMEWORK_HOOKS.items():
        # 1. Check detect_files
        file_match = None
        for detect_file in fw_config["detect_files"]:
            if (project_dir / detect_file).exists():
                file_match = detect_file
                break

        if file_match:
            detected.append({
                "key": fw_key,
                "display_name": fw_config["display_name"],
                "detected_by": file_match,
            })
            continue

        # 2. Check package.json
        pkg_reason = _check_package_json(fw_config, pkg_data)
        if pkg_reason:
            detected.append({
                "key": fw_key,
                "display_name": fw_config["display_name"],
                "detected_by": pkg_reason,
            })
            continue

        # 3. Check pyproject.toml
        pyproject_reason = _check_pyproject(fw_config, pyproject_data)
        if pyproject_reason:
            detected.append({
                "key": fw_key,
                "display_name": fw_config["display_name"],
                "detected_by": pyproject_reason,
            })
            continue

    return detected


def scan_test_scripts(project_dir: Path) -> List[Dict[str, str]]:
    """Scan for test-related scripts in package.json and pyproject.toml.

    For package.json: finds scripts keys starting with "test".
    For pyproject.toml: reports pytest command from tool.pytest.ini_options.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        List of dicts with keys: name, command, source.
    """
    results: List[Dict[str, str]] = []

    # Scan package.json scripts
    pkg_data = _parse_package_json(project_dir)
    scripts = pkg_data.get("scripts", {})
    if isinstance(scripts, dict):
        for key, value in scripts.items():
            if key.startswith("test"):
                results.append({
                    "name": key,
                    "command": value,
                    "source": "package.json",
                })

    # Scan pyproject.toml
    pyproject_data = _parse_pyproject_toml(project_dir)
    if pyproject_data:
        ini_options = (
            pyproject_data.get("tool", {})
            .get("pytest", {})
            .get("ini_options", {})
        )
        if ini_options:
            # Report the addopts or testpaths if present
            addopts = ini_options.get("addopts", "")
            testpaths = ini_options.get("testpaths", [])
            if addopts:
                results.append({
                    "name": "pytest",
                    "command": f"python -m pytest {addopts}",
                    "source": "pyproject.toml",
                })
            elif testpaths:
                paths_str = " ".join(testpaths) if isinstance(testpaths, list) else str(testpaths)
                results.append({
                    "name": "pytest",
                    "command": f"python -m pytest {paths_str}",
                    "source": "pyproject.toml",
                })

    return results
