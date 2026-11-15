"""End-to-end tests for `aec migrate agents-md`, `aec rollback` and layout-aware setup."""

from __future__ import annotations

import builtins
import shutil
import subprocess
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


def test_tidy_runs_agent_in_repo_and_records_its_edits(store, legacy_repo, monkeypatch, tmp_path, capsys):
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
    real_run = subprocess.run

    def fake_run(args, cwd, **kw):
        if args[0] == "git":
            return real_run(args, cwd=cwd, **kw)
        calls.append((args, cwd))
        (Path(cwd) / "AGENTS.md").write_text("tidied\n")
        (Path(cwd) / "notes.txt").write_text("stray edit\n")
        (Path(cwd) / "scratch.txt").unlink()
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(migrate_cmd.subprocess, "run", fake_run)
    real_run(["git", "init", "-q"], cwd=legacy_repo, check=True)
    (legacy_repo / "scratch.txt").write_text("untracked\n")
    assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True, tidy_with="fake") == 0
    (args, cwd), = calls
    assert args == [str(fake), "-p", migrate_cmd.TIDY_PROMPT]
    assert Path(cwd) == legacy_repo
    tidy, migrate = changesets.list_changesets()
    assert (tidy.kind, migrate.kind) == ("tidy", "migrate-agents-md")
    out = capsys.readouterr().out
    assert "does not undo them" in out and "notes.txt" in out
    assert "scratch.txt" in out  # a deleted file is reported too
    assert "    AGENTS.md" not in out  # recorded files are not listed as unrecorded


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






def test_setup_adds_rules_reference_to_existing_agents_md(tmp_path, monkeypatch):
    from aec.commands import repo as repo_cmd

    monkeypatch.setattr("aec.lib.preferences.get_setting", lambda key: None)
    project = tmp_path / "my-app"
    project.mkdir()
    (project / "AGENTS.md").write_bytes(b"# my-app\r\n\r\nMy notes.\r\n")
    repo_cmd._copy_agent_files(project, TEMPLATES.parent)

    agents = (project / "AGENTS.md").read_bytes()
    assert agents.startswith(b"# my-app\r\n\r\nMy notes.\r\n\r\n## Rules Reference")
    assert b"\n" not in agents.replace(b"\r\n", b"")  # stays CRLF
    assert (project / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    repo_cmd._copy_agent_files(project, TEMPLATES.parent)  # second run adds nothing
    assert (project / "AGENTS.md").read_bytes() == agents


def test_setup_adds_aec_rules_next_to_a_users_own_rules_reference(tmp_path, monkeypatch):
    from aec.commands import repo as repo_cmd

    monkeypatch.setattr("aec.lib.preferences.get_setting", lambda key: None)
    project = tmp_path / "my-app"
    project.mkdir()
    (project / "AGENTS.md").write_text("# my-app\n\n## Rules Reference\n\n- see ~/.agent-tools/rules/my-team/security.md\n")
    repo_cmd._copy_agent_files(project, TEMPLATES.parent)

    agents = (project / "AGENTS.md").read_text()
    assert "my-team/security.md" in agents and "agent-tools/rules/agents-environment-config/" in agents
    repo_cmd._copy_agent_files(project, TEMPLATES.parent)  # second run adds nothing
    assert (project / "AGENTS.md").read_text() == agents




def test_tidy_timeout_still_reports_unrecorded_edits(store, legacy_repo, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        migrate_cmd,
        "_headless_agents",
        lambda: {"fake": {"commands": ["fake-agent"], "headless_args": ["{prompt}"]}},
    )
    monkeypatch.setattr(migrate_cmd.shutil, "which", lambda cmd: "fake-agent")
    real_run = subprocess.run

    def fake_run(args, cwd, **kw):
        if args[0] == "git":
            return real_run(args, cwd=cwd, **kw)
        (Path(cwd) / "src.py").write_text("half done\n")
        raise subprocess.TimeoutExpired(args, kw.get("timeout"))

    monkeypatch.setattr(migrate_cmd.subprocess, "run", fake_run)
    real_run(["git", "init", "-q"], cwd=legacy_repo, check=True)
    with pytest.raises(subprocess.TimeoutExpired):
        migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True, tidy_with="fake")
    out = capsys.readouterr().out
    assert "does not undo them" in out and "src.py" in out


@pytest.mark.parametrize("edited_before_prompt", [True, False])
def test_rollback_refuses_a_file_saved_after_the_prompt(store, tmp_path, monkeypatch, capsys, edited_before_prompt):
    f = tmp_path / "f"
    f.write_bytes(b"old")
    pending = changesets.begin([f], "s", "l", "test")
    f.write_bytes(b"new")
    cs = pending.commit()
    if edited_before_prompt:
        f.write_bytes(b"edit the user saw")

    def answer_while_editor_saves(*a, **kw):
        f.write_bytes(b"saved after the prompt")
        return "y"

    monkeypatch.setattr(rollback_cmd, "prompt", answer_while_editor_saves)
    assert rollback_cmd.run_rollback_apply(cs.id) == 1
    assert f.read_bytes() == b"saved after the prompt"
    assert "Nothing rolled back" in capsys.readouterr().out


