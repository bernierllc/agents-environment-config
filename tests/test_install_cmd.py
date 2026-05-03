"""Tests for aec install <type> <name> command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, call


AGENT_FRONTMATTER = (
    "---\nname: my-agent\nversion: 1.0.0\ndescription: Test agent\nauthor: Test\n---\n# Agent"
)


@pytest.fixture
def install_env(temp_dir, monkeypatch):
    """Set up a complete install environment with source repo, project, and manifest."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    # Create the AEC source repo with a skill and an agent
    repo = temp_dir / "aec-repo"
    skills_src = repo / ".claude" / "skills" / "my-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 1.0.0\ndescription: Test skill\nauthor: Test\n---\n# Skill"
    )
    agents_src = repo / ".claude" / "agents"
    agents_src.mkdir(parents=True)
    (agents_src / "my-agent.md").write_text(AGENT_FRONTMATTER)
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()

    # Create a tracked project
    project = temp_dir / "projects" / "my-app"
    (project / ".claude" / "skills").mkdir(parents=True)
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".agent-rules").mkdir(parents=True)
    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{project.resolve()}\n")

    # Global dirs
    (temp_dir / ".claude" / "skills").mkdir(parents=True)
    (temp_dir / ".claude" / "agents").mkdir(parents=True)

    # Empty v2 manifest
    manifest = {
        "manifestVersion": 2,
        "installedAt": "2026-04-04T00:00:00Z",
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {"skills": {}, "rules": {}, "agents": {}},
        "repos": {},
    }
    manifest_path = aec_home / "installed-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    return {
        "repo": repo,
        "project": project,
        "aec_home": aec_home,
        "manifest_path": manifest_path,
    }


def _patch_repo(install_env):
    """Return a stack of patches that redirect repo root and source dirs to test fixtures."""
    repo = install_env["repo"]
    return [
        patch("aec.commands.install_cmd.get_repo_root", return_value=repo),
        patch(
            "aec.commands.install_cmd.get_source_dirs",
            return_value={
                "skills": repo / ".claude" / "skills",
                "rules": repo / ".agent-rules",
                "agents": repo / ".claude" / "agents",
            },
        ),
    ]


class TestInstallValidation:
    def test_rejects_unknown_type(self, install_env):
        from aec.commands.install_cmd import run_install

        with _patch_repo(install_env)[0], _patch_repo(install_env)[1]:
            with pytest.raises(SystemExit):
                run_install(item_type="widget", name="foo", global_flag=True, yes=True)

    def test_error_when_repo_root_not_found(self, install_env):
        from aec.commands.install_cmd import run_install

        with patch("aec.commands.install_cmd.get_repo_root", return_value=None), \
             _patch_repo(install_env)[1]:
            with pytest.raises(SystemExit):
                run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)


class TestInstallSkill:
    def test_install_to_local_scope(self, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)
        monkeypatch.chdir(install_env["project"])

        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=False, yes=True)

        installed = install_env["project"] / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()
        assert "1.0.0" in installed.read_text()

    def test_install_to_global_scope(self, install_env):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)

        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        installed = install_env["aec_home"].parent / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()

    def test_error_not_in_repo_without_g(self, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)
        untracked = install_env["aec_home"].parent / "random"
        untracked.mkdir()
        monkeypatch.chdir(untracked)

        with patches[0], patches[1]:
            with pytest.raises(SystemExit):
                run_install(item_type="skill", name="my-skill", global_flag=False, yes=True)

    def test_error_unknown_skill(self, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)
        monkeypatch.chdir(install_env["project"])

        with patches[0], patches[1]:
            with pytest.raises(SystemExit):
                run_install(item_type="skill", name="nonexistent", global_flag=False, yes=True)

    def test_records_in_manifest(self, install_env):
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        patches = _patch_repo(install_env)

        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        m = load_manifest(install_env["manifest_path"])
        assert "my-skill" in m["global"]["skills"]
        assert m["global"]["skills"]["my-skill"]["version"] == "1.0.0"

    def test_overwrites_existing_when_yes(self, install_env):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)

        with patches[0], patches[1]:
            # Install once
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)
            # Install again (should overwrite without error)
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        installed = install_env["aec_home"].parent / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()

    def test_skips_when_overwrite_declined(self, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)

        with patches[0], patches[1]:
            # Install once
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

            # Simulate user declining overwrite
            monkeypatch.setattr("builtins.input", lambda _: "n")

            # Install again without yes flag - should skip
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=False)

        # File should still exist from first install
        installed = install_env["aec_home"].parent / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()

    def test_local_install_records_repo_scope_in_manifest(self, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        patches = _patch_repo(install_env)
        monkeypatch.chdir(install_env["project"])

        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=False, yes=True)

        m = load_manifest(install_env["manifest_path"])
        repo_key = str(install_env["project"].resolve())
        assert repo_key in m["repos"]
        assert "my-skill" in m["repos"][repo_key]["skills"]


