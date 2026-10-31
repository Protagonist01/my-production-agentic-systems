"""Explicit prospective routing composition; no credential discovery or live-scope activation."""

import json
import subprocess
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from agent_harness.admission import GEMINI_TOKEN_CEILING, GeminiFreeAdmission
from agent_harness.cases import LoadedManifest
from agent_harness.contracts import AgentResult, ModelRequest, ModelResponse, RunContext
from agent_harness.cost_accounting import (
    AccountedTransport,
    CostAccounting,
    FreeTariff,
    control_pin,
    verify_accounting,
)
from agent_harness.evaluation import EvalCase, ScoreResult
from agent_harness.fresh_recording import FreshComponents, record_candidate
from agent_harness.gateway import ModelExchange
from agent_harness.isolated_transport import IsolatedTransport
from agent_harness.provider_budget import AttemptLedger, BudgetedTransport
from agent_harness.release_contracts import (
    AttemptReceipt,
    CandidateSpec,
    EvidenceManifest,
    pin,
    sha256,
)
from agent_harness.release_evidence import VerifiedEvidence, read_evidence
from agent_harness.routing_budget import (
    RoutingExtension,
    acknowledge_canary,
    behavior_pin,
    historical_pins,
    load,
    stop,
)
from agent_harness.scorers import ScorerCompatibility, ScorerRegistry, ScorerSpec
from agent_harness.trial_runner import StateLease, WorkerCleanupError
from agent_harness.trials import TrialSchedule, TrialTask, _write_exclusive

from olist_support.h10_config import verify_runtime
from olist_support.h10_runtime import ObservationSlot
from olist_support.policy import POLICY_VERSION
from olist_support.policy_cases import external
from olist_support.routing_evaluation import SCORER_VERSION, private_case
from olist_support.routing_h10 import (
    FIXTURE,
    SCORER_ID,
    RoutingAgent,
    RoutingEnvironment,
    RoutingScorer,
    checked_access,
    fingerprints,
    validate_population,
    verify_observations,
)

Variant = Literal["candidate", "legacy"]


def controlled_fingerprints(
    route: ModelRequest, sources: dict[str, str], variant: Variant
) -> dict[str, str]:
    values = fingerprints(route, sources, variant)
    values["scorer_sha256"] = sha256(
        json.dumps(
            {
                "base": values["scorer_sha256"],
                "controlled_scorer": sources[
                    "projects/olist-support/src/olist_support/routing_provider.py"
                ],
            },
            sort_keys=True,
        ).encode()
    )
    return values


def validate_candidate(
    candidate: CandidateSpec, route: ModelRequest, variant: Variant, control_sha256: str
) -> None:
    candidate = CandidateSpec.model_validate_json(candidate.canonical_json())
    route = ModelRequest.model_validate_json(route.canonical_json())
    verify_runtime(candidate)
    if (
        variant not in ("candidate", "legacy")
        or candidate.provider_control_sha256 != control_sha256
        or any(
            getattr(candidate, k) != v
            for k, v in controlled_fingerprints(route, candidate.source_files, variant).items()
        )
        or (route.provider, route.endpoint, route.model)
        != (
            "google-gemini-developer-api",
            "https://generativelanguage.googleapis.com",
            "gemini-3.5-flash-lite",
        )
        or route.parameters
        != {"temperature": 0.0, "max_output_tokens": 512, "thinking_level": "LOW"}
        or route.tools
        or route.tool_choice
        or route.output_schema is not None
        or candidate.execution.max_attempts != 1
        or candidate.execution.attempt_timeout_seconds != 30.0
        or candidate.recording_budget.max_model_calls != 3
        or candidate.recording_budget.max_tokens != 3 * GEMINI_TOKEN_CEILING
        or candidate.recording_budget.max_cost != 0
        or candidate.recording_budget.cost_currency != "USD"
    ):
        raise ValueError("controlled routing candidate/route/budgets differ")


