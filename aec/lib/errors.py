"""Errors the user can fix themselves.

Raise ``AecError`` (or a subclass) when a command fails for a reason the user
can act on: a diverged git branch, a missing tool, a network problem. The CLI
entry point (``aec.cli.main``) prints the message, any underlying tool output,
and the numbered fix steps, then exits 1, so the user is never left with only
"something went wrong, file an issue".
"""

from typing import Optional, Sequence


class AecError(Exception):
    """A failure with a known cause and steps the user can take to fix it."""

    def __init__(
        self,
        message: str,
        fix: Sequence[str] = (),
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.fix = list(fix)
        self.detail = detail


class RepoSyncError(AecError):
    """Pulling the AEC repo or its submodules failed."""
