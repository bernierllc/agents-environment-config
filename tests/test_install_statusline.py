"""Tests for the Claude Code statusline step of `aec install`."""

import json
import os
import shlex
from pathlib import Path

import pytest

from aec.commands.install import _prompt_claude_statusline
from aec.lib.preferences import get_setting

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def claude_env(temp_dir, monkeypatch):
    """A fake ~/.claude plus isolated AEC preferences; Claude detected."""
    claude_dir = temp_dir / ".claude"
    claude_dir.mkdir()
    monkeypatch.setattr("aec.lib.CLAUDE_DIR", claude_dir)
    monkeypatch.setattr("aec.lib.IS_WINDOWS", False)
    monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
    monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
    monkeypatch.setattr("aec.commands.agent_tools._is_claude_installed", lambda: True)
    return claude_dir


def _answer(monkeypatch, reply):
    monkeypatch.setattr("aec.lib.prompts._stdin_is_tty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _: reply)


def _no_prompt(monkeypatch):
    def fail(_):
        raise AssertionError("should not prompt")
    monkeypatch.setattr("builtins.input", fail)


def test_yes_links_script_and_merges_settings(claude_env, monkeypatch):
    (claude_env / "settings.json").write_text(json.dumps({"model": "opus"}))
    _answer(monkeypatch, "y")

    _prompt_claude_statusline(REPO_ROOT)

    link = claude_env / "statusline.sh"
    assert link.is_symlink()
    assert link.resolve() == (REPO_ROOT / ".claude" / "statusline.sh").resolve()
    settings = json.loads((claude_env / "settings.json").read_text())
    assert settings["model"] == "opus"  # other keys preserved
    assert settings["statusLine"] == {"type": "command", "command": shlex.quote(str(link)), "padding": 0}
    assert get_setting("claude_statusline") is True


def test_no_records_decline_and_is_not_asked_again(claude_env, monkeypatch):
    _answer(monkeypatch, "n")
    _prompt_claude_statusline(REPO_ROOT)

    assert not (claude_env / "statusline.sh").exists()
    assert not (claude_env / "settings.json").exists()
    assert get_setting("claude_statusline") is False

    _no_prompt(monkeypatch)
    _prompt_claude_statusline(REPO_ROOT)


def test_reset_re_offers_after_decline(claude_env, monkeypatch):
    from aec.lib.preferences import reset_preference, set_setting

    set_setting("claude_statusline", False)
    reset_preference("claude_statusline")
    assert get_setting("claude_statusline") is None


def test_skips_when_claude_not_installed(claude_env, monkeypatch):
    monkeypatch.setattr("aec.commands.agent_tools._is_claude_installed", lambda: False)
    _no_prompt(monkeypatch)
    _prompt_claude_statusline(REPO_ROOT)
    assert get_setting("claude_statusline") is None


def test_existing_statusline_is_never_overwritten(claude_env, monkeypatch):
    mine = {"statusLine": {"type": "command", "command": "~/mine.sh"}}
    (claude_env / "settings.json").write_text(json.dumps(mine))
    _no_prompt(monkeypatch)

    _prompt_claude_statusline(REPO_ROOT)

    assert json.loads((claude_env / "settings.json").read_text()) == mine


def test_foreign_statusline_script_is_left_alone(claude_env, monkeypatch):
    (claude_env / "statusline.sh").write_text("#!/bin/sh\necho mine\n")
    _answer(monkeypatch, "y")

    _prompt_claude_statusline(REPO_ROOT)

    assert (claude_env / "statusline.sh").read_text() == "#!/bin/sh\necho mine\n"
    assert not (claude_env / "settings.json").exists()


def test_stale_aec_symlink_is_repointed(claude_env, monkeypatch, temp_dir):
    link = claude_env / "statusline.sh"
    link.symlink_to(temp_dir / "old" / "agents-environment-config" / ".claude" / "statusline.sh")
    _answer(monkeypatch, "y")

    _prompt_claude_statusline(REPO_ROOT)

    assert link.resolve() == (REPO_ROOT / ".claude" / "statusline.sh").resolve()
    assert get_setting("claude_statusline") is True


def test_stale_aec_symlink_is_repointed_when_already_configured(claude_env, monkeypatch, temp_dir):
    link = claude_env / "statusline.sh"
    link.symlink_to(temp_dir / "old" / "agents-environment-config" / ".claude" / "statusline.sh")
    (claude_env / "settings.json").write_text(json.dumps(
        {"statusLine": {"type": "command", "command": shlex.quote(str(link))}}))
    _no_prompt(monkeypatch)

    _prompt_claude_statusline(REPO_ROOT)

    assert link.resolve() == (REPO_ROOT / ".claude" / "statusline.sh").resolve()


def test_unreadable_settings_json_is_not_clobbered(claude_env, monkeypatch):
    (claude_env / "settings.json").write_text("{not json")
    _no_prompt(monkeypatch)

    _prompt_claude_statusline(REPO_ROOT)

    assert (claude_env / "settings.json").read_text() == "{not json"


@pytest.mark.parametrize("content", ["[]", "3", '"x"'])
def test_non_object_settings_json_is_not_touched(claude_env, monkeypatch, content):
    (claude_env / "settings.json").write_text(content)
    _no_prompt(monkeypatch)

    _prompt_claude_statusline(REPO_ROOT)

    assert (claude_env / "settings.json").read_text() == content
    assert not (claude_env / "statusline.sh").exists()


def test_symlinked_settings_json_stays_a_symlink(claude_env, monkeypatch, temp_dir):
    real = temp_dir / "dotfiles-settings.json"
    real.write_text("{}")
    (claude_env / "settings.json").symlink_to(real)
    _answer(monkeypatch, "y")

    _prompt_claude_statusline(REPO_ROOT)

    assert (claude_env / "settings.json").is_symlink()
    assert "statusLine" in json.loads(real.read_text())


def test_installed_script_is_executable():
    import os
    assert os.access(REPO_ROOT / ".claude" / "statusline.sh", os.X_OK)


def test_dry_run_changes_nothing(claude_env, monkeypatch):
    _answer(monkeypatch, "y")
    _prompt_claude_statusline(REPO_ROOT, dry_run=True)

    assert not (claude_env / "statusline.sh").exists()
    assert not (claude_env / "settings.json").exists()
    assert get_setting("claude_statusline") is None


def test_settings_write_failure_changes_nothing(claude_env, monkeypatch):
    (claude_env / "settings.json").write_text("{}")
    _answer(monkeypatch, "y")

    def boom(*_):
        raise PermissionError("read-only")
    monkeypatch.setattr("aec.lib.atomic_write.atomic_write_json", boom)

    _prompt_claude_statusline(REPO_ROOT)  # must not raise

    assert not (claude_env / "statusline.sh").is_symlink()
    assert get_setting("claude_statusline") is None


def test_link_failure_rolls_back_settings(claude_env, monkeypatch):
    (claude_env / "settings.json").write_text('{"model": "opus"}')
    _answer(monkeypatch, "y")
    monkeypatch.setattr("aec.lib.create_symlink", lambda *_: False)

    _prompt_claude_statusline(REPO_ROOT)

    assert json.loads((claude_env / "settings.json").read_text()) == {"model": "opus"}
    assert get_setting("claude_statusline") is None
