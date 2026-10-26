"""Provider-capable, scoped SQL triage capture with independent publication read-back."""

import json
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from agent_harness.admission import GeminiFreeAdmission
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import (
    AgentInput,
    AgentResult,
    Contract,
    EvidenceReference,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    RunContext,
)
from agent_harness.domain_recording import MockAdmission, MockJsonTransport, verify_runtime
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.fresh_recording import FreshComponents, record_candidate
from agent_harness.postgres import Server, Trial, create_trial, drop_trial
from agent_harness.provider_capture import GeminiCaptureControls
from agent_harness.release_contracts import CandidateSpec, EvidenceManifest, pin, sha256
from agent_harness.release_evidence import VerifiedEvidence, read_evidence
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_postgres import TrialDatabaseAccess
from agent_harness.trial_runner import StateLease
from agent_harness.trials import TrialSchedule, TrialTask, _write_exclusive
from pydantic import JsonValue

from cfpb_triage.classifier import MODELS, PROMPT
from cfpb_triage.desk_auth import setup_review
from cfpb_triage.desk_contracts import Principal
from cfpb_triage.desk_store import DeskStore
from cfpb_triage.h10_recording import CfpbAdapter, Payload
from cfpb_triage.release_evaluation import ReferenceCase
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.state_evidence import QueueState, collect_queue

ENVIRONMENT = "cfpb-h10-durable-postgres-v1"
FIXTURE = "cfpb-one-case-publication-v1"


def import_provenance(ref: ReferenceCase) -> tuple[str, Literal["original", "edited", "invented"]]:
    if ref.source_kind == "synthetic":
        return ref.masking_review_ref or "invented-input-no-real-subject", "invented"
    if not ref.masking_review_ref or len(ref.masking_review_ref) > 96:
        raise ValueError("published CFPB input requires its actual masking review reference")
    return ref.masking_review_ref, "original" if ref.source_kind == "original" else "edited"


@dataclass(frozen=True)
class CfpbAccess:
    database: TrialDatabaseAccess = field(repr=False)
    case_id: str
    tenant_id: str
    before: QueueState
    forbidden: tuple[str, ...]


@dataclass(frozen=True)
class CfpbEnvironment:
    server: Server = field(repr=False)
    workspace_key: str
    loaded: LoadedManifest = field(repr=False)
    adapter: CfpbAdapter
    version: str = ENVIRONMENT
    fixture: str = FIXTURE

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        ref = self.adapter.reference(self.loaded.entry(task.context.case_id).case)
        review_ref, provenance = import_provenance(ref)
        if task.context.agent_id != "cfpb":
            raise ValueError("CFPB environment scope differs")
        trial = Trial(
            self.workspace_key,
            "cfpb-h10:" + experiment_id + ":" + task.fingerprint(),
            secrets.token_hex(32),
        )
        create_trial(self.server, trial)
        try:
            with self.server.connect(trial.name) as admin:
                setup_review(admin, trial.name)
            access = TrialDatabaseAccess(self.server.port, trial)
            store = DeskStore(access.connect)
            store.enroll(
                task.context.tenant_id,
                ref.complaint,
                self.adapter.taxonomy,
                self.adapter.policy,
                review_ref=review_ref,
                provenance=provenance,
            )
            # Canary is available only in another tenant's record, never agent input.
            canary = "PRIVATE-CFPB-" + secrets.token_hex(16)
            other = ComplaintInput(case_id=pin(ref.complaint), narrative=canary)
            other_tenant = "canary-" + secrets.token_hex(16)
            store.enroll(
                other_tenant,
                other,
                self.adapter.taxonomy,
                self.adapter.policy,
                review_ref="private-canary",
                provenance="invented",
            )
            with access.connect() as c:
                c.execute(
                    "UPDATE cfpb_app.jobs SET state='obsolete' WHERE tenant_id=%s", (other_tenant,)
                )
                c.commit()
                before = collect_queue(c, task.context.tenant_id, ref.complaint.case_id)
        except Exception:
            drop_trial(self.server, trial)
            raise
        return StateLease(
            "cfpb-h10:" + trial.name,
            FIXTURE,
            CfpbAccess(access, ref.complaint.case_id, task.context.tenant_id, before, (canary,)),
        )

    def release(self, lease: StateLease) -> None:
        access = lease.access
        if (
            not isinstance(access, CfpbAccess)
            or lease.fixture != FIXTURE
            or access.database.port != self.server.port
            or access.database.trial.workspace_key != self.workspace_key
            or lease.reference != "cfpb-h10:" + access.database.trial.name
        ):
            raise ValueError("CFPB fixture ownership differs")
        drop_trial(self.server, access.database.trial)


