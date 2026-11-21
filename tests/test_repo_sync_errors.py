"""`aec update` git failures reach the user as a cause plus fix steps (real git repos)."""

import json
import shlex
import subprocess

import pytest

from aec import cli
from aec.lib import prompts
from aec.lib.errors import AecError, RepoSyncError, Remedy
from aec.lib.prompt_catalog import get_spec
from aec.lib.prompt_catalog.maintenance_area import UPDATE_RESET_TO_REMOTE
from aec.lib.prompts import prompt
from aec.lib.sources import _diagnose_sync_failure, fetch_latest


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


def multi_ref_error(clone):
    return _diagnose_sync_failure(
        clone, ["git", "pull", "--ff-only"], "fatal: Cannot fast-forward to multiple branches."
    )


def add_remote_branch(seed, clone, name="staging"):
    git(seed, "checkout", "-q", "-b", name)
    commit(seed, f"{name}-file")
    git(seed, "push", "-q", "origin", name)
    git(clone, "fetch", "-q", "origin")


def run_repair(clone, err, keep):
    """Run the printed steps through a real shell, as a user pasting them would.

    `<the one ref to keep, ...>` is replaced by `keep`, a full merge ref the user copied from the listing.
    """
    for step in err.fix:
        if step.startswith(("cd ", "git config --get-all")) or step.split()[0] != "git":
            continue
        subprocess.run(
            ["bash", "-c", step.replace("<the one ref to keep, copied from that list>", shlex.quote(keep))],
            cwd=clone, check=True, capture_output=True, text=True,
        )


def merge_refs(clone, branch="main"):
    out = subprocess.run(["git", "config", "--get-all", f"branch.{branch}.merge"], cwd=clone, check=True,
                         capture_output=True, text=True)
    return out.stdout.split()


def test_two_merge_refs_name_the_branch_and_the_replace_fix(remote_and_clone):
    seed, clone = remote_and_clone
    add_remote_branch(seed, clone)
    git(clone, "config", "--add", "branch.main.merge", "refs/heads/staging")

    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)

    err = exc.value
    assert "'main' has more than one upstream merge ref" in err.message
    steps = "\n".join(err.fix)
    assert "git config --get-all branch.main.merge" in steps
    assert "git config --replace-all branch.main.merge <the one ref to keep" in steps
    assert "--unset-all" not in steps and "--set-upstream-to" not in steps  # no guessed upstream
    assert err.detail and "multiple branches" in err.detail.lower()


@pytest.mark.parametrize("keep", ["refs/heads/main", "refs/heads/staging"])
def test_repair_keeps_exactly_the_chosen_ref_and_git_pull_works_again(remote_and_clone, keep):
    seed, clone = remote_and_clone
    add_remote_branch(seed, clone)
    git(clone, "config", "--add", "branch.main.merge", "refs/heads/staging")

    run_repair(clone, multi_ref_error(clone), keep=keep)

    assert merge_refs(clone) == [keep]


def test_repair_for_a_local_upstream_and_a_same_named_tag(remote_and_clone):
    # Codex P2 on #173 round 3: `remote = .` plus a tag named like the branch made a guessed target ambiguous.
    _, clone = remote_and_clone
    git(clone, "branch", "staging")
    git(clone, "tag", "main")
    git(clone, "checkout", "-q", "-b", "local-aec", "refs/heads/main")  # the tag makes bare `main` ambiguous
    git(clone, "config", "branch.local-aec.remote", ".")
    git(clone, "config", "branch.local-aec.merge", "refs/heads/main")
    git(clone, "config", "--add", "branch.local-aec.merge", "refs/heads/staging")

    err = multi_ref_error(clone)

    run_repair(clone, err, keep="refs/heads/main")
    assert merge_refs(clone, "local-aec") == ["refs/heads/main"]


