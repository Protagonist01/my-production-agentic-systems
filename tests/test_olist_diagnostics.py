"""Hand-counted diagnostic errors/unknowns, not a language model benchmark."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from agent_harness.release_contracts import pin
from olist_support.routing_contracts import RoutingPlan
from pydantic import ValidationError
from test_olist_workflow import context

import olist_diagnostic_readback
from olist_diagnostics import Observation, Plan, Reference, development_plan, summarize


def subset(*ids):
    all_cases = development_plan()
    return Plan(
        cases=tuple(c for c in all_cases.cases if c.case_id in ids),
        trials=("one", "two"),
        variants=("candidate", "rules", "always-review"),
    )


def observation(plan, case, intent, amount=None, **kw):
    return Observation(
        plan_sha256=pin(plan),
        case_id=case,
        variant="candidate",
        trial="one",
        predicted=RoutingPlan(
            routing_version="olist-intent-routing-v2", intent=intent, requested_minor=amount
        ),
        resolved=True,
        **kw,
    )


def overall(plan, *rows):
    return summarize(plan, rows)["variants"]["candidate"]["overall"]


def test_complete_schedule_keeps_missing_variants_trials_and_unknown_safety():
    p = subset("poem", "status")
    r = observation(
        p, "poem", "refund", 5000, proposed_refund=True, unauthorized_effect=False, review=True
    )
    s = summarize(p, (r,))
    c = s["variants"]["candidate"]["overall"]
    assert (c["scheduled"], c["observed"], c["missing"]) == (4, 1, 3)
    assert c["unsupported_correctly_rejected"] == {
        "yes": 0,
        "no": 1,
        "unknown_or_missing": 1,
        "scheduled": 2,
        "fraction_of_schedule": 0.0,
        "fraction_of_observed": 0.0,
    }
    assert c["wrong_refund_proposal_on_ineligible"]["yes"] == 1
    assert c["unauthorized_effect"]["yes"] == 0
    assert c["unauthorized_effect"]["unknown_or_missing"] == 3
    assert s["variants"]["rules"]["overall"]["missing"] == 4
    assert not s["semantic_gold_validated"] and not s["release_allowed"]


def test_intent_precision_recall_count_false_positive_and_missing_as_miss():
    p = subset("poem", "refund")
    s = overall(p, observation(p, "poem", "refund", 5000), observation(p, "refund", "refund", 5000))
    assert s["per_intent"]["refund"] == {
        "support": 2,
        "predicted": 2,
        "true_positive": 1,
        "precision": 0.5,
        "recall": 0.5,
    }
    assert s["reference_relative_joint_intent_amount"]["yes"] == 1


def test_unresolved_prediction_cannot_be_credited_even_if_label_matches():
    p = subset("status")
    r = observation(p, "status", "status").model_copy(update={"resolved": False})
    s = overall(p, r)
    assert s["per_intent"]["status"]["predicted"] == 1
    assert s["per_intent"]["status"]["true_positive"] == 0
    assert s["reference_relative_intent"]["unknown_or_missing"] == 2


def test_wrong_amount_attack_blocked_and_unsafe_effect_are_separate():
    p = subset("partial")
    r = observation(
        p,
        "partial",
        "refund",
        10000,
        proposed_refund=True,
        unauthorized_effect=False,
        disclosure=False,
    )
    s = overall(p, r)
    assert s["attack_wrong_interpretation"]["yes"] == 1
    assert s["attack_unauthorized_effect"]["no"] == 1
    assert s["attack_unauthorized_effect"]["unknown_or_missing"] == 1
    unsafe = r.model_copy(update={"unauthorized_effect": True})
    assert overall(p, unsafe)["attack_unauthorized_effect"]["yes"] == 1


def test_wrong_amount_on_eligible_case_does_not_gain_completion_or_cost_credit():
    p = subset("refund")
    r = observation(
        p,
        "refund",
        "refund",
        2000,
        proposed_refund=True,
        correct_completion=True,
        unauthorized_effect=False,
        disclosure=False,
        cost=Decimal(0),
    )
    s = overall(p, r)
    assert s["wrong_refund_proposal"]["yes"] == 1
    assert s["eligible_correct_completion"]["yes"] == 0
    assert s["usage"]["cost_per_correct_completion_usd"] is None


def test_review_everything_does_not_earn_eligible_completion():
    p = subset("refund", "poem")
    s = overall(
        p,
        observation(p, "refund", "review", review=True, correct_completion=False),
        observation(p, "poem", "unsupported", review=True),
    )
    assert s["unnecessary_review"]["yes"] == 1
    assert s["eligible_correct_completion"]["yes"] == 0
    assert s["required_review_received"]["yes"] == 1


def test_no_amount_and_unknown_amount_have_different_credit():
    p = subset("refund")
    c = p.cases[0]
    unknown = c.reference.model_copy(
        update={
            "amount_state": "unknown",
            "requested_minor": None,
            "amount_start": None,
            "amount_end": None,
        }
    )
    p2 = p.model_copy(update={"cases": (c.model_copy(update={"reference": unknown}),)})
    r = observation(p2, "refund", "refund")
    assert overall(p2, r)["reference_relative_intent"]["yes"] == 1
    assert overall(p2, r)["reference_relative_joint_intent_amount"]["unknown_or_missing"] == 2


def test_latency_incomplete_does_not_claim_full_population_percentile():
    p = subset("refund")
    s = overall(
        p,
        observation(p, "refund", "refund", 5000, elapsed_seconds=4.0, stage_timings_complete=False),
    )
    assert s["latency"]["observed_percentiles_seconds"]["0.95"] == 4
    assert s["latency"]["complete"] is False
    assert s["timing_coverage"]["no"] == s["timing_coverage"]["unknown_or_missing"] == 1


def test_unknown_cost_is_not_zero_or_cost_per_success():
    p = subset("refund")
    r = observation(
        p,
        "refund",
        "refund",
        5000,
        unauthorized_effect=False,
        disclosure=False,
        correct_completion=True,
        cost=Decimal(".10"),
        model_calls=1,
    )
    s = overall(p, r)
    assert s["usage"]["known_cost_subtotal_usd"] == "0.10"
    assert s["usage"]["cost_per_correct_completion_usd"] is None
    r2 = r.model_copy(update={"trial": "two", "cost": Decimal(".20")})
    assert overall(p, r, r2)["usage"]["cost_per_correct_completion_usd"] == "0.15"


def test_consistently_wrong_paraphrases_do_not_receive_consistency_credit():
    p0 = development_plan()
    ids = {"refund", "refund_paraphrase", "negation"}
    p = Plan(
        cases=tuple(c for c in p0.cases if c.case_id in ids),
        trials=("one",),
        variants=("candidate",),
        relations=tuple(r for r in p0.relations if r.left in ids),
    )
    rows = tuple(observation(p, k, "unsupported") for k in ids)
    relations = summarize(p, rows)["variants"]["candidate"]["relations"]
    assert relations["same_meaning"]["yes"] == 0
    assert relations["negation_changes_intent"]["yes"] == 0
    good = (
        observation(p, "refund", "refund", 5000),
        observation(p, "refund_paraphrase", "refund", 5000),
        observation(p, "negation", "status"),
    )
    relations = summarize(p, good)["variants"]["candidate"]["relations"]
    assert relations["same_meaning"]["yes"] == relations["negation_changes_intent"]["yes"] == 1


def test_development_pack_is_grouped_exposed_and_not_provider_permission():
    p = development_plan()
    assert len(p.cases) == 24
    assert len({c.attack_family for c in p.cases if c.attack_family}) >= 10
    assert all(
        c.split == "development" and not c.reference.semantic_gold_validated for c in p.cases
    )
    assert not p.provider_calls_authorized and not p.release_allowed
    assert Plan.model_validate_json(p.canonical_json()) == p


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_sha256", "f" * 64),
        ("trial", "foreign"),
        ("case_id", "foreign"),
        ("variant", "foreign"),
    ],
)
def test_foreign_observations_refuse(field, value):
    p = subset("poem")
    r = observation(p, "poem", "unsupported").model_copy(update={field: value})
    with pytest.raises(ValueError, match="foreign"):
        summarize(p, (r,))


def test_duplicate_rows_split_leakage_and_false_completion_refuse():
    p = subset("refund", "refund_paraphrase")
    r = observation(p, "refund", "refund", 5000)
    with pytest.raises(ValueError, match="duplicate"):
        summarize(p, (r, r))
    changed = p.cases[1].model_copy(update={"split": "holdout"})
    with pytest.raises(ValueError, match="crosses split"):
        Plan.model_validate_json(
            p.model_copy(update={"cases": (p.cases[0], changed)}).canonical_json()
        )
    with pytest.raises(ValidationError):
        Observation.model_validate_json(
            r.model_copy(update={"correct_completion": True}).canonical_json()
        )


def test_reference_cannot_hide_missing_span_or_claim_semantic_gold():
    r = development_plan().cases[9].reference
    for change in (
        {"amount_end": 10000},
        {"requested_minor": 10000},
        {"amount_state": "unknown"},
        {"semantic_gold_validated": True},
        {"limitations": ()},
    ):
        with pytest.raises(ValueError):
            Reference.model_validate_json(r.model_copy(update=change).canonical_json())


@pytest.mark.parametrize("currency,expected", [("USD", Decimal(".10")), ("SIM", None)])
def test_service_projection_never_relabels_other_currency_as_usd(monkeypatch, currency, expected):
    # A boundary unit double; real scorer/context/database behavior has SQL integration tests.
    p = subset("vague")
    c = p.cases[0]
    ctx = context()
    prediction = RoutingPlan(routing_version="olist-intent-routing-v2", intent="clarify")
    scenario = SimpleNamespace(
        case_id="service-case",
        expects_commit=False,
        script=SimpleNamespace(require_review=False),
        reference=SimpleNamespace(
            reference=SimpleNamespace(
                text=c.reference.text,
                expected=SimpleNamespace(intent="clarify", requested_minor=None),
            ),
            expected=SimpleNamespace(outcome="review_required"),
            recovery_required=False,
        ),
    )
    decision = SimpleNamespace(
        failure_code=None,
        plan=prediction,
        usage=SimpleNamespace(cost=Decimal(".10"), cost_currency=currency, model_calls=1),
    )
    capture = SimpleNamespace(
        before=SimpleNamespace(business="unchanged"),
        final=SimpleNamespace(business="unchanged"),
        proposed=SimpleNamespace(
            cases=(
                SimpleNamespace(
                    case_id="service-case",
                    tenant_id=ctx.tenant_id,
                    document=SimpleNamespace(intent_decision=decision, command=None),
                ),
            )
        ),
    )
    monkeypatch.setattr(
        olist_diagnostic_readback,
        "score_service",
        lambda *args: {
            "state_safety": True,
            "correct": True,
            "observed_review": True,
        },
    )
    row = olist_diagnostic_readback.observe_service(
        p, "vague", "candidate", "one", scenario, ctx, capture
    )
    assert row.cost == expected
    assert row.model_calls == 1
    assert row.correct_completion is None and row.disclosure is None


def test_ineligible_metadata_cannot_claim_autonomous_completion_population():
    c = development_plan().cases[0]
    with pytest.raises(ValueError, match="eligible autonomy"):
        type(c).model_validate_json(c.model_copy(update={"eligible": True}).canonical_json())
