"""Errors the user can fix themselves.

Raise ``AecError`` (or a subclass) when a command fails for a reason the user
can act on: a diverged git branch, a missing tool, a network problem. The CLI
entry point (``aec.cli.main``) prints the message, any underlying tool output,
and the numbered fix steps, then exits 1, so the user is never left with only
"something went wrong, file an issue".

When AEC can apply the fix to its own checkout safely, attach a ``Remedy``:
the CLI asks first (a sensitive prompt, so ``--yes``/``--defaults`` never
answer it), applies it only on an explicit yes, then re-runs the command once.
AEC never changes anything outside its own checkout this way.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Sequence


@dataclass(frozen=True)
class Remedy:
    """A safe fix for AEC's own checkout, applied only with the user's consent."""

    confirm: Callable[[], bool]  # asks via aec.lib.prompts.prompt (sensitive=True); True = yes
    apply: Callable[[], str]  # performs the fix, returns what it did; raises AecError on failure


class AecError(Exception):
    """A failure with a known cause and steps the user can take to fix it."""

    def __init__(
        self,
        message: str,
        fix: Sequence[str] = (),
        detail: Optional[str] = None,
        remedy: Optional[Remedy] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.fix = list(fix)
        self.detail = detail
        self.remedy = remedy


class RepoSyncError(AecError):
    """Pulling the AEC repo or its submodules failed."""