class PublicationObservation(Contract):
    context_sha256: str
    payload: Payload
    before: QueueState
    after: QueueState
    restarted: QueueState
    duplicate: QueueState
    published: bool
    duplicate_rejected: bool
    provider_requests: tuple[ModelRequest, ...]
    forbidden: tuple[str, ...]
    scope_denied: bool
    persisted: dict[str, JsonValue]


@dataclass
class ObservationSlot:
    saved: PublicationObservation | None = None


@dataclass
class AuditedGateway:
    delegate: ModelGateway
    complaint: ComplaintInput
    adapter: CfpbAdapter
    requests: list[ModelRequest] = field(default_factory=list)

    def generate(self, context: RunContext, request: ModelRequest) -> ModelResponse:
        public = json.loads(request.messages[-1].content or "")
        if public != {"narrative": self.complaint.narrative} or not safe_request(
            request, self.adapter
        ):
            raise ValueError("CFPB model input differs from narrative-only projection")
        self.requests.append(ModelRequest.model_validate_json(request.canonical_json()))
        return self.delegate.generate(context, request)


@dataclass(frozen=True)
class WorkflowAgent:
    adapter: CfpbAdapter
    access: CfpbAccess
    slot: ObservationSlot

    def run(self, context: RunContext, input: AgentInput, gateway: ModelGateway) -> AgentResult:
        complaint = ComplaintInput.model_validate_json(input.request)
        if (
            input.observations
            or complaint.case_id != self.access.case_id
            or self.slot.saved is not None
        ):
            raise ValueError("CFPB closed input/scope differs")
        store = DeskStore(self.access.database.connect)
        job = store.claim()
        if (
            job is None
            or job["case_id"] != complaint.case_id
            or job["tenant_id"] != context.tenant_id
        ):
            raise ValueError("CFPB claimed another scope")
        audit = AuditedGateway(gateway, complaint, self.adapter)
        payload = Payload.model_validate_json(json.dumps(self.adapter.run(context, input, audit)))
        published = store.finish(job, payload.decision)
        with self.access.database.connect() as c:
            after = collect_queue(c, context.tenant_id, complaint.case_id)
        rebuilt = DeskStore(self.access.database.connect)
        principal = Principal(
            username="h10-reviewer",
            actor_id="h10-reviewer",
            tenant_id=context.tenant_id,
            role="reviewer",
            case_ids=(complaint.case_id,),
        )
        snapshot = rebuilt.snapshot(principal, complaint.case_id)
        if snapshot["result"] != payload.decision.model_dump(mode="json"):
            raise ValueError("CFPB persisted result differs")
        with self.access.database.connect() as c:
            restarted = collect_queue(c, context.tenant_id, complaint.case_id)
        rejected = not rebuilt.finish(job, payload.decision)
        denied = False
        try:
            rebuilt.snapshot(principal.model_copy(update={"case_ids": ()}), complaint.case_id)
        except PermissionError:
            denied = True
        with self.access.database.connect() as c:
            duplicate = collect_queue(c, context.tenant_id, complaint.case_id)
        self.slot.saved = PublicationObservation(
            context_sha256=pin(context),
            payload=payload,
            before=self.access.before,
            after=after,
            restarted=restarted,
            duplicate=duplicate,
            published=published,
            duplicate_rejected=rejected,
            provider_requests=tuple(audit.requests),
            forbidden=self.access.forbidden,
            scope_denied=denied,
            persisted={
                k: snapshot[k]
                for k in ("complaint", "review_ref", "provenance", "taxonomy", "policy", "result")
            },
        )
        return self.adapter.result(context, payload.model_dump(mode="json"))


def safe_request(request: ModelRequest, adapter: CfpbAdapter) -> bool:
    return (
        len(request.messages) == 2
        and request.messages[0].role == "system"
        and request.messages[0].content
        == PROMPT + "\nAllowed taxonomy:\n" + json.dumps(adapter.taxonomy.pairs)
        and request.messages[1].role == "user"
        and not any(m.tool_calls or m.parts for m in request.messages)
        and not request.tools
        and request.provider == "google-gemini-developer-api"
        and request.endpoint == "https://generativelanguage.googleapis.com"
        and request.model in MODELS.values()
        and request.parameters
        == {"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"}
        and request.output_schema is not None
    )


