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

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup-hung-processes.sh"


def _helper_prelude() -> str:
    """Everything before the first top-level statement: just the function defs."""
    text = SCRIPT.read_text()
    marker = "\nKILLED_COUNT=0"
    assert marker in text, "script layout changed; update the prelude marker"
    return text.split(marker, 1)[0]


@pytest.fixture
def fake_yarn(tmp_path: Path) -> Path:
    """A `yarn` that mimics a Corepack shim: refuses when offline, otherwise
    waits on stdin forever (the prompt that caused the hang)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    yarn = bindir / "yarn"
    yarn.write_text(
        "#!/bin/bash\n"
        'if [ "${COREPACK_ENABLE_NETWORK:-1}" = "0" ]; then\n'
        '  echo "Internal Error: Cannot download yarn (network disabled)" >&2; exit 1\n'
        "fi\n"
        'echo "? Do you want to continue? [Y/n] " >&2\n'
        "read -r _answer\n"
        'echo "cleaned"\n'
    )
    yarn.chmod(0o755)
    return bindir


def _run_clean_pm_cache(bindir: Path, env_extra: dict, timeout_s: int = 2) -> subprocess.CompletedProcess:
    script = _helper_prelude() + f'\nclean_pm_cache {timeout_s} "Cleaning yarn cache" yarn cache clean\n'
    env = {**os.environ, **env_extra, "PATH": f"{bindir}:{os.environ['PATH']}"}
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
    assert time.monotonic() - start < 2, "step should return immediately, not wait on a prompt"
    assert "failed or timed out" in result.stdout
    assert "network disabled" in result.stdout


def test_blocking_prompt_is_cut_by_timeout(fake_yarn: Path) -> None:
    # Force the fake shim down the prompt path to prove the timeout + /dev/null
    # stdin guard holds even if network were allowed.
    prelude = _helper_prelude().replace("COREPACK_ENABLE_NETWORK=0 ", "")
    script = prelude + '\nclean_pm_cache 2 "Cleaning yarn cache" yarn cache clean\n'
    env = {**os.environ, "PATH": f"{fake_yarn}:{os.environ['PATH']}"}
    start = time.monotonic()
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=15)
    elapsed = time.monotonic() - start
    # stdin is /dev/null so `read` returns at once and the fake "cleans";
    # either way the step returns well inside the 2s alarm.
    assert elapsed < 3, f"step took {elapsed:.1f}s"
    assert "cleaned" in result.stdout or "failed or timed out" in result.stdout
