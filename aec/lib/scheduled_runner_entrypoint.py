#!/usr/bin/env python3
"""Generic OS-scheduled entrypoint for AEC tests.

Reads tracked projects and scheduler settings via ``aec.lib.runner`` (same
code path as ``aec test run -g``). This file is copied to the per-user config
directory as ``runner.py``; keep logic in ``aec.lib.runner``, not here.
"""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from aec.lib.runner import run_all_projects
    except ImportError as exc:
        print(
            "error: cannot import aec; use the Python environment where "
            "aec is installed.",
            file=sys.stderr,
        )
        print(exc, file=sys.stderr)
        return 1
    result = run_all_projects()
    if result.get("failed", 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
