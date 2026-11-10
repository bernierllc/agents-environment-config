"""Exercise shared setup and installed hook commands against real repositories."""
import json
from pathlib import Path
import subprocess

import pytest

from aec.lib.hooks.lifecycle import install_hooks_for_item
from aec.lib.hooks.state import load_state
from aec.lib.hooks.setup import configure_directories, validate_directory
from aec.lib.prompts import set_answers, clear_answers, set_mode, reset_mode, PromptUnanswered


@pytest.fixture(autouse=True)
def answers():
    clear_answers()
    set_mode(non_interactive=True, use_defaults=False)
    yield
    clear_answers()
    reset_mode()


def install(repo, item, name="example", **kwargs):
    return install_hooks_for_item(
        item_type="skill", item_key=name, item_version=json.loads((item / "hooks.json").read_text())["version"],
        item_dir=item, repo_root=repo, agents=["claude"], **kwargs,
    )


def item_at(root):
    root.mkdir()
    (root / "hooks.json").write_text(json.dumps({
        "version": "1.0.0", "directories": {"reports": "docs/reports"},
        "hooks": [{"id": "report", "event": "on_file_edit", "command": "test -d {directory:reports}",
                   "description": "Check reports", "when": {"repo_has": ["docs/reports"]}}],
    }))
    return root


def test_fresh_install_creates_directory_and_working_hook(tmp_path):
    item = item_at(tmp_path / "item")
    install(tmp_path, item, assume_yes=True)
    assert (tmp_path / "docs/reports").is_dir()
    state = load_state(tmp_path, "skill", "example")
    assert state.hooks_enabled is True and state.hooks_installed and not state.hooks_skipped
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    command = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True)


def test_explicit_answers_override_yes_and_survive_reinstall(tmp_path):
    item = item_at(tmp_path / "item")
    set_answers({"install.directory.reports": "quality reports", "install.hooks.enable.skill.example": False})
    install(tmp_path, item, assume_yes=True)
    clear_answers()
    install(tmp_path, item)
    assert (tmp_path / "quality reports").is_dir()
    assert not (tmp_path / "docs/reports").exists()
    state = load_state(tmp_path, "skill", "example")
    assert state.hooks_enabled is False and not state.hooks_installed
    set_answers({"install.hooks.enable.skill.example": True})
    install(tmp_path, item)
    state = load_state(tmp_path, "skill", "example")
    assert state.hooks_installed


def test_missing_answer_fails_loudly(tmp_path):
    with pytest.raises(PromptUnanswered, match="install.directory.reports"):
        install(tmp_path, item_at(tmp_path / "item"))
    assert not (tmp_path / "docs/reports").exists()


@pytest.mark.parametrize("path", ["../outside", "/outside", ".", "x/../../outside", "a\\b", "x\ny"])
def test_unsafe_directory_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        validate_directory(path, tmp_path)


def test_files_and_symlink_escape_rejected(tmp_path):
    (tmp_path / "file").write_text("keep")
    (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    for path in ["file", "escape/outside"]:
        with pytest.raises(ValueError):
            validate_directory(path, tmp_path)


def test_shared_directory_selection_is_reused(tmp_path):
    set_answers({"install.directory.reports": "quality/reports"})
    configure_directories({"reports": "docs/reports"}, tmp_path)
    clear_answers()
    assert configure_directories({"reports": "docs/reports"}, tmp_path) == {"reports": "quality/reports"}


def test_real_verification_writer_uses_custom_directory(tmp_path):
    source = Path(__file__).resolve().parents[1] / ".claude/skills/verification-writer"
    selected = "quality docs/checks"
    set_answers({"install.directory.verification": selected, "install.hooks.enable.skill.verification-writer": True})
    install(tmp_path, source, "verification-writer")
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    command = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    subprocess.run(["sh", "-c", command], cwd=tmp_path, check=True)
    assert (tmp_path / selected / ".scan-cache.json").is_file()
    assert f"{selected}/.scan-cache.json" in (tmp_path / ".gitignore").read_text()
    assert not (tmp_path / "docs/verification").exists()


def test_real_playwright_custom_precommit_path_is_rendered(tmp_path):
    source = Path(__file__).resolve().parents[1] / ".claude/skills/playwright-test-generator"
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    set_answers({"install.directory.verification": "quality docs/checks", "install.hooks.enable.skill.playwright-test-generator": True})
    install_hooks_for_item(item_type="skill", item_key="playwright-test-generator",
        item_version=json.loads((source / "hooks.json").read_text())["version"],
        item_dir=source, repo_root=tmp_path, agents=["git"])
    hook = tmp_path / ".git/hooks/pre-commit"
    text = hook.read_text()
    assert "{directory:" not in text and "quality docs/checks" in text
    subprocess.run(["sh", str(hook)], cwd=tmp_path, check=True)


def test_custom_directory_has_no_drift_and_repair_preserves_choice(tmp_path):
    from aec.lib.hooks.drift import verify_repo, repair_repo, Drift
    item = tmp_path / ".claude/skills/example"
    item.parent.mkdir(parents=True)
    item_at(item)
    set_answers({"install.directory.reports": "quality/reports", "install.hooks.enable.skill.example": True})
    install(tmp_path, item)
    clear_answers()
    assert all(status.status is Drift.OK for status in verify_repo(tmp_path))
    (tmp_path / ".claude/settings.json").write_text("{}")
    assert repair_repo(tmp_path)[0].repaired
    assert all(status.status is Drift.OK for status in verify_repo(tmp_path))


def test_disabled_hooks_are_not_reported_as_missing(tmp_path):
    from aec.lib.hooks.drift import verify_repo
    item = tmp_path / ".claude/skills/example"
    item.parent.mkdir(parents=True)
    item_at(item)
    set_answers({"install.directory.reports": "docs/reports", "install.hooks.enable.skill.example": False})
    install(tmp_path, item)
    assert verify_repo(tmp_path) == []


def test_undeclared_directory_token_fails_before_install(tmp_path):
    item = item_at(tmp_path / "item")
    hooks = json.loads((item / "hooks.json").read_text())
    hooks["hooks"][0]["command"] = "test -d {directory:typo}"
    (item / "hooks.json").write_text(json.dumps(hooks))
    with pytest.raises(ValueError, match="undeclared directory: typo"):
        install(tmp_path, item, assume_yes=True)
    assert not (tmp_path / "docs/reports").exists()
