"""Copy the generic scheduled-test runner into the user's AEC_HOME."""

from __future__ import annotations

import shutil
from pathlib import Path


def scheduled_runner_source_path() -> Path:
    """Committed entrypoint beside this module (same file on every OS)."""
    return Path(__file__).resolve().parent / "scheduled_runner_entrypoint.py"


def _needs_install(dest: Path, source: Path) -> bool:
    if not source.is_file():
        raise FileNotFoundError(f"Missing packaged runner: {source}")
    if not dest.is_file():
        return True
    try:
        return dest.read_bytes() != source.read_bytes()
    except OSError:
        return True


def ensure_runner_script(dest: Path | None = None) -> Path:
    """Copy ``scheduled_runner_entrypoint.py`` to ``runner.py`` under AEC_HOME if needed.

    The installed file is static Python source (not synthesized). It only
    delegates to ``run_all_projects()``, which loads ``scheduler-config.json``,
    ``tracked-repos.json``, and each project's ``.aec.json``.

    Paths use :class:`pathlib.Path` and ``AEC_HOME`` / ``AEC_RUNNER_SCRIPT`` from
    ``aec.lib.config`` (``Path.home()``-based, OS-correct).

    Args:
        dest: Override destination path (tests).

    Returns:
        Resolved path to the installed ``runner.py``.
    """
    from aec.lib.config import AEC_RUNNER_SCRIPT

    source = scheduled_runner_source_path()
    path = AEC_RUNNER_SCRIPT if dest is None else dest
    path.parent.mkdir(parents=True, exist_ok=True)
    if _needs_install(path, source):
        shutil.copyfile(source, path)
        try:
            path.chmod(0o755)
        except OSError:
            pass
    return path.resolve()
