"""End-to-end: export on machine 1 -> apply on machine 2 reproduces the setup."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aec.commands.apply_cmd import run_apply
from aec.commands.export_cmd import run_export
from aec.lib.manifest_v2 import load_manifest


def _make_source_repo(root: Path) -> Path:
    repo = root / "aec-repo"
    skill = repo / ".claude" / "skills" / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 1.0.0\ndescription: d\nauthor: t\n---\n# s"
    )
    rules = repo / ".agent-rules"
    rules.mkdir(parents=True)
    (rules / "my-rule.md").write_text("---\nname: my-rule\nversion: 1.0.0\ndescription: d\n---\n# r")
    agents = repo / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "my-agent.md").write_text(
        "---\nname: my-agent\nversion: 1.0.0\ndescription: d\nauthor: t\n---\n# a"
    )
    (repo / ".git").mkdir()
    (repo / "aec").mkdir()
    return repo


def _source_dirs(repo: Path) -> dict:
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
        "mcps": repo / "mcp-servers",
    }


def _machine1_manifest(project: Path) -> dict:
    item = {"version": "1.0.0", "contentHash": "", "installedAt": "x"}
    return {
        "manifestVersion": 2,
        "installedAt": "x",
        "updatedAt": "x",
        "lastUpdateCheck": None,
        "global": {
            "skills": {"my-skill": dict(item)},
            "rules": {"my-rule": dict(item)},
            "agents": {"my-agent": dict(item)},
            "mcps": {},
        },
        "repos": {
            str(project.resolve()): {
                "skills": {"my-skill": dict(item)},
                "rules": {},
                "agents": {},
                "mcps": {},
            }
        },
    }


def test_export_then_apply_reproduces_setup(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    manifest_file = tmp_path / "shared" / "my.aec.json"
    manifest_file.parent.mkdir()

    # ---- machine 1: export ----
    home1 = tmp_path / "home1"
    (home1 / ".agents-environment-config").mkdir(parents=True)
    project1 = home1 / "projects" / "my-app"
    project1.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home1)
    monkeypatch.setenv("PROJECTS_DIR", str(home1 / "projects"))
    (home1 / ".agents-environment-config" / "installed-manifest.json").write_text(
        json.dumps(_machine1_manifest(project1))
    )

    run_export(out=str(manifest_file))

    text = manifest_file.read_text()
    assert str(home1) not in text  # no machine-1 absolute paths leaked
    assert "${PROJECTS}/my-app" in text

    # ---- machine 2: apply (different home dir) ----
    home2 = tmp_path / "home2"
    (home2 / ".agents-environment-config").mkdir(parents=True)
    project2 = home2 / "projects" / "my-app"
    project2.mkdir(parents=True)
    repo = _make_source_repo(home2)
    monkeypatch.setattr(Path, "home", lambda: home2)
    monkeypatch.setenv("PROJECTS_DIR", str(home2 / "projects"))

    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=_source_dirs(repo)
    ):
        run_apply(file=str(manifest_file))

    # global items reproduced on machine 2
    assert (home2 / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()
    assert (home2 / ".agent-tools" / "rules" / "my-rule.md").exists()
    assert (home2 / ".claude" / "agents" / "my-agent.md").exists()
    # repo-scoped item reproduced at machine-2's path
    assert (project2 / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()

    m2 = load_manifest(home2 / ".agents-environment-config" / "installed-manifest.json")
    assert "my-skill" in m2["global"]["skills"]
    assert "my-rule" in m2["global"]["rules"]
    assert "my-agent" in m2["global"]["agents"]
    assert "my-skill" in m2["repos"][str(project2.resolve())]["skills"]


def test_apply_dry_run_makes_no_changes(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    home = tmp_path / "home"
    (home / ".agents-environment-config").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    repo = _make_source_repo(home)
    manifest_file = tmp_path / "m.json"
    manifest_file.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "generatedBy": "aec test",
                "global": {"skills": [{"name": "my-skill", "version": "1.0.0"}]},
            }
        )
    )

    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=_source_dirs(repo)
    ):
        run_apply(file=str(manifest_file), dry_run=True)

    assert not (home / ".claude" / "skills" / "my-skill").exists()


def test_apply_missing_file_errors(tmp_path):
    with pytest.raises(SystemExit):
        run_apply(file=str(tmp_path / "nope.json"))


def _external_plugin_loadout() -> dict:
    return {
        "schema": "loadout/v1",
        "item_type": "plugin",
        "name": "impeccable-style",
        "version": "1.0.0",
        "description": "External style plugin.",
        "source": "https://example.test",
        "install_type": "external",
        "install": {
            "external": {
                "download": "https://example.test/download",
                "instructions": "Download and run setup.",
            }
        },
    }


def test_export_then_apply_reproduces_external_plugin(tmp_path, monkeypatch):
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    manifest_file = tmp_path / "shared" / "plug.aec.json"
    manifest_file.parent.mkdir()

    # ---- machine 1: export (manifest has an installed external plugin) ----
    home1 = tmp_path / "home1"
    (home1 / ".agents-environment-config").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home1)
    monkeypatch.setenv("PROJECTS_DIR", str(home1 / "projects"))
    m1 = {
        "manifestVersion": 2,
        "installedAt": "x",
        "updatedAt": "x",
        "lastUpdateCheck": None,
        "global": {
            "skills": {},
            "rules": {},
            "agents": {},
            "mcps": {},
            "plugins": {
                "impeccable-style": {
                    "version": "1.0.0",
                    "install_type": "external",
                    "targets": [],
                    "installedAs": "explicit",
                    "installedAt": "x",
                }
            },
        },
        "repos": {},
    }
    (home1 / ".agents-environment-config" / "installed-manifest.json").write_text(json.dumps(m1))

    run_export(out=str(manifest_file))
    assert "impeccable-style" in manifest_file.read_text()

    # ---- machine 2: apply into a fresh home, with the plugin in the catalog ----
    home2 = tmp_path / "home2"
    (home2 / ".agents-environment-config").mkdir(parents=True)
    repo = _make_source_repo(home2)
    plugins_dir = repo / "plugins"
    plugin_dir = plugins_dir / "impeccable-style"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(_external_plugin_loadout()))
    monkeypatch.setattr(Path, "home", lambda: home2)
    monkeypatch.setenv("PROJECTS_DIR", str(home2 / "projects"))

    source_dirs = _source_dirs(repo)
    source_dirs["plugins"] = plugins_dir

    ran = []
    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=source_dirs
    ), patch("subprocess.run", side_effect=lambda *a, **k: ran.append(a)):
        run_apply(file=str(manifest_file), yes=True)

    m2 = load_manifest(home2 / ".agents-environment-config" / "installed-manifest.json")
    assert "impeccable-style" in m2["global"]["plugins"]
    assert m2["global"]["plugins"]["impeccable-style"]["install_type"] == "external"
    assert ran == [], "external plugin must never execute anything during apply"


def test_apply_declined_batch_prompt_installs_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    manifest_file = tmp_path / "plug.aec.json"

    home = tmp_path / "home"
    (home / ".agents-environment-config").mkdir(parents=True)
    repo = _make_source_repo(home)
    plugin_dir = repo / "plugins" / "impeccable-style"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(_external_plugin_loadout()))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("PROJECTS_DIR", str(home / "projects"))

    # manifest with only the plugin (no items) so apply reaches the plugin pass
    manifest_file.write_text(json.dumps({
        "schemaVersion": 1,
        "global": {"skills": [], "rules": [], "agents": [], "mcps": [],
                   "plugins": [{"name": "impeccable-style", "version": "1.0.0"}]},
        "repos": {},
    }))

    source_dirs = _source_dirs(repo)
    source_dirs["plugins"] = repo / "plugins"
    mp = home / ".agents-environment-config" / "installed-manifest.json"

    ran = []
    monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=source_dirs
    ), patch("subprocess.run", side_effect=lambda *a, **k: ran.append(a)):
        run_apply(file=str(manifest_file), yes=False)

    out = capsys.readouterr().out
    assert "Skipped" in out
    assert ran == [], "declined batch must not execute anything"
    # nothing recorded: the install-manifest must not exist or have no plugins
    if mp.exists():
        m = load_manifest(mp)
        assert not m["global"].get("plugins"), "declined plugin must not be recorded"


def test_plugins_apply_even_when_item_pass_fails(tmp_path, monkeypatch):
    """Regression guard: a failing item pass must not skip the plugin pass,
    and the item-failure exit code must still surface."""
    monkeypatch.delenv("PROJECTS_DIR", raising=False)
    manifest_file = tmp_path / "plug.aec.json"

    home = tmp_path / "home"
    (home / ".agents-environment-config").mkdir(parents=True)
    repo = _make_source_repo(home)  # provides my-skill in the catalog
    plugin_dir = repo / "plugins" / "impeccable-style"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(_external_plugin_loadout()))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("PROJECTS_DIR", str(home / "projects"))

    # one item (so a plan exists -> execute_apply runs) plus one plugin
    manifest_file.write_text(json.dumps({
        "schemaVersion": 1,
        "global": {"skills": [{"name": "my-skill", "version": "1.0.0"}],
                   "rules": [], "agents": [], "mcps": [],
                   "plugins": [{"name": "impeccable-style", "version": "1.0.0"}]},
        "repos": {},
    }))

    source_dirs = _source_dirs(repo)
    source_dirs["plugins"] = repo / "plugins"

    # force the item pass to report an error (lightest path: _print_result keys on result.errors)
    failed_result = SimpleNamespace(
        applied=[], skipped=[],
        errors=[(SimpleNamespace(item=SimpleNamespace(name="my-skill")), "boom")],
    )

    with patch("aec.commands.apply_cmd.get_repo_root", return_value=repo), patch(
        "aec.commands.apply_cmd.get_source_dirs", return_value=source_dirs
    ), patch("aec.commands.apply_cmd.execute_apply", return_value=failed_result):
        with pytest.raises(SystemExit) as exc:
            run_apply(file=str(manifest_file), yes=True)
    assert exc.value.code == 1  # item failure still surfaced

    # (b) the key assertion: plugin pass STILL ran despite the item failure
    m = load_manifest(home / ".agents-environment-config" / "installed-manifest.json")
    assert "impeccable-style" in m["global"]["plugins"]
