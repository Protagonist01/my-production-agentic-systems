"""Bounded v2 worker step. CLI publishes an unavailable result, never loads keys."""

import json
from collections.abc import Callable
from typing import Any

from cfpb_triage.evaluation_store import EvaluationStore
from cfpb_triage.measurement import CURRENT, Profiler
from cfpb_triage.scope_routing import ScopeAttempt, ScopeDecision, ScopePolicy
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import Taxonomy, digest_text


def unavailable(claim: dict[str, Any]) -> ScopeDecision:
    complaint = ComplaintInput.model_validate_json(json.dumps(claim["complaint"]))
    taxonomy = Taxonomy.model_validate_json(json.dumps(claim["taxonomy"]))
    policy = ScopePolicy.model_validate_json(json.dumps(claim["policy"]))
    return ScopeDecision(
        case_id=complaint.case_id,
        narrative_sha256=digest_text(complaint.narrative),
        taxonomy_sha256=taxonomy.digest(),
        policy_sha256=digest_text(policy.canonical_json()),
        scope=None,
        action="review_required",
        reason="operational_failure",
        prediction=None,
        attempts=(
            ScopeAttempt(route="cheap", model="no-provider-dispatch", failure="unavailable"),
        ),
        timings=(),
    )


def step_evaluation(
    store: EvaluationStore, assess: Callable[[dict[str, Any]], ScopeDecision] = unavailable
) -> dict[str, bool]:
    profiler = Profiler()
    token = CURRENT.set(profiler)
    try:
        with profiler.span("claim"):
            claim = store.claim_evaluation()
        if claim is None:
            return {"claimed": False, "published": False}
        # An expired claim may already have consumed a request. Do not redispatch it.
        decision = unavailable(claim) if claim["attempts"] > 1 else assess(claim)
        existing = {t.canonical_json() for t in profiler.rows}
        profiler.rows.extend(t for t in decision.timings if t.canonical_json() not in existing)
        combined = decision.model_copy(update={"timings": tuple(profiler.rows)})
        with profiler.span("publication"):
            published = store.finish_evaluation(claim, combined)
        # Publication/commit profiling is captured in the separate service receipt so it
        # cannot be falsely claimed to have been known before its own transaction committed.
        from cfpb_triage.desk_contracts import Principal

        user = Principal(
            username="trusted-worker",
            tenant_id=claim["tenant_id"],
            actor_id=claim["actor_id"],
            role="reviewer",
            case_ids=(claim["case_id"],),
        )
        store.record_profile(user, claim["case_id"], tuple(profiler.rows), worker=True)
        return {"claimed": True, "published": published}
    finally:
        CURRENT.reset(token)
