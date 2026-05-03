"""Tests for aec.lib.skill_dependencies.resolve_install_graph."""

import pytest
from pathlib import Path
from typing import List


def _make_skill_md(name: str, version: str, deps: List[dict] = None) -> str:
    """Build SKILL.md content with optional dependencies block."""
    lines = [
        "---",
        f"name: {name}",
        f"version: {version}",
        f"description: Test skill {name}",
        "author: Test",
    ]
    if deps:
        lines.append("dependencies:")
        lines.append("  skills:")
        for dep in deps:
            lines.append(f'    - name: {dep["name"]}')
            lines.append(f'      min_version: "{dep["min_version"]}"')
            lines.append(f'      reason: "{dep["reason"]}"')
    lines.append("---")
    lines.append(f"# {name}")
    return "\n".join(lines) + "\n"


def _create_skill_in(base: Path, name: str, version: str, deps: List[dict] = None) -> Path:
    """Create a minimal skill directory under base/name/SKILL.md."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(_make_skill_md(name, version, deps))
    return skill_dir


class TestNoDepsCases:
    def test_no_deps_returns_empty_to_install(self, temp_dir):
        """A skill with no dependencies produces an empty ResolvedGraph."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(temp_dir, "target-skill", "1.0.0")

        available = {"target-skill": {"version": "1.0.0", "path": "target-skill"}}
        installed = {}

        result = resolve_install_graph("target-skill", available, installed, temp_dir)

        assert result.to_install == []
        assert result.already_satisfied == []
        assert result.missing == []
        assert result.version_conflicts == []
        assert result.cycles == []


