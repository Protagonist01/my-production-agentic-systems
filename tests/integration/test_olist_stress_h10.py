"""Three real SQL/H10 trials per authored stress case, with canned model output."""

from dataclasses import dataclass, replace
from decimal import Decimal

import pytest
from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from agent_harness.release_contracts import pin, sha256
from agent_harness.trials import TrialSchedule
from olist_routing_fixtures import ROOT, composition
from olist_support.routing_contracts import RoutingPlan
from olist_support.routing_evaluation import RoutingPopulation
from olist_support.routing_h10 import RoutingEnvironment, manifest_for, read_mock, record_mock
from olist_support.routing_stress import build_draft
from test_olist_business import app as app


@dataclass(frozen=True)
class CannedDecision:
    text: str
    plan: RoutingPlan

    def generate(self, request, *, timeout_seconds=30.0):
        assert request.messages[1].content == self.text
        assert not request.tools
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content=self.plan.canonical_json()),
            usage=Usage(
                model_calls=1, input_tokens=1, output_tokens=1, cost=Decimal(0), cost_currency="USD"
            ),
        )


@pytest.mark.parametrize("entry", build_draft().entries, ids=lambda e: e.challenge)
def test_constructed_stress_decision_reaches_expected_sql_state_without_replanning(
    app, tmp_path, entry
):
    server, parent, _ = app
    _, _, old_schedule, old_factory = composition()
    case = entry.case
    manifest = manifest_for(RoutingPopulation(entries=(case,)))
    raw = manifest.canonical_json().encode()
    loaded = LoadedManifest(
        raw, ManifestPin(manifest_id=manifest.manifest_id, version="v1", sha256=sha256(raw))
    )
    tasks = tuple(
        original.model_copy(
            update={
                "context": original.context.model_copy(
                    update={
                        "tenant_id": case.order.tenant_id,
                        "case_id": case.case_id,
                        "versions": original.context.versions.model_copy(
                            update={"data_snapshot": case.order.source_manifest_sha256}
                        ),
                    }
                ),
                "eligible_for_autonomy": case.expected.outcome == "refunded",
                "required_review": case.expected.outcome == "review_required",
            }
        )
        for original in old_schedule.tasks
    )
    schedule = TrialSchedule.model_validate_json(
        old_schedule.model_copy(
            update={
                "manifest": loaded.pin,
                "case_ids": (case.case_id,),
                "tasks": tasks,
            }
        ).canonical_json()
    )
    factory = replace(
        old_factory, transport=CannedDecision(case.reference.text, case.reference.expected)
    )
    output = tmp_path / "canned-stress-mechanism"
    evidence = record_mock(
        schedule,
        loaded,
        factory,
        RoutingEnvironment(server, parent.workspace_key, loaded),
        output,
        candidate_sha256=pin(factory.candidate),
        source_root=ROOT,
    )
    verified = read_mock(
        output,
        loaded,
        route=factory.route,
        variant="candidate",
        evidence_sha256=pin(evidence),
        candidate_sha256=pin(factory.candidate),
    )
    assert evidence.origin == "mock" and verified.batch.complete
    assert len(verified.batch.rows) == len(verified.receipts) == 3
    for row in verified.batch.rows:
        assert not row.errors and row.report is not None
        result = row.report.report.result
        scores = {s.metric: s.value for s in row.report.report.scores}
        assert scores["correct"] == scores["exact_state"] == scores["duplicate_delivery"] == 1
        assert scores["routing_safe"] == scores["truthful_confirmation"] == 1
        assert result.usage.model_calls == 1
        if case.recovery_required:
            assert scores["recovery"] == 1
        else:
            assert "recovery" not in scores
        with server.connect() as admin:
            database = row.state_ref.removeprefix("olist-routing:")
            assert not admin.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (database,)
            ).fetchone()
            assert not admin.execute(
                "SELECT 1 FROM pg_roles WHERE rolname=%s", (database,)
            ).fetchone()
