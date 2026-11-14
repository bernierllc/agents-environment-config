"""End-to-end tests for `aec migrate agents-md`, `aec rollback` and layout-aware setup."""

from __future__ import annotations

import builtins
import shutil
from pathlib import Path

import pytest

from aec.commands import migrate_cmd, rollback_cmd
from aec.lib import changesets

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
LEGACY = ("AGENTINFO.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "QWEN.md")


@pytest.fixture
def store(tmp_path, monkeypatch):
    root = tmp_path / "rollbacks"
    monkeypatch.setattr(changesets, "rollbacks_dir", lambda: root)
    return root


@pytest.fixture
def legacy_repo(tmp_path):
    repo = tmp_path / "my-project"
    (repo / ".cursor" / "rules").mkdir(parents=True)
    for name in LEGACY:
        shutil.copy(TEMPLATES / name, repo / name)
    shutil.copy(TEMPLATES / ".cursor/rules/CURSOR.mdc", repo / ".cursor/rules/CURSOR.mdc")
    with open(repo / "CLAUDE.md", "ab") as f:
        f.write(b"\r\n## My notes\r\n\r\nUse AGENTINFO.md wisely.\r\n")
    return repo


def _snapshot(repo: Path) -> dict:
    return {p.relative_to(repo): p.read_bytes() for p in sorted(repo.rglob("*")) if p.is_file()}


def _answer(monkeypatch, *answers):
    it = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda *_: next(it))


def test_migrate_then_rollback_is_byte_exact_and_redo_works(store, legacy_repo):
    before = _snapshot(legacy_repo)

    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True) == 0
    assert not (legacy_repo / "AGENTINFO.md").exists()
    claude = (legacy_repo / "CLAUDE.md").read_bytes()
    assert claude.startswith(b"@AGENTS.md")
    assert b"Use AGENTS.md wisely." in claude
    migrated = _snapshot(legacy_repo)

    (cs,) = changesets.list_changesets()
    assert cs.kind == "migrate-agents-md"
    assert rollback_cmd.run_rollback_apply(cs.id, yes=True) == 0
    assert _snapshot(legacy_repo) == before

    undo = changesets.list_changesets()[0]
    assert undo.reverses == cs.id
    assert rollback_cmd.run_rollback_apply(undo.id, yes=True) == 0
    assert _snapshot(legacy_repo) == migrated


def test_dry_run_and_already_migrated_change_nothing(store, legacy_repo):
    before = _snapshot(legacy_repo)
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], dry_run=True) == 0
    assert _snapshot(legacy_repo) == before

    migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True)
    after = _snapshot(legacy_repo)
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True) == 0
    assert _snapshot(legacy_repo) == after
    assert len(changesets.list_changesets()) == 1


def test_declined_confirmation_changes_nothing(store, legacy_repo, monkeypatch):
    before = _snapshot(legacy_repo)
    _answer(monkeypatch, "n")
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)]) == 0
    assert _snapshot(legacy_repo) == before
    assert changesets.list_changesets() == []


def test_rollback_asks_before_overwriting_edits(store, legacy_repo, monkeypatch):
    migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True)
    (cs,) = changesets.list_changesets()
    agents = legacy_repo / "AGENTS.md"
    agents.write_bytes(agents.read_bytes() + b"my edit\n")

    _answer(monkeypatch, "n")
    assert rollback_cmd.run_rollback_apply(cs.id, yes=True) == 1  # --yes never answers overwrite
    assert agents.read_bytes().endswith(b"my edit\n")

    assert rollback_cmd.run_rollback_apply(cs.id, force=True, yes=True) == 0
    assert (legacy_repo / "AGENTINFO.md").exists()
    redo = changesets.list_changesets()[0]
    rollback_cmd.run_rollback_apply(redo.id, yes=True)
    assert agents.read_bytes().endswith(b"my edit\n")  # the overwritten edit comes back


def test_rollback_of_rolled_back_change_points_at_redo(store, legacy_repo, capsys):
    migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True)
    (cs,) = changesets.list_changesets()
    rollback_cmd.run_rollback_apply(cs.id, yes=True)
    assert rollback_cmd.run_rollback_apply(cs.id, yes=True) == 1
    assert changesets.load(cs.id).reversed_by in capsys.readouterr().out


