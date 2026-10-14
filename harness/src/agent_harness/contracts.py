"""Versioned wire contracts; no domain rules or evaluator labels in public input."""

import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal, Protocol, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

NonEmpty = Annotated[str, Field(min_length=1)]
Count = Annotated[int, Field(ge=0)]
Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Outcome = Literal["completed", "review_required", "blocked", "failed"]


class Contract(BaseModel):
    """Reject extra fields/coercion; revalidate instances at dispatch boundaries."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        revalidate_instances="always",
        allow_inf_nan=False,
    )
    schema_version: Literal[1] = 1

    def canonical_json(self) -> str:
        # JSON mode preserves wire types; sorting never reorders messages or trims text.
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )


class Budget(Contract):
    max_model_calls: Annotated[int, Field(gt=0)]
    max_tokens: Annotated[int, Field(gt=0)]
    max_cost: Money
    cost_currency: NonEmpty


class CandidateVersions(Contract):
    code_revision: NonEmpty
    candidate: NonEmpty
    data_snapshot: NonEmpty
    policy: NonEmpty
    environment_lock: NonEmpty


class RunContext(Contract):
    run_id: NonEmpty
    tenant_id: NonEmpty
    agent_id: NonEmpty
    case_id: NonEmpty
    trial_id: NonEmpty
    business_event_id: NonEmpty
    mode: Literal["offline_fake", "strict_replay", "fresh_candidate", "monitoring"]
    clock: AwareDatetime
    deadline: AwareDatetime
    seed: Count
    budget: Budget
    versions: CandidateVersions

    @model_validator(mode="after")
    def ordered_deadline(self) -> Self:
        if self.deadline <= self.clock:
            raise ValueError("deadline must be later than the fixed clock")
        return self


class PublicObservation(Contract):
    """A domain adapter supplies reviewed public text and its source reference."""

    reference: NonEmpty
    text: NonEmpty


class AgentInput(Contract):
    request: NonEmpty
    observations: tuple[PublicObservation, ...] = ()


class EvidenceReference(Contract):
    reference: NonEmpty
    kind: Literal["source", "state", "review", "trace", "model", "score"]


class Usage(Contract):
    model_calls: Count
    input_tokens: Count | None
    output_tokens: Count | None
    cost: Money | None
    cost_currency: NonEmpty | None

    @model_validator(mode="after")
    def paired_cost(self) -> Self:
        if (self.cost is None) != (self.cost_currency is None):
            raise ValueError("cost and cost_currency must both be known or both be unknown")
        return self


class Failure(Contract):
    stage: Literal["agent", "model", "tool", "scorer"]
    code: Literal[
        "timeout",
        "rate_limited",
        "invalid_response",
        "budget_exhausted",
        "replay_mismatch",
        "permission_denied",
        "unavailable",
        "scorer_error",
    ]
    message: NonEmpty
    retryable: bool
    evidence: tuple[EvidenceReference, ...] = ()


class AgentResult(Contract):
    run_id: NonEmpty
    case_id: NonEmpty
    trial_id: NonEmpty
    decision: NonEmpty
    outcome: Outcome
    output: str | None = None
    state_change_refs: tuple[NonEmpty, ...] = ()
    review_ref: NonEmpty | None = None
    evidence: tuple[EvidenceReference, ...] = ()
    trace_ref: NonEmpty | None = None
    usage: Usage
    failure: Failure | None = None

    @model_validator(mode="after")
    def consistent_outcome(self) -> Self:
        if (self.outcome == "review_required") != (self.review_ref is not None):
            raise ValueError("only review_required results must carry a review_ref")
        if (self.outcome == "failed") != (self.failure is not None):
            raise ValueError("only failed results must carry a typed failure")
        return self


class ToolCall(Contract):
    call_id: NonEmpty
    name: NonEmpty
    arguments: dict[str, JsonValue]


class ModelMessage(Contract):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: NonEmpty | None = None
    tool_name: NonEmpty | None = None

    @model_validator(mode="after")
    def valid_tool_shape(self) -> Self:
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only assistant messages may contain tool_calls")
        if self.role == "tool":
            if self.tool_call_id is None or self.tool_name is None or self.content is None:
                raise ValueError("tool messages require call ID, name and content")
        elif self.tool_call_id is not None or self.tool_name is not None:
            raise ValueError("tool result identifiers belong only to tool messages")
        if self.content is None and not self.tool_calls:
            raise ValueError("a message needs content or tool calls")
        return self


class ToolSchema(Contract):
    name: NonEmpty
    description: str
    parameters: dict[str, JsonValue]


class ModelRequest(Contract):
    serializer_version: Literal[1] = 1
    provider: NonEmpty
    endpoint: NonEmpty
    model: NonEmpty
    model_revision: NonEmpty | None = None
    messages: Annotated[tuple[ModelMessage, ...], Field(min_length=1)]
    parameters: dict[str, JsonValue]
    tools: tuple[ToolSchema, ...] = ()
    tool_choice: JsonValue = None
    output_schema: dict[str, JsonValue] | None = None

    def fingerprint(self) -> str:
        """Request identity only; replay also needs trial and occurrence identity."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ModelResponse(Contract):
    provider: NonEmpty
    model: NonEmpty
    model_revision: NonEmpty | None = None
    provider_request_id: NonEmpty | None = None
    output: ModelMessage | None = None
    finish_reason: NonEmpty | None = None
    usage: Usage
    failure: Failure | None = None

    @model_validator(mode="after")
    def output_or_failure(self) -> Self:
        if (self.output is None) == (self.failure is None):
            raise ValueError("a response requires exactly one of output or failure")
        if self.output is not None and self.output.role != "assistant":
            raise ValueError("model output must be an assistant message")
        if self.failure is not None and self.failure.stage != "model":
            raise ValueError("model response failures must have stage model")
        return self


class ModelGateway(Protocol):
    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse: ...


class Agent(Protocol):
    def run(
        self,
        context: RunContext,
        input: AgentInput,
        gateway: ModelGateway,
    ) -> AgentResult: ...
