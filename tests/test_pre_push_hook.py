"""The pre-push hook must never create commits.

A commit made inside pre-push is not part of the push already in flight, so it
stays local and leaves the branch diverged from its remote (this is how a
checkout's ``main`` ended up ahead of origin and broke ``aec update``).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "scripts" / "git-hooks" / "pre-push"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_pre_push_leaves_generated_changes_uncommitted(tmp_path):
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com")):
        _git(work, "config", k, v)
    (work / "README.md").write_text("x\n")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "remote", "add", "origin", str(remote))

    # A sync script that regenerates .cursor/commands, as the real one does
    # when submodules float ahead of their pins.
    scripts = work / "scripts"
    scripts.mkdir()
    (scripts / "sync-agents-skills.py").write_text(
        "from pathlib import Path\n"
        "p = Path(__file__).resolve().parents[1] / '.cursor' / 'commands'\n"
        "p.mkdir(parents=True, exist_ok=True)\n"
        "(p / 'generated.md').write_text('regenerated\\n')\n"
    )
    hooks = work / ".git" / "hooks"
    shutil.copy(HOOK, hooks / "pre-push")
    (hooks / "pre-push").chmod(0o755)

    head_before = _git(work, "rev-parse", "HEAD")
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=work, check=True, capture_output=True)

    assert _git(work, "rev-parse", "HEAD") == head_before
    assert _git(work, "rev-parse", "origin/main") == head_before
