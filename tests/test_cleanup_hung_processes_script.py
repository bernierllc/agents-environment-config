"""The package-manager cache steps in scripts/cleanup-hung-processes.sh must
never block on stdin or run without a timeout.

Regression: `yarn` resolved to node's Corepack shim, which prompts
"Do you want to continue? [Y/n]" on stdin before downloading yarn. With stderr
piped into `tail -1` the prompt was invisible and the script hung forever.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup-hung-processes.sh"


def _helper_prelude() -> str:
    """Everything before the first top-level statement: just the function defs."""
    text = SCRIPT.read_text()
    marker = "\nKILLED_COUNT=0"
    assert marker in text, "script layout changed; update the prelude marker"
    return text.split(marker, 1)[0]


def _fake_tool(tmp_path: Path, name: str, body: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    tool = bindir / name
    tool.write_text("#!/bin/bash\n" + body)
    tool.chmod(0o755)
    return bindir


@pytest.fixture
def fake_yarn(tmp_path: Path) -> Path:
    """A `yarn` that mimics a Corepack shim: refuses when offline, otherwise
    waits on stdin forever (the prompt that caused the hang)."""
    return _fake_tool(
        tmp_path,
        "yarn",
        'if [ "${COREPACK_ENABLE_NETWORK:-1}" = "0" ]; then\n'
        '  echo "Internal Error: Cannot download yarn (network disabled)" >&2; exit 1\n'
        "fi\n"
        'echo "? Do you want to continue? [Y/n] " >&2\n'
        "read -r _answer\n"
        'echo "cleaned"\n',
    )


def _prelude_with_network_allowed() -> str:
    """Drop the offline guard so the fake shim takes the prompt path."""
    prelude = _helper_prelude()
    prefix = "COREPACK_ENABLE_NETWORK=0 "
    assert prefix in prelude, "offline guard moved; update this test"
    return prelude.replace(prefix, "")


def _env(bindir: Path, extra: Optional[dict] = None) -> dict:
    env = {**os.environ, **(extra or {}), "PATH": f"{bindir}:{os.environ['PATH']}"}
    env.pop("COREPACK_ENABLE_NETWORK", None)  # the script sets it; ambient values must not steer the fakes
    return env


def _run_clean_pm_cache(bindir: Path, env_extra: dict, timeout_s: int = 2) -> subprocess.CompletedProcess:
    script = _helper_prelude() + f'\nclean_pm_cache {timeout_s} "Cleaning yarn cache" yarn cache clean\n'
    env = _env(bindir, env_extra)
    return subprocess.run(
        ["bash", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        stdin=None,  # inherit: on a TTY this is exactly the hang scenario
    )


def test_corepack_shim_fails_fast_instead_of_downloading(fake_yarn: Path) -> None:
    start = time.monotonic()
    result = _run_clean_pm_cache(fake_yarn, {})
    assert time.monotonic() - start < 5, "step should return immediately, not wait on a prompt"
    assert "failed or timed out" in result.stdout
    assert "network disabled" in result.stdout


def test_stdin_guard_stops_prompt_from_blocking(fake_yarn: Path) -> None:
    # Hold the parent's stdin open, as a terminal would. Without the </dev/null
    # guard the fake shim's `read` blocks until the 5s alarm fires.
    script = _prelude_with_network_allowed() + '\nclean_pm_cache 5 "Cleaning yarn cache" yarn cache clean\n'
    env = _env(fake_yarn)
    read_end, write_end = os.pipe()  # write_end stays open for the whole run
    start = time.monotonic()
    try:
        result = subprocess.run(
            ["bash", "-c", script], env=env, stdin=read_end, capture_output=True, text=True, timeout=15
        )
    finally:
        os.close(read_end)
        os.close(write_end)
    elapsed = time.monotonic() - start
    assert "cleaned" in result.stdout, result.stdout
    assert elapsed < 3, f"read blocked on inherited stdin for {elapsed:.1f}s"


def test_timeout_kills_children_holding_the_pipe(tmp_path: Path) -> None:
    # A tool that forks a child and then hangs. Killing only the leader leaves
    # the child holding stdout, so `$(...)` would wait the full 30s for EOF.
    bindir = _fake_tool(tmp_path, "yarn", "sleep 30 &\nsleep 30\n")
    script = _helper_prelude() + '\nclean_pm_cache 1 "Cleaning yarn cache" yarn cache clean\n'
    env = _env(bindir)
    start = time.monotonic()
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=20)
    elapsed = time.monotonic() - start
    assert "failed or timed out" in result.stdout, result.stdout
    assert elapsed < 10, f"grandchild kept the step alive for {elapsed:.1f}s"
