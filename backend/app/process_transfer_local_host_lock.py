from __future__ import annotations

import errno
import os
import time
from pathlib import Path
from types import TracebackType


TRUTH_BOUNDARY = (
    "This module provides a local-host advisory file lock for cooperating MORPHEUS processes only. "
    "POSIX uses flock and Windows uses a one-byte msvcrt region lock. The operating system releases the held lock when the owning "
    "file descriptor/process terminates, including ordinary process crash/abandonment cases covered by CI. It does not prevent a "
    "non-cooperating process from modifying the protected state path, does not provide distributed mutual exclusion, consensus, "
    "lease semantics, a database compare-and-swap, filesystem transactionality, power-loss durability, or a linearizability proof."
)

_RETRY_SECONDS = 0.01


class LocalHostFileLock:
    """Cross-process advisory lock scoped to one canonical local-host sidecar path."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path).resolve(strict=False)
        self._handle = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> None:
        if self._handle is not None:
            raise RuntimeError("local-host file lock is already acquired by this object")

        handle = self._path.open("a+b")
        try:
            if os.name == "nt":
                self._acquire_windows(handle)
            else:
                self._acquire_posix(handle)
        except BaseException:
            handle.close()
            raise
        self._handle = handle

    @staticmethod
    def _acquire_posix(handle) -> None:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _acquire_windows(handle) -> None:
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        while True:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                    raise
                time.sleep(_RETRY_SECONDS)

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            raise RuntimeError("local-host file lock is not acquired")
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle = None
            handle.close()

    def __enter__(self) -> "LocalHostFileLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
