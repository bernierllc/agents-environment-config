"""Phase 1: git-sourced enroll, the refresh-then-apply table, pending, and --replace.

Real git against a local bare repo (see ``tests/lib/org_config/test_git_source.py``
for how the https URL is rewritten to it in a test-only git config) and a real
``~/.aec`` under ``tmp_path``. Nothing AEC owns is mocked.
"""
import base64
import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import aec.commands.org as org_cmd
from aec.cli import app
from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.state import read_state, write_state
from tests.lib.org_config.test_git_source import REMOTE_URL, _git, commit_file, remote  # noqa: F401

SOURCE = f"git+{REMOTE_URL}#main:org/my-org.yaml"

UNSIGNED = """---
schema_version: "1.0"
org_id: "my-org"
org_name: "My Org"
config_version: "{version}"
trust:
  mode: "unsigned"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom: []

items:
  skills: {{}}
  rules: {{}}
  agents: {{}}
  mcps: {{}}
"""

PINNED = """---
schema_version: "1.0"
org_id: "my-org"
org_name: "My Org"
config_version: "{version}"
trust:
  mode: "pinned_key"
  pubkey: "{pubkey}"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom: []
{install}
items:
  skills: {{}}
  rules: {{}}
  agents: {{}}
  mcps: {{}}
"""

runner = CliRunner()

try:
    import nacl.signing as nacl_signing
except ImportError:  # signed-mode tests need the crypto extra
    nacl_signing = None
needs_nacl = pytest.mark.skipif(nacl_signing is None, reason="PyNaCl not installed")


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setattr(Path, "home", lambda: h)
    monkeypatch.setenv("HOME", str(h))
    return h


@pytest.fixture
def paths(home):
    return OrgPaths(home_dir=home)


def _push_unsigned(remote, version):
    return commit_file(remote, "org/my-org.yaml", UNSIGNED.format(version=version))


def _enroll_unsigned(remote, version="1.0.0"):
    commit = _push_unsigned(remote, version)
    org_cmd.perform_enroll(SOURCE, allow_unsigned=True)
    return commit


def _exit_code(fn, *a, **kw):
    with pytest.raises(typer.Exit) as exc:
        fn(*a, **kw)
    return exc.value.exit_code


# --------------------------------------------------------------------------- #
#  Enroll                                                                      #
# --------------------------------------------------------------------------- #

def test_git_enroll_records_source_and_keeps_clone(remote, paths):
    commit = _enroll_unsigned(remote)

    st = read_state(paths, "my-org")
    assert (st.source_of_record, st.source_repo, st.source_ref, st.source_path) == (
        "git", REMOTE_URL, "main", "org/my-org.yaml",
    )
    assert st.resolved_commit == commit
    assert st.last_applied_at is None
    assert st.pending is None
    assert (paths.org_dir_for("my-org") / "repo" / "org" / "my-org.yaml").is_file()
    assert not list(paths.orgs_dir.glob(".tmp-enroll-*"))


def test_status_renders_never_applied(remote, home):
    _enroll_unsigned(remote)
    result = runner.invoke(app, ["org", "status"], env={"HOME": str(home)})
    assert result.exit_code == 0, result.output
    assert "never applied" in result.output


def test_remove_deletes_org_dir(remote, paths):
    _enroll_unsigned(remote)
    org_cmd.remove_cmd(org_id="my-org", yes=True)
    assert not paths.org_dir_for("my-org").exists()
    assert read_state(paths, "my-org") is None


def test_replace_refuses_org_that_is_not_enrolled(remote, paths):
    _push_unsigned(remote, "1.0.0")
    assert _exit_code(org_cmd.perform_enroll, SOURCE, allow_unsigned=True, replace="my-org") == 13
    assert read_state(paths, "my-org") is None


def test_replace_refuses_a_different_org_id(remote, paths, tmp_path):
    _enroll_unsigned(remote)
    other = tmp_path / "other.yaml"
    other.write_text(UNSIGNED.format(version="1").replace('"my-org"', '"other-org"'), encoding="utf-8")
    assert _exit_code(org_cmd.perform_enroll, str(other), allow_unsigned=True, replace="my-org") == 13
    assert read_state(paths, "my-org").source_of_record == "git"