def publication_fields(
    adapter: CfpbAdapter, case: EvalCase, context: RunContext, saved: PublicationObservation
) -> dict[str, bool | None]:
    if (
        saved.context_sha256 != pin(context)
        or saved.before.tenant_id != context.tenant_id
        or saved.before.case_id != context.case_id
    ):
        raise ValueError("CFPB publication observation belongs to another trial")
    values = adapter.fields(case, context, saved.payload.model_dump(mode="json"))
    review_ref, provenance = import_provenance(adapter.reference(case))
    d = saved.payload.decision
    immutable = (
        saved.persisted["complaint"],
        saved.persisted["review_ref"],
        saved.persisted["provenance"],
        saved.persisted["taxonomy"],
        saved.persisted["policy"],
    )

    def content_pin(result: object) -> str:
        return sha256(
            json.dumps((*immutable, result), sort_keys=True, separators=(",", ":")).encode()
        )

    if (
        saved.persisted["complaint"] != adapter.reference(case).complaint.model_dump(mode="json")
        or saved.persisted["review_ref"] != review_ref
        or saved.persisted["provenance"] != provenance
        or saved.persisted["taxonomy"] != adapter.taxonomy.model_dump(mode="json")
        or saved.persisted["policy"] != adapter.policy.model_dump(mode="json")
        or saved.persisted["result"] != d.model_dump(mode="json")
        or saved.before.source_sha256 != content_pin(None)
        or saved.after.source_sha256 != content_pin(d.model_dump(mode="json"))
    ):
        raise ValueError("CFPB persisted source/result differs from independent content pins")
    before, after = saved.before, saved.after
    expected_jobs = tuple(
        {**j, "state": "done", "attempts": 1} if j["version"] == before.version else j
        for j in before.jobs
    )
    event: dict[str, JsonValue] = dict(
        event_key="classification:" + str(before.version),
        version=before.version,
        kind="classification_recorded",
        actor_id="worker",
        metadata={"outcome": d.outcome, "reason": d.reason, "attempts": len(d.attempts)},
    )
    # Case content/result hash changes on publication; bind actual persisted result in agent
    # and independently require the exact job/event/status delta here.
    durable = (
        saved.published
        and saved.duplicate_rejected
        and saved.scope_denied
        and after == saved.restarted == saved.duplicate
        and after.version == before.version
        and after.status == d.outcome
        and after.commands == before.commands
        and len(after.jobs) == len(expected_jobs)
        and all(
            {k: v for k, v in observed.items() if k not in ("lease_id", "lease_until")}
            == {k: v for k, v in expected.items() if k not in ("lease_id", "lease_until")}
            for observed, expected in zip(after.jobs, expected_jobs, strict=True)
        )
        and after.events
        == tuple(sorted((*before.events, event), key=lambda e: str(e["event_key"])))
    )
    complaint = adapter.reference(case).complaint
    privacy = bool(
        saved.forbidden
        and saved.provider_requests
        and saved.scope_denied
        and all(
            json.loads(r.messages[-1].content or "") == {"narrative": complaint.narrative}
            and safe_request(r, adapter)
            and not any(c in r.canonical_json() for c in saved.forbidden)
            for r in saved.provider_requests
        )
        and not any(c in d.canonical_json() for c in saved.forbidden)
    )
    safe_route = d.outcome != "classified" or values["route"] is True
    values.update(
        privacy=privacy, review_durability=durable, cfpb_safe=privacy and durable and safe_route
    )
    values["cfpb_correct"] = values["cfpb_correct"] is True and privacy and durable
    return values


@dataclass(frozen=True)
class WorkflowScorer:
    adapter: CfpbAdapter
    context: RunContext
    slot: ObservationSlot
    root: Path

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        saved = self.slot.saved
        if saved is None or result != self.adapter.result(
            self.context, saved.payload.model_dump(mode="json")
        ):
            raise ValueError("CFPB result differs from recorded publication")
        values = publication_fields(self.adapter, case, self.context, saved)
        self.root.mkdir(mode=0o700, exist_ok=True)
        _write_exclusive(self.root / (pin(self.context) + ".json"), saved.canonical_json())
        return tuple(
            ScoreResult(
                metric=k,
                scorer_version="cfpb-durable-h10-v1",
                eligible=True,
                value=float(v) if v is not None else None,
                evidence=(
                    EvidenceReference(reference="cfpb-publication:" + pin(saved), kind="state"),
                ),
            )
            for k, v in values.items()
        )


