"""OS-level scheduler abstraction (launchd / cron / Task Scheduler).

Stub module: will be fully implemented by a parallel unit.
"""

from typing import Optional, Protocol


class Scheduler(Protocol):
    """Interface that platform schedulers must implement."""

    def register(self, runner_path: str, time: str) -> None: ...
    def unregister(self) -> None: ...
    def is_registered(self) -> bool: ...
    def next_run(self) -> Optional[str]: ...
    def last_run(self) -> Optional[str]: ...


class _StubScheduler:
    """No-op scheduler used when the real implementation isn't merged yet."""

    def register(self, runner_path: str, time: str) -> None:
        pass

    def unregister(self) -> None:
        pass

    def is_registered(self) -> bool:
        return False

    def next_run(self) -> Optional[str]:
        return None

    def last_run(self) -> Optional[str]:
        return None


def get_scheduler() -> Scheduler:
    """Return the appropriate scheduler for the current platform."""
    return _StubScheduler()
