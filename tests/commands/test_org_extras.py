"""Extra coverage for the `aec org` CLI exit-code and output branches.

Focuses on edges not covered by `tests/commands/test_org.py`:
file-not-found, parse/validation errors, signed trust modes, multi-org
discovery, status/show targeting, and the various remove paths.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from aec.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "lib" / "org_config" / "fixtures"


def _run(args, env_home: Path):
    return runner.invoke(app, args, env={"HOME": str(env_home)})


def _all_output(result) -> str:
    """Return stdout + stderr regardless of click version.

    Old click's ``CliRunner`` merges streams by default and raises
    ``ValueError`` on ``result.stderr``. Newer click splits them. We just
    want every byte the command emitted, so try both and concatenate.
    """
    parts = [result.stdout or ""]
    try:
        parts.append(result.stderr or "")
    except (ValueError, AttributeError):
        pass
    return "".join(parts).lower()


def _enroll_minimal(env_home: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    return _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], env_home)


# --- enroll ---------------------------------------------------------------


def test_enroll_file_not_found_exits_validation(tmp_path: Path):
    missing = tmp_path / "does-not-exist.yaml"
    result = _run(["org", "enroll", str(missing), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 13
    assert "file not found" in _all_output(result)


def test_enroll_directory_path_treated_as_not_a_file(tmp_path: Path):
    a_dir = tmp_path / "a-dir"
    a_dir.mkdir()
    result = _run(["org", "enroll", str(a_dir), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 13


def test_enroll_invalid_yaml_exits_validation(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not a frontmatter doc\n", encoding="utf-8")
    result = _run(["org", "enroll", str(bad), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 13
    assert "error:" in _all_output(result)


def test_enroll_validation_error_exits_13(tmp_path: Path):
    cfg = FIXTURES / "invalid-bad-stance.yaml"
    result = _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 13


def test_enroll_unknown_schema_exits_13(tmp_path: Path):
    cfg = FIXTURES / "invalid-future-schema.yaml"
    result = _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 13


def test_enroll_signed_trust_mode_exits_trust(tmp_path: Path):
    """A `pinned_key` overlay with no `pubkey` fails validation — exit 13."""
    src = (FIXTURES / "valid-minimal.yaml").read_text()
    pinned = src.replace('mode: "unsigned"', 'mode: "pinned_key"')
    p = tmp_path / "pinned.yaml"
    p.write_text(pinned, encoding="utf-8")
    result = _run(["org", "enroll", str(p), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 13


def test_enroll_unsigned_consent_declined_via_stdin_exits_trust(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    # No --allow-unsigned and no --yes; pipe "n" to the typer.confirm prompt.
    result = runner.invoke(
        app,
        ["org", "enroll", str(cfg)],
        env={"HOME": str(tmp_path)},
        input="n\n",
    )
    assert result.exit_code == 10


# --- list -----------------------------------------------------------------


def test_list_with_one_enrolled_org_prints_summary_line(tmp_path: Path):
    _enroll_minimal(tmp_path)
    result = _run(["org", "list"], tmp_path)
    assert result.exit_code == 0
    assert "minimal" in result.stdout
    assert "config_version=" in result.stdout
    assert "trust_mode=unsigned" in result.stdout
    assert "last_applied_at=" in result.stdout


def test_list_multi_org_lists_all(tmp_path: Path):
    _enroll_minimal(tmp_path)
    # A second enrolled org now coexists (Phase 2d multi-org).
    orgs_dir = tmp_path / ".aec" / "orgs"
    shutil.copy(FIXTURES / "valid-full.yaml", orgs_dir / "acme.yaml")
    result = _run(["org", "list"], tmp_path)
    assert result.exit_code == 0
    assert "minimal" in result.stdout
    assert "acme" in result.stdout


# --- status ---------------------------------------------------------------


def test_status_with_no_orgs_prints_message(tmp_path: Path):
    result = _run(["org", "status"], tmp_path)
    assert result.exit_code == 0
    assert "no orgs enrolled" in result.stdout.lower()


def test_status_with_org_id_match(tmp_path: Path):
    _enroll_minimal(tmp_path)
    result = _run(["org", "status", "minimal"], tmp_path)
    assert result.exit_code == 0
    assert "org_id: minimal" in result.stdout


def test_status_with_org_id_mismatch_exits_13(tmp_path: Path):
    _enroll_minimal(tmp_path)
    result = _run(["org", "status", "ghost"], tmp_path)
    assert result.exit_code == 13
    assert "ghost" in _all_output(result)


def test_status_multi_org_shows_all(tmp_path: Path):
    _enroll_minimal(tmp_path)
    orgs_dir = tmp_path / ".aec" / "orgs"
    shutil.copy(FIXTURES / "valid-full.yaml", orgs_dir / "acme.yaml")
    result = _run(["org", "status"], tmp_path)
    assert result.exit_code == 0
    assert "org_id: minimal" in result.stdout
    assert "org_id: acme" in result.stdout


def test_status_prints_no_state_when_state_file_missing(tmp_path: Path):
    _enroll_minimal(tmp_path)
    # Delete the state file but leave the yaml — exercises the `state is None`
    # branch in _print_status_for.
    (tmp_path / ".aec" / "orgs" / "minimal.state.json").unlink()
    result = _run(["org", "status"], tmp_path)
    assert result.exit_code == 0
    assert "(no state file)" in result.stdout


# --- show -----------------------------------------------------------------


def test_show_unknown_org_exits_13(tmp_path: Path):
    result = _run(["org", "show", "ghost"], tmp_path)
    assert result.exit_code == 13
    assert "ghost" in _all_output(result)


def test_show_raw_prints_file_verbatim(tmp_path: Path):
    _enroll_minimal(tmp_path)
    result = _run(["org", "show", "minimal", "--raw"], tmp_path)
    assert result.exit_code == 0
    assert "schema_version: \"1.0\"" in result.stdout
    assert "org_id: \"minimal\"" in result.stdout


def test_show_renders_description_when_present(tmp_path: Path):
    cfg = FIXTURES / "valid-full.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    result = _run(["org", "show", "acme"], tmp_path)
    assert result.exit_code == 0
    assert "description:" in result.stdout
    assert "Acme" in result.stdout


def test_show_validation_error_on_corrupted_file_exits_13(tmp_path: Path):
    _enroll_minimal(tmp_path)
    # Corrupt the on-disk config so validate_org_config fails on `show`.
    (tmp_path / ".aec" / "orgs" / "minimal.yaml").write_text("garbage\n", encoding="utf-8")
    result = _run(["org", "show", "minimal"], tmp_path)
    assert result.exit_code == 13


# --- remove ---------------------------------------------------------------


def test_remove_nonexistent_org_exits_13(tmp_path: Path):
    result = _run(["org", "remove", "ghost", "--yes"], tmp_path)
    assert result.exit_code == 13


def test_remove_declined_at_prompt_exits_1(tmp_path: Path):
    _enroll_minimal(tmp_path)
    result = runner.invoke(
        app,
        ["org", "remove", "minimal"],
        env={"HOME": str(tmp_path)},
        input="n\n",
    )
    assert result.exit_code == 1
    assert "aborted" in result.stdout.lower()
    # Files should still exist since the user declined.
    assert (tmp_path / ".aec" / "orgs" / "minimal.yaml").exists()
