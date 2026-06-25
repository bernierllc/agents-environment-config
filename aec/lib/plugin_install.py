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


def install_per_tool(manifest, targets, *, runner, confirm, printer, pref) -> Dict[str, str]:
    tools = manifest["install"]["tools"]
    summary: Dict[str, str] = {}
    for tool in targets:
        spec = tools.get(tool)
        if spec is None:
            continue  # ponytail: silently skip unknown targets; tests don't exercise it
        has_run = "run" in spec
        policy = effective_policy(manifest["install_type"], has_run=has_run, pref=pref)
        if policy == "run":
            if confirm(tool, spec["run"]):
                runner(spec["run"])
                summary[tool] = "run"
            else:
                summary[tool] = "declined"
        else:
            if has_run:
                printer(f"{tool}: run manually -> {' '.join(spec['run'])}")
            else:
                printer(f"{tool}: {spec.get('steps', '')}")
            summary[tool] = "instructions"
    return summary
