"""Payload-free opt-in Prior Auth timings; no automatic trace or content export."""

import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Annotated, Literal, Self

from agent_harness.contracts import (
    ModelGateway,
    ModelRequest,
    ModelResponse,
    RunContext,
    Usage,
    WireContract,
)
from pydantic import Field, model_validator

Stage = Literal[
    "intake",
    "extraction",
    "normalization",
    "policy_selection",
    "relevance",
    "redaction",
    "retrieval",
    "assessment",
    "model",
    "citation_check",
    "persistence",
    "publication",
    "sandbox_submit",
    "total",
    "pdf_metadata",
    "pdf_text",
    "pdf_raster",
    "ocr",
    "claim",
    "expiry",
]


class Timing(WireContract):
    stage: Stage
    start_ns: Annotated[int, Field(ge=0)]
    end_ns: Annotated[int, Field(ge=0)]
    failed: bool

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_ns < self.start_ns:
            raise ValueError("monotonic clock regressed")
        return self


@dataclass
class Profiler:
    clock: Callable[[], int] = time.perf_counter_ns
    rows: list[Timing] = field(default_factory=list)
    model_attempts: int = 0
    usage: list[Usage] = field(default_factory=list)

    @contextmanager
    def span(self, stage: Stage) -> Iterator[None]:
        if len(self.rows) >= 256:
            raise ValueError("stage inventory exceeds bound")
        start, failed = self.clock(), False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            self.rows.append(
                Timing(stage=stage, start_ns=start, end_ns=self.clock(), failed=failed)
            )

    def report(self) -> dict[str, object]:
        stages = tuple(sorted({t.stage for t in self.rows}))
        return {
            "version": "prior-auth-timing-v2",
            "observed": len(self.rows),
            "counts": dict(Counter(t.stage for t in self.rows)),
            "stages": {
                s: {
                    "observed": sum(t.stage == s for t in self.rows),
                    "failed": sum(t.stage == s and t.failed for t in self.rows),
                    "inclusive_ns": sum(t.end_ns - t.start_ns for t in self.rows if t.stage == s),
                }
                for s in stages
            },
            "total_ns": next(
                (t.end_ns - t.start_ns for t in self.rows if t.stage == "total"), None
            ),
            "unmeasured": ["queue_wait", "independent_lock_wait", "human_work", "document_wait"],
            "model_accounting": {
                "attempts": self.model_attempts,
                "responses": len(self.usage),
                "missing_response_usage": self.model_attempts - len(self.usage),
                "unknown_input_tokens": self.model_attempts
                - sum(u.input_tokens is not None for u in self.usage),
                "unknown_output_tokens": self.model_attempts
                - sum(u.output_tokens is not None for u in self.usage),
                "unknown_cost": self.model_attempts - sum(u.cost is not None for u in self.usage),
                "known_input_token_subtotal": sum(u.input_tokens or 0 for u in self.usage),
                "known_output_token_subtotal": sum(u.output_tokens or 0 for u in self.usage),
                "known_costs_by_currency": {
                    currency: str(
                        sum(
                            u.cost
                            for u in self.usage
                            if u.cost is not None and u.cost_currency == currency
                        )
                    )
                    for currency in sorted({u.cost_currency for u in self.usage if u.cost_currency})
                },
                "known_subtotals_are_not_complete_cost": True,
            },
            "parallel_spans_are_not_additive_elapsed_time": True,
        }


@dataclass
class TimedGateway:
    gateway: ModelGateway
    profiler: Profiler

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        self.profiler.model_attempts += 1
        with self.profiler.span("model"):
            response = self.gateway.generate(context, request)
            self.profiler.usage.append(response.usage)
            return response
