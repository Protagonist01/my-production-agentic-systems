"""Serialize owned Process bookkeeping, while waiting outside the shared lock.

POSIX multiprocessing.start() polls other children via its global cleanup list.
Concurrent join/poll on those same children can race when reaping exit status
(CPython #130895). Both harness spawn paths must use this control boundary.
"""

import threading
import time
from multiprocessing.connection import wait
from multiprocessing.process import BaseProcess

_CONTROL = threading.Lock()


class OwnedProcess:
    """Only short process-control operations are serialized, never worker lifetime."""

    def __init__(self, process: BaseProcess) -> None:
        self._process = process

    def start(self) -> None:
        with _CONTROL:
            self._process.start()

    def join(self, timeout: float) -> None:
        end = time.monotonic() + max(0.0, timeout)
        while True:
            remaining = max(0.0, end - time.monotonic())
            if remaining > 0:
                wait([self._process.sentinel], timeout=remaining)
            with _CONTROL:
                # A blocking join would race other starts, or serialize whole trials.
                self._process.join(0)
                exited = self._process.exitcode is not None
            remaining = end - time.monotonic()
            if exited or remaining <= 0:
                return
            # POSIX sentinel EOF can be visible before waitpid exposes exit status.
            # Recheck until the original bound, without holding the control lock
            # or spinning on an already-readable sentinel. EOF is not exit status.
            time.sleep(min(0.001, remaining))

    def is_alive(self) -> bool:
        with _CONTROL:
            return self._process.is_alive()

    @property
    def exitcode(self) -> int | None:
        with _CONTROL:
            return self._process.exitcode

    def terminate(self) -> None:
        with _CONTROL:
            self._process.terminate()

    def kill(self) -> None:
        with _CONTROL:
            self._process.kill()

    def close(self) -> None:
        with _CONTROL:
            self._process.close()
