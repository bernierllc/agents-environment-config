"""The package-manager cache steps in scripts/cleanup-hung-processes.sh must
never block on stdin or run without a timeout.

Regression: `yarn` resolved to node's Corepack shim, which prompts
"Do you want to continue? [Y/n]" on stdin before downloading yarn. With stderr
piped into `tail -1` the prompt was invisible and the script hung forever.
"""

from __future__ import annotations

import os
import signal
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


def _env(bindir: Path, extra: dict | None = None) -> dict:
    env = {**os.environ, **(extra or {}), "PATH": f"{bindir}:{os.environ['PATH']}"}
    env.pop("COREPACK_ENABLE_NETWORK", None)  # the script sets it; ambient values must not steer the fakes
    return env


def _run_clean_pm_cache(bindir: Path, env_extra: dict, timeout_s: int = 2) -> subprocess.CompletedProcess:
    script = _helper_prelude() + f'\nclean_pm_cache {timeout_s} "Cleaning yarn cache" yarn cache clean\n'
    env = _env(bindir, env_extra)
    return subprocess.run(
        ["bash", "-c", script],
        env=env,
        check=False, capture_output=True,
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
            ["bash", "-c", script], env=env, stdin=read_end, check=False, capture_output=True, text=True, timeout=15
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
    result = subprocess.run(["bash", "-c", script], env=env, check=False, capture_output=True, text=True, timeout=20)
    elapsed = time.monotonic() - start
    assert "failed or timed out" in result.stdout, result.stdout
    assert elapsed < 10, f"grandchild kept the step alive for {elapsed:.1f}s"


def test_ctrl_c_aborts_the_script_through_the_timeout_wrapper() -> None:
    # The wrapper must die of SIGINT, not exit normally, or bash carries on
    # with the next cleanup step after Ctrl-C.
    script = _helper_prelude() + "\nrun_with_timeout 20 sh -c 'sleep 20 & sleep 20'\necho STEP2_RAN\n"
    proc = subprocess.Popen(
        ["bash", "-c", script], start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(1.5)
    os.killpg(proc.pid, signal.SIGINT)
    out, _ = proc.communicate(timeout=15)
    assert proc.returncode == -signal.SIGINT, (proc.returncode, out)
    assert "STEP2_RAN" not in out, out


def _run_snippet(bindir: Path, body: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", _helper_prelude() + "\n" + body],
        env=_env(bindir),
        check=False, capture_output=True,
        text=True,
        timeout=timeout,
    )


COLIMA_SOCKET = "unix://${HOME}/.colima/default/docker.sock"
DESKTOP_SOCKET = "unix:///var/run/docker.sock"


@pytest.mark.parametrize(
    ("colima_status", "cli_endpoint", "docker_info", "expected"),
    [
        (0, COLIMA_SOCKET, 0, "colima"),  # VM up and the CLI targets it
        (0, DESKTOP_SOCKET, 0, "desktop"),  # VM up, but the CLI targets another daemon
        (1, COLIMA_SOCKET, 1, "none"),  # CLI targets Colima, which is stopped
        (1, DESKTOP_SOCKET, 0, "desktop"),  # colima stopped, another daemon answers
        (1, DESKTOP_SOCKET, 1, "none"),  # nothing running
    ],
)
def test_detect_runtime_follows_the_cli_endpoint(
    tmp_path: Path, colima_status: int, cli_endpoint: str, docker_info: int, expected: str
) -> None:
    _fake_tool(tmp_path, "colima", f"exit {colima_status}\n")
    bindir = _fake_tool(
        tmp_path,
        "docker",
        f'case "$1" in\n  context) echo "{cli_endpoint}" ;;\n  *) exit {docker_info} ;;\nesac\n',
    )
    result = _run_snippet(bindir, "unset DOCKER_HOST\ndetect_docker_runtime\n")
    assert result.stdout.strip() == expected, result.stderr


def test_pm_jobs_run_concurrently_and_log_in_start_order(tmp_path: Path) -> None:
    bindir = _fake_tool(tmp_path, "pnpm", "sleep 2\necho pnpm-done\n")
    _fake_tool(tmp_path, "yarn", "sleep 2\necho yarn-done\n")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    body = (
        f'PM_LOG_DIR="{log_dir}"\n'
        'start_pm_job pnpm 10 "Pruning pnpm store" pnpm store prune\n'
        'start_pm_job yarn 10 "Cleaning yarn cache" yarn cache clean\n'
        "wait\n"
        'for name in "${PM_JOB_NAMES[@]}"; do cat "$PM_LOG_DIR/$name.log"; done\n'
    )
    start = time.monotonic()
    result = _run_snippet(bindir, body)
    elapsed = time.monotonic() - start
    assert elapsed < 3.5, f"jobs ran one after another ({elapsed:.1f}s for two 2s tools)"
    assert "pnpm-done" in result.stdout and "yarn-done" in result.stdout, result.stdout
    assert result.stdout.index("pnpm-done") < result.stdout.index("yarn-done")


def test_wait_for_docker_gives_up_after_the_deadline(tmp_path: Path) -> None:
    # Each `docker info` hangs 3s, longer than the 2s deadline. Counting only
    # sleeps would retry once more; the wall clock stops at the first check past 2s.
    bindir = _fake_tool(tmp_path, "docker", "sleep 3\nexit 1\n")
    start = time.monotonic()
    result = _run_snippet(bindir, "wait_for_docker 2 && echo UP || echo DOWN\n")
    elapsed = time.monotonic() - start
    assert "DOWN" in result.stdout, result.stdout
    assert elapsed < 6, f"wait_for_docker overran its 2s deadline ({elapsed:.1f}s)"


def test_orphan_stack_report_names_only_stacks_whose_directory_is_gone(tmp_path: Path) -> None:
    live = tmp_path / "live-worktree"
    live.mkdir()
    gone = tmp_path / "removed-worktree"
    bindir = _fake_tool(
        tmp_path,
        "docker",
        f'printf "byo-live\\t{live}\\nbyo-live\\t{live}\\nbyo-gone\\t{gone}\\n"\n',
    )
    result = _run_snippet(bindir, "report_orphan_compose_stacks\n")
    assert "byo-gone" in result.stdout, result.stdout
    assert "byo-live" not in result.stdout, result.stdout


def test_failed_colima_restart_is_reported_and_flagged(tmp_path: Path) -> None:
    # `colima start` fails at once, so wait_for_docker is never reached.
    bindir = _fake_tool(tmp_path, "colima", "exit 1\n")
    body = 'COLIMA_STOPPED_BY_US=1\nrestart_colima || true\necho "FLAG=$RESTART_FAILED"\n'
    result = _run_snippet(bindir, body)
    assert "FLAG=1" in result.stdout, result.stdout
    assert "did not come back up" in result.stderr, result.stderr


def test_restart_is_a_no_op_when_this_run_did_not_stop_colima(tmp_path: Path) -> None:
    bindir = _fake_tool(tmp_path, "colima", "exit 1\n")
    result = _run_snippet(bindir, 'restart_colima\necho "FLAG=$RESTART_FAILED"\n')
    assert "FLAG=0" in result.stdout, result.stdout
    assert "Starting Colima" not in result.stdout, result.stdout


def test_failed_start_is_reported_once_and_not_retried_on_exit(tmp_path: Path) -> None:
    # A start that fails normally is reported; the EXIT handler must not start it again.
    starts = tmp_path / "starts.log"
    bindir = _fake_tool(tmp_path, "colima", f'echo start >> "{starts}"\nexit 1\n')
    body = 'COLIMA_STOPPED_BY_US=1\nrestart_colima || true\nrestart_colima || true\necho "FLAG=$RESTART_FAILED"\n'
    result = _run_snippet(bindir, body)
    assert "FLAG=1" in result.stdout, result.stdout
    assert starts.read_text().count("start") == 1, starts.read_text()


def test_interrupt_during_start_leaves_the_exit_handler_to_retry(tmp_path: Path) -> None:
    # Ctrl-C while `colima start` runs must not count as a failed start: the INT
    # trap exits, the EXIT handler runs restart_colima again, and the VM comes back.
    starts = tmp_path / "starts.log"
    bindir = _fake_tool(tmp_path, "colima", f'echo start >> "{starts}"\nsleep 3\nexit 1\n')
    body = (
        "trap 'exit 130' INT TERM\n"
        "trap 'restart_colima || true' EXIT\n"
        "COLIMA_STOPPED_BY_US=1\n"
        "(sleep 1; kill -INT $$) &\n"
        "restart_colima\n"
    )
    _run_snippet(bindir, body, timeout=30)
    assert starts.read_text().count("start") == 2, starts.read_text()


def test_docker_context_overrides_docker_host(tmp_path: Path) -> None:
    # `docker --help`: DOCKER_CONTEXT overrides DOCKER_HOST, so the endpoint comes from the context.
    bindir = _fake_tool(
        tmp_path,
        "docker",
        'case "$*" in\n  "context inspect ssh-remote "*) echo "ssh://remote" ;;\n  *) echo "unix:///wrong.sock" ;;\nesac\n',
    )
    body = "export DOCKER_HOST=unix:///colima.sock\nexport DOCKER_CONTEXT=ssh-remote\nactive_docker_endpoint\n"
    result = _run_snippet(bindir, body)
    assert result.stdout.strip() == "ssh://remote", result.stderr


def test_recycle_is_skipped_unless_opted_in(tmp_path: Path) -> None:
    # Stopping the VM interrupts every container in it, so ordinary cleanups must not.
    stopped = tmp_path / "stopped.log"
    bindir = _fake_tool(tmp_path, "colima", f'echo "$@" >> "{stopped}"\nexit 0\n')
    result = _run_snippet(bindir, "recycle_colima\necho \"FLAG=$RESTART_FAILED\"\n")
    assert "recycle skipped" in result.stdout, result.stdout
    assert not stopped.exists(), f"colima ran without opt-in: {stopped.read_text()}"


def test_recycle_leaves_containers_to_their_restart_policy(tmp_path: Path) -> None:
    # Colima's daemon restarts containers whose policy is unless-stopped/always.
    # Containers set to `no` must stay down, so the recycle must never `docker start`.
    started = tmp_path / "started.log"
    bindir = _fake_tool(tmp_path, "colima", "exit 0\n")
    (bindir / "docker").write_text(
        "#!/bin/bash\n"
        'case "$1" in\n'
        '  ps) echo "abc123" ;;\n'
        f'  start) echo "$@" >> "{started}" ;;\n'
        "esac\n"
        "exit 0\n"
    )
    (bindir / "docker").chmod(0o755)
    result = _run_snippet(bindir, "CLEANUP_RECYCLE_COLIMA=1\nrecycle_colima\necho \"FLAG=$RESTART_FAILED\"\n")
    assert "FLAG=0" in result.stdout, result.stdout
    assert not started.exists(), f"recycle started containers: {started.read_text()}"


def test_windows_script_never_prunes_volumes() -> None:
    # Same policy as the bash script: an unused volume can hold a stopped dev
    # database, so no volume prune on any platform.
    ps1 = SCRIPT.with_suffix(".ps1").read_text()
    assert "docker volume prune" not in ps1, "volume prune would delete stopped dev databases"

def test_pm_cache_runs_from_home_not_the_callers_repo(tmp_path: Path) -> None:
    # Regression: run from a repo whose .npmrc has an unset ${NPM_TOKEN},
    # `yarn cache clean` failed. The caches are global, so run from $HOME.
    bindir = _fake_tool(tmp_path, "yarn", 'echo "cwd=$PWD"\n')
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    script = _helper_prelude() + '\nclean_pm_cache 5 "Cleaning yarn cache" yarn cache clean\n'
    result = subprocess.run(
        ["bash", "-c", script], cwd=repo, env=_env(bindir, {"HOME": str(home)}), check=False, capture_output=True, text=True, timeout=15
    )
    assert f"cwd={home}" in result.stdout, result.stdout
