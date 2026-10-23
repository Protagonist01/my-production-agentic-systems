"""One bounded graph invocation; SQL leases and compare-and-publish own recovery."""

import json
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from prior_auth.contracts import CandidateAssessment, CriterionId, NoteInput, Policy
from prior_auth.review_store import ReviewStore, contract


class Assessor(Protocol):
    def __call__(
        self, note: NoteInput, policy: Policy, keys: tuple[CriterionId, ...]
    ) -> CandidateAssessment | None: ...


class Flow(TypedDict, total=False):
    claimed: bool
    published: bool
    expired: int


class ReviewWorkflow:
    def __init__(self, store: ReviewStore, assessor: Assessor) -> None:
        self.store, self.assessor = store, assessor

    def step(self) -> Flow:
        job: dict[str, Any] | None = None
        candidate: CandidateAssessment | None = None

        def reconcile(state: Flow) -> Flow:
            nonlocal job
            count = self.store.expire()
            job = self.store.claim()
            return {"claimed": job is not None, "expired": count}

        def assess_current(state: Flow) -> Flow:
            nonlocal candidate
            if job is None:
                return {}
            note = contract(job["note"], NoteInput)
            policy = contract(job["policy"], Policy)
            # Three leased attempts maximum. A hard crash can repeat model calls;
            # an exhausted job resolves as qualified review without another call.
            if job["attempts"] < 3:
                proposed = self.assessor(note, policy, tuple(job["criteria"]))
                if proposed is not None:
                    proposed = CandidateAssessment.model_validate_json(proposed.canonical_json())
                    valid = (
                        proposed.case_id == note.case_id
                        and proposed.note_sha256 == note.note_sha256
                        and proposed.policy_sha256 == note.policy_sha256
                        and {c.criterion_id for c in proposed.claims} == set(job["criteria"])
                        and len(proposed.claims) == len(job["criteria"])
                    )
                    if valid:
                        retained = (
                            contract(job["candidate"], CandidateAssessment)
                            if job["candidate"]
                            else None
                        )
                        # Stored retained claims refer to the unchanged prefix.
                        kept = (
                            tuple(
                                c for c in retained.claims if c.criterion_id not in job["criteria"]
                            )
                            if retained
                            else ()
                        )
                        candidate = proposed.model_copy(update={"claims": kept + proposed.claims})
            return {}

        def publish(state: Flow) -> Flow:
            return {"published": self.store.finish(job, candidate) if job else False}

        graph = StateGraph(Flow)
        graph.add_node("reconcile_durable_work", reconcile)
        graph.add_node("assess_redacted_criteria", assess_current)
        graph.add_node("publish_if_current", publish)
        graph.add_edge(START, "reconcile_durable_work")
        graph.add_edge("reconcile_durable_work", "assess_redacted_criteria")
        graph.add_edge("assess_redacted_criteria", "publish_if_current")
        graph.add_edge("publish_if_current", END)
        # No automatic third-party capture of notes, policy or candidate output.
        with tracing_context(enabled=False):
            result = graph.compile().invoke({}, config={"recursion_limit": 6})
        return json.loads(json.dumps(result))  # type: ignore[no-any-return]
