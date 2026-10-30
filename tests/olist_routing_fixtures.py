"""Invented wider H10 fixtures; never source references or measured model behavior."""

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
from olist_h10_fixtures import composition as old_composition
from olist_support.routing_contracts import RoutingPlan
from olist_support.routing_evaluation import ExpectedWorkflow, RoutingCase, RoutingPopulation
from olist_support.routing_h10 import FIXTURE, RoutingMockFactory, fingerprints, manifest_for
from olist_support.routing_reference import RoutingReference
from test_olist_policy import confirmation, invented_view

ROOT = Path(__file__).resolve().parents[1]
INTENTS = ("refund", "status", "reship", "review", "clarify", "unsupported")
REASONS = dict(
    zip(
        INTENTS,
        (
            "ledger_and_state_verified",
            "scoped_recorded_status",
            "reship_requires_inventory_and_shipping_review",
            "intent_requires_review",
            "request_needs_clarification",
            "unsupported_request",
        ),
        strict=True,
    )
)


def label_for(intent="clarify", *, recovery=False):
    return RoutingCase(
        case_id=sha256(("invented-routing-" + intent).encode()),
        group_id=sha256(("invented-parent-" + intent).encode()),
        language_family="invented-" + intent,
        split="development",
        source_kind="synthetic",
        reference_source_sha256="a" * 64,
        reference=RoutingReference(
            text="Invented request for " + intent,
            expected=RoutingPlan(routing_version="olist-intent-routing-v2", intent=intent),
            provenance="constructed_development",
        ),
        order=invented_view(),
        confirmation=confirmation(),
        expected=ExpectedWorkflow(
            outcome="refunded"
            if intent == "refund"
            else "status"
            if intent == "status"
            else "review_required",
            reason=REASONS[intent],
            refund_minor=5000 if intent == "refund" else None,
        ),
        recovery_required=recovery,
    )


@dataclass(frozen=True)
class MockRoute:
    intent: str
    variant: str = "candidate"

    def generate(self, request, *, timeout_seconds=30.0):
        assert request.messages[1].content == "Invented request for " + self.intent
        content = (
            RoutingPlan(
                routing_version="olist-intent-routing-v2", intent=self.intent
            ).canonical_json()
            if self.variant == "candidate"
            else '{"intent":"review"}'
        )
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content=content),
            usage=Usage(
                model_calls=1, input_tokens=1, output_tokens=1, cost=Decimal(0), cost_currency="USD"
            ),
        )


def composition(intent="clarify", variant="candidate", recovery=False):
    _, _, old_schedule, old = old_composition()
    label = label_for(intent, recovery=recovery)
    population = RoutingPopulation(entries=(label,))
    manifest = manifest_for(population)
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw, ManifestPin(manifest_id=manifest.manifest_id, version="v1", sha256=sha256(raw))
    )
    spec = old.candidate.model_copy(
        update={
            "candidate": "invented-routing-" + variant,
            **fingerprints(old.route, old.candidate.source_files, variant),
        }
    )
    now, run = datetime.now(UTC), uuid4().hex
    tasks = tuple(
        TrialTask(
            context=t.context.model_copy(
                update={
                    "case_id": label.case_id,
                    "run_id": run + str(i),
                    "business_event_id": run + "-event-" + str(i),
                    "clock": now,
                    "deadline": now + timedelta(seconds=300),
                    "mode": "offline_fake"
                    if variant in ("rules", "always-review")
                    else "fresh_candidate",
                    "versions": t.context.versions.model_copy(
                        update={
                            "candidate": spec.candidate,
                            "data_snapshot": label.order.source_manifest_sha256,
                        }
                    ),
                }
            ),
            eligible_for_autonomy=intent == "refund",
            required_review=intent not in ("refund", "status"),
        )
        for i, t in enumerate(old_schedule.tasks)
    )
    schedule = TrialSchedule(
        experiment_id="invented-routing-" + run,
        manifest=loaded.pin,
        environment_version="olist-routing-environment-v1",
        state_fixture=FIXTURE,
        outcome_policy=OutcomePolicy(
            version="olist-routing-outcomes-v1",
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
    factory = RoutingMockFactory(
        spec, old.route, MockRoute(intent, variant), MockAdmission(), variant, Path("unused")
    )
    return label, loaded, schedule, factory
