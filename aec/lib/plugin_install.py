"""Install/uninstall plugins from validated loadout manifests."""

from typing import Any, Dict, List

ALL_TOOLS = ("claude", "cursor", "gemini", "qwen", "codex")


def resolve_targets(manifest: Dict[str, Any], detected: Dict[str, Any]) -> List[str]:
    if manifest.get("install_type") == "marketplace":
        supports = ["claude"]
    else:
        supports = manifest.get("supports") or list(detected.keys())
    return [t for t in supports if t in detected]