def test_replace_swaps_source_keeps_last_applied_and_drops_clone(remote, paths, tmp_path):
    _enroll_unsigned(remote)
    st = read_state(paths, "my-org")
    write_state(paths, type(st)(**{**st.__dict__, "last_applied_at": "2026-10-01T00:00:00Z"}))
    local = tmp_path / "my-org.yaml"
    local.write_text(UNSIGNED.format(version="1.0.0"), encoding="utf-8")

    org_cmd.perform_enroll(str(local), allow_unsigned=True, replace="my-org")

    st = read_state(paths, "my-org")
    assert st.source_of_record == "local"
    assert st.last_applied_at == "2026-10-01T00:00:00Z"
    assert not (paths.org_dir_for("my-org") / "repo").exists()


# --------------------------------------------------------------------------- #
#  Refresh table (unsigned)                                                    #
# --------------------------------------------------------------------------- #

def test_refresh_unchanged(remote, paths):
    _enroll_unsigned(remote)
    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "unchanged")]
    assert read_state(paths, "my-org").pending is None


def test_unsigned_change_is_staged_for_review_not_applied(remote, paths):
    _enroll_unsigned(remote)
    before = paths.config_for("my-org").read_bytes()
    new_commit = _push_unsigned(remote, "2.0.0")

    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "pending review")]

    st = read_state(paths, "my-org")
    assert st.pending["kind"] == "review"
    assert st.pending["commit"] == new_commit
    assert st.config_version == "1.0.0"
    assert paths.config_for("my-org").read_bytes() == before
    assert b"2.0.0" in (paths.org_dir_for("my-org") / "staged.yaml").read_bytes()


def test_refresh_follows_force_push(remote, paths):
    _enroll_unsigned(remote)
    (remote / "org/my-org.yaml").write_text(UNSIGNED.format(version="9.9.9"), encoding="utf-8")
    _git("commit", "-q", "-a", "--amend", "-m", "rewritten", cwd=remote)
    _git("push", "-q", "--force", "origin", "HEAD:main", cwd=remote)
    rewritten = _git("rev-parse", "HEAD", cwd=remote)

    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "pending review")]
    assert read_state(paths, "my-org").pending["commit"] == rewritten


def test_back_to_applied_content_clears_review(remote, paths):
    _enroll_unsigned(remote)
    _push_unsigned(remote, "2.0.0")
    org_cmd.refresh_remote_orgs(paths)
    _push_unsigned(remote, "1.0.0")

    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "unchanged")]
    assert read_state(paths, "my-org").pending is None
    assert not (paths.org_dir_for("my-org") / "staged.yaml").exists()


def test_update_reports_pending_and_doctor_fails(remote, paths, home):
    from aec.commands.doctor import _check_org_configurations
    from aec.commands.update import _refresh_org_configs

    _enroll_unsigned(remote)
    assert _refresh_org_configs() is False
    assert _check_org_configurations() == []

    _push_unsigned(remote, "2.0.0")
    assert _refresh_org_configs() is True  # aec update exits EXIT_PENDING (14)
    issues = _check_org_configurations()
    assert len(issues) == 1 and "aec org apply" in issues[0]


def test_corrupt_state_is_reported_not_raised(remote, paths, home):
    from aec.commands.update import _refresh_org_configs

    _enroll_unsigned(remote)
    paths.state_for("my-org").write_text("{not json", encoding="utf-8")

    [(org_id, status)] = org_cmd.refresh_remote_orgs(paths)
    assert org_id == "my-org" and status.startswith("error:")
    assert _refresh_org_configs() is True


def test_dead_clone_is_recloned(remote, paths):
    _enroll_unsigned(remote)
    repo = paths.org_dir_for("my-org") / "repo"
    import shutil
    shutil.rmtree(repo / ".git")  # what a clone killed mid-way leaves behind
    new_commit = _push_unsigned(remote, "2.0.0")

    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "pending review")]
    assert read_state(paths, "my-org").pending["commit"] == new_commit


def test_unparseable_fetch_is_verify_failed(remote, paths):
    _enroll_unsigned(remote)
    commit_file(remote, "org/my-org.yaml", "not: [valid\n")
    [(org_id, status)] = org_cmd.refresh_remote_orgs(paths)
    assert status.startswith("verify_failed")
    assert read_state(paths, "my-org").pending["kind"] == "verify_failed"
    assert read_state(paths, "my-org").config_version == "1.0.0"


