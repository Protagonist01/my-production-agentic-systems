"""Closed executable fault plans and metadata-only evidence; no agent capabilities."""

import hashlib
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from agent_harness.contracts import Contract, NonEmpty

FaultTiming = Literal["before_dispatch", "after_dispatch", "after_commit", "on_resume"]
FaultKind = Literal[
    "malformed_output",
    "outage",
    "stale_read",
    "tool_timeout",
    "duplicate_delivery",
    "injection_content",
]


def digest(value: Contract) -> str:
    return hashlib.sha256(value.canonical_json().encode("utf-8")).hexdigest()


class FaultRule(Contract):
    scenario_id: NonEmpty
    kind: FaultKind
    target: NonEmpty
    timing: FaultTiming
    first_occurrence: Annotated[int, Field(ge=1, le=100)] = 1
    last_occurrence: Annotated[int, Field(ge=1, le=100)] = 1
    payload: JsonValue = None

    @model_validator(mode="after")
    def supported_boundary(self) -> Self:
        if self.first_occurrence > self.last_occurrence:
            raise ValueError("fault occurrence window is reversed")
        if self.kind == "injection_content":
            valid = self.target == "input" and self.timing == "before_dispatch"
            valid = valid and self.first_occurrence == self.last_occurrence == 1
        elif self.kind in ("malformed_output", "outage"):
            valid = self.target == "model" and self.timing == (
                "after_dispatch" if self.kind == "malformed_output" else "before_dispatch"
            )
        else:
            valid = self.target.startswith("tool:") and len(self.target) > 5
            valid = (
                valid
                and self.timing
                in {
                    "stale_read": ("after_dispatch",),
                    "tool_timeout": ("before_dispatch", "after_commit", "on_resume"),
                    "duplicate_delivery": ("after_dispatch",),
                }[self.kind]
            )
        if not valid:
            raise ValueError("unsupported fault target/timing")
        if self.kind in ("injection_content", "malformed_output"):
            if not isinstance(self.payload, str) or not self.payload.strip():
                raise ValueError("text fault requires a nonempty string payload")
        elif self.kind != "stale_read" and self.payload is not None:
            raise ValueError("this fault does not accept a payload")
        return self


class FaultPlan(Contract):
    version: NonEmpty
    rules: Annotated[tuple[FaultRule, ...], Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def unique_rules(self) -> Self:
        if len({rule.scenario_id for rule in self.rules}) != len(self.rules):
            raise ValueError("duplicate fault scenario ID")
        return self


class FaultEvent(Contract):
    scenario_id: NonEmpty
    kind: FaultKind
    target: NonEmpty
    timing: FaultTiming
    occurrence: Annotated[int, Field(ge=1, le=100)]


class FaultEvidence(Contract):
    plan_version: NonEmpty
    plan_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    declaration_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    seed: Annotated[int, Field(ge=0)]
    expected_scenarios: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    required_invariants: Annotated[tuple[NonEmpty, ...], Field(min_length=1)]
    events: tuple[FaultEvent, ...]

    @model_validator(mode="after")
    def unique_events(self) -> Self:
        if len(set(self.expected_scenarios)) != len(self.expected_scenarios):
            raise ValueError("duplicate expected fault scenario")
        if len(set(self.required_invariants)) != len(self.required_invariants):
            raise ValueError("duplicate required fault invariant")
        ids = [event.scenario_id for event in self.events]
        if len(set(ids)) != len(ids) or set(ids) - set(self.expected_scenarios):
            raise ValueError("duplicate or unexpected fault event")
        return self

    @property
    def complete(self) -> bool:
        return {event.scenario_id for event in self.events} == set(self.expected_scenarios)
