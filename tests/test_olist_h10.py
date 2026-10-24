"""Independent label/result/state mutations; invented observations are not quality evidence."""

from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal

import pytest
from agent_harness.cases import LoadedManifest, ManifestPin
from agent_harness.contracts import Usage
from agent_harness.release_contracts import pin, sha256
from olist_h10_fixtures import ROOT, composition, population
from olist_support import h10_runtime
from olist_support.field_evaluation import FIELDS, FieldCapture
from olist_support.h10_config import validate_composition
from olist_support.h10_environment import OlistAccess, OlistEnvironment, grant_for
from olist_support.h10_manifest import domain_task, private_case
from olist_support.h10_recording import record_olist
from olist_support.h10_runtime import ObservationSlot, OlistScorer, observed_result
from olist_support.release import (
    Observation,
    OrderState,
    StateSnapshot,
    _expected_state,
    enrollment_pin,
)
from olist_support.workflow import IntentDecision, IntentPlan, WorkflowResult


def test_manifest_preserves_private_labels_and_regression_without_input_leakage():
    case, loaded = population()
    entry = loaded.entry(case.input.case_id)
    assert (
        entry.split == "development" and entry.case.hidden_state["original_split"] == "regression"
    )
    assert entry.group_id == case.group_id
    assert entry.case.agent_input().model_dump()["observations"] == ()
    assert entry.case.agent_input().request == case.input.request.message
    assert private_case(entry.case) == (case, False)
    assert '"expected"' not in entry.case.agent_input().canonical_json()
    assert (
        case.expected.model_dump(mode="json") == entry.case.hidden_state["olist_case"]["expected"]
    )


@pytest.mark.parametrize("field", ["input", "source_kind", "expected", "recovery"])
def test_private_binding_rejects_inconsistent_projection(field):
    _, loaded = population()
    case = loaded.manifest.entries[0].case
    updates = {
        "input": {"input": case.input.model_copy(update={"request": "changed"})},
        "source_kind": {"source_kind": "hybrid"},
        "expected": {"expected": case.expected.model_copy(update={"required_review": True})},
        "recovery": {"hidden_state": {**case.hidden_state, "recovery_required": "true"}},
    }
    with pytest.raises(ValueError, match="Olist manifest"):
        private_case(case.model_copy(update=updates[field]))


def test_behavior_and_executing_source_must_match_the_separately_pinned_candidate():
    _, _, _, factory = composition()
    validate_composition(factory.candidate, factory.route, factory.transport, "mock")
    changed = factory.route.model_copy(update={"parameters": {"temperature": 1.0}})
    with pytest.raises(ValueError, match="fingerprint"):
        validate_composition(factory.candidate, changed, factory.transport, "mock")
    files = {**factory.candidate.source_files, "uv.lock": "f" * 64}
    with pytest.raises(ValueError, match="lock"):
        validate_composition(
            factory.candidate.model_copy(update={"source_files": files}),
            factory.route,
            factory.transport,
            "mock",
        )
    assert pin(factory.candidate) != pin(
        factory.candidate.model_copy(update={"candidate": "other"})
    )


def captured(monkeypatch, tmp_path, *, recovery=False):
    label, loaded, schedule, _ = composition(recovery=recovery)
    context = schedule.tasks[0].context
    before = StateSnapshot(
        orders=(
            OrderState(
                tenant_id=context.tenant_id,
                order_id=label.input.order.order_id,
                record_sha256=enrollment_pin(label),
                version=0,
                refunded_minor=0,
            ),
        ),
        ledger=(),
        budgets=(),
    )
    grant = grant_for(context.tenant_id, label.input.order.order_id)
    task = domain_task(label, context, grant, 10000)
    after = _expected_state(label, task, before)
    result = WorkflowResult(
        outcome="refunded",
        reason="ledger_and_state_verified",
        receipt=after.ledger[0].receipt,
        message="A refund of 50.00 SIM is committed in the controlled simulation ledger.",
    )
    capture = FieldCapture(
        case_id=context.case_id,
        trial_id=context.trial_id,
        observation=Observation(
            case_id=context.case_id,
            trial_id=context.trial_id,
            before=before,
            after=after,
            outcome=result.outcome,
            message=result.message,
            receipt=result.receipt,
        ),
        decision=IntentDecision(
            plan=IntentPlan(intent="refund"),
            usage=Usage(
                model_calls=1, input_tokens=5, output_tokens=3, cost=Decimal(0), cost_currency="USD"
            ),
        ),
        workflow_result=result,
        duplicate_delivery_unchanged=True,
        before_redelivery=after,
        redelivered_result=result,
    )

    class Database:
        @contextmanager
        def connect(self):
            yield None

    access = OlistAccess(Database(), label.input.order.order_id, grant, before, recovery)
    slot = ObservationSlot(capture)
    scorer = OlistScorer(context, access, slot, tmp_path / "observations")
    monkeypatch.setattr(h10_runtime, "collect_state", lambda connection: after)
    return loaded.manifest.entries[0].case, scorer, capture, observed_result(context, capture)