def test_rollback_apply_refuses_a_running_change(store, tmp_path, capsys):
    f = tmp_path / "f"
    f.write_bytes(b"old")
    pending = changesets.begin([f], "s", "l", "test")
    f.write_bytes(b"new")
    (cs,) = changesets.list_changesets()
    assert rollback_cmd.run_rollback_apply(cs.id, yes=True) == 1
    assert "still being made" in capsys.readouterr().out
    assert f.read_bytes() == b"new"
    pending.commit()


def _link_out(repo: Path, rel: str, outside: Path) -> None:
    """Move repo/rel to `outside` and leave a symlink to it in its place."""
    shutil.move(str(repo / rel), str(outside))
    (repo / rel).symlink_to(outside, target_is_directory=outside.is_dir())


def _setup(repo: Path) -> int:
    from aec.commands import repo as repo_cmd

    repo_cmd._copy_agent_files(repo, TEMPLATES.parent)
    return 0


def _tidy(repo: Path) -> int:
    config = {"commands": ["true"], "headless_args": []}
    return 0 if migrate_cmd._tidy(repo, "fake", config, yes=True) else 1


def _ports(repo: Path) -> int:
    from aec.commands import repo as repo_cmd

    repo_cmd._inject_port_registry(repo)
    return 0


def _path_migration(repo: Path) -> int:
    from aec.commands import repo as repo_cmd

    repo_cmd._migrate_agent_files(repo)
    return 0


def _rollback(repo: Path) -> int:
    (cs,) = changesets.list_changesets()
    return rollback_cmd.run_rollback_apply(cs.id, yes=True)


# Every AEC command that writes repo files, each with a symlinked file and a
# symlinked directory where it can reach one. All go through aec.lib.confine.
CALLERS = ["migrate", "tidy", "setup", "ports", "path-migration", "rollback"]
REPO_ROOT_ONLY = {"tidy", "ports", "path-migration"}  # write only files at the repo root


@pytest.mark.parametrize("caller", CALLERS)
@pytest.mark.parametrize("kind", ["file", "dir"])
def test_every_writer_refuses_paths_that_leave_the_repo(store, legacy_repo, tmp_path, monkeypatch, caller, kind):
    monkeypatch.setattr("aec.lib.preferences.get_setting", lambda key: None)
    monkeypatch.setattr("aec.lib.preferences.get_preference", lambda key: key == "port_registry_enabled")
    if caller in REPO_ROOT_ONLY and kind == "dir":
        pytest.skip(f"{caller} only writes files at the repo root")
    outside = tmp_path / "shared"
    rel = {"ports": "AGENTINFO.md", "path-migration": "AGENTS.md"}.get(caller, "CLAUDE.md") if kind == "file" else ".cursor/rules"
    if caller == "path-migration":  # give the updater an old-style reference to rewrite
        (legacy_repo / rel).write_text("Read relevant `.agent-rules/general/architecture.md`\n")
    link = lambda: _link_out(legacy_repo, rel, outside)  # noqa: E731
    if caller == "setup":
        for name in list(LEGACY) + [".cursor"]:  # an empty repo, so setup has files to create
            p = legacy_repo / name
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        if kind == "file":
            outside.write_text("shared notes\n")
            (legacy_repo / "AGENTS.md").symlink_to(outside)
        else:
            outside.mkdir()
            (legacy_repo / ".cursor").symlink_to(outside, target_is_directory=True)
        run = _setup
    else:
        if caller == "rollback":  # record a migration, then link one of its files out
            assert migrate_cmd.run_migrate_agents_md([str(legacy_repo)], yes=True) == 0
        link()
        run = {
            "migrate": lambda r: migrate_cmd.run_migrate_agents_md([str(r)], yes=True),
            "tidy": _tidy,
            "ports": _ports,
            "path-migration": _path_migration,
            "rollback": _rollback,
        }[caller]

    def state():
        files = outside.rglob("*") if outside.is_dir() else [outside]
        return {str(p): p.read_bytes() for p in files if p.is_file()}

    before, outside_before, recorded = _snapshot(legacy_repo), state(), changesets.list_changesets()
    status = run(legacy_repo)
    assert state() == outside_before  # nothing written through the link
    if caller not in ("setup", "ports", "path-migration"):  # these warn and skip instead of failing
        assert status == 1
        assert _snapshot(legacy_repo) == before
        assert changesets.list_changesets() == recorded


def test_all_keeps_non_git_and_separate_git_dir_projects_and_skips_linked_worktrees(tmp_path, monkeypatch):
    main, sep, plain = tmp_path / "main", tmp_path / "sep", tmp_path / "plain"
    plain.mkdir()
    run = lambda *a: subprocess.run(["git", *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q", str(main))
    run("init", "-q", "--separate-git-dir", str(tmp_path / "sep.git"), str(sep))
    run("-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", str(main), "commit", "-q", "--allow-empty", "-m", "init")
    run("-C", str(main), "worktree", "add", "-q", str(tmp_path / "wt"))
    tracked = [main, sep, tmp_path / "wt", plain]
    monkeypatch.setattr("aec.lib.scope.get_all_tracked_repos", lambda: tracked)
    assert migrate_cmd._target_repos([], all_repos=True) == [main, sep, plain]
