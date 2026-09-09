"""The verification-playwright PostToolUse hook must actually fire.

Regression: the original command branched on $CLAUDE_FILE_PATH, an env var
Claude Code never sets, so the condition was always false and sync-tests.js
never ran. Claude Code delivers hook input as JSON on stdin instead.
"""

import json
import os
import subprocess

from aec.lib.hooks import (
    VERIFICATION_PLAYWRIGHT_MARKER,
    get_verification_playwright_hook,
)


def _command() -> str:
    return get_verification_playwright_hook()["hooks"]["PostToolUse"][0]["hooks"][0][
        "command"
    ]


def _run(tmp_path, file_path):
    """Run the hook command with a stub `node` on PATH; return its stdout."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    node = bin_dir / "node"
    node.write_text('#!/bin/sh\necho "SYNCED $1 $2"\n')
    node.chmod(0o755)

    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    return subprocess.run(
        ["bash", "-c", _command()],
        input=payload, capture_output=True, text=True, env=env,
    ).stdout


def test_fires_on_verification_doc(tmp_path):
    out = _run(tmp_path, "/repo/docs/verification/login.md")
    assert VERIFICATION_PLAYWRIGHT_MARKER in out
    assert "/repo/docs/verification/login.md" in out


def test_silent_on_unrelated_file(tmp_path):
    assert _run(tmp_path, "/repo/src/app.ts").strip() == ""


def test_silent_when_stdin_is_not_hook_json(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    proc = subprocess.run(
        ["bash", "-c", _command()],
        input="not json", capture_output=True, text=True, env=env,
    )
    assert proc.stdout.strip() == ""
