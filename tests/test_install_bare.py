"""Bare `aec install` runs full setup; `aec install <type>` without a name errors."""

from unittest.mock import patch

from typer.testing import CliRunner

from aec.cli import app

runner = CliRunner()


def _invoke(args):
    with patch("aec.lib.preferences.check_pending_preferences"):
        return runner.invoke(app, args)


def test_bare_install_runs_full_setup():
    with patch("aec.commands.install.install") as full_install:
        result = _invoke(["install"])
    assert result.exit_code == 0, result.output
    full_install.assert_called_once_with(dry_run=False)


def test_bare_install_passes_dry_run():
    with patch("aec.commands.install.install") as full_install:
        result = _invoke(["install", "--dry-run"])
    assert result.exit_code == 0, result.output
    full_install.assert_called_once_with(dry_run=True)


def test_type_without_name_errors():
    with patch("aec.commands.install.install") as full_install, \
         patch("aec.commands.install_cmd.run_install") as item_install:
        result = _invoke(["install", "skill"])
    assert result.exit_code == 2
    full_install.assert_not_called()
    item_install.assert_not_called()
