"""Clone and update custom org-config sources (Phase 4c).

When an org overlay declares ``sources.custom[]`` entries, ``aec`` clones each
into ``~/.aec/org-sources/<id>`` so items from those sources can be installed.
A failure to sync one source (e.g. permission denied) is captured and reported
but does not halt the overall enroll/apply — items referencing that source are
skipped while everything else proceeds.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .schema import CustomSource


@dataclass(frozen=True)
class SyncResult:
    source_id: str
    success: bool
    path: Optional[Path]
    error: Optional[str]


Cloner = Callable[[str, Path, str], None]


def _default_clone(url: str, dest: Path, ref: str) -> None:
    """Clone (or update) ``url`` at ``ref`` into ``dest`` using local ``git``.

    Captures stderr so failures surface in SyncResult.error rather than as
    raw subprocess noise.
    """
    if dest.exists():
        subprocess.run(
            ["git", "fetch", "origin", ref],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "checkout", "FETCH_HEAD"],
            cwd=dest,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    subprocess.run(
        ["git", "checkout", ref],
        cwd=dest,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def sync_source(
    source: CustomSource,
    *,
    sources_dir: Path,
    cloner: Optional[Cloner] = None,
) -> SyncResult:
    """Clone or update one custom source. Errors are captured, never raised."""
    dest = sources_dir / source.id
    impl = cloner or _default_clone
    try:
        impl(source.url, dest, source.ref)
    except subprocess.CalledProcessError as e:
        return SyncResult(source.id, False, None, (e.stderr or str(e)).strip())
    except Exception as e:  # noqa: BLE001 - convert any failure to a SyncResult
        return SyncResult(source.id, False, None, str(e))
    return SyncResult(source.id, True, dest, None)


def sync_sources(
    sources: list[CustomSource],
    *,
    sources_dir: Path,
    cloner: Optional[Cloner] = None,
) -> dict[str, SyncResult]:
    return {s.id: sync_source(s, sources_dir=sources_dir, cloner=cloner) for s in sources}


def failed_source_ids(results: dict[str, SyncResult]) -> set:
    return {sid for sid, r in results.items() if not r.success}
