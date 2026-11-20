"""Releases are tag-only: the version comes from the git tag, never from a commit to main.

Why this is pinned: ruleset `main promotion gate` rejects any direct push to main, so a
release that commits a version bump there cannot work. If someone reintroduces a static
version in pyproject.toml, or a workflow step that commits/pushes a branch, the release
breaks only after a promotion lands. These tests fail before that.
"""

import re
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = (REPO / "pyproject.toml").read_text(encoding="utf-8")
WORKFLOW = yaml.safe_load(
    (REPO / ".github" / "workflows" / "version-bump.yml").read_text(encoding="utf-8")
)


def _section(text: str, header: str) -> str:
    match = re.search(rf"^\[{re.escape(header)}\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    assert match, f"[{header}] missing from pyproject.toml"
    return match.group(1)


def test_pyproject_version_is_dynamic_not_static():
    project = _section(PYPROJECT, "project")
    assert re.search(r'^dynamic\s*=\s*\[[^\]]*"version"', project, re.M)
    assert not re.search(r"^version\s*=", project, re.M), "static version would be stale at release"


def test_setuptools_scm_is_pinned_in_build_requires():
    build = _section(PYPROJECT, "build-system")
    assert re.search(r'"setuptools-scm==\d+\.\d+\.\d+"', build)


def test_setuptools_scm_is_switched_on():
    # Without this table setuptools silently builds version 0.0.0.
    assert re.search(r"^\[tool\.setuptools_scm\]", PYPROJECT, re.M)


def test_release_workflow_pushes_only_the_tag():
    steps = WORKFLOW["jobs"]["version-bump"]["steps"]
    script = "\n".join(s.get("run", "") for s in steps)
    assert "git commit" not in script
    assert not re.search(r"git push\s+origin\s+(main|HEAD)\b", script)
    assert "--tags" not in script
    assert re.search(r'git push origin "refs/tags/v\$NEW"', script)


def test_runtime_version_is_the_installed_metadata_version():
    from importlib.metadata import version

    from aec.lib.config import VERSION

    assert VERSION == version("aec")
    assert VERSION not in ("0.0.0", "2.0.0")


def test_version_without_install_metadata_is_the_zero_sentinel(monkeypatch):
    import importlib.metadata

    from aec.lib import config

    def _missing(_name):
        raise PackageNotFoundError("aec")

    monkeypatch.setattr(importlib.metadata, "version", _missing)
    assert config._read_version() == "0.0.0"