# --------------------------------------------------------------------------- #
#  apply / --decline                                                           #
# --------------------------------------------------------------------------- #

def _stage_review(remote, paths):
    _enroll_unsigned(remote)
    commit = _push_unsigned(remote, "2.0.0")
    org_cmd.refresh_remote_orgs(paths)
    return commit


def test_apply_promotes_staged_review(remote, paths, home):
    commit = _stage_review(remote, paths)

    result = runner.invoke(app, ["org", "apply", "--yes"], env={"HOME": str(home)})

    assert result.exit_code == 0, result.output
    st = read_state(paths, "my-org")
    assert (st.config_version, st.resolved_commit, st.pending) == ("2.0.0", commit, None)
    assert st.last_applied_at is not None
    assert not (paths.org_dir_for("my-org") / "staged.yaml").exists()


@pytest.mark.parametrize("args,stdin", [(["--dry-run"], None), ([], "n\n")])
def test_apply_not_done_restores_and_keeps_staged(remote, paths, home, args, stdin):
    _stage_review(remote, paths)
    before_yaml = paths.config_for("my-org").read_bytes()
    before_state = read_state(paths, "my-org")

    result = runner.invoke(app, ["org", "apply", *args], env={"HOME": str(home)}, input=stdin)

    assert result.exit_code == 0, result.output
    assert paths.config_for("my-org").read_bytes() == before_yaml
    assert read_state(paths, "my-org") == before_state
    assert (paths.org_dir_for("my-org") / "staged.yaml").exists()


def test_apply_interrupted_restores_and_keeps_staged(remote, paths, home):
    # stdin closed at the guided confirm: the prompt raises instead of answering.
    _stage_review(remote, paths)
    before_yaml = paths.config_for("my-org").read_bytes()
    before_state = read_state(paths, "my-org")

    result = runner.invoke(app, ["org", "apply"], env={"HOME": str(home)}, input="")

    assert result.exit_code != 0
    assert paths.config_for("my-org").read_bytes() == before_yaml
    assert read_state(paths, "my-org") == before_state
    assert (paths.org_dir_for("my-org") / "staged.yaml").exists()


def test_decline_review_discards_it(remote, paths):
    commit = _stage_review(remote, paths)
    assert _exit_code(org_cmd._decline_review, paths, commit[:6]) == 13

    org_cmd._decline_review(paths, commit[:7])

    st = read_state(paths, "my-org")
    assert st.pending is None and st.config_version == "1.0.0"
    assert not (paths.org_dir_for("my-org") / "staged.yaml").exists()


def test_decline_matches_url_hash_without_its_prefix(remote, paths):
    import dataclasses

    _stage_review(remote, paths)
    st = read_state(paths, "my-org")
    write_state(paths, dataclasses.replace(st, pending={**st.pending, "commit": "sha256:" + "ab" * 32}))

    assert "--decline abababababab" in org_cmd.pending_fix(read_state(paths, "my-org"))
    assert _exit_code(org_cmd._decline_review, paths, "sha256:") == 13
    org_cmd._decline_review(paths, "abababa")
    assert read_state(paths, "my-org").pending is None


# --------------------------------------------------------------------------- #
#  Trust anchor changes                                                        #
# --------------------------------------------------------------------------- #

def _pinned_text(key, version, install=""):
    pub = base64.b64encode(bytes(key.verify_key)).decode()
    return PINNED.format(version=version, pubkey=pub, install=install)


def _push_signed(remote, key, version, install="", sign_with=None):
    text = _pinned_text(key, version, install)
    (remote / "org").mkdir(exist_ok=True)
    (remote / "org/my-org.yaml.sig").write_bytes((sign_with or key).sign(text.encode()).signature)
    return commit_file(remote, "org/my-org.yaml", text)


def _flip_to_pinned(remote, paths):
    _enroll_unsigned(remote)
    _push_signed(remote, nacl_signing.SigningKey.generate(), "2.0.0")
    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "trust_change")]


@needs_nacl
def test_trust_change_is_recorded_and_not_downgraded(remote, paths):
    _flip_to_pinned(remote, paths)
    st = read_state(paths, "my-org")
    assert st.pending["kind"] == "trust_change"
    assert st.pending["from"]["trust_mode"] == "unsigned"
    assert st.config_version == "1.0.0"

    # A later ordinary change does not turn the trust change into a review.
    _push_unsigned(remote, "3.0.0")
    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "trust_change")]
    assert read_state(paths, "my-org").pending["from"]["trust_mode"] == "unsigned"


