"""Vendored guard copies must match aec; aec's canonical must not lag aec's own workflows."""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_vendored_drift", ROOT / "scripts" / "check-vendored-drift.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
GUARD = (ROOT / ".github" / "workflows" / "main-via-staging.yml").read_text()


def test_every_workflow_pins_one_checkout_major():
    # Dependabot bumps each repo's copy; if aec's canonical lags its own other workflows, every vendoring
    # repo's bump is drift. Fails when a new workflow is copied from a stale template.
    pins = {}
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        for major in re.findall(r"actions/checkout@v(\d+)", wf.read_text()):
            pins.setdefault(major, []).append(wf.name)
    assert len(pins) == 1, f"mixed actions/checkout majors: {pins}"


def test_guard_checks_out_the_event_sha_never_pr_code():
    # checkout@v7 blocks fork PR checkouts under pull_request_target; the bump is safe only while the guard
    # pins the event commit (github.sha) and does not opt in to unsafe PR checkouts.
    assert "ref: ${{ github.sha }}" in GUARD
    assert not re.search(r"^\s*allow-unsafe-pr-checkout:", GUARD, re.M)
    assert "pull_request.head.sha" not in re.search(r"uses: actions/checkout.*?persist-credentials", GUARD, re.S).group(0)


def _tree(tmp_path, files):
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)


def test_identical_copy_is_not_drift(tmp_path):
    _tree(tmp_path, {"a.yml": b"x"})
    assert mod.drifted(tmp_path, ["a.yml"], lambda p: b"x") == []


def test_a_dependabot_style_edit_is_drift(tmp_path):
    _tree(tmp_path, {"a.yml": b"uses: actions/checkout@v7\n", "b.sh": b"same"})
    canonical = {"a.yml": b"uses: actions/checkout@v4\n", "b.sh": b"same"}
    assert mod.drifted(tmp_path, ["a.yml", "b.sh"], canonical.__getitem__) == ["a.yml"]


def test_a_missing_vendored_file_is_drift(tmp_path):
    _tree(tmp_path, {"a.yml": b"x"})
    assert mod.drifted(tmp_path, ["a.yml", "gone.sh"], lambda p: b"x") == ["gone.sh"]


def test_cli_default_set_flags_a_deleted_member_instead_of_passing(tmp_path, monkeypatch):
    # Only one of the default files exists locally; the rest were deleted. Must not exit 0.
    _tree(tmp_path, {mod.COPY_SET[0]: b"x"})
    monkeypatch.setattr(mod, "gh_fetch", lambda repo, ref, path: b"x")
    assert mod.main(["--canonical-repo", "my-org/my-aec", "--root", str(tmp_path)]) == 1


def _cli(tmp_path, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "check-vendored-drift.py"), "--root", str(tmp_path), *args],
                          capture_output=True, text=True)


def test_cli_fails_closed_when_nothing_to_compare(tmp_path):
    proc = _cli(tmp_path, "--canonical-repo", "my-org/my-aec")
    assert proc.returncode == 2 and "failing closed" in proc.stderr


def test_cli_fails_closed_when_the_canonical_cannot_be_read(tmp_path):
    _tree(tmp_path, {"a.yml": b"x"})
    proc = _cli(tmp_path, "--canonical-repo", "my-org/no-such-repo-0000", "a.yml")
    assert proc.returncode == 2 and "failing closed" in proc.stderr
