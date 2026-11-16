#!/usr/bin/env python3
"""Fail when a repo's vendored copy of an aec guard file differs from aec's canonical bytes.

Downstream repos copy the promotion guard byte-identically (main-via-staging.yml, its scripts, the
detector and its test). Dependabot then edits the copy (for example an actions/checkout bump) and the
copy silently stops matching aec. This compares each vendored file with the same path in the canonical
repo (public, read through `gh api`) so the drift is a failing check, not something to remember.

Usage: python3 scripts/check-vendored-drift.py --canonical-repo OWNER/aec-repo [--ref main] [path ...]
With no paths, the whole default copy set is compared and a member missing locally is drift (a deleted or
renamed guard file must not pass); a repo that vendors only a subset names those paths explicitly.
Exit 0: identical. Exit 1: drift or a missing file (listed on stderr). Exit 2: could not evaluate (fails
closed), including when none of the files exist locally.
"""
import argparse
import subprocess
import sys
from pathlib import Path

COPY_SET = (
    ".github/workflows/main-via-staging.yml",
    "scripts/check-main-source.sh",
    "scripts/check-forged-gate-names.py",
    "tests/test_check_forged_gate_names.py",
)


def gh_fetch(repo, ref, path):
    return subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}", "-H", "Accept: application/vnd.github.raw"],
        capture_output=True, check=True,
    ).stdout


def drifted(root, paths, fetch):
    """Paths whose local bytes differ from the canonical bytes, or are missing; fetch(path) may raise (fail closed)."""
    return [p for p in paths if not (root / p).is_file() or (root / p).read_bytes() != fetch(p)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonical-repo", required=True)
    ap.add_argument("--ref", default="main")
    ap.add_argument("--root", default=".")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    root = Path(args.root)
    paths = args.paths or list(COPY_SET)
    if not any((root / p).is_file() for p in paths):
        print("::error::no vendored guard files found to compare, failing closed", file=sys.stderr)
        return 2
    try:
        bad = drifted(root, paths, lambda p: gh_fetch(args.canonical_repo, args.ref, p))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"::error::could not compare with {args.canonical_repo}@{args.ref}, failing closed: {exc}", file=sys.stderr)
        return 2
    for path in bad:
        print(f"::error::{path} differs from {args.canonical_repo}@{args.ref}; re-vendor it from aec, "
              "or land the change in aec first", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
