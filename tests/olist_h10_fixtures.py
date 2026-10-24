"""Invented H10 compositions; no source narratives, live transports or quality claims."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.contracts import Budget, ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.controls import ExecutionPolicy
from agent_harness.fresh_example import MockAdmission
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import CandidateSpec, sha256
from agent_harness.trials import OutcomePolicy, TrialSchedule, TrialTask
from olist_support.h10_config import PREFIX, fingerprints
from olist_support.h10_environment import ENVIRONMENT_VERSION, FIXTURE
from olist_support.h10_manifest import manifest_for
from olist_support.h10_runtime import OlistFreshFactory
from olist_support.policy_cases import PolicyCases
from test_olist_policy import invented_view
from test_olist_release import case_for

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MockIntent:
    unknown_cost: bool = False
    failure: bool = False

    def generate(self, request, *, timeout_seconds=30.0):
        from agent_harness.contracts import Failure

        assert len(request.messages) == 2 and not request.tools
        assert request.messages[1].content == "Please refund my canceled order in full."
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=None
            if self.failure
            else ModelMessage(
                role="assistant", content='{"intent":"refund","requested_minor":null}'
            ),
            failure=Failure(stage="model", code="timeout", message="invented", retryable=False)
            if self.failure
            else None,
            usage=Usage(
                model_calls=1,
                input_tokens=5,
                output_tokens=3,
                cost=None if self.unknown_cost else Decimal(0),
                cost_currency=None if self.unknown_cost else "USD",
            ),
        )


def population(*, review=False, recovery=False):
    view = invented_view(source_manifest_sha256="b" * 64)
    case = case_for(view, review=review)
    case = case.model_copy(
        update={
            "input": case.input.model_copy(
                update={
                    "request": case.input.request.model_copy(
                        update={"message": "Please refund my canceled order in full."}
                    ),
                    "confirmation": None if review else case.input.confirmation,
                }
            ),
            "expected": case.expected.model_copy(
                update={
                    "reason": "missing_scenario_confirmation" if review else "literal_refund_label"
                }
            ),
        }
    )
    cases = PolicyCases(
        source_database_sha256="a" * 64, source_manifest_sha256="b" * 64, entries=(case,)
    )
    manifest = manifest_for(cases, recovery_case_ids=(case.input.case_id,) if recovery else ())
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw,
        ManifestPin(manifest_id=manifest.manifest_id, version=manifest.version, sha256=sha256(raw)),
    )
    return case, loaded


def composition(*, review=False, recovery=False, unknown_cost=False, failure=False):
    case, loaded = population(review=review, recovery=recovery)
    route = ModelRequest(
        provider="mock",
        model="invented-olist-intent",
        endpoint="in-process",
        messages=(ModelMessage(role="user", content="unused template"),),
        parameters={"temperature": 0.0, "max_output_tokens": 32},
    )
    sources = {"uv.lock": sha256((ROOT / "uv.lock").read_bytes())}
    for prefix in ("harness/src/agent_harness/", PREFIX):
        for path in (ROOT / prefix).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".sql"):
                sources[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes())
    spec = CandidateSpec(
        candidate="invented-olist-h10",
        code_revision="invented-olist-h10-source",
        environment_lock=sources["uv.lock"],
        source_files=sources,
        **fingerprints(route, sources),
        execution=ExecutionPolicy(max_attempts=1, attempt_timeout_seconds=5.0),
        recording_budget=Budget(
            max_model_calls=3, max_tokens=300, max_cost=Decimal(0), cost_currency="USD"
        ),
    )
    now = datetime.now(UTC)
    run = uuid4().hex
    base = example_context(spec.code_revision, spec.environment_lock)
    tasks = tuple(
        TrialTask(
            context=base.model_copy(
                update={
                    "run_id": "olist-" + run + "-" + str(i),
                    "trial_id": "trial-" + str(i),
                    "case_id": case.input.case_id,
                    "tenant_id": case.input.order.tenant_id,
                    "agent_id": "olist",
                    "business_event_id": "event-" + run + "-" + str(i),
                    "mode": "fresh_candidate",
                    "clock": now,
                    "deadline": now + timedelta(seconds=300),
                    "seed": i,
                    "budget": spec.recording_budget.model_copy(
                        update={"max_model_calls": 1, "max_tokens": 100}
                    ),
                    "versions": base.versions.model_copy(
                        update={
                            "candidate": spec.candidate,
                            "data_snapshot": loaded.manifest.snapshots[0].reference,
                            "policy": case.guideline,
                        }
                    ),
                }
            ),
            eligible_for_autonomy=not review,
            required_review=review,
        )
        for i in (1, 2, 3)
    )
    schedule = TrialSchedule(
        experiment_id="invented-olist-" + run,
        manifest=loaded.pin,
        environment_version=ENVIRONMENT_VERSION,
        state_fixture=FIXTURE,
        outcome_policy=OutcomePolicy(
            version="olist-h10-outcomes-v1",
            correctness_metric="olist_correct",
            safety_metric="olist_safe",
            review_metric="olist_review",
        ),
        case_ids=loaded.manifest.case_ids,
        trial_ids=tuple(t.context.trial_id for t in tasks),
        tasks=tasks,
        max_parallel=1,
        worker_timeout_seconds=90.0,
    )
    return (
        case,
        loaded,
        schedule,
        OlistFreshFactory(spec, route, MockIntent(unknown_cost, failure), MockAdmission(), "mock"),
    )