class TestInstallAgent:
    def test_install_global_agent_has_md_extension(self, install_env):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)
        with patches[0], patches[1]:
            run_install(item_type="agent", name="my-agent", global_flag=True, yes=True)

        installed = install_env["aec_home"].parent / ".claude" / "agents" / "my-agent.md"
        assert installed.exists(), "Agent file must be installed with .md extension"
        assert "my-agent" in installed.read_text()

    def test_install_global_agent_no_bare_name(self, install_env):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)
        with patches[0], patches[1]:
            run_install(item_type="agent", name="my-agent", global_flag=True, yes=True)

        bare = install_env["aec_home"].parent / ".claude" / "agents" / "my-agent"
        assert not bare.exists(), "Agent must not be installed without .md extension"

    def test_install_agent_records_in_manifest(self, install_env):
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        patches = _patch_repo(install_env)
        with patches[0], patches[1]:
            run_install(item_type="agent", name="my-agent", global_flag=True, yes=True)

        m = load_manifest(install_env["manifest_path"])
        assert "my-agent" in m["global"]["agents"]
        assert m["global"]["agents"]["my-agent"]["version"] == "1.0.0"

    def test_install_local_agent_has_md_extension(self, install_env, monkeypatch):
        from aec.commands.install_cmd import run_install

        patches = _patch_repo(install_env)
        monkeypatch.chdir(install_env["project"])
        with patches[0], patches[1]:
            run_install(item_type="agent", name="my-agent", global_flag=False, yes=True)

        installed = install_env["project"] / ".claude" / "agents" / "my-agent.md"
        assert installed.exists(), "Local agent file must be installed with .md extension"


# ---------------------------------------------------------------------------
# Helper: build a skill directory with optional dependencies
# ---------------------------------------------------------------------------

def _make_skill_with_deps(skills_src: Path, name: str, version: str, deps=None) -> Path:
    """Create a minimal skill directory under skills_src/name/SKILL.md."""
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
    content = "\n".join(lines) + "\n"
    skill_dir = skills_src / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


