"""Separately versioned citation-completeness candidate; no clinical rule replacement."""

import json
from dataclasses import dataclass

from agent_harness.contracts import (
    ModelGateway,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RunContext,
)
from prior_auth.assessment import CRITERIA
from prior_auth.candidate import extract
from prior_auth.contracts import CandidateAssessment, CriterionId, NoteInput, Policy, digest

VERSION = "prior-auth-complete-citations-v1"
SUPPLEMENT = """
Citation completeness:
Before returning a state, check every subcondition in the supplied policy criterion.
For a conjunction, cite the passages supporting each applicable subcondition, including
when they are in separate sentences or documents. A single nearby fact is not enough.
Include relevant negative or competing observations; do not omit context that changes
the finding. If the required support or interpretation is incomplete, return insufficient.
Use only exact quotations from the note and the supplied policy. Do not infer rounding,
resolve competing observations, or substitute another policy's thresholds.
"""


@dataclass
class CompleteGateway:
    delegate: ModelGateway

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        request = ModelRequest.model_validate_json(request.canonical_json())
        if len(request.messages) != 2 or request.messages[0].role != "system":
            raise ValueError("expected pinned criterion-extraction request")
        payload = json.loads(request.messages[1].content or "")
        if payload["criterion"]["criterion_id"] not in CRITERIA:
            raise ValueError("known criterion required")
        updated = request.model_copy(
            update={
                "messages": (
                    ModelMessage(
                        role="system", content=(request.messages[0].content or "") + SUPPLEMENT
                    ),
                    request.messages[1],
                )
            }
        )
        # The delegate sees the final bytes before any admission/fingerprint occurs.
        return self.delegate.generate(context, updated)


def extract_complete(
    gateway: ModelGateway,
    context: RunContext,
    note: NoteInput,
    policy: Policy,
    keys: tuple[CriterionId, ...] = CRITERIA,
) -> CandidateAssessment | None:
    note = NoteInput.model_validate_json(note.canonical_json())
    policy = Policy.model_validate_json(policy.canonical_json())
    if (
        note.provenance != "invented"
        or note.use != "initial"
        or note.service_date < policy.effective_from
        or (policy.effective_until is not None and note.service_date >= policy.effective_until)
        or context.versions.candidate != VERSION
        or (note.policy_sha256 != digest(policy.canonical_json()))
    ):
        raise PermissionError("explicit invented complete-citation candidate required")
    return extract(CompleteGateway(gateway), context, note, policy, criteria_subset=keys)
