"""Tests for skills symlink cleanup during install."""

import os
from pathlib import Path

import pytest


class TestSymlinkCleanup:
    """Test legacy symlink removal."""

    def test_removes_aec_skills_symlink_from_claude(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Create the AEC symlink
        target = agent_tools_skills / "agents-environment-config"
        target.mkdir()
        link = claude_skills / "agents-environment-config"
        link.symlink_to(target)

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        assert not link.exists()

    def test_does_not_remove_non_aec_symlinks(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Create a non-AEC symlink at the same name but pointing elsewhere
        other_target = temp_dir / "some-other-place"
        other_target.mkdir()
        link = claude_skills / "agents-environment-config"
        link.symlink_to(other_target)

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        # Should NOT be removed — it doesn't point to agent-tools
        assert link.exists()

    def test_leaves_real_directories_alone(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Real directory, not a symlink
        real = claude_skills / "braingrid-cli"
        real.mkdir()

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        assert real.exists()

    def test_removes_agent_tools_skills_symlink(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        # Create an AEC symlink in agent-tools pointing to repo
        # (In real use, repo path contains "agents-environment-config")
        repo_skills = temp_dir / "agents-environment-config" / ".claude" / "skills"
        repo_skills.mkdir(parents=True)
        link = agent_tools_skills / "agents-environment-config"
        link.symlink_to(repo_skills)

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=False,
        )

        assert not link.exists()

    def test_dry_run_does_not_remove(self, temp_dir: Path):
        claude_skills = temp_dir / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        agent_tools_skills = temp_dir / ".agent-tools" / "skills"
        agent_tools_skills.mkdir(parents=True)

        target = agent_tools_skills / "agents-environment-config"
        target.mkdir()
        link = claude_skills / "agents-environment-config"
        link.symlink_to(target)

        from aec.commands.install import _cleanup_legacy_symlinks

        _cleanup_legacy_symlinks(
            claude_skills_dir=claude_skills,
            agent_tools_skills_dir=agent_tools_skills,
            dry_run=True,
        )

        assert link.exists()


class TestParseSelection:
    """Test range/selection parsing for skill install prompt."""

    def test_parse_all(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("a", 10) == set(range(1, 11))
        assert _parse_selection("all", 10) == set(range(1, 11))

    def test_parse_none(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("n", 10) == set()
        assert _parse_selection("none", 10) == set()

    def test_parse_single_numbers(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,3,5", 10) == {1, 3, 5}

    def test_parse_ranges(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1-3,7", 10) == {1, 2, 3, 7}

    def test_parse_mixed(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,3-5,8", 10) == {1, 3, 4, 5, 8}

    def test_ignores_out_of_range(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,99", 5) == {1}

    def test_empty_input_returns_empty(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("", 10) == set()