class TestInstallWithDeps:
    """Tests for the dependency resolution + approval flow during skill install."""

    def _patch_repo_with_skills(self, install_env):
        """Return patches using the install_env's repo (which we augment with extra skills)."""
        return _patch_repo(install_env)

    def test_install_skill_with_no_deps_proceeds_normally(self, install_env):
        """A skill with no dependencies installs without any dep prompt."""
        from aec.commands.install_cmd import run_install

        patches = self._patch_repo_with_skills(install_env)
        # my-skill has no deps — already in install_env fixture
        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        installed = install_env["aec_home"].parent / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert installed.exists()

    def test_install_skill_with_dep_prompts_user(self, install_env, monkeypatch):
        """When a dep is needed and user approves, both target and dep are installed."""
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        repo = install_env["repo"]
        skills_src = repo / ".claude" / "skills"

        # Create dep-skill (no deps)
        _make_skill_with_deps(skills_src, "dep-skill", "2.0.0")
        # Re-create main-skill with a dep on dep-skill
        _make_skill_with_deps(
            skills_src,
            "main-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "2.0.0", "reason": "Needs dep"}],
        )

        # User approves all deps
        monkeypatch.setattr("builtins.input", lambda _: "y")

        patches = self._patch_repo_with_skills(install_env)
        with patches[0], patches[1]:
            run_install(item_type="skill", name="main-skill", global_flag=True, yes=False)

        # Both skills should be installed
        skills_install_dir = install_env["aec_home"].parent / ".claude" / "skills"
        assert (skills_install_dir / "main-skill" / "SKILL.md").exists()
        assert (skills_install_dir / "dep-skill" / "SKILL.md").exists()

        # Both should be in the manifest
        m = load_manifest(install_env["manifest_path"])
        assert "main-skill" in m["global"]["skills"]
        assert "dep-skill" in m["global"]["skills"]

    def test_install_skill_dep_rejected_aborts(self, install_env, monkeypatch):
        """When the user rejects deps, SystemExit is raised and neither skill is installed."""
        from aec.commands.install_cmd import run_install

        repo = install_env["repo"]
        skills_src = repo / ".claude" / "skills"

        _make_skill_with_deps(skills_src, "dep-skill", "2.0.0")
        _make_skill_with_deps(
            skills_src,
            "main-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "2.0.0", "reason": "Needs dep"}],
        )

        # User rejects
        monkeypatch.setattr("builtins.input", lambda _: "n")

        patches = self._patch_repo_with_skills(install_env)
        with patches[0], patches[1]:
            with pytest.raises(SystemExit):
                run_install(item_type="skill", name="main-skill", global_flag=True, yes=False)

        # Neither should be installed
        skills_install_dir = install_env["aec_home"].parent / ".claude" / "skills"
        assert not (skills_install_dir / "main-skill").exists()
        assert not (skills_install_dir / "dep-skill").exists()

    def test_install_skill_missing_dep_aborts(self, install_env):
        """A dep not in the catalog causes SystemExit with an error message."""
        from aec.commands.install_cmd import run_install

        repo = install_env["repo"]
        skills_src = repo / ".claude" / "skills"

        # skill declares dep on 'ghost-skill' which is NOT in the catalog
        _make_skill_with_deps(
            skills_src,
            "main-skill",
            "1.0.0",
            deps=[{"name": "ghost-skill", "min_version": "1.0.0", "reason": "Needs ghost"}],
        )

        patches = self._patch_repo_with_skills(install_env)
        with patches[0], patches[1]:
            with pytest.raises(SystemExit):
                run_install(item_type="skill", name="main-skill", global_flag=True, yes=True)

    def test_install_skill_with_assume_yes_installs_deps_silently(self, install_env):
        """With -y flag, deps are installed without any prompt."""
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        repo = install_env["repo"]
        skills_src = repo / ".claude" / "skills"

        _make_skill_with_deps(skills_src, "dep-skill", "2.0.0")
        _make_skill_with_deps(
            skills_src,
            "main-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "2.0.0", "reason": "Needs dep"}],
        )

        patches = self._patch_repo_with_skills(install_env)
        # No monkeypatch on input — if prompt_dep_install is called with assume_yes=True
        # it must not call input() at all.  We verify by not patching input.
        with patches[0], patches[1]:
            run_install(item_type="skill", name="main-skill", global_flag=True, yes=True)

        skills_install_dir = install_env["aec_home"].parent / ".claude" / "skills"
        assert (skills_install_dir / "main-skill" / "SKILL.md").exists()
        assert (skills_install_dir / "dep-skill" / "SKILL.md").exists()

        m = load_manifest(install_env["manifest_path"])
        assert "main-skill" in m["global"]["skills"]
        assert "dep-skill" in m["global"]["skills"]

    def test_explicit_install_records_installed_as_explicit(self, install_env):
        """A skill installed directly gets installedAs='explicit'."""
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        patches = self._patch_repo_with_skills(install_env)
        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=True, yes=True)

        m = load_manifest(install_env["manifest_path"])
        assert m["global"]["skills"]["my-skill"]["installedAs"] == "explicit"

    def test_dep_install_records_installed_as_dependency(self, install_env, monkeypatch):
        """A skill installed as a dependency gets installedAs='dependency'."""
        from aec.commands.install_cmd import run_install
        from aec.lib.manifest_v2 import load_manifest

        repo = install_env["repo"]
        skills_src = repo / ".claude" / "skills"

        _make_skill_with_deps(skills_src, "dep-skill", "2.0.0")
        _make_skill_with_deps(
            skills_src,
            "main-skill",
            "1.0.0",
            deps=[{"name": "dep-skill", "min_version": "2.0.0", "reason": "Needs dep"}],
        )

        monkeypatch.setattr("builtins.input", lambda _: "y")
        patches = self._patch_repo_with_skills(install_env)
        with patches[0], patches[1]:
            run_install(item_type="skill", name="main-skill", global_flag=True, yes=False)

        m = load_manifest(install_env["manifest_path"])
        assert m["global"]["skills"]["main-skill"]["installedAs"] == "explicit"
        assert m["global"]["skills"]["dep-skill"]["installedAs"] == "dependency"
