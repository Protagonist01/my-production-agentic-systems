"""Bounded, payload-free within-process timing; elapsed spans are not additive labor."""

import math
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated, Literal, Self

from agent_harness.contracts import WireContract
from pydantic import Field, model_validator

Stage = Literal[
    "receipt",
    "input_validation",
    "queue_wait",
    "worker_startup",
    "claim",
    "database_read",
    "cheap_request",
    "strong_request",
    "parse",
    "evidence_check",
    "routing",
    "database_write",
    "commit",
    "publication",
    "client_visible",
    "human_review",
    "correction",
    "acceptance",
    "export",
]
STAGES: tuple[Stage, ...] = (
    "receipt",
    "input_validation",
    "queue_wait",
    "worker_startup",
    "claim",
    "database_read",
    "cheap_request",
    "strong_request",
    "parse",
    "evidence_check",
    "routing",
    "database_write",
    "commit",
    "publication",
    "client_visible",
    "human_review",
    "correction",
    "acceptance",
    "export",
)


class Timing(WireContract):
    stage: Stage
    start_ns: Annotated[int, Field(ge=0)]
    end_ns: Annotated[int, Field(ge=0)]
    failed: bool = False

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.end_ns < self.start_ns:
            raise ValueError("timing ends before it starts")
        return self


class Profiler:
    def __init__(self, clock: Callable[[], int] = time.perf_counter_ns) -> None:
        self.clock = clock
        self.rows: list[Timing] = []

    @contextmanager
    def span(self, stage: Stage) -> Iterator[None]:
        if stage not in STAGES or len(self.rows) >= 256:
            raise ValueError("unknown stage or timing limit")
        start = self.clock()
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            end = self.clock()
            if end < start:
                raise ValueError("monotonic clock regressed")
            self.rows.append(Timing(stage=stage, start_ns=start, end_ns=end, failed=failed))


CURRENT: ContextVar[Profiler | None] = ContextVar("cfpb_measurement", default=None)


@contextmanager
def measured(stage: Stage) -> Iterator[None]:
    profiler = CURRENT.get()
    if profiler is None:
        yield
    else:
        with profiler.span(stage):
            yield


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def timing_report(runs: Sequence[Sequence[Timing]]) -> dict[str, object]:
    stages = {}
    for stage in STAGES:
        values = [(r.end_ns - r.start_ns) / 1e9 for run in runs for r in run if r.stage == stage]
        stages[stage] = {
            "observations": len(values),
            "runs_present": sum(any(r.stage == stage for r in run) for run in runs),
            "p50_seconds": percentile(values, 0.5),
            "p95_seconds": percentile(values, 0.95),
        }
    return {
        "runs": len(runs),
        "stages": stages,
        "inclusive_spans_do_not_sum": True,
        "provider_internal_and_network_phases": "unmeasured",
    }
