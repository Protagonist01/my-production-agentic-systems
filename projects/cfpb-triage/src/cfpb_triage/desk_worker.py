"""One bounded durable worker step; no model dispatch after three claimed attempts."""

import json
from collections.abc import Callable
from typing import Any

from cfpb_triage.desk_store import DeskStore
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import Decision, RouterPolicy, Taxonomy, digest_text

Assessor = Callable[[dict[str, Any]], Decision]


def failed(job: dict[str, Any]) -> Decision:
    complaint = ComplaintInput.model_validate_json(json.dumps(job["complaint"]))
    taxonomy = Taxonomy.model_validate_json(json.dumps(job["taxonomy"]))
    policy = RouterPolicy.model_validate_json(json.dumps(job["policy"]))
    return Decision(
        case_id=complaint.case_id,
        narrative_sha256=digest_text(complaint.narrative),
        taxonomy_sha256=taxonomy.digest(),
        policy_sha256=digest_text(policy.canonical_json()),
        outcome="review_required",
        reason="model_failure",
        prediction=None,
        attempts=(),
        mode="cheap_first",
    )


def step(store: DeskStore, assess: Assessor) -> dict[str, bool]:
    job = store.claim()
    if job is None:
        return {"claimed": False, "published": False}
    decision = failed(job) if job["attempts"] > 3 else assess(job)
    return {"claimed": True, "published": store.finish(job, decision)}
