"""aec export -- write the current setup to a portable manifest file."""

from pathlib import Path
from typing import Optional

from ..lib import Console
from ..lib.atomic_write import atomic_write_text
from ..lib.manifest_v2 import load_manifest
from ..lib.portable_manifest import build_portable_manifest, dump_manifest


def _manifest_path() -> Path:
    """Compute manifest path dynamically so tests can monkeypatch Path.home()."""
    return Path.home() / ".agents-environment-config" / "installed-manifest.json"


def run_export(out: Optional[str] = None, latest: bool = False, include_repos: bool = True) -> None:
    """Export installed state to a portable manifest (stdout unless ``out`` given)."""
    manifest = load_manifest(_manifest_path())
    portable = build_portable_manifest(manifest, latest=latest, include_repos=include_repos)
    text = dump_manifest(portable)
    if out:
        atomic_write_text(Path(out), text)
        Console.success(f"Exported setup to {out}")
    else:
        print(text, end="")