@dataclass(frozen=True)
class RoutingCaptureControls:
    api_key: str = field(repr=False)
    ledger: AttemptLedger
    tariff: FreeTariff
    tariff_sha256: str
    project_sha256: str
    # Explicit fake HTTP can exercise the SDK/workers, but must ALWAYS produce mock origin.
    test_http: httpx.MockTransport | None = field(default=None, repr=False, compare=False)

    @property
    def origin(self) -> Literal["mock", "provider"]:
        return "mock" if self.test_http is not None else "provider"

    def scope(self) -> RoutingExtension:
        with self.ledger.connect() as db:
            self.ledger.authorization(db)
            extension = load(db, self.ledger)
        if extension is None:
            raise ValueError("explicit routing extension required")
        return extension

    @property
    def scope_sha256(self) -> str:
        return sha256(
            json.dumps(
                {
                    "history": historical_pins(self.ledger),
                    "routing": self.ledger.routing_extension_sha256,
                },
                sort_keys=True,
            ).encode()
        )

    @property
    def sha256(self) -> str:
        return control_pin(
            self.ledger.allowance_sha256, self.tariff_sha256, self.project_sha256, self.scope_sha256
        )

    def validate(self) -> None:
        if (
            not self.api_key
            or pin(self.tariff) != self.tariff_sha256
            or self.ledger.routing_extension_sha256 is None
        ):
            raise ValueError("explicit key, tariff and routing scope required")
        if self.scope().execution_origin != self.origin:
            raise ValueError("routing transport origin differs from its authorized scope")
        with self.ledger.connect() as db:
            grant = self.ledger.authorization(db)
        now = datetime.now(UTC)
        if (
            grant.max_attempts != 614
            or grant.project_sha256 != self.project_sha256
            or self.tariff.project_sha256 != self.project_sha256
            or self.tariff.models != ("gemini-3.5-flash-lite",)
            or not grant.approved_at <= now < grant.expires_at
            or not self.tariff.reviewed_at <= now < self.tariff.expires_at
            or (self.test_http is not None and type(self.test_http) is not httpx.MockTransport)
        ):
            raise ValueError("routing project/tariff/interval differs")

    def transport(self, context: RunContext) -> AccountedTransport:
        self.validate()
        from agent_harness.gemini import GeminiTransport

        raw = GeminiTransport(self.api_key, free_tier_confirmed=True, http_transport=self.test_http)
        return AccountedTransport(
            BudgetedTransport(raw, self.ledger, context, self.project_sha256),
            self.tariff,
            self.tariff_sha256,
            self.project_sha256,
            self.ledger.allowance_sha256,
            self.scope_sha256,
        )


@dataclass(frozen=True)
class ControlledRoutingScorer(RoutingScorer):
    ledger: AttemptLedger

    def score(self, case: EvalCase, result: AgentResult) -> tuple[ScoreResult, ...]:
        try:
            scores = super().score(case, result)
        except Exception:
            stop(self.ledger, "scorer_observation_failed")
            raise
        if any(s.metric in ("state_safety", "routing_safe") and s.value != 1.0 for s in scores):
            stop(self.ledger, "unsafe_or_unknown_state")
        return scores


