"""Asking the process that serves the app to stop and come back, after an update.

The launcher hands over how to stop its server (attach). The interface asks for a restart
when a new version is ready (restart); the launcher then ends with RESTART, and start.bat or
start.command put the new version in place and start again. Run any other way, by uvicorn
by hand for instance, there is nobody to start it again, and can_restart says so.
"""

from collections.abc import Callable

RESTART = 75
_stop: Callable[[], None] | None = None
wanted = False


def attach(stop: Callable[[], None]) -> None:
    global _stop
    _stop = stop


def can_restart() -> bool:
    return _stop is not None


def restart() -> bool:
    global wanted
    if _stop is None:
        return False
    wanted = True
    _stop()
    return True
