"""`aec update` git failures reach the user as a cause plus fix steps (real git repos)."""

import json
import subprocess

import pytest

from aec import cli
from aec.lib import prompts
from aec.lib.errors import AecError, RepoSyncError, Remedy
from aec.lib.prompt_catalog import get_spec
from aec.lib.prompt_catalog.maintenance_area import UPDATE_RESET_TO_REMOTE
from aec.lib.prompts import prompt
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
    assert "git branch backup/aec-local HEAD && git reset --keep @{u}" in steps
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


def rev(repo, ref):
    return subprocess.run(["git", "rev-parse", ref], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def diverge(seed, clone):
    commit(seed, "upstream1")
    git(seed, "push", "-q", "origin", "main")
    commit(clone, "local-only")


def test_diverged_clean_checkout_offers_reset_that_keeps_a_backup(remote_and_clone):
    seed, clone = remote_and_clone
    diverge(seed, clone)
    local_head = rev(clone, "HEAD")

    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    remedy = exc.value.remedy
    assert remedy is not None
    spec = get_spec(UPDATE_RESET_TO_REMOTE)
    assert spec.sensitive and spec.default is False  # never answered by --yes/--defaults
    prompts.set_answers({UPDATE_RESET_TO_REMOTE: "y"})
    try:
        assert remedy.confirm() is True  # the remedy asks under the catalogued ID
    finally:
        prompts.clear_answers()

    said = remedy.apply()
    [backup] = subprocess.run(["git", "branch", "--list", "aec-backup/*", "--format=%(refname:short)"],
                              cwd=clone, capture_output=True, text=True).stdout.split()
    assert backup in said
    assert rev(clone, backup) == local_head  # the local commit is kept
    assert rev(clone, "HEAD") == rev(clone, "@{u}")
    fetch_latest(clone)  # the retry now succeeds


def test_diverged_with_uncommitted_changes_offers_no_remedy(remote_and_clone):
    seed, clone = remote_and_clone
    diverge(seed, clone)
    (clone / "base").write_text("uncommitted")
    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    assert exc.value.remedy is None


@pytest.fixture
def remedy_cli(monkeypatch, tmp_path):
    """Run cli.main() with an app that fails with a remedy until it is applied."""
    monkeypatch.setenv("AGENT_FEEDBACK_HOME", str(tmp_path / "fb"))
    state = {"runs": 0, "applied": 0, "always_fail": False}

    def apply():
        state["applied"] += 1
        return "fixed it"

    def fake_app():
        state["runs"] += 1
        if state["always_fail"] or not state["applied"]:
            confirm = lambda: prompt(UPDATE_RESET_TO_REMOTE, "Fix? [y/N]: ",  # noqa: E731
                                     type="yes_no", default=False, sensitive=True) == "y"
            raise AecError("Broke.", fix=["manual step"], remedy=Remedy(confirm, apply))
        raise SystemExit(0)

    monkeypatch.setattr(cli, "app", fake_app)
    yield state
    prompts.clear_answers()
    prompts.reset_mode()


def test_accepted_remedy_is_applied_and_command_rerun(remedy_cli, capsys):
    prompts.set_answers({UPDATE_RESET_TO_REMOTE: "y"})
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert remedy_cli == {"runs": 2, "applied": 1, "always_fail": False}
    assert "fixed it" in capsys.readouterr().out


def test_declined_remedy_changes_nothing(remedy_cli):
    prompts.set_answers({UPDATE_RESET_TO_REMOTE: "n"})
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert remedy_cli["applied"] == 0


def test_headless_run_without_an_answer_never_applies_the_remedy(remedy_cli, capsys):
    prompts.set_mode(non_interactive=True, use_defaults=True)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert remedy_cli["applied"] == 0
    assert "manual step" in capsys.readouterr().out


def test_remedy_is_retried_only_once(remedy_cli):
    remedy_cli["always_fail"] = True
    prompts.set_answers({UPDATE_RESET_TO_REMOTE: "y"})
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert remedy_cli["runs"] == 2 and remedy_cli["applied"] == 1
