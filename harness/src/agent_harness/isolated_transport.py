"""One owned spawned process per attempt: bounded wait without background requests."""

import ctypes
import math
import multiprocessing
import os
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Protocol

from agent_harness.contracts import ModelRequest, ModelResponse
from agent_harness.gateway import failed_response

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 8 * 1024 * 1024
CLEANUP_SECONDS = 0.25  # terminate join, then kill join: up to twice this allowance


class AttemptWorker(Protocol):
    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse: ...


def _run_worker(
    worker: AttemptWorker,
    request_json: str,
    timeout_seconds: float,
    buffer: ctypes.Array[ctypes.c_ubyte],
    size: ctypes.c_int,
) -> None:
    # No arbitrary stdout, provider errors or traceback escape into the parent's logs.
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        request = ModelRequest.model_validate_json(request_json)
        try:
            result = ModelResponse.model_validate(
                worker.generate(request, timeout_seconds=timeout_seconds)
            )
            data = result.canonical_json().encode("utf-8")
            if len(data) > MAX_RESPONSE_BYTES:
                data = (
                    failed_response(
                        request,
                        "invalid_response",
                        "Worker response exceeded frame limit",
                        dispatched=True,
                        usage=result.usage,
                    )
                    .canonical_json()
                    .encode("utf-8")
                )
        except BaseException:
            data = (
                failed_response(
                    request,
                    "unavailable",
                    "Worker failed; usage unknown",
                    dispatched=True,
                )
                .canonical_json()
                .encode("utf-8")
            )
        # Fixed shared memory avoids blocking recv on a partially written pipe frame.
        ctypes.memmove(buffer, data, len(data))
        size.value = len(data)


class IsolatedTransport:
    """Trusted importable worker; spawn is explicit on Linux and Windows alike."""

    def __init__(self, worker: AttemptWorker) -> None:
        self._worker = worker

    def generate(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        if timeout_seconds is None or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            return failed_response(
                request, "timeout", "Isolated transport requires a deadline", dispatched=False
            )
        end = time.monotonic() + timeout_seconds
        encoded = ModelRequest.model_validate(request).canonical_json()
        if len(encoded.encode("utf-8")) > MAX_REQUEST_BYTES:
            return failed_response(
                request, "invalid_response", "Worker request exceeded frame limit", dispatched=False
            )
        ctx = multiprocessing.get_context("spawn")
        buffer = ctx.RawArray(ctypes.c_ubyte, MAX_RESPONSE_BYTES)
        size = ctx.RawValue(ctypes.c_int, 0)
        process = ctx.Process(
            target=_run_worker,
            args=(self._worker, encoded, timeout_seconds, buffer, size),
            daemon=True,
        )
        started = False
        try:
            process.start()
            started = True
            process.join(max(0.0, end - time.monotonic()))
            if process.is_alive() or time.monotonic() >= end:
                return failed_response(
                    request,
                    "timeout",
                    "Isolated attempt deadline exhausted; usage unknown",
                    dispatched=True,
                    retryable=True,
                )
            if process.exitcode != 0 or not 0 < size.value <= MAX_RESPONSE_BYTES:
                return failed_response(
                    request, "unavailable", "Worker exited without a valid frame", dispatched=True
                )
            try:
                return ModelResponse.model_validate_json(bytes(buffer[: size.value]))
            except ValueError:
                return failed_response(
                    request, "invalid_response", "Worker returned an invalid frame", dispatched=True
                )
        finally:
            if started:
                if process.is_alive():
                    process.terminate()
                    process.join(CLEANUP_SECONDS)
                if process.is_alive():
                    process.kill()
                    process.join(CLEANUP_SECONDS)
                if process.is_alive():
                    raise RuntimeError("Owned worker cleanup failed")
            process.close()


@dataclass(frozen=True)
class GeminiWorker:
    api_key: str = field(repr=False)
    free_tier_confirmed: bool
    flash_comparison: bool = False

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        # Base harness imports need no Google SDK. Only a selected live worker imports it.
        from agent_harness.gemini import GeminiTransport

        return GeminiTransport(
            self.api_key,
            free_tier_confirmed=self.free_tier_confirmed,
            flash_comparison=self.flash_comparison,
        ).generate(
            request,
            timeout_seconds=timeout_seconds,
        )
