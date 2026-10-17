"""Safe telemetry output; evaluation journals remain private, full-fidelity evidence."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from agent_harness.contracts import Contract, Count

TraceId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


class TraceHealth(Contract):
    trace_id: TraceId
    spans: Count
    dropped: Count
    export: Literal["accepted", "failed", "empty"]
    flush: Literal["ok", "failed"]
    cleanup: Literal["ok", "failed"]

    @model_validator(mode="after")
    def matching_counts(self) -> Self:
        if (self.export == "empty") != (self.spans == 0):
            raise ValueError("export status differs from span count")
        return self

    @property
    def healthy(self) -> bool:
        return self.export == "accepted" and self.flush == self.cleanup == "ok" and not self.dropped
