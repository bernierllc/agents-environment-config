"""Git-sourced org configs: ``git+<url>#<ref>:<path/to/org.yaml>``.

AEC owns the clone at ``~/.aec/orgs/<org_id>.d/repo/``. Every git call is an
argv list (no shell) with a protocol allow-list (https and ssh only), no
terminal prompts, and a timeout. Credentials come from the user's own git
setup; AEC never stores them.

A refresh fetches the ref and checks out ``FETCH_HEAD`` detached, so
force-pushes and moved tags are followed rather than failed on. Every file is
then read from that single checked-out commit.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import OrgConfigFetchError, OrgConfigValidationError

GIT_PREFIX = "git+"
PROTO_FLAGS = [
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "protocol.ssh.allow=always",
]
GIT_TIMEOUT_SECONDS = 120
MAX_CONFIG_BYTES = 1024 * 1024

_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_SCP_RE = re.compile(r"^[A-Za-z0-9._-]+@[A-Za-z0-9][A-Za-z0-9.-]*:[A-Za-z0-9._/~-]+$")
# No userinfo in the authority: a token in the url would land in state and output.
_HTTPS_RE = re.compile(r"^https://[^\s/@]+/[^\s]+$")


@dataclass(frozen=True)
class GitSource:
    url: str
    ref: str
    path: str

    @property
    def spec(self) -> str:
        return f"{GIT_PREFIX}{self.url}#{self.ref}:{self.path}"


def is_git_source(source: str) -> bool:
    return source.startswith(GIT_PREFIX)


def validate_git_source(url: str, ref: str, path: str) -> GitSource:
    """Validate the three parts. Runs at enroll and before every refresh."""
    if url.startswith("-") or "::" in url:
        raise OrgConfigValidationError(f"git url not allowed: {url!r}", field_path="source")
    if not (_HTTPS_RE.match(url) or _SCP_RE.match(url)):
        raise OrgConfigValidationError(
            f"git url must be https:// or git@host:path, got {url!r}", field_path="source"
        )
    if ref.startswith("-") or not _REF_RE.match(ref):
        raise OrgConfigValidationError(f"git ref not allowed: {ref!r}", field_path="source")
    norm = os.path.normpath(path) if path else ""
    if not norm or norm == "." or os.path.isabs(norm) or norm.split(os.sep)[0] == "..":
        raise OrgConfigValidationError(
            f"config path must stay inside the repo, got {path!r}", field_path="source"
        )
    return GitSource(url=url, ref=ref, path=norm)


def parse_git_source(source: str) -> GitSource:
    """Parse ``git+<url>#<ref>:<path>``."""
    if not is_git_source(source):
        raise OrgConfigValidationError(f"not a git source: {source!r}", field_path="source")
    url, sep, fragment = source[len(GIT_PREFIX):].rpartition("#")
    ref, colon, path = fragment.partition(":")
    if not sep or not colon:
        raise OrgConfigValidationError(
            "git source must look like git+<url>#<ref>:<path/to/org.yaml>", field_path="source"
        )
    return validate_git_source(url, ref, path)


def _git(argv: list[str], note: str) -> str:
    from .. import debug as _debug

    cmd = ["git", *PROTO_FLAGS, *argv]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        done = subprocess.run(
            cmd, capture_output=True, check=True, text=True, env=env,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise OrgConfigFetchError(f"git timed out after {GIT_TIMEOUT_SECONDS}s ({note})") from exc
    except subprocess.CalledProcessError as exc:
        _debug.log_subprocess_failure(
            cmd=cmd, returncode=exc.returncode, stdout=exc.stdout, stderr=exc.stderr, note=note,
        )
        detail = (exc.stderr or "").strip().splitlines()
        raise OrgConfigFetchError(
            f"git failed ({note}): {detail[-1] if detail else f'exit {exc.returncode}'}"
        ) from exc
    except FileNotFoundError as exc:
        raise OrgConfigFetchError("git is not installed") from exc
    return done.stdout.strip()


def head_commit(dest: Path) -> str:
    return _git(["-C", str(dest), "rev-parse", "HEAD"], f"rev-parse in {dest}")


def clone(src: GitSource, dest: Path) -> str:
    """Shallow-clone ``src.ref`` into ``dest`` (must not exist). Returns the commit."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(
        ["clone", "--depth", "1", "--branch", src.ref, "--", src.url, str(dest)],
        f"clone {src.url}",
    )
    return head_commit(dest)


def refresh(src: GitSource, dest: Path) -> str:
    """Fetch ``src.ref`` and check it out detached. Returns the commit."""
    _git(
        ["-C", str(dest), "fetch", "--depth", "1", "origin", "--", src.ref],
        f"fetch {src.url}",
    )
    _git(["-C", str(dest), "checkout", "--quiet", "--detach", "FETCH_HEAD"], f"checkout in {dest}")
    return head_commit(dest)


def read_file(dest: Path, rel_path: str) -> Optional[bytes]:
    """Read ``rel_path`` from the checkout; None if absent.

    Raises if the resolved path escapes the clone (``..`` or a symlink).
    """
    root = dest.resolve()
    target = (root / rel_path).resolve()
    if not target.is_relative_to(root):
        raise OrgConfigValidationError(
            f"{rel_path!r} resolves outside the repo", field_path="source"
        )
    if not target.is_file():
        return None
    if target.stat().st_size > MAX_CONFIG_BYTES:
        raise OrgConfigFetchError(f"{rel_path!r} is larger than {MAX_CONFIG_BYTES} bytes")
    return target.read_bytes()