@dataclass(frozen=True)
class RoutingProviderFactory:
    candidate: CandidateSpec
    route: ModelRequest
    variant: Variant
    controls: RoutingCaptureControls
    observation_root: Path

    @property
    def origin(self) -> Literal["mock", "provider"]:
        return self.controls.origin

    def validate(self) -> None:
        self.controls.validate()
        validate_candidate(self.candidate, self.route, self.variant, self.controls.sha256)
        scope = self.controls.scope()
        if behavior_pin(self.candidate) != scope.candidate_behavior_sha256[self.variant]:
            raise ValueError("routing candidate behavior differs from frozen scope")

    def build(self, context: RunContext, state: StateLease) -> FreshComponents:
        self.validate()
        access = checked_access(context, state)
        scope = self.controls.scope()
        if (
            context.versions.candidate != scope.candidate_versions[self.variant]
            or context.versions.code_revision != scope.code_revision
            or context.versions.environment_lock != scope.environment_lock
        ):
            raise ValueError("routing context differs from candidate scope")
        slot = ObservationSlot()
        registry = ScorerRegistry()
        registry.register(
            ScorerSpec(
                scorer_id=SCORER_ID,
                version=SCORER_VERSION,
                compatible=(
                    ScorerCompatibility(
                        snapshot_ref=context.versions.data_snapshot, policy_version=POLICY_VERSION
                    ),
                ),
            ),
            ControlledRoutingScorer(
                context, access, slot, self.observation_root, self.controls.ledger
            ),
        )
        return FreshComponents(
            RoutingAgent(access, self.route, slot, self.variant),
            self.controls.transport(context),
            GeminiFreeAdmission(free_tier_confirmed=True),
            registry,
        )


@dataclass(frozen=True)
class ControlledEnvironment:
    base: RoutingEnvironment
    ledger: AttemptLedger

    @property
    def version(self) -> str:
        return self.base.version

    @property
    def fixture(self) -> str:
        return self.base.fixture

    def prepare(self, experiment_id: str, task: TrialTask) -> StateLease:
        try:
            return self.base.prepare(experiment_id, task)
        except Exception:
            stop(self.ledger, "fixture_setup_failed")
            raise

    def release(self, lease: StateLease) -> None:
        try:
            self.base.release(lease)
        except Exception:
            stop(self.ledger, "owned_cleanup_failed")
            raise


@dataclass(frozen=True)
class RoutingCanaryWorker:
    controls: RoutingCaptureControls
    context: RunContext

    def generate(self, request: ModelRequest, *, timeout_seconds: float) -> ModelResponse:
        return self.controls.transport(self.context).generate(
            request, timeout_seconds=min(30.0, timeout_seconds)
        )


def _capture_canary(
    context: RunContext,
    request: ModelRequest,
    controls: RoutingCaptureControls,
    output: Path,
    *,
    source_root: Path,
) -> dict[str, object]:
    """One owned bounded SDK request, durable ledger receipt and exclusive private files."""
    controls.validate()
    scope = controls.scope()
    matches = [
        s
        for s in scope.slots[:2]
        if (s.run_id, s.case_id, s.trial_id, s.request_sha256)
        == (context.run_id, context.case_id, context.trial_id, pin(request))
    ]
    if len(matches) != 1:
        raise ValueError("canary differs from the exact prospective slot")
    if controls.origin == "provider":
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source_root, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=source_root, text=True
        ).strip()
        if dirty or revision != scope.code_revision:
            raise ValueError("canary requires the clean final source")
    output = external(output)
    output.mkdir(mode=0o700)
    started = datetime.now(UTC)
    transport = IsolatedTransport(RoutingCanaryWorker(controls, context))
    try:
        response = transport.generate(request, timeout_seconds=90.0)
    except Exception:
        stop(controls.ledger, "canary_capture_failed")
        raise
    passed = False
    if response.failure is None and response.accounting is not None:
        verify_accounting(request, response, expected_control_sha256=controls.sha256)
        account = CostAccounting.model_validate_json(json.dumps(response.accounting))
        raw = response.model_copy(update={"usage": account.raw_usage, "accounting": None})
        with controls.ledger.connect() as db:
            saved = db.execute(
                "SELECT response_pin,canary_pass,document FROM routing_settlements WHERE ordinal=?",
                (matches[0].ordinal,),
            ).fetchone()
        passed = (
            saved is not None
            and saved[0] == pin(raw)
            and saved[1] == 1
            and saved[2] == raw.canonical_json()
        )
    if not passed:
        stop(controls.ledger, "canary_capture_failed")
    finished = datetime.now(UTC)
    receipt = AttemptReceipt(
        execution_id=context.run_id,
        nonce=uuid4().hex,
        started_at=started,
        finished_at=finished,
        exchange=ModelExchange(context=context, occurrence=1, request=request, response=response),
    )
    _write_exclusive(output / "canary-receipt.json", receipt.canonical_json())
    if passed:
        acknowledge_canary(controls.ledger, receipt)
    report: dict[str, object] = {
        "version": "olist-routing-canary-capture-v1",
        "origin": controls.origin,
        "passed": passed,
        "control_sha256": controls.sha256,
        "extension_sha256": pin(scope),
        "receipt_sha256": pin(receipt),
        "timing": transport.last_timing.model_dump(mode="json") if transport.last_timing else None,
        "quality_measured": False,
        "release_allowed": False,
    }
    _write_exclusive(output / "canary.json", json.dumps(report, sort_keys=True))
    return report


