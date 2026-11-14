"""`aec update` git failures reach the user as a cause plus fix steps (real git repos)."""

import json
import subprocess

import pytest

from aec import cli
from aec.lib.errors import AecError, RepoSyncError
from aec.lib.sources import fetch_latest


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def commit(repo, name, text="x"):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", name)


@pytest.fixture
def remote_and_clone(tmp_path):
    """A bare remote and a clone of it whose main tracks origin/main."""
    remote, seed, clone = tmp_path / "remote.git", tmp_path / "seed", tmp_path / "clone"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(tmp_path, "init", "-q", "-b", "main", str(seed))
    commit(seed, "base")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-q", "origin", "main")
    git(tmp_path, "clone", "-q", str(remote), str(clone))
    return seed, clone


def test_up_to_date_clone_syncs(remote_and_clone):
    _, clone = remote_and_clone
    fetch_latest(clone)  # no exception


def test_diverged_branch_names_counts_and_both_ways_out(remote_and_clone):
    seed, clone = remote_and_clone
    commit(seed, "upstream1")
    commit(seed, "upstream2")
    git(seed, "push", "-q", "origin", "main")
    commit(clone, "local-only")

    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)

    err = exc.value
    assert "diverged" in err.message
    assert "1 local commit(s)" in err.message and "2 new one(s)" in err.message
    steps = "\n".join(err.fix)
    assert "git pull --rebase" in steps
    assert "git branch backup/aec-local HEAD && git reset --hard @{u}" in steps
    assert err.detail and "fast-forward" in err.detail.lower()


def test_conflicting_local_edit_says_commit_or_stash(remote_and_clone):
    seed, clone = remote_and_clone
    commit(seed, "base", "upstream change")
    git(seed, "push", "-q", "origin", "main")
    (clone / "base").write_text("uncommitted local change")

    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    assert "Uncommitted changes" in exc.value.message
    assert any("git stash push" in s for s in exc.value.fix)


def test_detached_head_says_switch_to_branch(remote_and_clone):
    _, clone = remote_and_clone
    git(clone, "checkout", "-q", "--detach")
    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    assert "not on a branch" in exc.value.message
    assert "git switch main" in exc.value.fix


def test_unreachable_remote_points_at_network_or_credentials(remote_and_clone, tmp_path):
    _, clone = remote_and_clone
    git(clone, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    assert "Could not reach the AEC remote" in exc.value.message


def test_cli_prints_cause_output_and_numbered_fix(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("AGENT_FEEDBACK_HOME", str(tmp_path / "fb"))

    def failing_app():
        raise AecError("Thing broke.", fix=["do a", "do b"], detail="git: nope")

    monkeypatch.setattr(cli, "app", failing_app)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Thing broke." in out
    assert "git: nope" in out
    assert "1. do a" in out and "2. do b" in out
    assert "issue" not in out.lower()  # the user has a fix; no "report a bug" fallback
    [entry] = [json.loads(line) for line in
               (tmp_path / "fb" / "subjects" / "aec" / "aec" / "entries.jsonl").read_text().splitlines()]
    assert entry["summary"] == "AecError: Thing broke."
