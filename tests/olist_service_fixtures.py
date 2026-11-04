"""Invented service evaluation fixtures; no independent source labels or provider calls."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from agent_harness.fresh_example import MockAdmission
from agent_harness.release_contracts import sha256
from agent_harness.trials import OutcomePolicy, TrialSchedule, TrialTask
from olist_h10_fixtures import ROOT as ROOT
from olist_h10_fixtures import composition as old_composition
from olist_routing_fixtures import label_for
from olist_support.console_cases import MODEL_SERVICE_AGENT, MODEL_SERVICE_CANDIDATE
from olist_support.routing_contracts import RoutingPlan
from olist_support.service_evaluation import ServiceScenario, ServiceScript
from olist_support.service_h10 import (
    ENVIRONMENT,
    FIXTURE,
    ServiceMockFactory,
    fingerprints,
    manifest_for,
)


@dataclass(frozen=True)
class MockServiceRoute:
    intent: str
    requested_minor: int | None = None

    def generate(self, request, *, timeout_seconds=30.0):
        assert len(request.messages) == 2 and not request.tools
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(
                role="assistant",
                content=RoutingPlan(
                    routing_version="olist-intent-routing-v2",
                    intent=self.intent,
                    requested_minor=self.requested_minor,
                ).canonical_json(),
            ),
            usage=Usage(
                model_calls=1, input_tokens=1, output_tokens=1, cost=Decimal(0), cost_currency="USD"
            ),
        )


def composition(
    intent="clarify",
    *,
    script=None,
    recovery=False,
    emitted=None,
    variant="candidate",
    scenario=None,
):
    _, _, old_schedule, old = old_composition()
    scenario = (
        scenario
        if scenario is not None
        else ServiceScenario(
            reference=label_for(intent, recovery=recovery),
            script=script if script is not None else ServiceScript(),
        )
    )
    manifest = manifest_for((scenario,))
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw, ManifestPin(manifest_id=manifest.manifest_id, version="v1", sha256=sha256(raw))
    )
    spec = old.candidate.model_copy(
        update={
            "candidate": MODEL_SERVICE_CANDIDATE,
            **fingerprints(old.route, old.candidate.source_files, variant),
        }
    )
    now, run = datetime.now(UTC), uuid4().hex
    expected = manifest.entries[0].case.expected
    tasks = tuple(
        TrialTask(
            context=t.context.model_copy(
                update={
                    "agent_id": MODEL_SERVICE_AGENT,
                    "tenant_id": scenario.reference.order.tenant_id,
                    "case_id": scenario.case_id,
                    "business_event_id": scenario.case_id,
                    "run_id": run + str(i),
                    "clock": now,
                    "deadline": now + timedelta(seconds=300),
                    "mode": "fresh_candidate" if variant == "candidate" else "offline_fake",
                    "versions": t.context.versions.model_copy(
                        update={
                            "candidate": MODEL_SERVICE_CANDIDATE,
                            "data_snapshot": scenario.reference.order.source_manifest_sha256,
                        }
                    ),
                }
            ),
            eligible_for_autonomy=expected.eligible_for_autonomy,
            required_review=expected.required_review,
        )
        for i, t in enumerate(old_schedule.tasks)
    )
    schedule = TrialSchedule(
        experiment_id="invented-service-" + run,
        manifest=loaded.pin,
        environment_version=ENVIRONMENT,
        state_fixture=FIXTURE,
        outcome_policy=OutcomePolicy(
            version="olist-confirmed-service-outcomes-v1",
            correctness_metric="correct",
            safety_metric="routing_safe",
            review_metric="observed_review",
        ),
        case_ids=manifest.case_ids,
        trial_ids=old_schedule.trial_ids,
        tasks=tasks,
        max_parallel=1,
        worker_timeout_seconds=90.0,
    )
    return (
        scenario,
        loaded,
        schedule,
        ServiceMockFactory(
            spec, old.route, MockServiceRoute(emitted or intent), MockAdmission(), Path("unused")
        ),
    )