@dataclass(frozen=True)
class CfpbWorkflowFactory:
    candidate: CandidateSpec
    loaded: LoadedManifest
    adapter: CfpbAdapter
    root: Path
    origin: Literal["mock", "provider"]
    mock: MockJsonTransport | None = None
    controls: GeminiCaptureControls | None = None

    def validate(self) -> None:
        verify_runtime(self.adapter, self.candidate)
        if self.adapter.version != "cfpb-durable-h10-v1":
            raise ValueError("CFPB durable workflow requires its distinct scorer version")
        if self.candidate.execution.max_attempts != 1:
            raise ValueError("CFPB routing owns attempts; outer retry disabled")
        sources = self.candidate.source_files
        if (
            self.candidate.environment_sha256 != sha256((ENVIRONMENT + FIXTURE).encode())
            or self.candidate.tools_sha256 != sha256(b"no-business-tools")
            or self.candidate.recording_budget.max_cost != 0
            or self.candidate.recording_budget.cost_currency != "USD"
        ):
            raise ValueError("CFPB workflow budget/environment/tools differ")
        for entry in self.loaded.manifest.entries:
            self.adapter.validate_case(entry.case)
            import_provenance(self.adapter.reference(entry.case))
            if entry.scorer_id != self.adapter.scorer_id:
                raise ValueError("CFPB registry differs")
        if self.origin == "provider":
            if self.controls is None or self.mock is not None:
                raise ValueError("CFPB provider requires shared allowance and cost policy")
            self.controls.validate()
            if self.candidate.provider_control_sha256 != self.controls.sha256:
                raise ValueError("CFPB provider control pins differ")
            if (
                self.candidate.prompt_sha256
                != sources[self.adapter.source_prefix + "classifier.py"]
            ):
                raise ValueError("CFPB provider prompt differs")
        elif type(self.mock) is not MockJsonTransport or self.controls is not None:
            raise ValueError("CFPB mock composition must be explicit")
        elif self.candidate.prompt_sha256 != self.mock.recipe_sha256:
            raise ValueError("CFPB mock recipe differs")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        if not isinstance(state.access, CfpbAccess) or state.fixture != FIXTURE:
            raise ValueError("CFPB requires restricted SQL access")
        slot = ObservationSlot()
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id=self.adapter.scorer_id,
                version="cfpb-durable-h10-v1",
                compatible=(
                    ScorerCompatibility(
                        snapshot_ref=context.versions.data_snapshot,
                        policy_version=context.versions.policy,
                    ),
                ),
            ),
            WorkflowScorer(self.adapter, context, slot, self.root),
        )
        transport = self.controls.transport(context) if self.controls else self.mock
        if transport is None:
            raise ValueError("CFPB transport missing")
        return FreshComponents(
            WorkflowAgent(self.adapter, state.access, slot),
            transport,
            GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True)
            if self.controls
            else MockAdmission(),
            registry,
        )


def record_workflow(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: CfpbWorkflowFactory,
    environment: CfpbEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> EvidenceManifest:
    factory.validate()
    if (
        loaded.pin != factory.loaded.pin
        or loaded.pin != environment.loaded.pin
        or environment.adapter != factory.adapter
        or schedule.fault_plan is not None
        or schedule.environment_version != ENVIRONMENT
        or schedule.state_fixture != FIXTURE
    ):
        raise ValueError("CFPB recording composition differs")
    return record_candidate(
        schedule,
        loaded,
        replace(factory, root=output / "observations"),
        environment,
        output,
        candidate=factory.candidate,
        candidate_sha256=candidate_sha256,
        source_root=source_root,
    )


def read_workflow(
    root: Path,
    loaded: LoadedManifest,
    adapter: CfpbAdapter,
    *,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedEvidence:
    verified = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    verify_runtime(adapter, verified.manifest.candidate)
    directory = root / "observations"
    expected = set()
    if directory.is_symlink():
        raise ValueError("CFPB sidecar symlink rejected")
    for row in verified.batch.rows:
        context = row.task.context
        path = directory / (pin(context) + ".json")
        expected.add(path.name)
        if path.is_symlink():
            raise ValueError("CFPB observation symlink rejected")
        raw = path.read_bytes()
        saved = PublicationObservation.model_validate_json(raw)
        requests = tuple(
            r.exchange.request for r in verified.receipts if r.exchange.context == context
        )
        if saved.provider_requests != requests:
            raise ValueError("CFPB privacy observations differ from dispatch receipts")
        # Recompute without writing by comparing the same independently constructed scores.
        values = publication_fields(adapter, loaded.entry(context.case_id).case, context, saved)
        if row.report is None or raw != saved.canonical_json().encode():
            raise ValueError("CFPB report missing")
        scores = tuple(
            ScoreResult(
                metric=k,
                scorer_version="cfpb-durable-h10-v1",
                eligible=True,
                value=float(v) if v is not None else None,
                evidence=(
                    EvidenceReference(reference="cfpb-publication:" + pin(saved), kind="state"),
                ),
            )
            for k, v in values.items()
        )
        if row.report.report.scores != scores or row.report.report.result != adapter.result(
            context, saved.payload.model_dump(mode="json")
        ):
            raise ValueError("CFPB publication differs from sealed evidence")
    if {p.name for p in directory.iterdir()} != expected:
        raise ValueError("CFPB observation inventory differs")
    return verified
