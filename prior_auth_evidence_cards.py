"""Authenticated synthetic-case evidence cards: policy requirement plus document sources."""

import json
from typing import Literal

from agent_harness.contracts import WireContract
from prior_auth.assessment import assess
from prior_auth.contracts import (
    CandidateAssessment,
    CriterionId,
    Digest,
    NoteInput,
    Policy,
    Span,
    State,
    digest,
)
from prior_auth.review_contracts import Principal, StateChanged
from prior_auth.review_store import ReviewStore

from prior_auth_intake_readback import IntakeReader, SourceLocation


class DocumentCitation(WireContract):
    evidence: Span
    locations: tuple[SourceLocation, ...]


class EvidenceCard(WireContract):
    criterion: CriterionId
    state: State
    policy_url: str
    policy_source_sha256: Digest
    policy_text_sha256: Digest
    policy_requirement: Span
    policy_review_status: str
    note_sha256: Digest
    document_citations: tuple[DocumentCitation, ...]
    source_mapping: Literal["mapped", "incomplete", "no_evidence"]
    reason: str
    clinical_validation: Literal[False] = False


class EvidenceReader:
    def __init__(self, store: ReviewStore) -> None:
        self.store, self.sources = store, IntakeReader(store.connect)

    def cards(
        self, user: Principal, case_id: str, *, expected_version: int
    ) -> tuple[EvidenceCard, ...]:
        # Snapshot authenticates case/tenant scope before retrieving any evidence.
        snapshot = self.store.snapshot(user, case_id)
        note = NoteInput.model_validate_json(json.dumps(snapshot["note"]))
        policy = Policy.model_validate_json(json.dumps(snapshot["policy"]))
        if snapshot["version"] != expected_version or note.provenance != "invented":
            raise StateChanged("current synthetic case/version required")
        if snapshot["result"] is None or snapshot["status"] == "assessing":
            raise StateChanged("assessment not yet published")
        candidate = (
            CandidateAssessment.model_validate_json(json.dumps(snapshot["candidate"]))
            if snapshot["candidate"]
            else None
        )
        checked = assess(note, policy, candidate)
        if checked.model_dump(mode="json") != snapshot["result"]:
            raise StateChanged("saved assessment differs from pinned evidence")
        with self.store.transaction() as c:
            documents = c.execute(
                "SELECT document_id FROM prior_auth_intake.documents "
                "WHERE tenant_id=%s AND case_id=%s ORDER BY document_id",
                (user.tenant_id, case_id),
            ).fetchall()
        result = []
        for claim in checked.claims:
            criterion = next(c for c in policy.criteria if c.criterion_id == claim.criterion_id)
            citations = []
            for span in claim.evidence:
                span.require(note.text)
                locations = []
                for document in documents:
                    try:
                        location = self.sources.locate(
                            user,
                            case_id,
                            document["document_id"],
                            note_sha256=note.note_sha256,
                            start=span.start,
                            end=span.end,
                        )
                        locations.append(location)
                    except ValueError as error:
                        if isinstance(error, StateChanged):
                            raise
                        # The span may belong to another imported document. Do not
                        # invent a location or count an unmapped span as cited.
                        continue
                citations.append(DocumentCitation(evidence=span, locations=tuple(locations)))
            mapping: Literal["mapped", "incomplete", "no_evidence"] = "no_evidence"
            if citations:
                mapping = "mapped" if all(c.locations for c in citations) else "incomplete"
            result.append(
                EvidenceCard(
                    criterion=claim.criterion_id,
                    state=claim.state,
                    policy_url=policy.source_url,
                    policy_source_sha256=policy.source_sha256,
                    policy_text_sha256=policy.text_sha256,
                    policy_requirement=criterion.source,
                    policy_review_status=policy.review_status,
                    note_sha256=note.note_sha256,
                    document_citations=tuple(citations),
                    source_mapping=mapping,
                    reason=claim.reason,
                )
            )
        # A concurrent document delivery must not make the assembled cards appear current.
        current = self.store.snapshot(user, case_id)
        if (
            current["version"] != expected_version
            or current["note"]["note_sha256"] != note.note_sha256
            or (
                digest(Policy.model_validate_json(json.dumps(current["policy"])).canonical_json())
                != note.policy_sha256
            )
        ):
            raise StateChanged("case changed while assembling evidence")
        return tuple(result)