def capture_canary(
    context: RunContext,
    request: ModelRequest,
    controls: RoutingCaptureControls,
    output: Path,
    *,
    source_root: Path,
) -> dict[str, object]:
    controls.validate()
    try:
        return _capture_canary(context, request, controls, output, source_root=source_root)
    except Exception:
        stop(controls.ledger, "canary_capture_failed")
        raise


def record_controlled(
    schedule: TrialSchedule,
    loaded: LoadedManifest,
    factory: RoutingProviderFactory,
    environment: RoutingEnvironment,
    output: Path,
    *,
    candidate_sha256: str,
    source_root: Path,
) -> EvidenceManifest:
    validate_population(loaded)
    factory.validate()
    external(output)
    if (
        environment.loaded.pin != loaded.pin
        or environment.fixture != FIXTURE
        or (schedule.state_fixture, schedule.environment_version) != (FIXTURE, environment.version)
        or schedule.worker_timeout_seconds != 90
        or len(loaded.manifest.entries) != 1
    ):
        raise ValueError("controlled recording requires one case with three bounded trials")
    extension = factory.controls.scope()
    for task in schedule.tasks:
        label = private_case(loaded.entry(task.context.case_id).case)
        matches = [
            s
            for s in extension.slots
            if s.phase == "domain"
            and s.variant == factory.variant
            and (s.case_id, s.trial_id, s.run_id, s.tenant_id, s.business_event_id)
            == (
                task.context.case_id,
                task.context.trial_id,
                task.context.run_id,
                task.context.tenant_id,
                task.context.business_event_id,
            )
        ]
        if (
            len(matches) != 1
            or matches[0].case_sha256 != pin(label)
            or task.context.deadline <= datetime.now(UTC)
            or (task.context.deadline - datetime.now(UTC)).total_seconds() > 300
        ):
            raise ValueError("recording task/reference/deadline differs from prospective scope")
    if factory.origin == "provider":
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source_root, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=source_root, text=True
        ).strip()
        if dirty or revision != factory.candidate.code_revision:
            raise ValueError("provider capture requires clean final candidate source")
    try:
        return record_candidate(
            schedule,
            loaded,
            replace(factory, observation_root=output / "observations"),
            ControlledEnvironment(environment, factory.controls.ledger),
            output,
            candidate=factory.candidate,
            candidate_sha256=candidate_sha256,
            source_root=source_root,
        )
    except WorkerCleanupError:
        stop(factory.controls.ledger, "owned_cleanup_failed")
        raise
    except Exception:
        stop(factory.controls.ledger, "scorer_observation_failed")
        raise


def read_controlled(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    variant: Variant,
    expected_origin: Literal["provider", "mock"],
    control_sha256: str,
    evidence_sha256: str,
    candidate_sha256: str,
) -> VerifiedEvidence:
    validate_population(loaded)
    evidence = read_evidence(
        root, loaded, evidence_sha256=evidence_sha256, candidate_sha256=candidate_sha256
    )
    if evidence.manifest.origin != expected_origin:
        raise ValueError("controlled routing evidence origin differs")
    validate_candidate(evidence.manifest.candidate, route, variant, control_sha256)
    verify_observations(root, loaded, evidence.batch)
    return evidence
