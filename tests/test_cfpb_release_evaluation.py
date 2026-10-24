"""Invented matrix/route witnesses; no consumer narrative or model quality claim."""

import pytest
from agent_harness.release_contracts import pin
from cfpb_triage.release_evaluation import EvaluationPlan, Observation, ReferenceCase, evaluate
from cfpb_triage.review import EvidenceSpan
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import (
    Attempt,
    Decision,
    Prediction,
    RouterPolicy,
    Taxonomy,
    digest_text,
)


def population():
    taxonomy = Taxonomy(
        version="invented",
        source_manifest="a" * 64,
        pairs={"Credit": ("Fees",), "Loan": ("Payment",)},
    )
    policy = RouterPolicy(
        taxonomy_sha256=pin(taxonomy),
        fit_manifest_sha256="b" * 64,
        fit_cases=0,
        cheap_threshold=0.5,
        strong_threshold=0.5,
    )
    cases = tuple(
        ReferenceCase(
            complaint=ComplaintInput(case_id=hex(i + 1)[2:] * 64, narrative="Invented complaint."),
            group_id=hex(i + 5)[2:] * 64,
            split="holdout",
            source_kind="synthetic",
            product="Credit" if i < 2 else "Loan",
            issue="Fees" if i < 2 else "Payment",
            priority="routine" if i != 1 else "elevated",
            ambiguity="clear",
        )
        for i in range(3)
    )
    return EvaluationPlan(
        source_manifest_sha256="a" * 64,
        taxonomy=taxonomy,
        policy=policy,
        cases=cases,
        trial_ids=("t1", "t2"),
    )


def decision(plan, case, *, failure=False, product=None, priority=None):
    p = Prediction(
        product=product or case.product,
        issue=case.issue,
        priority=priority or case.priority,
        ambiguity="clear",
        confidence=0.9,
        evidence=(EvidenceSpan(start=0, end=8, text="Invented"),),
    )
    return Decision(
        case_id=case.complaint.case_id,
        narrative_sha256=digest_text(case.complaint.narrative),
        taxonomy_sha256=pin(plan.taxonomy),
        policy_sha256=pin(plan.policy),
        outcome="review_required" if failure or p.priority != "routine" else "classified",
        reason="model_failure"
        if failure
        else "uncertain_or_high_priority"
        if p.priority != "routine"
        else "supported_route",
        prediction=None if failure else p,
        attempts=(
            Attempt(
                route="cheap",
                model="invented",
                prediction=None if failure else p,
                failure="timeout" if failure else None,
            ),
        ),
        mode="cheap_first",
    )


def rows(plan):
    return tuple(
        Observation(case_id=c.complaint.case_id, trial_id=t, decision=decision(plan, c))
        for c in plan.cases
        for t in plan.trial_ids
    )


def test_report_counts_missing_failed_and_minority_classes_without_refitting():
    plan = population()
    observations = list(rows(plan))
    observations[2] = observations[2].model_copy(
        update={"decision": decision(plan, plan.cases[1], failure=True)}
    )
    observations.pop()  # one of two minority-label trials is absent
    report = evaluate(plan, tuple(observations))
    all = report["all"]
    assert (
        all["scheduled"] == 6
        and all["missing"] == 1
        and all["failed"] == 1
        and all["unresolved"] == 2
    )
    assert (
        all["elevated"] == 2
        and all["elevated_reviewed"] == 1
        and all["elevated_review_recall"] == 0.5
    )
    assert all["reviewed"] == 1 and all["classified"] == 3
    assert all["priority_correct"] == all["ambiguity_correct"] == 4
    assert all["product"]["classes"]["Loan"] == {
        "support": 2,
        "predicted": 1,
        "true_positive": 1,
        "f1": pytest.approx(2 / 3),
    }
    assert all["product"]["macro_f1"] == pytest.approx((6 / 7 + 2 / 3) / 2)
    assert not report["release_allowed"] and report["unreviewed_labels"] == 3
    assert report["source_kinds"]["original"]["scheduled"] == 0


@pytest.mark.parametrize(
    "change", ["quote", "unsafe_route", "early_stop", "wrong_identity", "duplicate", "group"]
)
def test_forged_routes_spans_and_population_are_rejected_or_counted_invalid(change):
    plan = population()
    observed = list(rows(plan))
    if change == "duplicate":
        with pytest.raises(ValueError, match="duplicate"):
            evaluate(plan, tuple(observed + [observed[0]]))
        return
    if change == "group":
        plan = plan.model_copy(
            update={
                "cases": (
                    plan.cases[0],
                    plan.cases[1].model_copy(
                        update={"group_id": plan.cases[0].group_id, "split": "development"}
                    ),
                    plan.cases[2],
                )
            }
        )
        with pytest.raises(ValueError, match="crosses"):
            evaluate(plan, tuple(observed))
        return
    index = 2 if change == "unsafe_route" else 0
    d = observed[index].decision
    if change == "wrong_identity":
        observed[index] = observed[index].model_copy(
            update={"decision": d.model_copy(update={"narrative_sha256": "c" * 64})}
        )
        with pytest.raises(ValueError, match="input/policy"):
            evaluate(plan, tuple(observed))
        return
    p = d.prediction
    if change == "quote":
        p = p.model_copy(update={"evidence": (EvidenceSpan(start=0, end=6, text="Forged"),)})
    if change == "early_stop":
        p = p.model_copy(update={"confidence": 0.0})
    changed = d.model_copy(
        update={
            "prediction": p,
            "attempts": (d.attempts[0].model_copy(update={"prediction": p}),),
            **(
                {"outcome": "classified", "reason": "supported_route"}
                if change == "unsafe_route"
                else {}
            ),
        }
    )
    observed[index] = observed[index].model_copy(update={"decision": changed})
    metrics = evaluate(plan, tuple(observed))["all"]
    assert metrics["invalid"] == 1 and metrics["unresolved"] == 1
    if change == "unsafe_route":
        assert metrics["missed_review"] == 1


def test_all_review_earns_no_classification_and_failed_risk_is_not_successful_review():
    plan = population()
    report = evaluate(
        plan,
        tuple(
            Observation(
                case_id=c.complaint.case_id, trial_id=t, decision=decision(plan, c, failure=True)
            )
            for c in plan.cases
            for t in plan.trial_ids
        ),
    )
    assert report["all"]["classified"] == report["all"]["reviewed"] == 0
    assert report["all"]["failed"] == report["all"]["unresolved"] == 6
    assert report["all"]["product"]["macro_f1"] == 0.0
