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


def test_org_enroll_url_not_supported_in_phase_1(tmp_path: Path):
    result = _run(["org", "enroll", "https://example.com/config.yaml", "--allow-unsigned", "--yes"], tmp_path)
    assert result.exit_code != 0
    assert "phase 2" in result.stdout.lower() or "phase 2" in result.stderr.lower()


def test_doctor_shows_org_section_when_org_enrolled(tmp_path: Path):
    cfg = FIXTURES / "valid-minimal.yaml"
    _run(["org", "enroll", str(cfg), "--allow-unsigned", "--yes"], tmp_path)
    result = _run(["doctor"], tmp_path)
    assert result.exit_code == 0
    assert "org configuration" in result.stdout.lower()
    assert "minimal" in result.stdout
    assert "unsigned" in result.stdout.lower()


def test_doctor_omits_org_section_when_no_orgs(tmp_path: Path):
    result = _run(["doctor"], tmp_path)
    assert result.exit_code == 0
    out_low = result.stdout.lower()
    assert "no orgs enrolled" in out_low or "org configurations" not in out_low
