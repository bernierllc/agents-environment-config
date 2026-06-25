"""Debug logging for the aec CLI.

When `--debug` is enabled (flag or AEC_DEBUG=1 env var), unhandled exceptions
and quietly-swallowed subprocess failures are written to a rotating log at
``~/.agents-environment-config/logs/aec-debug.log``.

Paths and environment variable values are redacted before being written so the
log is safe to attach to a public GitHub issue.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable, Optional

from . import config

ISSUE_URL = "https://github.com/mattbernier/agents-environment-config/issues/new?template=cli-error.md"

_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
_BACKUP_COUNT = 5

_LOGGER_NAME = "aec.debug"
_logger: Optional[logging.Logger] = None
_logger_path: Optional[Path] = None  # path the cached logger's handler writes to
_debug_enabled: bool = False


def _log_dir() -> Path:
    """Resolve the log directory live from config, so tests (and any runtime
    HOME change) get the current path rather than the import-time one."""
    return config.AEC_HOME / "logs"


def _log_file() -> Path:
    return _log_dir() / "aec-debug.log"


def reset() -> None:
    """Drop the cached logger and its handlers. For test isolation: lets the
    next log call rebuild against the current HOME without reloading this
    module (which would orphan references held by aec.cli)."""
    global _logger, _logger_path, _debug_enabled
    stale = logging.getLogger(_LOGGER_NAME)
    for h in list(stale.handlers):
        h.close()
        stale.removeHandler(h)
    _logger = None
    _logger_path = None
    _debug_enabled = False

# Env var names whose values are always redacted in full.
_SECRET_NAME_RE = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|API)",
    re.IGNORECASE,
)

# Heuristic: long base64/hex-ish strings that look like secrets.
_SECRETLIKE_VALUE_RE = re.compile(r"\b[A-Za-z0-9+/_\-]{32,}={0,2}\b")


def is_debug() -> bool:
    """Return True when debug mode is active for this process."""
    return _debug_enabled


def enable_debug() -> None:
    """Mark debug mode active. Idempotent."""
    global _debug_enabled
    _debug_enabled = True


def debug_from_env_or_argv(argv: Optional[list[str]] = None) -> bool:
    """Detect --debug or AEC_DEBUG=1 without fully parsing arguments.

    Used so the top-level error handler knows the mode even if the parser
    never ran (e.g. an exception during argv parsing or import time).
    """
    if os.environ.get("AEC_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    args = argv if argv is not None else sys.argv[1:]
    return "--debug" in args


def _build_logger() -> logging.Logger:
    global _logger, _logger_path
    target = _log_file()
    if _logger is not None and _logger_path == target:
        return _logger
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # Drop any handler pointing at a stale path (e.g. a prior HOME in tests).
    for h in list(logger.handlers):
        h.close()
        logger.removeHandler(h)
    target.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        target,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    _logger = logger
    _logger_path = target
    return logger


def _redact_paths(text: str) -> str:
    """Replace user home and platform user dirs with stable placeholders."""
    if not text:
        return text
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    text = re.sub(r"/Users/[^/\s\"':]+", "/Users/USER", text)
    text = re.sub(r"/home/[^/\s\"':]+", "/home/USER", text)
    text = re.sub(r"[A-Z]:\\Users\\[^\\\s\"':]+", r"C:\\Users\\USER", text)
    return text


def redact(text: str) -> str:
    """Best-effort redaction of paths and secret-shaped values."""
    if not text:
        return text
    text = _redact_paths(text)
    text = _SECRETLIKE_VALUE_RE.sub("<REDACTED>", text)
    return text


def _safe_env_snapshot() -> dict[str, str]:
    """Return a redacted snapshot of AEC_* and a few diagnostic env vars."""
    snapshot: dict[str, str] = {}
    keys: Iterable[str] = [k for k in os.environ if k.startswith("AEC_")]
    for k in list(keys) + ["SHELL", "TERM", "LANG", "PATH"]:
        if k not in os.environ:
            continue
        v = os.environ[k]
        if _SECRET_NAME_RE.search(k):
            snapshot[k] = "<REDACTED>"
        else:
            snapshot[k] = redact(v)
    return snapshot


def _header(command: Optional[str] = None) -> str:
    try:
        from .. import __version__ as ver
    except Exception:
        ver = "unknown"
    parts = [
        "==== aec error ====",
        f"command: {redact(command or ' '.join(sys.argv))}",
        f"aec_version: {ver}",
        f"python: {sys.version.split()[0]}",
        f"platform: {platform.platform()}",
        f"env: {_safe_env_snapshot()}",
    ]
    return "\n".join(parts)


def log_exception(exc: BaseException, command: Optional[str] = None) -> Path:
    """Write a redacted exception report to the debug log. Returns log path."""
    logger = _build_logger()
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error("%s\n%s\n==== end ====", _header(command), redact(tb))
    return _log_file()


def log_subprocess_failure(
    cmd: list[str] | str,
    returncode: Optional[int],
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    note: Optional[str] = None,
) -> Optional[Path]:
    """Write a redacted record of a swallowed subprocess failure.

    Only writes when debug mode is active so production runs never touch the
    log file. Returns the log path on write, else None.
    """
    if not _debug_enabled:
        return None
    logger = _build_logger()
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    parts = [
        "---- subprocess failure ----",
        f"cmd: {redact(cmd_str)}",
        f"returncode: {returncode}",
    ]
    if note:
        parts.append(f"note: {redact(note)}")
    if stdout:
        parts.append(f"stdout:\n{redact(stdout)}")
    if stderr:
        parts.append(f"stderr:\n{redact(stderr)}")
    parts.append("---- end ----")
    logger.error("\n".join(parts))
    return _log_file()


def friendly_error_message(log_path: Optional[Path] = None) -> str:
    """User-facing message when an exception bubbles up without --debug."""
    return (
        "aec encountered an error.\n"
        "  - To capture details, re-run the command with --debug\n"
        "    (or set AEC_DEBUG=1).\n"
        f"  - Then file an issue at: {ISSUE_URL}\n"
        f"    and attach the log at: {log_path or _log_file()}\n"
    )


def debug_error_message(log_path: Path) -> str:
    """User-facing message when an exception bubbles up with --debug."""
    return (
        "aec encountered an error. Details written to:\n"
        f"  {log_path}\n"
        f"File an issue at: {ISSUE_URL}\n"
    )
