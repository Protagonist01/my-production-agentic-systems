"""Private fixed-size HTTP counters. No paths, payloads, identities or exception text."""

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import BinaryIO

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from olist_support.policy_cases import external


class ServiceTelemetry:
    """One lifespan owner; a forced exit leaves an incomplete (empty) output file."""

    def __init__(
        self, *, code_revision: str, environment_lock: str, output: Path | None = None
    ) -> None:
        self._pin = hashlib.sha256(
            json.dumps([code_revision, environment_lock], separators=(",", ":")).encode()
        ).hexdigest()
        self._output = output
        self._file: BinaryIO | None = None
        self._lock = threading.Lock()
        self._started_at = time.monotonic_ns()
        self._started = 0
        self._completed = 0
        self._interrupted = 0
        self._duration_ns = 0
        self._classes = [0] * 5
        self._opened = False
        self._closed = False

    def open(self) -> None:
        with self._lock:
            if self._opened or self._closed:
                raise ValueError("service telemetry is single-use")
            if self._output is not None:
                if self._output.is_symlink():
                    raise ValueError("telemetry requires a new private output")
                path = external(self._output)
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                self._file = os.fdopen(descriptor, "wb")
            self._opened = True

    def begin(self) -> int:
        with self._lock:
            if self._closed:
                raise ValueError("service telemetry is closed")
            self._started += 1
        return time.monotonic_ns()

    def end(self, started: int, status: int, complete: bool) -> None:
        with self._lock:
            self._duration_ns += max(0, time.monotonic_ns() - started)
            self._completed += int(complete)
            self._interrupted += int(not complete)
            self._classes[min(5, max(1, status // 100)) - 1] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "version": "olist-service-telemetry-v1",
                "configuration_sha256": self._pin,
                "started": self._started,
                "completed": self._completed,
                "interrupted": self._interrupted,
                "active": self._started - self._completed - self._interrupted,
                "status_classes": dict(
                    zip(("1xx", "2xx", "3xx", "4xx", "5xx"), self._classes, strict=True)
                ),
                "total_request_ns": self._duration_ns,
                "uptime_ns": max(0, time.monotonic_ns() - self._started_at),
                "shutdown_finished": self._closed,
                "business_unit": "SIM",
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        # Close runs after the server's drain. It does not change any business state.
        if self._file is not None:
            try:
                raw = json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":")).encode()
                self._file.write(raw)
                self._file.flush()
                os.fsync(self._file.fileno())
            except OSError:
                # Do not leave a parseable success snapshot after a failed flush.
                try:
                    self._file.seek(0)
                    self._file.truncate()
                    self._file.flush()
                except OSError:
                    pass
                raise
            finally:
                self._file.close()


class CountHTTP:
    def __init__(self, app: ASGIApp, telemetry: ServiceTelemetry) -> None:
        self.app, self.telemetry = app, telemetry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = self.telemetry.begin()
        status, complete = 500, False

        async def counted(message: Message) -> None:
            nonlocal status, complete
            await send(message)
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and not message.get("more_body", False):
                complete = True

        try:
            await self.app(scope, receive, counted)
        finally:
            self.telemetry.end(started, status, complete)