class TestDirectDepCases:
    def test_dep_not_installed_added_to_to_install(self, temp_dir):
        """A dep in the catalog but not installed should appear in to_install."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(temp_dir, "dep-skill", "2.0.0")
        _create_skill_in(
            temp_dir,
            "target-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "2.0.0", "reason": "Needs dep"}],
        )

        available = {
            "target-skill": {"version": "1.0.0", "path": "target-skill"},
            "dep-skill": {"version": "2.0.0", "path": "dep-skill"},
        }
        installed = {}

        result = resolve_install_graph("target-skill", available, installed, temp_dir)

        assert "dep-skill" in result.to_install
        assert result.already_satisfied == []
        assert result.missing == []
        assert result.version_conflicts == []

    def test_dep_already_satisfied_excluded(self, temp_dir):
        """A dep installed at the exact required version is in already_satisfied."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(temp_dir, "dep-skill", "3.3.0")
        _create_skill_in(
            temp_dir,
            "target-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "3.3.0", "reason": "Uses dep"}],
        )

        available = {
            "target-skill": {"version": "1.0.0", "path": "target-skill"},
            "dep-skill": {"version": "3.3.0", "path": "dep-skill"},
        }
        installed = {
            "dep-skill": {"version": "3.3.0", "contentHash": "", "installedAt": "2026-01-01"},
        }

        result = resolve_install_graph("target-skill", available, installed, temp_dir)

        assert result.to_install == []
        assert "dep-skill" in result.already_satisfied
        assert result.missing == []
        assert result.version_conflicts == []

    def test_dep_already_satisfied_newer_version(self, temp_dir):
        """A dep installed at a *newer* than required version is also satisfied."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(temp_dir, "dep-skill", "4.0.0")
        _create_skill_in(
            temp_dir,
            "target-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "3.3.0", "reason": "Uses dep"}],
        )

        available = {
            "target-skill": {"version": "1.0.0", "path": "target-skill"},
            "dep-skill": {"version": "4.0.0", "path": "dep-skill"},
        }
        installed = {
            "dep-skill": {"version": "4.0.0", "contentHash": "", "installedAt": "2026-01-01"},
        }

        result = resolve_install_graph("target-skill", available, installed, temp_dir)

        assert result.to_install == []
        assert "dep-skill" in result.already_satisfied

    def test_dep_below_min_version_in_version_conflicts(self, temp_dir):
        """A dep that is installed but below the required version goes to version_conflicts."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(temp_dir, "dep-skill", "3.3.0")
        _create_skill_in(
            temp_dir,
            "target-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "3.3.0", "reason": "Needs new dep"}],
        )

        available = {
            "target-skill": {"version": "1.0.0", "path": "target-skill"},
            "dep-skill": {"version": "3.3.0", "path": "dep-skill"},
        }
        installed = {
            "dep-skill": {"version": "2.0.0", "contentHash": "", "installedAt": "2026-01-01"},
        }

        result = resolve_install_graph("target-skill", available, installed, temp_dir)

        assert result.to_install == []
        assert "dep-skill" in result.version_conflicts
        assert result.missing == []
        assert result.already_satisfied == []

    def test_dep_not_in_catalog_in_missing(self, temp_dir):
        """A dep that is unknown to the catalog goes to missing."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(
            temp_dir,
            "target-skill",
            "1.0.0",
            deps=[{"name": "unknown-dep", "min_version": "1.0.0", "reason": "Needs it"}],
        )

        available = {
            "target-skill": {"version": "1.0.0", "path": "target-skill"},
        }
        installed = {}

        result = resolve_install_graph("target-skill", available, installed, temp_dir)

        assert "unknown-dep" in result.missing
        assert result.to_install == []
        assert result.version_conflicts == []


class TestTransitiveDeps:
    def test_transitive_deps_included(self, temp_dir):
        """A depends on B, B depends on C; installing A → to_install=[C, B] (topo order)."""
        from aec.lib.skill_dependencies import resolve_install_graph

        # C has no deps
        _create_skill_in(temp_dir, "skill-c", "1.0.0")
        # B depends on C
        _create_skill_in(
            temp_dir,
            "skill-b",
            "1.0.0",
            deps=[{"name": "skill-c", "min_version": "1.0.0", "reason": "B needs C"}],
        )
        # A (target) depends on B
        _create_skill_in(
            temp_dir,
            "skill-a",
            "1.0.0",
            deps=[{"name": "skill-b", "min_version": "1.0.0", "reason": "A needs B"}],
        )

        available = {
            "skill-a": {"version": "1.0.0", "path": "skill-a"},
            "skill-b": {"version": "1.0.0", "path": "skill-b"},
            "skill-c": {"version": "1.0.0", "path": "skill-c"},
        }
        installed = {}

        result = resolve_install_graph("skill-a", available, installed, temp_dir)

        assert result.missing == []
        assert result.version_conflicts == []
        assert result.cycles == []
        # C must appear before B (deps before dependents)
        assert "skill-c" in result.to_install
        assert "skill-b" in result.to_install
        assert result.to_install.index("skill-c") < result.to_install.index("skill-b")

    def test_transitive_dep_already_satisfied_not_in_to_install(self, temp_dir):
        """If C is already installed, A→B→C chain only requires B in to_install."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(temp_dir, "skill-c", "1.0.0")
        _create_skill_in(
            temp_dir,
            "skill-b",
            "1.0.0",
            deps=[{"name": "skill-c", "min_version": "1.0.0", "reason": "B needs C"}],
        )
        _create_skill_in(
            temp_dir,
            "skill-a",
            "1.0.0",
            deps=[{"name": "skill-b", "min_version": "1.0.0", "reason": "A needs B"}],
        )

        available = {
            "skill-a": {"version": "1.0.0", "path": "skill-a"},
            "skill-b": {"version": "1.0.0", "path": "skill-b"},
            "skill-c": {"version": "1.0.0", "path": "skill-c"},
        }
        installed = {
            "skill-c": {"version": "1.0.0", "contentHash": "", "installedAt": "2026-01-01"},
        }

        result = resolve_install_graph("skill-a", available, installed, temp_dir)

        assert "skill-c" in result.already_satisfied
        assert "skill-b" in result.to_install
        assert "skill-c" not in result.to_install


class TestCycleDetection:
    def test_cycle_detected(self, temp_dir):
        """A depends on B, B depends on A → cycles is non-empty."""
        from aec.lib.skill_dependencies import resolve_install_graph

        _create_skill_in(
            temp_dir,
            "skill-a",
            "1.0.0",
            deps=[{"name": "skill-b", "min_version": "1.0.0", "reason": "A needs B"}],
        )
        _create_skill_in(
            temp_dir,
            "skill-b",
            "1.0.0",
            deps=[{"name": "skill-a", "min_version": "1.0.0", "reason": "B needs A"}],
        )

        available = {
            "skill-a": {"version": "1.0.0", "path": "skill-a"},
            "skill-b": {"version": "1.0.0", "path": "skill-b"},
        }
        installed = {}

        result = resolve_install_graph("skill-a", available, installed, temp_dir)

        assert len(result.cycles) > 0
