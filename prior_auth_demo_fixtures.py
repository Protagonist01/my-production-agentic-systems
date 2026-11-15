"""Explicit invented demo records and a scripted gateway, never a model-quality result."""

import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, RunContext, Usage
from agent_harness.offline_example import example_context
from prior_auth.candidate import QuoteClaim
from prior_auth.contracts import NoteInput, Policy, digest

from prior_auth_complete_citations import VERSION, extract_complete
from prior_auth_demo_runtime import Scope

COMPLETE = """The patient is an adult with documented obstructive sleep apnea.
CPAP education completed prior to use.
Clinical evaluation completed with positive OSA diagnosis.
Positive attended PSG performed in a sleep laboratory.
Sleep test previously ordered by treating physician and furnished under physician supervision.
AHI: 18 events/hour. 2 hours of recorded sleep. 36 total recorded events.
"""
EDUCATION = "CPAP education completed prior to use."


def note(case_id: str, policy: Policy, *, missing_education: bool = False) -> NoteInput:
    text = COMPLETE.replace(EDUCATION + "\n", "") if missing_education else COMPLETE
    return NoteInput(
        case_id=case_id,
        tenant_id="demo",
        text=text,
        note_sha256=digest(text),
        service_date=policy.effective_from,
        policy_id=policy.policy_id,
        policy_sha256=digest(policy.canonical_json()),
        use="initial",
        provenance="invented",
    )


class ScriptedGateway:
    """Returns scripted complete-note citations; explicitly not an evaluated AI model."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        if context.mode != "offline_fake":
            raise PermissionError("scripted gateway cannot claim fresh provider output")
        self.requests.append(request)
        payload = json.loads(request.messages[1].content or "")
        claim = QuoteClaim(
            criterion_id=payload["criterion"]["criterion_id"],
            state="met",
            quotes=(EDUCATION,)
            if payload["criterion"]["criterion_id"] == "education"
            and "--- Reviewed supplemental evidence ---" in payload["full_note"]
            and EDUCATION in payload["full_note"]
            else (payload["full_note"],),
            rationale="Scripted invented demo; server checks evidence.",
        )
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content=claim.canonical_json()),
            usage=Usage(
                model_calls=1, input_tokens=0, output_tokens=0, cost=Decimal(0), cost_currency="USD"
            ),
        )


def requests(notes: Iterable[NoteInput], policy: Policy) -> tuple[ModelRequest, ...]:
    gateway = ScriptedGateway()
    for value in notes:
        context = example_context("invented-demo", "invented-demo").model_copy(
            update={
                "tenant_id": value.tenant_id,
                "case_id": value.case_id,
                "versions": example_context("invented-demo", "invented-demo").versions.model_copy(
                    update={"candidate": VERSION}
                ),
            }
        )
        extract_complete(gateway, context, value, policy)
    return tuple(gateway.requests)


def fake_scope(
    scope_id: str, notes: tuple[NoteInput, ...], policy: Policy, *, now: datetime
) -> Scope:
    # Supplemental note bytes must be forecast explicitly before registration.
    planned = requests(notes, policy)
    return Scope(
        scope_id=scope_id,
        tenant_id="demo",
        case_ids=tuple(dict.fromkeys(n.case_id for n in notes)),
        mode="offline_fake",
        authorization_ref="owner-approved-synthetic-demo-scripted-only",
        code_revision="invented-demo-offline",
        environment_sha256=digest("invented-demo-offline"),
        starts_at=now,
        expires_at=now + timedelta(hours=1),
        max_attempts=len(planned),
        max_tokens=max(1, len(planned)) * GEMINI_TOKEN_CEILING,
        request_sha256s=tuple(dict.fromkeys(r.fingerprint() for r in planned)),
    )
