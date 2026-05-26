from pathlib import Path

from typer.testing import CliRunner

from aec.cli import app


runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "lib" / "org_config" / "fixtures"


def _run(args, env_home: Path):
    return runner.invoke(app, args, env={"HOME": str(env_home)})


def test_org_help_lists_phase_1_commands(tmp_path: Path):
    result = _run(["org", "--help"], tmp_path)
    assert result.exit_code == 0
    for cmd in ("enroll", "list", "status", "show", "remove"):
        assert cmd in result.stdout


def test_org_list_empty(tmp_path: Path):
    result = _run(["org", "list"], tmp_path)
    assert result.exit_code == 0
    assert "no orgs enrolled" in result.stdout.lower()


def test_org_enroll_local_path_with_consent(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    result = _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code == 0
    assert (tmp_path / ".aec" / "orgs" / "minimal.yaml").exists()
    assert (tmp_path / ".aec" / "orgs" / "minimal.state.json").exists()


def test_org_enroll_unsigned_without_consent_refuses(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    result = _run(["org", "enroll", str(cfg)], tmp_path)
    assert result.exit_code != 0


def test_org_status_shows_enrolled_org(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    result = _run(["org", "status"], tmp_path)
    assert result.exit_code == 0
    assert "minimal" in result.stdout
    assert "unsigned" in result.stdout.lower()


def test_org_show_prints_config(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    result = _run(["org", "show", "minimal"], tmp_path)
    assert result.exit_code == 0
    assert "schema_version" in result.stdout


def test_org_remove_deletes_state_and_config(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    result = _run(["org", "remove", "minimal", "--yes"], tmp_path)
    assert result.exit_code == 0
    assert not (tmp_path / ".aec" / "orgs" / "minimal.yaml").exists()
    assert not (tmp_path / ".aec" / "orgs" / "minimal.state.json").exists()


def test_org_enroll_rejects_non_https_url(tmp_path: Path):
    # https URL enrollment is supported (see test_org_enroll_url.py); plaintext
    # http is refused before any network access.
    result = _run(["org", "enroll", "http://example.com/config.yaml", "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code != 0
    # Console.error prints to stdout, captured in result.output. Avoid result.stderr,
    # which raises "stderr not separately captured" on click < 8.2 (Python 3.9 CI).
    assert "https" in result.output.lower()


def test_doctor_shows_org_section_when_org_enrolled(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    result = _run(["doctor"], tmp_path)
    assert result.exit_code == 0
    assert "org configuration" in result.stdout.lower()
    assert "minimal" in result.stdout
    assert "unsigned" in result.stdout.lower()


def test_doctor_surfaces_unresolved_conflicts(tmp_path: Path):
    orgs_dir = tmp_path / ".aec" / "orgs"
    orgs_dir.mkdir(parents=True)
    tmpl = (
        '---\nschema_version: "1.0"\norg_id: "{oid}"\norg_name: "{oid}"\n'
        'config_version: "1.0.0"\ntrust:\n  mode: "unsigned"\n---\n\n'
        "sources:\n  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}\n"
        "  custom: []\n\nitems:\n  skills:\n    \"foo\":\n      source: \"aec.default.skills\"\n"
        "      stance: {stance}\n  rules: {{}}\n  agents: {{}}\n  mcps: {{}}\n"
    )
    (orgs_dir / "acme.yaml").write_text(tmpl.format(oid="acme", stance="required"))
    (orgs_dir / "globex.yaml").write_text(tmpl.format(oid="globex", stance="blocked"))

    result = _run(["doctor"], tmp_path)
    assert result.exit_code == 0
    out = result.stdout.lower()
    assert "org conflicts" in out
    assert "skills/foo" in result.stdout
    assert "aec org resolve" in result.stdout


def test_cli_gate_surfaces_rotation_lockout(tmp_path: Path):
    # Enroll a local unsigned org, then inject a long-overdue key rotation into
    # its state; any aec command's pre-command gate must surface the lockout.
    cfg = FIXTURES / "valid-minimal.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)

    import dataclasses

    from aec.lib.org_config.paths import OrgPaths
    from aec.lib.org_config.state import read_state, write_state

    paths = OrgPaths(home_dir=tmp_path)
    st = read_state(paths, "minimal")
    write_state(
        paths,
        dataclasses.replace(
            st,
            key_rotation_pending={
                "detected_at": "2026-01-01T00:00:00Z",
                "new_fingerprint": "SHA256:x",
                "old_fingerprint": "SHA256:y",
            },
        ),
    )

    result = _run(["org", "list"], tmp_path)
    assert "LOCKED" in result.stdout


def test_doctor_omits_org_section_when_no_orgs(tmp_path: Path):
    result = _run(["doctor"], tmp_path)
    assert result.exit_code == 0
    out_low = result.stdout.lower()
    assert "no orgs enrolled" in out_low or "org configurations" not in out_low
