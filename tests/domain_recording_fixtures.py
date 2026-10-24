"""Synthetic private fixtures; every dispatch is explicitly origin=mock."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.contracts import Budget, ModelMessage, ModelRequest
from agent_harness.controls import ExecutionPolicy
from agent_harness.domain_recording import (
    ENVIRONMENT,
    FIXTURE,
    MockDomainFactory,
    MockJsonTransport,
    scorer_pin,
    source_inventory,
)
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import CandidateSpec, sha256
from agent_harness.trials import OutcomePolicy, TrialSchedule, TrialTask
from cfpb_triage.h10_recording import CfpbAdapter
from revenue_integrity.h10_recording import RevenueAdapter
from test_cfpb_release_evaluation import population as cfpb_population
from test_revenue_release_evaluation import extraction_plan

ROOT = Path(__file__).resolve().parents[1]


def composition(domain, *, fail=False, unknown_cost=False):
    if domain == "cfpb":
        plan = cfpb_population()
        adapter = CfpbAdapter(plan.taxonomy, plan.policy)
        manifest = adapter.manifest_for((plan.cases[0],))
        content = (
            '{"product":"Credit","issue":"Fees","priority":"routine",'
            '"ambiguity":"clear","confidence":0.9,"quotes":["Invented"]}'
        )
    else:
        plan = extraction_plan()
        route = ModelRequest(
            provider="mock",
            endpoint="in-process",
            model="invented-extraction",
            messages=(ModelMessage(role="user", content="unused"),),
            parameters={},
        )
        adapter = RevenueAdapter(route, plan.source_manifest_sha256)
        manifest = adapter.manifest_for((plan.cases[0],))
        content = (
            '{"outcome":"supported","spans":[{"start":11,"text":"renewal"}],'
            '"rationale":"Invented extraction."}'
        )
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw,
        ManifestPin(manifest_id=manifest.manifest_id, version=manifest.version, sha256=sha256(raw)),
    )
    transport = MockJsonTransport(content, fail=fail, unknown_cost=unknown_cost)
    sources = {**source_inventory(adapter), "uv.lock": sha256((ROOT / "uv.lock").read_bytes())}
    spec = CandidateSpec(
        candidate="invented-" + domain + "-partial",
        code_revision="invented-domain-source",
        environment_lock=sources["uv.lock"],
        source_files=sources,
        prompt_sha256=transport.recipe_sha256,
        model_config_sha256=adapter.configuration_sha256,
        tools_sha256=sha256(b"no-business-tools"),
        policy_sha256=sha256(manifest.entries[0].case.policy_version.encode()),
        scorer_sha256=scorer_pin(adapter, sources),
        environment_sha256=sha256((ENVIRONMENT + FIXTURE).encode()),
        execution=ExecutionPolicy(max_attempts=1, attempt_timeout_seconds=30.0),
        recording_budget=Budget(
            max_model_calls=6, max_tokens=9000, max_cost=Decimal(0), cost_currency="USD"
        ),
    )
    now = datetime.now(UTC)
    original = example_context(spec.code_revision, spec.environment_lock)
    case = manifest.entries[0].case
    tasks = tuple(
        TrialTask(
            context=original.model_copy(
                update={
                    "run_id": domain + "-run-" + str(i),
                    "case_id": case.case_id,
                    "trial_id": "trial-" + str(i),
                    "agent_id": adapter.agent_id,
                    "mode": "fresh_candidate",
                    "clock": now,
                    "deadline": now + timedelta(seconds=300),
                    "seed": i,
                    "versions": original.versions.model_copy(
                        update={
                            "candidate": spec.candidate,
                            "code_revision": spec.code_revision,
                            "environment_lock": spec.environment_lock,
                            "data_snapshot": case.snapshot_ref,
                            "policy": case.policy_version,
                        }
                    ),
                    "budget": Budget(
                        max_model_calls=2, max_tokens=3000, max_cost=Decimal(0), cost_currency="USD"
                    ),
                }
            ),
            eligible_for_autonomy=case.expected.eligible_for_autonomy,
            required_review=case.expected.required_review,
        )
        for i in (1, 2, 3)
    )
    schedule = TrialSchedule(
        experiment_id="invented-" + domain + "-partial",
        manifest=loaded.pin,
        environment_version=ENVIRONMENT,
        state_fixture=FIXTURE,
        outcome_policy=OutcomePolicy(
            version="invented",
            correctness_metric=domain + "_correct",
            safety_metric=domain + "_safe",
            review_metric=domain + "_review",
        ),
        case_ids=manifest.case_ids,
        trial_ids=tuple(t.context.trial_id for t in tasks),
        tasks=tasks,
        worker_timeout_seconds=90.0,
    )
    return (
        loaded,
        schedule,
        MockDomainFactory(spec, loaded, adapter, transport, Path("unused-output")),
    )
