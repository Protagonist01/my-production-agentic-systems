"""Opt-in trusted import and payload-free assessment wrappers; no default provider."""

from dataclasses import dataclass, replace
from typing import Annotated, Literal, Self

from agent_harness.contracts import ModelGateway, RunContext, WireContract
from prior_auth.assessment import CRITERIA, assess, retrieve
from prior_auth.candidate import extract
from prior_auth.contracts import (
    AssessmentResult,
    CandidateAssessment,
    CriterionId,
    Digest,
    Id,
    NoteInput,
    Policy,
    Redaction,
    digest,
)
from prior_auth.redaction import redact
from pydantic import Field, model_validator

from prior_auth_documents import Document, DocumentError, Format, NativeTools, normalize
from prior_auth_intake import CaseBinding, DocumentBinding, IntakeDecision, Registry, decide
from prior_auth_profiling import Profiler, TimedGateway


class ImportRequest(WireContract):
    case: CaseBinding
    document: DocumentBinding
    registry: Registry
    policy: Policy
    source_sha256: Digest
    format: Format
    provenance: Literal["invented"] = "invented"
    # Text spans apply to normalized text, never to PDF bytes. Review covers exact pins.
    redactions: tuple[Redaction, ...] = ()
    normalization_sha256: Digest
    extraction_review_ref: Id | None = None
    expected_version: Annotated[int, Field(ge=1)] | None = None


class PreparedImport(WireContract):
    request_sha256: Digest
    source_sha256: Digest
    case: CaseBinding
    binding: DocumentBinding
    decision: IntakeDecision
    normalized: Document | None
    note: NoteInput | None
    policy: Policy
    expected_version: Annotated[int, Field(ge=1)] | None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.decision.admitted != (self.note is not None):
            raise ValueError("intake note/admission differ")
        if self.note is not None:
            if (
                self.normalized is None
                or self.note.text != self.normalized.text
                or self.note.case_id != self.case.case_id
                or self.note.tenant_id != self.case.tenant_id
                or self.note.policy_sha256 != digest(self.policy.canonical_json())
            ):
                raise ValueError("import evidence binding differs")
        return self


def prepare(
    raw: bytes, request: ImportRequest, profiler: Profiler, tools: NativeTools | None = None
) -> PreparedImport:
    import hashlib

    request = ImportRequest.model_validate_json(request.canonical_json())
    if hashlib.sha256(raw).hexdigest() != request.source_sha256:
        raise ValueError("source pin differs")
    document = None
    unsafe = False
    with profiler.span("intake"):
        with profiler.span("extraction"):
            try:
                document = normalize(
                    raw, request.format, replace(tools, profiler=profiler) if tools else None
                )
            except DocumentError as error:
                # Fixed intake state. Original parser code is available to trusted caller
                # on direct normalization; no parser/body output reaches event metadata.
                document = None
                unsafe = str(error) in {"unsafe_xml", "active_narrative", "binary_text"}
        if document is not None and document.text_sha256 != request.normalization_sha256:
            raise ValueError("normalization pin differs")
        reviewed = document is not None and (
            not document.extraction_review_required or request.extraction_review_ref is not None
        )
        with profiler.span("policy_selection"):
            decision = decide(
                request.case,
                request.document,
                request.registry,
                request.policy,
                readable=reviewed,
                safe=not unsafe,
            )
        if decision.admitted and document is not None:
            with profiler.span("redaction"):
                text = redact(document.text, request.redactions)
                document = Document.model_validate_json(
                    document.model_copy(
                        update={"text": text, "text_sha256": digest(text)}
                    ).canonical_json()
                )
    note = None
    if decision.admitted and document is not None:
        note = NoteInput(
            case_id=request.case.case_id,
            tenant_id=request.case.tenant_id,
            text=document.text,
            note_sha256=document.text_sha256,
            service_date=request.case.service_date,
            policy_id=request.policy.policy_id,
            policy_sha256=digest(request.policy.canonical_json()),
            use="initial",
            provenance="invented",
        )
    return PreparedImport(
        request_sha256=digest(request.canonical_json()),
        source_sha256=request.source_sha256,
        case=request.case,
        binding=request.document,
        decision=decision,
        normalized=document if note else None,
        note=note,
        policy=request.policy,
        expected_version=request.expected_version,
    )


@dataclass
class ProfiledAssessor:
    """Existing worker-compatible callable. Gateway must enforce its own approved budget.

    Retrieval here measures the identical deterministic preflight; candidate.extract also
    retrieves internally, so it is not falsely presented as isolated internal retrieval time.
    """

    gateway: ModelGateway
    context: RunContext
    profiler: Profiler

    def __call__(
        self, note: NoteInput, policy: Policy, keys: tuple[CriterionId, ...] = CRITERIA
    ) -> CandidateAssessment | None:
        with self.profiler.span("retrieval"):
            for key in keys:
                retrieve(note, key)
        with self.profiler.span("assessment"):
            return extract(
                TimedGateway(self.gateway, self.profiler),
                self.context,
                note,
                policy,
                criteria_subset=keys,
            )


def checked(
    note: NoteInput, policy: Policy, candidate: CandidateAssessment | None, profiler: Profiler
) -> AssessmentResult:
    with profiler.span("citation_check"):
        return assess(note, policy, candidate)
