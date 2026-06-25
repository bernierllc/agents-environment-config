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


def _marketplace_cmds(manifest) -> List[List[str]]:
    blk = manifest["install"]
    return [
        ["claude", "plugin", "marketplace", "add", blk["marketplace"]],
        ["claude", "plugin", "install", blk["plugin"]],
    ]


def install_marketplace(manifest, *, runner, confirm) -> List[str]:
    cmds = _marketplace_cmds(manifest)
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


def install_external(manifest, *, runner, printer) -> None:
    # ponytail: external is instructions-only; runner accepted for a uniform
    # signature but deliberately never called. Nothing here executes.
    blk = manifest["install"]["external"]
    printer(f"download: {blk['download']}")
    printer(blk["instructions"])


def _note_skipped(manifest, detected, *, printer) -> None:
    if manifest.get("install_type") == "marketplace":
        supported = ["claude"]
    else:
        supported = manifest.get("supports") or list(detected.keys())
    for tool in supported:
        if tool not in detected:
            printer(f"{tool}: supported but not detected, skipped")


def install_plugin(manifest, detected, *, runner, confirm, printer, pref) -> Dict[str, Any]:
    install_type = manifest["install_type"]
    targets = resolve_targets(manifest, detected)
    _note_skipped(manifest, detected, printer=printer)

    if install_type == "marketplace":
        # ponytail: install_marketplace doesn't check detection; guard here so a
        # claude-less environment skips cleanly instead of running claude commands.
        if "claude" not in detected:
            executed = False
        elif effective_policy("marketplace", has_run=True, pref=pref) == "instructions":
            # never-auto-install: print-only, mirroring per-tool/external downgrade.
            for cmd in _marketplace_cmds(manifest):
                printer(f"run manually -> {' '.join(cmd)}")
            executed = False
        else:
            executed = bool(install_marketplace(manifest, runner=runner, confirm=confirm))
    elif install_type == "per-tool":
        summary = install_per_tool(manifest, targets, runner=runner, confirm=confirm,
                                   printer=printer, pref=pref)
        executed = any(v == "run" for v in summary.values())
    else:  # external
        install_external(manifest, runner=runner, printer=printer)
        executed = False

    if manifest.get("usage"):
        printer(manifest["usage"])
    return {"install_type": install_type, "targets": targets, "executed": executed}


def uninstall_plugin(manifest, detected, *, runner, confirm, printer, pref) -> Dict[str, Any]:
    install_type = manifest["install_type"]
    targets = resolve_targets(manifest, detected)
    block = manifest.get("uninstall")
    executed = False

    if not block:
        printer("manual cleanup may be required")
    elif "tools" in block:
        shim = {**manifest, "install": block}
        summary = install_per_tool(shim, targets, runner=runner, confirm=confirm,
                                   printer=printer, pref=pref)
        executed = any(v == "run" for v in summary.values())
    elif "external" in block:
        ext = block["external"]
        if "download" in ext:
            printer(f"download: {ext['download']}")
        printer(ext.get("instructions", ""))
    else:
        # ponytail: no documented marketplace-uninstall command exists; punt to
        # manual rather than fabricate a claude command. Add a handler if one ships.
        printer("manual cleanup may be required")

    return {"install_type": install_type, "targets": targets, "executed": executed}
