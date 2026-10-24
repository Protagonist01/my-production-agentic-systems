"""One owned spawned process per attempt: bounded wait without background requests."""

import ctypes
import math
import multiprocessing
import os
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Annotated, Protocol

from pydantic import Field

from agent_harness.contracts import Contract, ModelRequest, ModelResponse
from agent_harness.gateway import failed_response
from agent_harness.process_control import OwnedProcess

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 8 * 1024 * 1024
CLEANUP_SECONDS = 0.25  # terminate join, then kill join: up to twice this allowance


class AttemptTiming(Contract):
    """Local process phases, never evidence of provider dispatch or billing."""

    elapsed_seconds: Annotated[float, Field(ge=0)]
    worker_entered_after_seconds: Annotated[float, Field(ge=0)] | None
    generation_returned_after_seconds: Annotated[float, Field(ge=0)] | None
    frame_ready_after_seconds: Annotated[float, Field(ge=0)] | None
    timed_out: bool
    exit_code: int | None


class AttemptWorker(Protocol):
    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse: ...


def _run_worker(
    worker: AttemptWorker,
    request_json: str,
    timeout_seconds: float,
    buffer: ctypes.Array[ctypes.c_ubyte],
    size: ctypes.c_int,
    phases: ctypes.Array[ctypes.c_double],
    origin: float,
) -> None:
    # No arbitrary stdout, provider errors or traceback escape into the parent's logs.
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        phases[0] = max(0.0, time.monotonic() - origin)
        request = ModelRequest.model_validate_json(request_json)
        try:
            result = ModelResponse.model_validate(
                worker.generate(request, timeout_seconds=timeout_seconds)
            )
            phases[1] = max(0.0, time.monotonic() - origin)
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
        phases[2] = max(0.0, time.monotonic() - origin)


class IsolatedTransport:
    """Trusted importable worker; spawn is explicit on Linux and Windows alike."""

    def __init__(self, worker: AttemptWorker) -> None:
        self._worker = worker
        self.last_timing: AttemptTiming | None = None

    def generate(
        self, request: ModelRequest, *, timeout_seconds: float | None = None
    ) -> ModelResponse:
        self.last_timing = None
        if timeout_seconds is None or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            return failed_response(
                request, "timeout", "Isolated transport requires a deadline", dispatched=False
            )
        origin = time.monotonic()
        end = origin + timeout_seconds
        encoded = ModelRequest.model_validate(request).canonical_json()
        if len(encoded.encode("utf-8")) > MAX_REQUEST_BYTES:
            return failed_response(
                request, "invalid_response", "Worker request exceeded frame limit", dispatched=False
            )
        ctx = multiprocessing.get_context("spawn")
        buffer = ctx.RawArray(ctypes.c_ubyte, MAX_RESPONSE_BYTES)
        size = ctx.RawValue(ctypes.c_int, 0)
        phases = ctx.RawArray(ctypes.c_double, (-1.0, -1.0, -1.0))
        process = OwnedProcess(
            ctx.Process(
                target=_run_worker,
                args=(self._worker, encoded, timeout_seconds, buffer, size, phases, origin),
                daemon=True,
            )
        )
        started = False
        timed_out = False
        try:
            process.start()
            started = True
            process.join(max(0.0, end - time.monotonic()))
            if process.is_alive() or time.monotonic() >= end:
                timed_out = True
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
            self.last_timing = AttemptTiming(
                elapsed_seconds=max(0.0, time.monotonic() - origin),
                worker_entered_after_seconds=phases[0] if phases[0] >= 0 else None,
                generation_returned_after_seconds=phases[1] if phases[1] >= 0 else None,
                frame_ready_after_seconds=phases[2] if phases[2] >= 0 else None,
                timed_out=timed_out,
                exit_code=process.exitcode if started else None,
            )
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
