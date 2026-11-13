"""AEC's side of the feedback loop: capture its own failures, point at the store's CLI.

The store and every operation on it (status, review, resolve, config) belong to the
``feedback-loop`` skill's ``feedback.py``. AEC does only what the skill cannot do for it:

- ``capture``: write one ``aec:aec`` entry when an AEC run crashes, with no agent present
  and even when the skill is not installed. It uses the store's documented entry format
  (one JSON line, single ``O_APPEND`` write), pinned by ``tests/test_feedback.py`` against
  the real ``feedback.py``.
- ``locate_script``: find the installed ``feedback.py`` so ``aec feedback`` can hand off to it.
- ``maybe_notify``: once a day, tell the user when the ``aec`` subject is due for review,
  asking ``feedback.py`` (which owns the threshold) rather than re-deciding it here.
"""

import json
import logging
import os
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # shortcut: no lock on Windows; single O_APPEND writes of one line still rarely interleave

logger = logging.getLogger(__name__)

SUBJECT = "aec:aec"
NOTICE_INTERVAL = timedelta(days=1)

# Set by the CLI callback so a crash names the command, never its arguments.
current_command: Optional[str] = None


def store_home() -> Path:
    return Path(os.environ.get("AGENT_FEEDBACK_HOME") or Path.home() / ".agent-feedback")


def _logging_enabled() -> bool:
    try:
        cfg = json.loads((store_home() / "config.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return True  # the store's default: enabled, nothing opted out
    if not isinstance(cfg, dict) or not isinstance(cfg.get("opt_out", []), list):
        raise ValueError("config.json is not {enabled, opt_out: [...]}")  # capture logs and skips
    return bool(cfg.get("enabled", True)) and SUBJECT not in cfg.get("opt_out", [])


def capture(severity: str, summary: str) -> None:
    """Append one ``aec:aec`` entry. Best-effort: never raises into the failing run."""
    try:
        if not _logging_enabled():
            return
        entry = {
            "id": secrets.token_hex(6),
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "aec",
            "name": "aec",
            "severity": severity,
            "summary": " ".join(summary.split()),
            "reporter": "cli",
        }
        path = store_home() / "subjects" / "aec" / "aec" / "entries.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except Exception as exc:
        # Best-effort by design: capture runs inside main()'s error handlers, so any failure
        # here would replace the original error. Log it and let the original path continue.
        logger.warning("feedback capture skipped: %r", exc)


def prompt_label(prompt_id: str) -> str:
    """A value-free name for a prompt: its static catalog ID, or its dynamic family's prefix.

    Dynamic prompt IDs embed item names and resolved paths (``untrack.confirm.<path>``),
    so they are never written to the store verbatim.
    """
    try:
        from .prompt_catalog import all_families, catalog_ids
        if prompt_id in catalog_ids():
            return prompt_id
        for family in all_families():
            if prompt_id.startswith(family.prefix + "."):
                return family.prefix + ".*"
    except Exception as exc:
        # Called from main()'s error handler: a catalog failure must not replace the original error.
        logger.warning("prompt label lookup failed: %r", exc)
    return "an uncatalogued prompt"


def crash_summary(exc: BaseException) -> str:
    """Exception type, AEC command and the innermost AEC function. No arguments, paths or values."""
    where = ""
    tb = exc.__traceback__
    while tb is not None:
        module = tb.tb_frame.f_globals.get("__name__", "")
        if module == "aec" or module.startswith("aec."):
            where = f" at {module}.{tb.tb_frame.f_code.co_name}"
        tb = tb.tb_next
    command = f"`aec {current_command}`" if current_command else "aec"
    return f"{command} crashed: {type(exc).__name__}{where}"


def locate_script() -> Optional[Path]:
    """The installed feedback-loop ``feedback.py``, or None."""
    override = os.environ.get("AGENT_FEEDBACK_BIN")
    candidates = [Path(override)] if override else []
    from .config import AGENT_TOOLS_DIR, CLAUDE_DIR
    candidates += [
        CLAUDE_DIR / "skills" / "feedback-loop" / "scripts" / "feedback.py",
        AGENT_TOOLS_DIR / "skills" / "feedback-loop" / "scripts" / "feedback.py",
    ]
    return next((c for c in candidates if c.is_file()), None)


def maybe_notify() -> None:
    """At most once a day, print one line when ``aec:aec`` is due for review."""
    if os.environ.get("AEC_NO_UPDATE_CHECK", "").strip().lower() in ("1", "true", "yes"):
        return
    try:
        if not _logging_enabled():
            return  # disabled or opted out: no capture, no nagging
    except (OSError, ValueError) as exc:
        logger.warning("feedback notice skipped: %r", exc)
        return
    script = locate_script()
    if script is None:
        return
    from .config import AEC_HOME
    stamp = AEC_HOME / "feedback-notice.json"
    now = datetime.now(timezone.utc)
    try:
        last = datetime.fromisoformat(json.loads(stamp.read_text())["last"])
        if now - last < NOTICE_INTERVAL:
            return
    except (OSError, KeyError, TypeError, ValueError):
        pass  # never noticed, or an unreadable/naive stamp: check now
    try:
        result = subprocess.run(
            [sys.executable, str(script), "status", SUBJECT, "--json"],
            capture_output=True, text=True, timeout=5,
        )
        rows = json.loads(result.stdout)["subjects"] if result.returncode == 0 else []
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(json.dumps({"last": now.isoformat()}))
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError) as exc:
        logger.warning("feedback notice skipped: %r", exc)
        return
    if rows and rows[0].get("due"):
        print(f"aec has feedback due ({rows[0]['due']}): run `aec feedback review {SUBJECT}`",
              file=sys.stderr)
