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


@pytest.mark.parametrize("same_tree", [False, True])
def test_upgrade_setup_failure_stays_retryable(tmp_path, same_tree):
    import shutil
    from aec.commands.upgrade import _upgrade_scope
    from aec.lib.manifest_v2 import load_manifest, record_install, get_installed
    source = tmp_path / "catalog"
    source.mkdir()
    item = item_at(source / "example")
    (item / "SKILL.md").write_text("---\nname: example\nversion: 1.0.0\ndescription: example\n---\n")
    repo = tmp_path / "project"
    destination = repo / ".claude/skills/example"
    destination.parent.mkdir(parents=True)
    shutil.copytree(item, destination)
    if not same_tree:
        (destination / "SKILL.md").write_text("---\nname: example\nversion: 0.9.0\ndescription: example\n---\n")
    from aec.lib.skills_manifest import hash_skill_directory
    manifest = load_manifest(tmp_path / "manifest.json")
    record_install(manifest, str(repo), "skills", "example", "0.9.0", hash_skill_directory(destination))
    # Identical installed/source trees exercise adoption as well as failed-setup retry.
    with pytest.raises(PromptUnanswered):
        _upgrade_scope(manifest, str(repo), {"skills": source}, yes=False, dry_run=False)
    assert get_installed(manifest, str(repo), "skills")["example"]["version"] == "0.9.0"
    set_answers({"install.directory.reports": "quality/reports", "install.hooks.enable.skill.example": True})
    assert _upgrade_scope(manifest, str(repo), {"skills": source}, yes=False, dry_run=False)
    assert get_installed(manifest, str(repo), "skills")["example"]["version"] == "1.0.0"
    assert (repo / "quality/reports").is_dir()
    assert load_state(repo, "skill", "example").hooks_installed


def test_real_fresh_playwright_pipeline_copies_only_hook_scripts(tmp_path):
    import shutil
    from aec.commands.install_cmd import _post_install_playwright_pipeline
    from aec.lib.scope import Scope
    repo = tmp_path / "project"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    scope = Scope(is_global=False, repo_path=repo)
    source = Path(__file__).resolve().parents[1] / ".claude/skills/playwright-test-generator"
    shutil.copytree(source, scope.skills_dir / source.name,
                    ignore=shutil.ignore_patterns("node_modules", ".git"))
    _post_install_playwright_pipeline(source.name, scope, yes=True)
    assert (repo / "docs/verification").is_dir()
    assert (repo / "scripts/verification-playwright/hooks/pre-commit.sh").is_file()
    assert not (repo / "scripts/verification-playwright/hooks/__tests__").exists()


@pytest.mark.parametrize("enabled", [False, True])
def test_declarative_apply_honors_hook_opt_out(tmp_path, enabled):
    from aec.lib.apply_core import DesiredItem, plan_apply, execute_apply
    from aec.lib.manifest_v2 import load_manifest
    source = tmp_path / "catalog"
    source.mkdir()
    item_at(source / "example")
    repo = tmp_path / "project"
    manifest_path = tmp_path / "manifest.json"
    available = {"skills": {"example": {"version": "1.0.0", "path": "example"}}}
    plan = plan_apply([DesiredItem("skill", "example", str(repo))],
                      manifest=load_manifest(manifest_path), available_by_type=available)
    result = execute_apply(plan, source_dirs={"skills": source}, available_by_type=available,
                           manifest_path=manifest_path, install_hooks=enabled)
    assert not result.errors and len(result.applied) == 1
    assert bool(load_state(repo, "skill", "example").hooks_installed) is enabled


def test_declarative_apply_reports_failure_and_continues(tmp_path):
    from aec.lib.apply_core import DesiredItem, plan_apply, execute_apply
    from aec.lib.manifest_v2 import load_manifest, get_installed
    source = tmp_path / "catalog"
    source.mkdir()
    broken = item_at(source / "broken")
    (broken / "hooks.json").write_text('{"version":"1.0.0","hooks":[{}]}')
    item_at(source / "healthy")
    repo = tmp_path / "project"
    manifest_path = tmp_path / "manifest.json"
    available = {"skills": {name: {"version": "1.0.0", "path": name} for name in ("broken", "healthy")}}
    plan = plan_apply([DesiredItem("skill", name, str(repo)) for name in ("broken", "healthy")],
                      manifest=load_manifest(manifest_path), available_by_type=available)
    result = execute_apply(plan, source_dirs={"skills": source}, available_by_type=available,
                           manifest_path=manifest_path)
    assert len(result.errors) == 1 and result.errors[0][0].item.name == "broken"
    assert [entry.item.name for entry in result.applied] == ["healthy"]
    assert "broken" not in get_installed(load_manifest(manifest_path), str(repo), "skills")