@needs_nacl
def test_trust_change_refuses_decline_and_trust_rotate(remote, paths):
    _flip_to_pinned(remote, paths)
    assert _exit_code(org_cmd._decline_review, paths, "0000000") == 10
    assert _exit_code(org_cmd.trust_rotate_cmd, org_id="my-org", signature=None, yes=True) == 10
    assert read_state(paths, "my-org").pending["kind"] == "trust_change"


@needs_nacl
def test_trust_change_cleared_only_by_interactive_replace(remote, paths, monkeypatch):
    _flip_to_pinned(remote, paths)
    assert _exit_code(
        org_cmd.perform_enroll, SOURCE, trust_fingerprint=True, yes=True, replace="my-org",
    ) == 10
    assert read_state(paths, "my-org").pending["kind"] == "trust_change"

    monkeypatch.setattr(typer, "confirm", lambda *a, **k: True)
    org_cmd.perform_enroll(SOURCE, replace="my-org")

    st = read_state(paths, "my-org")
    assert (st.trust_mode, st.pending, st.config_version) == ("pinned_key", None, "2.0.0")


@needs_nacl
def test_reenroll_with_new_anchor_refuses_yes(remote, paths):
    _enroll_unsigned(remote)
    _push_signed(remote, nacl_signing.SigningKey.generate(), "2.0.0")
    assert _exit_code(org_cmd.perform_enroll, SOURCE, trust_fingerprint=True, yes=True) == 10
    assert read_state(paths, "my-org").trust_mode == "unsigned"


# --------------------------------------------------------------------------- #
#  Signed refresh                                                              #
# --------------------------------------------------------------------------- #

MANAGED = '\ninstall:\n  mode: "managed"\n'
GUIDED = '\ninstall:\n  mode: "guided"\n'


def _enroll_signed(remote, key, install):
    _push_signed(remote, key, "1.0.0", install)
    org_cmd.perform_enroll(SOURCE, trust_fingerprint=True, yes=True)


@needs_nacl
def test_signed_managed_change_is_applied(remote, paths):
    key = nacl_signing.SigningKey.generate()
    _enroll_signed(remote, key, MANAGED)
    commit = _push_signed(remote, key, "2.0.0", MANAGED)

    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "updated")]

    st = read_state(paths, "my-org")
    assert (st.config_version, st.resolved_commit, st.pending) == ("2.0.0", commit, None)
    assert st.last_applied_at is not None


@needs_nacl
@pytest.mark.parametrize("install", [GUIDED, ""])
def test_signed_guided_or_unset_change_is_pending_review(remote, paths, install):
    key = nacl_signing.SigningKey.generate()
    _enroll_signed(remote, key, install)
    _push_signed(remote, key, "2.0.0", install)

    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "pending review")]
    st = read_state(paths, "my-org")
    assert st.config_version == "1.0.0" and st.last_applied_at is None


@needs_nacl
def test_signed_bad_signature_is_verify_failed(remote, paths):
    key = nacl_signing.SigningKey.generate()
    _enroll_signed(remote, key, MANAGED)
    before = paths.config_for("my-org").read_bytes()
    _push_signed(remote, key, "2.0.0", MANAGED, sign_with=nacl_signing.SigningKey.generate())

    [(_, status)] = org_cmd.refresh_remote_orgs(paths)

    assert status.startswith("verify_failed")
    st = read_state(paths, "my-org")
    assert st.pending["kind"] == "verify_failed" and st.config_version == "1.0.0"
    assert paths.config_for("my-org").read_bytes() == before


@needs_nacl
def test_pinned_key_change_is_trust_change(remote, paths):
    key = nacl_signing.SigningKey.generate()
    _enroll_signed(remote, key, MANAGED)
    _push_signed(remote, nacl_signing.SigningKey.generate(), "2.0.0", MANAGED)
    assert org_cmd.refresh_remote_orgs(paths) == [("my-org", "trust_change")]


def test_unknown_state_key_is_ignored(remote, paths):
    _enroll_unsigned(remote)
    p = paths.state_for("my-org")
    data = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**data, "from_a_newer_aec": 1}), encoding="utf-8")
    assert read_state(paths, "my-org").org_id == "my-org"