def test_repair_does_not_guess_a_remote_for_custom_fetch_mappings(remote_and_clone):
    # Codex P2 on #173 round 4: with a non-default fetch refspec `origin/<branch>` is the wrong name.
    seed, clone = remote_and_clone
    add_remote_branch(seed, clone)
    git(clone, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/cache/*")
    git(clone, "config", "--replace-all", "branch.main.merge", "refs/heads/main")
    git(clone, "config", "--add", "branch.main.merge", "refs/heads/staging")

    err = multi_ref_error(clone)

    assert "origin/" not in "\n".join(err.fix)
    run_repair(clone, err, keep="refs/heads/staging")
    assert merge_refs(clone) == ["refs/heads/staging"]


def test_branch_name_with_shell_metacharacters_cannot_inject_through_the_printed_steps(remote_and_clone):
    # Codex P1 on #173 round 4: the steps are pasted into a shell, and a branch name can carry `;`.
    _, clone = remote_and_clone
    name = "aec;touch${IFS}INJECTED"
    git(clone, "checkout", "-q", "-b", name, "main")
    git(clone, "config", f"branch.{name}.remote", ".")
    git(clone, "config", f"branch.{name}.merge", "refs/heads/main")
    git(clone, "config", "--add", f"branch.{name}.merge", "refs/heads/other")

    err = multi_ref_error(clone)
    run_repair(clone, err, keep="refs/heads/main")

    assert not list(clone.glob("INJECTED*")) and not list(clone.parent.glob("INJECTED*"))
    assert merge_refs(clone, name) == ["refs/heads/main"]


def test_cd_step_quotes_a_checkout_path_with_spaces(remote_and_clone, tmp_path):
    _, clone = remote_and_clone
    spaced = tmp_path / "my clone"
    clone.rename(spaced)

    err = multi_ref_error(spaced)

    assert f"cd {shlex.quote(str(spaced))}" in err.fix


def test_multiple_branches_with_one_merge_ref_does_not_blame_the_config(remote_and_clone):
    # nevar-auth saw this error on a checkout whose branch.main.merge held ONE value; the
    # message must not claim two refs there, and rewriting the config would not help.
    _, clone = remote_and_clone
    git(clone, "config", "--get-all", "branch.main.merge")  # exactly one value, or git fails

    err = multi_ref_error(clone)

    assert "more than one upstream merge ref" not in err.message
    steps = "\n".join(err.fix)
    assert "--unset-all" not in steps and "--replace-all" not in steps and "origin/" not in steps
    assert "git branch -vv" in steps
    assert "git branch --set-upstream-to=<remote>/<branch> main" in steps
    assert err.detail and "multiple branches" in err.detail.lower()


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
        if state.get("apply_error"):
            raise state["apply_error"]
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


def test_no_remedy_when_reset_would_overwrite_an_ignored_file(remote_and_clone):
    seed, clone = remote_and_clone
    commit(seed, "settings.local", "upstream version")
    git(seed, "push", "-q", "origin", "main")
    commit(clone, "local-only")
    (clone / ".git" / "info" / "exclude").write_text("settings.local\n")
    (clone / "settings.local").write_text("my local secrets")

    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    assert exc.value.remedy is None
    assert (clone / "settings.local").read_text() == "my local secrets"


def test_remedy_refuses_when_checkout_changed_before_the_answer(remote_and_clone):
    seed, clone = remote_and_clone
    diverge(seed, clone)
    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    git(clone, "switch", "-q", "-c", "other")  # another terminal moved HEAD meanwhile
    before = rev(clone, "HEAD")

    with pytest.raises(AecError, match="changed before the reset"):
        exc.value.remedy.apply()
    assert rev(clone, "HEAD") == before
    assert not subprocess.run(["git", "branch", "--list", "aec-backup/*"], cwd=clone,
                              capture_output=True, text=True).stdout.strip()


def test_invalid_answer_to_remedy_exits_2(remedy_cli, capsys):
    prompts.set_answers({UPDATE_RESET_TO_REMOTE: "maybe"})
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert remedy_cli["applied"] == 0


def test_ctrl_c_at_remedy_prompt_aborts_with_130(remedy_cli, monkeypatch):
    def interrupted(*a, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr("aec.lib.prompts.prompt", interrupted)
    monkeypatch.setattr(__name__ + ".prompt", interrupted)
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 130
    assert remedy_cli["applied"] == 0


def test_failed_remedy_is_reported_and_exits_1(remedy_cli, monkeypatch, capsys):
    prompts.set_answers({UPDATE_RESET_TO_REMOTE: "y"})
    remedy_cli["apply_error"] = AecError("Reset failed.", fix=["do it by hand"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Reset failed." in out and "do it by hand" in out
    assert remedy_cli["runs"] == 1


def offered(seed, clone):
    git(seed, "push", "-q", "origin", "main")
    commit(clone, "local-only")
    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    return exc.value.remedy is not None


def test_no_remedy_for_ignored_file_with_a_quoted_name(remote_and_clone):
    seed, clone = remote_and_clone
    commit(seed, "café\tx", "upstream")
    (clone / ".git" / "info" / "exclude").write_text("caf*\n")
    (clone / "café\tx").write_text("SECRET")
    assert not offered(seed, clone)


def test_no_remedy_when_an_ignored_file_sits_where_upstream_adds_a_folder(remote_and_clone):
    seed, clone = remote_and_clone
    (seed / "folder").mkdir()
    commit(seed, "folder/child", "upstream")
    (clone / ".git" / "info" / "exclude").write_text("folder\n")
    (clone / "folder").write_text("SECRET")
    assert not offered(seed, clone)


def test_no_remedy_when_a_submodule_dir_with_content_becomes_a_file(remote_and_clone, tmp_path):
    seed, clone = remote_and_clone
    lib = tmp_path / "lib"
    git(tmp_path, "init", "-q", "-b", "main", str(lib))
    commit(lib, "f")
    for repo in (seed, clone):
        git(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(lib), "sub")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "sub")
    git(seed, "push", "-q", "-f", "origin", "main")
    git(clone, "fetch", "-q")
    git(clone, "reset", "-q", "--hard", "origin/main")
    git(seed, "rm", "-q", "sub")
    commit(seed, "sub", "now a file")
    (clone / "sub" / "keep.txt").write_text("SECRET")
    assert not offered(seed, clone)


def test_remedy_refuses_when_upstream_changed_before_the_answer(remote_and_clone):
    seed, clone = remote_and_clone
    diverge(seed, clone)
    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    commit(seed, "upstream2")
    git(seed, "push", "-q", "origin", "main")
    git(clone, "fetch", "-q")
    before = rev(clone, "HEAD")
    with pytest.raises(AecError, match="changed before the reset"):
        exc.value.remedy.apply()
    assert rev(clone, "HEAD") == before


def test_submodule_pointer_bump_still_offers_the_remedy(remote_and_clone, tmp_path):
    seed, clone = remote_and_clone
    lib = tmp_path / "lib"
    git(tmp_path, "init", "-q", "-b", "main", str(lib))
    commit(lib, "f")
    git(seed, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(lib), "sub")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "sub")
    git(seed, "push", "-q", "origin", "main")
    git(clone, "pull", "-q")
    git(clone, "-c", "protocol.file.allow=always", "submodule", "update", "-q", "--init")
    commit(lib, "g")
    git(seed / "sub", "pull", "-q")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "bump")
    assert offered(seed, clone)


def test_submodule_network_failure_is_diagnosed_as_network(tmp_path):
    from aec.lib.sources import _diagnose_sync_failure
    err = _diagnose_sync_failure(tmp_path, ["git", "submodule", "update"],
                                 "fatal: unable to access 'https://example.invalid/': Could not resolve host")
    assert "Could not reach the AEC remote" in err.message


def test_version_flag(monkeypatch, capsys):
    from aec import __version__
    monkeypatch.setattr("sys.argv", ["aec", "--version"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_remedy_for_unicode_equivalent_ignored_name(remote_and_clone):
    seed, clone = remote_and_clone
    git(seed, "config", "core.precomposeunicode", "false")
    git(clone, "config", "core.precomposeunicode", "false")
    commit(seed, "café", "upstream")  # composed
    (clone / ".git" / "info" / "exclude").write_text("caf*\n")
    decomposed = clone / "café"
    try:
        decomposed.write_text("SECRET")
    except OSError:
        pytest.skip("filesystem rejects the name")
    assert not offered(seed, clone)


def test_reset_does_not_recurse_into_submodules(remote_and_clone, tmp_path):
    seed, clone = remote_and_clone
    lib = tmp_path / "lib"
    git(tmp_path, "init", "-q", "-b", "main", str(lib))
    commit(lib, "f")
    git(seed, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(lib), "sub")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "sub")
    git(seed, "push", "-q", "origin", "main")
    git(clone, "pull", "-q")
    git(clone, "-c", "protocol.file.allow=always", "submodule", "update", "-q", "--init")
    git(clone, "config", "submodule.recurse", "true")
    commit(lib, "secret", "UPSTREAM")
    git(seed / "sub", "pull", "-q")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "bump")
    git(seed, "push", "-q", "origin", "main")
    commit(clone, "local-only")
    git(clone / "sub", "fetch", "-q")
    exclude = clone / ".git" / "modules" / "sub" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("secret\n")
    (clone / "sub" / "secret").write_text("LOCAL SECRET")

    with pytest.raises(RepoSyncError) as exc:
        fetch_latest(clone)
    assert exc.value.remedy is not None
    exc.value.remedy.apply()
    assert (clone / "sub" / "secret").read_text() == "LOCAL SECRET"
