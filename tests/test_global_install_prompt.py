"""Tests for multi-repo global install detection and migration."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from aec.lib.global_install_prompt import (
    THRESHOLD_KEY,
    dismiss_global_install_prompt,
    english_ordinal,
    get_multi_repo_global_threshold,
    is_global_install_prompt_dismissed,
    migrate_item_to_global,
    prompt_multi_repo_global_or_proceed,
    repo_keys_with_item,
    should_offer_global_multi_repo,
)


@pytest.mark.parametrize(
    "n,expected",
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
    ],
)
def test_english_ordinal(n, expected):
    assert english_ordinal(n) == expected


def _empty_manifest():
    return {
        "manifestVersion": 2,
        "installedAt": "2026-04-04T00:00:00Z",
        "updatedAt": "2026-04-04T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {"skills": {}, "rules": {}, "agents": {}},
        "repos": {},
    }


def _repo_scope_with_skill(name="my-skill"):
    return {
        "skills": {
            name: {
                "version": "1.0.0",
                "contentHash": "x",
                "installedAt": "2026-04-04T00:00:00Z",
            }
        },
        "rules": {},
        "agents": {},
    }


class TestShouldOfferGlobalMultiRepo:
    def test_assume_yes_skips(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        p = temp_dir / "p"
        p.mkdir()
        m = _empty_manifest()
        m["repos"][str(p.resolve())] = _repo_scope_with_skill()
        assert not should_offer_global_multi_repo(
            m, "skills", "my-skill", p, "skill", assume_yes=True
        )

    def test_dismissed_skips(self, temp_dir, monkeypatch):
        prefs = temp_dir / "preferences.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        dismiss_global_install_prompt("skill", "my-skill")

        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        r1, r2, r3 = temp_dir / "a", temp_dir / "b", temp_dir / "c"
        for x in (r1, r2, r3):
            x.mkdir()
        m = _empty_manifest()
        cur = temp_dir / "d"
        cur.mkdir()
        for rk in (r1, r2, r3):
            m["repos"][str(rk.resolve())] = _repo_scope_with_skill()
        assert not should_offer_global_multi_repo(
            m, "skills", "my-skill", cur, "skill", assume_yes=False
        )

    def test_already_in_global_skips(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        m = _empty_manifest()
        m["global"]["skills"]["my-skill"] = {"version": "1.0.0", "contentHash": "", "installedAt": "t"}
        cur = temp_dir / "d"
        cur.mkdir()
        for name in ("a", "b", "c"):
            p = temp_dir / name
            p.mkdir()
            m["repos"][str(p.resolve())] = _repo_scope_with_skill()
        assert not should_offer_global_multi_repo(
            m, "skills", "my-skill", cur, "skill", assume_yes=False
        )

    def test_current_repo_already_has_skill_skips(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        cur = temp_dir / "cur"
        cur.mkdir()
        m = _empty_manifest()
        m["repos"][str(cur.resolve())] = _repo_scope_with_skill()
        for name in ("a", "b", "c"):
            p = temp_dir / name
            p.mkdir()
            m["repos"][str(p.resolve())] = _repo_scope_with_skill()
        assert not should_offer_global_multi_repo(
            m, "skills", "my-skill", cur, "skill", assume_yes=False
        )

    def test_below_threshold_no_offer(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        prefs = temp_dir / "preferences.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        from aec.lib.preferences import save_preferences

        save_preferences(
            {
                "schema_version": "1.2",
                "optional_rules": {},
                "settings": {THRESHOLD_KEY: 5},
                "configurable_instructions": {},
            }
        )
        assert get_multi_repo_global_threshold() == 5

        m = _empty_manifest()
        cur = temp_dir / "new"
        cur.mkdir()
        for name in ("a", "b"):
            p = temp_dir / name
            p.mkdir()
            m["repos"][str(p.resolve())] = _repo_scope_with_skill()
        assert not should_offer_global_multi_repo(
            m, "skills", "my-skill", cur, "skill", assume_yes=False
        )

    def test_meets_default_threshold_offers(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        prefs = temp_dir / "preferences.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        m = _empty_manifest()
        cur = temp_dir / "new"
        cur.mkdir()
        for name in ("a", "b", "c"):
            p = temp_dir / name
            p.mkdir()
            m["repos"][str(p.resolve())] = _repo_scope_with_skill()
        assert should_offer_global_multi_repo(
            m, "skills", "my-skill", cur, "skill", assume_yes=False
        )


class TestRepoKeysWithItem:
    def test_lists_repos_with_skill(self, temp_dir):
        m = _empty_manifest()
        p1, p2 = temp_dir / "r1", temp_dir / "r2"
        m["repos"][str(p1.resolve())] = _repo_scope_with_skill()
        m["repos"][str(p2.resolve())] = {"skills": {}, "rules": {}, "agents": {}}
        keys = repo_keys_with_item(m, "skills", "my-skill")
        assert keys == [str(p1.resolve())]


class TestMigrateItemToGlobal:
    def test_removes_repo_copies_and_installs_global(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        monkeypatch.setattr("aec.lib.installed_store.AEC_HOME", aec_home)

        (temp_dir / ".claude" / "skills").mkdir(parents=True)

        repos = []
        for i in range(3):
            p = temp_dir / f"p{i}"
            p.mkdir()
            sk = p / ".claude" / "skills" / "my-skill"
            sk.mkdir(parents=True)
            (sk / "SKILL.md").write_text(
                "---\nname: my-skill\nversion: 1.0.0\ndescription: X\n---\n"
            )
            repos.append(p)

        src = temp_dir / "upstream" / "my-skill"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(
            "---\nname: my-skill\nversion: 2.0.0\ndescription: Upstream\n---\n"
        )

        manifest = _empty_manifest()
        for p in repos:
            manifest["repos"][str(p.resolve())] = _repo_scope_with_skill()
        manifest_path = aec_home / "installed-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        loaded = json.loads(manifest_path.read_text())

        migrate_item_to_global(
            item_type="skill",
            plural="skills",
            name="my-skill",
            item_info={"version": "2.0.0", "path": "my-skill"},
            src=src,
            manifest=loaded,
            manifest_path=manifest_path,
        )

        for p in repos:
            assert not (p / ".claude" / "skills" / "my-skill").exists()

        g = temp_dir / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert g.exists()
        assert "2.0.0" in g.read_text()

        after = json.loads(manifest_path.read_text())
        for p in repos:
            assert "my-skill" not in after["repos"].get(str(p.resolve()), {}).get("skills", {})
        assert "my-skill" in after["global"]["skills"]
        assert after["global"]["skills"]["my-skill"]["version"] == "2.0.0"


class TestPromptMultiRepoGlobalOrProceed:
    def test_returns_local_when_not_eligible(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        m = _empty_manifest()
        cur = temp_dir / "c"
        cur.mkdir()
        src = temp_dir / "s"
        src.mkdir()
        out = prompt_multi_repo_global_or_proceed(
            item_type="skill",
            plural="skills",
            name="my-skill",
            manifest=m,
            current_repo=cur,
            item_info={"version": "1.0.0"},
            src=src,
            manifest_path=temp_dir / "m.json",
            assume_yes=False,
        )
        assert out == "local"

    def test_no_then_remember_dismisses(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        prefs = temp_dir / "preferences.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        m = _empty_manifest()
        cur = temp_dir / "new"
        cur.mkdir()
        for name in ("a", "b", "c"):
            p = temp_dir / name
            p.mkdir()
            m["repos"][str(p.resolve())] = _repo_scope_with_skill()

        src = temp_dir / "src"
        src.mkdir()
        manifest_path = temp_dir / ".agents-environment-config" / "installed-manifest.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps(m))

        inputs = iter(["n", "y"])
        monkeypatch.setattr("builtins.input", lambda _="": next(inputs))

        out = prompt_multi_repo_global_or_proceed(
            item_type="skill",
            plural="skills",
            name="my-skill",
            manifest=json.loads(manifest_path.read_text()),
            current_repo=cur,
            item_info={"version": "1.0.0"},
            src=src,
            manifest_path=manifest_path,
            assume_yes=False,
        )
        assert out == "local"
        assert is_global_install_prompt_dismissed("skill", "my-skill")

    def test_yes_migrates(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        monkeypatch.setattr("aec.lib.installed_store.AEC_HOME", aec_home)

        (temp_dir / ".claude" / "skills").mkdir(parents=True)
        repos = []
        for i in range(3):
            p = temp_dir / f"p{i}"
            p.mkdir()
            sk = p / ".claude" / "skills" / "my-skill"
            sk.mkdir(parents=True)
            (sk / "SKILL.md").write_text(
                "---\nname: my-skill\nversion: 1.0.0\ndescription: X\n---\n"
            )
            repos.append(p)

        src = temp_dir / "upstream" / "my-skill"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text(
            "---\nname: my-skill\nversion: 2.0.0\ndescription: Upstream\n---\n"
        )

        manifest = _empty_manifest()
        for p in repos:
            manifest["repos"][str(p.resolve())] = _repo_scope_with_skill()
        manifest_path = aec_home / "installed-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        loaded = json.loads(manifest_path.read_text())

        cur = temp_dir / "fourth"
        cur.mkdir()

        monkeypatch.setattr("builtins.input", lambda _="": "y")

        out = prompt_multi_repo_global_or_proceed(
            item_type="skill",
            plural="skills",
            name="my-skill",
            manifest=loaded,
            current_repo=cur,
            item_info={"version": "2.0.0", "path": "my-skill"},
            src=src,
            manifest_path=manifest_path,
            assume_yes=False,
        )
        assert out == "global"
        assert (temp_dir / ".claude" / "skills" / "my-skill").is_dir()


class TestInstallCmdMultiRepoGlobal:
    """End-to-end: install into a 4th repo prompts and migrates to global."""

    def test_prompt_yes_migrates_via_run_install(self, temp_dir, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: temp_dir)
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        monkeypatch.setattr("aec.lib.installed_store.AEC_HOME", aec_home)

        repo = temp_dir / "aec-repo"
        skills_src = repo / ".claude" / "skills" / "my-skill"
        skills_src.mkdir(parents=True)
        (skills_src / "SKILL.md").write_text(
            "---\nname: my-skill\nversion: 1.0.0\ndescription: Test\n---\n# Skill"
        )
        (repo / ".git").mkdir()
        (repo / "aec").mkdir()
        (repo / ".agent-rules").mkdir()

        projects = []
        for i in range(4):
            p = temp_dir / "projects" / f"app{i}"
            (p / ".claude" / "skills").mkdir(parents=True)
            (p / ".agent-rules").mkdir(parents=True)
            projects.append(p)

        log = aec_home / "setup-repo-locations.txt"
        log.write_text(
            "\n".join(
                f"2026-04-04T00:00:00Z|2.5.4|{proj.resolve()}"
                for proj in projects
            )
            + "\n"
        )

        (temp_dir / ".claude" / "skills").mkdir(parents=True)

        manifest = _empty_manifest()
        for p in projects[:3]:
            sk = p / ".claude" / "skills" / "my-skill"
            sk.mkdir(parents=True)
            shutil.copytree(skills_src, sk, dirs_exist_ok=True)
            manifest["repos"][str(p.resolve())] = _repo_scope_with_skill()

        manifest_path = aec_home / "installed-manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        monkeypatch.setattr("builtins.input", lambda _="": "y")
        monkeypatch.chdir(projects[3])

        patches = [
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

        from aec.commands.install_cmd import run_install

        with patches[0], patches[1]:
            run_install(item_type="skill", name="my-skill", global_flag=False, yes=False)

        for p in projects[:3]:
            assert not (p / ".claude" / "skills" / "my-skill").exists()

        gskill = temp_dir / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert gskill.exists()

        final = json.loads(manifest_path.read_text())
        assert "my-skill" in final["global"]["skills"]
        assert str(projects[3].resolve()) not in final.get("repos", {}) or (
            "my-skill" not in final.get("repos", {}).get(str(projects[3].resolve()), {}).get("skills", {})
        )
