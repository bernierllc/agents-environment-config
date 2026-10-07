"""git_source: real git against a local bare repo.

The repo is reached through an https URL that a test-only git config rewrites
(``url.<file-url>.insteadOf``) to the local bare repo, with
``protocol.file.allow=always`` in that same config. Both settings live only in
the GIT_CONFIG_GLOBAL file this fixture creates, so production validation and
the protocol allow-list run unchanged.
"""
import subprocess
from pathlib import Path

import pytest

from aec.lib.org_config import git_source
from aec.lib.org_config.errors import OrgConfigFetchError, OrgConfigValidationError

REMOTE_URL = "https://git.example.test/my-org/aec-catalog.git"


def _git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_file(work: Path, rel: str, content: str, message: str = "update") -> str:
    path = work / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git("add", "-A", cwd=work)
    _git("commit", "-q", "-m", message, cwd=work)
    _git("push", "-q", "--force", "origin", "HEAD:main", cwd=work)
    return _git("rev-parse", "HEAD", cwd=work)


@pytest.fixture
def remote(tmp_path, monkeypatch):
    """A bare repo reachable as REMOTE_URL, plus a working clone to push from."""
    bare = tmp_path / "remote.git"
    _git("init", "-q", "--bare", "-b", "main", str(bare))
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = Test\n\temail = test@example.test\n"
        '[protocol "file"]\n\tallow = always\n'
        f'[url "{bare.as_uri()}"]\n\tinsteadOf = {REMOTE_URL}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    work = tmp_path / "work"
    _git("init", "-q", "-b", "main", str(work))
    _git("remote", "add", "origin", str(bare), cwd=work)
    return work


def test_parse_valid_https_and_scp():
    src = git_source.parse_git_source(f"git+{REMOTE_URL}#main:org/my-org.yaml")
    assert (src.url, src.ref, src.path) == (REMOTE_URL, "main", "org/my-org.yaml")
    assert src.spec == f"git+{REMOTE_URL}#main:org/my-org.yaml"
    scp = git_source.parse_git_source("git+git@git.example.test:my-org/cat.git#v1.2:a.yaml")
    assert (scp.url, scp.ref) == ("git@git.example.test:my-org/cat.git", "v1.2")


@pytest.mark.parametrize(
    "spec",
    [
        f"git+{REMOTE_URL}#--upload-pack=x:org.yaml",
        "git+ext::sh -c x#main:org.yaml",
        "git+file:///tmp/x#main:org.yaml",
        "git+-oProxyCommand=x#main:org.yaml",
        f"git+{REMOTE_URL}#main:../escape.yaml",
        f"git+{REMOTE_URL}#main:/etc/passwd",
        f"git+{REMOTE_URL}#main",
        f"git+{REMOTE_URL}",
    ],
)
def test_parse_rejects(spec):
    with pytest.raises(OrgConfigValidationError):
        git_source.parse_git_source(spec)


def test_clone_refresh_follows_force_push(remote, tmp_path):
    first = commit_file(remote, "org/my-org.yaml", "v1\n")
    src = git_source.parse_git_source(f"git+{REMOTE_URL}#main:org/my-org.yaml")
    dest = tmp_path / "clone"

    assert git_source.clone(src, dest) == first
    assert git_source.read_file(dest, src.path) == b"v1\n"

    # Rewrite history: amend and force-push. A fast-forward-only pull would fail.
    (remote / "org/my-org.yaml").write_text("v2\n", encoding="utf-8")
    _git("commit", "-q", "-a", "--amend", "-m", "rewritten", cwd=remote)
    _git("push", "-q", "--force", "origin", "HEAD:main", cwd=remote)
    rewritten = _git("rev-parse", "HEAD", cwd=remote)

    assert git_source.refresh(src, dest) == rewritten != first
    assert git_source.read_file(dest, src.path) == b"v2\n"


def test_read_file_rejects_symlink_escape(remote, tmp_path):
    (tmp_path / "secret.yaml").write_text("x", encoding="utf-8")
    (remote / "org").mkdir()
    (remote / "org" / "link.yaml").symlink_to(tmp_path / "secret.yaml")
    commit_file(remote, "README", "r\n")
    src = git_source.parse_git_source(f"git+{REMOTE_URL}#main:org/link.yaml")
    dest = tmp_path / "clone"
    git_source.clone(src, dest)
    with pytest.raises(OrgConfigValidationError):
        git_source.read_file(dest, src.path)
    assert git_source.read_file(dest, "missing.yaml") is None


def test_protocol_allow_list_blocks_file_transport(remote, tmp_path):
    """Without the test-only protocol.file.allow, PROTO_FLAGS refuse the file transport."""
    commit_file(remote, "a.yaml", "a\n")
    gitconfig = tmp_path / "gitconfig"
    text = gitconfig.read_text(encoding="utf-8")
    gitconfig.write_text(text.replace('[protocol "file"]\n\tallow = always\n', ""), encoding="utf-8")
    src = git_source.parse_git_source(f"git+{REMOTE_URL}#main:a.yaml")
    with pytest.raises(OrgConfigFetchError):
        git_source.clone(src, tmp_path / "clone")


@pytest.mark.parametrize("org_id", ["../x", "Acme", "-acme", "a/b", "", "a" * 64])
def test_org_id_charset_rejected(org_id):
    from aec.lib.org_config.validator import validate_org_config

    fm = {"schema_version": "1.0", "org_id": org_id, "org_name": "x",
          "config_version": "1", "trust": {"mode": "unsigned"}}
    with pytest.raises(OrgConfigValidationError):
        validate_org_config(fm, {})
