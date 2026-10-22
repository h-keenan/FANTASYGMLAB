"""Advisory cross-process file lock (single flight across worker processes).

The mobile API runs several uvicorn workers in one container plus a
players.db rebuild subprocess, all sharing ``data/``. Work that rewrites a
shared file there (the Sleeper players dump, players.db) only needs one
process doing it at a time, so the lock is an exclusive ``flock`` on a
sibling ``<file>.lock``. It is scoped to exactly the processes that share the
file, needs no network service, and is released by the kernel if the holder
dies.

Fail-open: where ``fcntl`` is unavailable (Windows dev) or the lock file
can't be opened, ``acquired`` is True, i.e. the old unlocked behavior.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

try:  # pragma: no cover - platform dependent
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None

_POLL_SECONDS = 0.05


class ExclusiveFileLock:
    """``with ExclusiveFileLock(path, wait_seconds=...) as lock: lock.acquired``.

    ``wait_seconds=0`` is a try-lock. When the wait runs out, the block still
    runs with ``acquired`` False; the caller decides what to do.
    """

    def __init__(self, path: str, *, wait_seconds: float = 0.0) -> None:
        self.path = str(path)
        self.wait_seconds = max(0.0, float(wait_seconds))
        self.acquired = False
        self._fd: Optional[int] = None

    def __enter__(self) -> "ExclusiveFileLock":
        if _fcntl is None:
            self.acquired = True
            return self
        try:
            self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError:
            self.acquired = True
            return self
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                _fcntl.flock(self._fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                self.acquired = True
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return self
                time.sleep(_POLL_SECONDS)
            except OSError:
                self.acquired = True
                return self

    def __exit__(self, *exc: Any) -> None:
        if self._fd is None:
            return
        try:
            if self.acquired and _fcntl is not None:
                _fcntl.flock(self._fd, _fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None