def test_custom_directory_browser_and_api_readers(tmp_path):
    import sys
    skills = Path(__file__).resolve().parents[1] / ".claude/skills"
    custom = tmp_path / "quality docs/checks"
    (custom / "pages").mkdir(parents=True)
    (custom / "pages/home.md").write_text("# Home")
    (tmp_path / ".aec").mkdir()
    (tmp_path / ".aec/directories.json").write_text(json.dumps({"verification": "quality docs/checks"}))
    for reader in ("browser-verification", "playwright-test-runner"):
        subprocess.run(["bash", str(skills / reader / "scripts/preflight.sh"), "--root", str(tmp_path)], check=True)
    (custom / "access-manifest.json").write_text(json.dumps({"entries": [{"surface": "rest", "id": "GET /health", "visibility": "public"}]}))
    (custom / "principals.json").write_text(json.dumps({"principals": {"anonymous": {}}}))
    result = subprocess.run([sys.executable, str(skills / "api-verification/scripts/matrix.py"), "plan"], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)[0]["id"] == "GET /health"


@pytest.mark.parametrize("existing_dependency", [False, True])
@pytest.mark.parametrize("broken_hooks", [False, True])
def test_parent_upgrade_configures_dependency_before_recording(tmp_path, existing_dependency, broken_hooks):
    import shutil
    from aec.commands.upgrade import _upgrade_scope
    from aec.lib.manifest_v2 import load_manifest, record_install, get_installed
    from aec.lib.skills_manifest import hash_skill_directory

    source = tmp_path / "catalog"
    source.mkdir()
    dependency = item_at(source / "example")
    (dependency / "SKILL.md").write_text("---\nname: example\nversion: 1.0.0\ndescription: example\n---\n")
    valid_hooks = (dependency / "hooks.json").read_text()
    parent = source / "parent"
    parent.mkdir()
    (parent / "SKILL.md").write_text(
        '---\nname: parent\nversion: 2.0.0\ndescription: parent\n'
        'dependencies:\n  skills:\n    - name: example\n      min_version: "1.0.0"\n      reason: "Reports"\n---\n')
    repo = tmp_path / "project"
    installed = repo / ".claude/skills"
    old_parent = installed / "parent"
    old_parent.mkdir(parents=True)
    (old_parent / "SKILL.md").write_text("---\nname: parent\nversion: 1.0.0\ndescription: parent\n---\n")
    manifest = load_manifest(tmp_path / "manifest.json")
    record_install(manifest, str(repo), "skills", "parent", "1.0.0", hash_skill_directory(old_parent))
    if existing_dependency:
        old_dep = installed / "example"
        shutil.copytree(dependency, old_dep)
        (old_dep / "SKILL.md").write_text("---\nname: example\nversion: 0.9.0\ndescription: example\n---\n")
        (old_dep / "hooks.json").write_text(json.dumps({"version": "0.9.0", "hooks": [
            {"id": "report", "event": "on_file_edit", "command": "echo old-hook", "description": "old"}]}))
        install(repo, old_dep, assume_yes=True)
        record_install(manifest, str(repo), "skills", "example", "0.9.0", hash_skill_directory(old_dep))
    if broken_hooks:
        (dependency / "hooks.json").write_text('{"version":"1.0.0","hooks":[{}]}')
        with pytest.raises(ValueError):
            _upgrade_scope(manifest, str(repo), {"skills": source}, yes=True, dry_run=False)
        recorded = get_installed(manifest, str(repo), "skills")
        assert recorded["parent"]["version"] == "1.0.0"
        assert recorded.get("example", {}).get("version") == ("0.9.0" if existing_dependency else None)
        (dependency / "hooks.json").write_text(valid_hooks)
    assert _upgrade_scope(manifest, str(repo), {"skills": source}, yes=True, dry_run=False)
    assert get_installed(manifest, str(repo), "skills")["example"]["version"] == "1.0.0"
    state = load_state(repo, "skill", "example")
    assert state.item_version == "1.0.0" and state.hooks_installed
    assert (repo / "docs/reports").is_dir()
    settings = (repo / ".claude/settings.json").read_text()
    assert "old-hook" not in settings
    command = json.loads(settings)["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
    subprocess.run(["sh", "-c", command], cwd=repo, check=True)
