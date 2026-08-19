"""aec untrack <path> — stop tracking a repo."""

from pathlib import Path

from ..lib import Console
from ..lib.manifest_v2 import load_manifest, save_manifest
from ..lib.prompt_catalog.install_flow_area import item_prompt_id
from ..lib.prompt_catalog.lifecycle_area import UNTRACK_CONFIRM_PREFIX
from ..lib.prompts import prompt
from ..lib.tracking import is_logged, untrack_repo


def _manifest_path() -> Path:
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_untrack(path: str, yes: bool = False) -> None:
    project = Path(path).resolve()
    if not is_logged(project):
        Console.warning(f"Not tracked: {project}")
        return
    if not yes:
        Console.print(f"This will stop tracking {project}.")
        resp = prompt(
            item_prompt_id(UNTRACK_CONFIRM_PREFIX, str(project)),
            "Continue? [y/N]: ",
            type="yes_no",
            default=False,
        ).strip().lower()
        if resp != "y":
            Console.info("Skipped.")
            return

    untrack_repo(project)

    mp = _manifest_path()
    manifest = load_manifest(mp)
    repo_key = str(project)
    if repo_key in manifest.get("repos", {}):
        del manifest["repos"][repo_key]
        save_manifest(manifest, mp)

    Console.success(f"Untracked: {project}")