def test_shared_scores_are_binary_and_independent_final_state_overrides_claim(
    monkeypatch, tmp_path
):
    case, scorer, capture, result = captured(monkeypatch, tmp_path)
    scores = {s.metric: s for s in scorer.score(case, result)}
    assert all(scores[name].value == 1 for name in FIELDS)
    assert scores["olist_correct"].value == 1
    monkeypatch.setattr(h10_runtime, "collect_state", lambda connection: capture.observation.before)
    changed = {
        s.metric: s
        for s in replace(scorer, observation_root=tmp_path / "changed").score(case, result)
    }
    assert changed["exact_state"].value == changed["olist_correct"].value == 0


@pytest.mark.parametrize("field", ["decision", "output", "state_change_refs", "usage"])
def test_shared_result_cannot_diverge_from_observed_workflow(monkeypatch, tmp_path, field):
    case, scorer, _, result = captured(monkeypatch, tmp_path)
    updates = {
        "decision": "status",
        "output": "invented paid outcome",
        "state_change_refs": (),
        "usage": result.usage.model_copy(update={"input_tokens": 0}),
    }
    with pytest.raises(ValueError, match="observation/identity"):
        scorer.score(case, result.model_copy(update={field: updates[field]}))


def test_missing_required_recovery_is_a_scorer_failure_not_a_passing_default(monkeypatch, tmp_path):
    case, scorer, _, result = captured(monkeypatch, tmp_path, recovery=True)
    scores = {s.metric: s for s in scorer.score(case, result)}
    assert scores["recovery"].value is None and scores["recovery"].failure is not None
    assert scores["olist_correct"].value == 0


@pytest.mark.parametrize("change", ["missing_snapshot", "changed_state", "changed_result"])
def test_duplicate_boolean_cannot_override_saved_redelivery_observations(
    monkeypatch, tmp_path, change
):
    case, scorer, capture, result = captured(monkeypatch, tmp_path)
    changes = {
        "missing_snapshot": {"before_redelivery": None},
        "changed_state": {"before_redelivery": capture.observation.before},
        "changed_result": {
            "redelivered_result": capture.workflow_result.model_copy(
                update={"reason": "changed_duplicate_reason"}
            )
        },
    }
    scorer.slot.capture = capture.model_copy(update=changes[change])
    scores = {s.metric: s for s in scorer.score(case, result)}
    assert scores["olist_correct"].value == 0
    if change == "missing_snapshot":
        assert scores["duplicate_delivery"].failure is not None
    else:
        assert scores["duplicate_delivery"].value == 0


@pytest.mark.parametrize("change", ["candidate_pin", "private_group"])
def test_recording_preflight_rejects_changed_binding_before_any_database_setup(tmp_path, change):
    _, loaded, schedule, factory = composition()
    expected = pin(factory.candidate)
    if change == "candidate_pin":
        expected = "f" * 64
    else:
        manifest = loaded.manifest
        manifest = manifest.model_copy(
            update={
                "entries": (manifest.entries[0].model_copy(update={"group_id": "wrong-group"}),)
            }
        )
        raw = manifest.canonical_json().encode()
        loaded = LoadedManifest(
            raw,
            ManifestPin(
                manifest_id=manifest.manifest_id,
                version=manifest.version,
                sha256=sha256(raw),
            ),
        )
        schedule = schedule.model_copy(update={"manifest": loaded.pin})
    # An unusable server is intentional: no lifecycle operation may run at preflight.
    environment = OlistEnvironment(None, "0123456789abcdef", loaded)
    with pytest.raises(ValueError, match="composition|group/split/scorer"):
        record_olist(
            schedule,
            loaded,
            factory,
            environment,
            tmp_path / "capture",
            candidate_sha256=expected,
            source_root=ROOT,
        )
    assert not (tmp_path / "capture").exists()