def test_unknown_tidy_agent_is_rejected_before_changing_anything(store, legacy_repo, monkeypatch):
    monkeypatch.setattr(migrate_cmd, "_headless_agents", lambda: {})
    before = _snapshot(legacy_repo)
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True, tidy_with="nope") == 2
    assert _snapshot(legacy_repo) == before


def test_tidy_runs_agent_in_repo_and_records_its_edits(store, legacy_repo, monkeypatch, tmp_path):
    fake = tmp_path / "bin" / "fake-agent"
    fake.parent.mkdir()
    fake.write_text("")
    monkeypatch.setattr(
        migrate_cmd,
        "_headless_agents",
        lambda: {"fake": {"commands": ["fake-agent"], "headless_args": ["-p", "{prompt}"]}},
    )
    monkeypatch.setattr(migrate_cmd.shutil, "which", lambda cmd: str(fake))
    calls = []

    def fake_run(args, cwd, timeout):
        calls.append((args, cwd))
        (Path(cwd) / "AGENTS.md").write_text("tidied\n")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(migrate_cmd.subprocess, "run", fake_run)
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True, tidy_with="fake") == 0
    (args, cwd), = calls
    assert args == [str(fake), "-p", migrate_cmd.TIDY_PROMPT]
    assert Path(cwd) == legacy_repo
    tidy, migrate = changesets.list_changesets()
    assert (tidy.kind, migrate.kind) == ("tidy", "migrate-agents-md")


@pytest.mark.parametrize("setting, expect_agentinfo", [(None, False), ("agentinfo", True)])
def test_setup_writes_the_configured_layout(tmp_path, monkeypatch, setting, expect_agentinfo):
    from aec.commands import repo as repo_cmd

    monkeypatch.setattr("aec.lib.preferences.get_setting", lambda key: setting)
    project = tmp_path / "my-app"
    project.mkdir()
    repo_cmd._copy_agent_files(project, TEMPLATES.parent)

    assert (project / "AGENTINFO.md").exists() is expect_agentinfo
    claude = (project / "CLAUDE.md").read_text()
    if expect_agentinfo:
        assert "AGENTINFO.md" in claude
    else:
        assert claude == "@AGENTS.md\n"
        assert "AGENTINFO.md" not in (project / "AGENTS.md").read_text()
        assert "## Rules Reference" in (project / "AGENTS.md").read_text()


def test_setup_keeps_a_legacy_repo_legacy(tmp_path, monkeypatch):
    from aec.commands import repo as repo_cmd

    monkeypatch.setattr("aec.lib.preferences.get_setting", lambda key: None)
    project = tmp_path / "my-app"
    project.mkdir()
    (project / "AGENTINFO.md").write_text("# mine\n")
    repo_cmd._copy_agent_files(project, TEMPLATES.parent)
    assert (project / "AGENTINFO.md").read_text() == "# mine\n"
    assert "AGENTINFO.md" in (project / "CLAUDE.md").read_text()


def test_port_block_goes_to_agents_md_without_agentinfo(tmp_path, monkeypatch):
    from aec.commands.repo import _PORT_START, _inject_port_registry

    monkeypatch.setattr(
        "aec.lib.preferences.get_preference",
        lambda key: True if key == "port_registry_enabled" else None,
    )
    (tmp_path / "AGENTS.md").write_text("# my-app\n")
    _inject_port_registry(tmp_path)
    assert _PORT_START in (tmp_path / "AGENTS.md").read_text()
    assert not (tmp_path / "AGENTINFO.md").exists()


def test_symlinked_stub_is_refused_without_touching_files(store, legacy_repo):
    (legacy_repo / "CLAUDE.md").unlink()
    (legacy_repo / "CLAUDE.md").symlink_to("AGENTS.md")
    before = _snapshot(legacy_repo)
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True) == 1
    assert _snapshot(legacy_repo) == before
    assert (legacy_repo / "CLAUDE.md").is_symlink()
    assert changesets.list_changesets() == []
