"""Install/uninstall plugins from validated loadout manifests."""

from typing import Any, Dict, List

ALL_TOOLS = ("claude", "cursor", "gemini", "qwen", "codex")


def resolve_targets(manifest: Dict[str, Any], detected: Dict[str, Any]) -> List[str]:
    if manifest.get("install_type") == "marketplace":
        supports = ["claude"]
    else:
        supports = manifest.get("supports") or list(detected.keys())
    return [t for t in supports if t in detected]


def effective_policy(install_type: str, *, has_run: bool, pref: str | None) -> str:
    if install_type == "external":
        return "instructions"
    if pref == "instructions-only":
        return "instructions"
    if install_type == "per-tool" and not has_run:
        return "instructions"
    return "run"


def install_marketplace(manifest, *, runner, confirm) -> List[str]:
    blk = manifest["install"]
    cmds = [
        ["claude", "plugin", "marketplace", "add", blk["marketplace"]],
        ["claude", "plugin", "install", blk["plugin"]],
    ]
    if not confirm(cmds):
        return []
    for cmd in cmds:
        runner(cmd)
    return cmds
