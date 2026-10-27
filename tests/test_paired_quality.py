"""Hand-counted paired outcomes, fixed missing denominators and no qualification."""

import pytest
from revenue_integrity.paired_quality import QualityOutcome, summarize


def sample():
    labels = {f"case-{i}": i < 6 for i in range(12)}
    controls = frozenset({"case-4", "case-5", "case-10", "case-11"})
    rows = tuple(
        QualityOutcome(
            case_id=c,
            variant=v,
            trial_id=t,
            decision="accept" if expected else "reject",
            raw_decision="accept" if expected else "reject",
            evidence_valid=True,
            failure=None,
            input_tokens=10,
            output_tokens=2,
            cost_known=False,
            elapsed_seconds=1.0,
        )
        for c, expected in labels.items()
        for v in ("baseline", "task_wording", "evidence_selection")
        for t in ("trial-1", "trial-2")
    )
    return labels, controls, rows


def test_complete_perfect_development_still_cannot_qualify_or_authorize_release():
    labels, controls, rows = sample()
    report = summarize(labels, controls, rows)
    assert report["observed"] == 72 and report["all_scheduled_reference_correct"]
    assert not report["qualification_met"] and not report["release_allowed"]
    for metrics in report["metrics"].values():
        assert metrics["correct"] == 24 and metrics["consistently_correct_families"] == 12
        assert metrics["unknown_cost_rows"] == 24 and metrics["unknown_input_token_rows"] == 0
        assert metrics["class_results"]["answerable"]["correct"] == 12
        assert metrics["class_results"]["no_answer"]["correct"] == 12


def test_hand_counted_paired_gain_control_regression_and_invalid_evidence_do_not_overlap():
    labels, controls, rows = sample()
    changed = []
    for r in rows:
        if r.variant == "baseline" and r.case_id == "case-0":
            r = r.model_copy(update={"decision": "reject", "raw_decision": "reject"})
        if r.variant == "task_wording" and r.case_id == "case-10":
            r = r.model_copy(update={"decision": "accept", "raw_decision": "accept"})
        if r.variant == "evidence_selection" and r.case_id == "case-2":
            r = r.model_copy(
                update={
                    "decision": None,
                    "evidence_valid": False,
                    "failure": "invalid_evidence",
                    "input_tokens": None,
                    "output_tokens": None,
                }
            )
        changed.append(r)
    report = summarize(labels, controls, tuple(changed))
    m = report["metrics"]
    p = report["paired_vs_fresh_baseline"]
    assert m["baseline"]["correct"] == 22 and m["task_wording"]["false_accepts"] == 2
    assert (
        m["evidence_selection"]["correct"] == 22
        and m["evidence_selection"]["raw_reference_agreement_count"] == 24
    )
    assert m["evidence_selection"]["unknown_input_token_rows"] == 2
    assert p["task_wording"]["gained_consistently_correct_families"] == 1
    assert p["task_wording"]["lost_consistently_correct_families"] == 1
    assert (
        p["task_wording"]["control_regressions"] == 1
        and p["task_wording"]["net_consistently_correct_families"] == 0
    )


def test_missing_keeps24_denominator_and_does_not_become_a_paired_gain_or_regression():
    labels, controls, rows = sample()
    report = summarize(labels, controls, rows[:-1])
    assert (
        report["missing"] == 1
        and report["metrics"]["evidence_selection"]["scheduled_agreement"] == 23 / 24
    )
    assert report["metrics"]["evidence_selection"]["unobserved_family_pairs"] == 1
    assert report["paired_vs_fresh_baseline"]["evidence_selection"]["unobserved_families"] == 1
    assert not report["all_scheduled_reference_correct"]


def test_duplicate_foreign_and_inconsistent_outcomes_refuse_instead_of_inflating_score():
    labels, controls, rows = sample()
    for bad in (
        rows + (rows[0],),
        rows + (rows[0].model_copy(update={"case_id": "other"}),),
        (rows[0].model_copy(update={"failure": "timeout"}),) + rows[1:],
    ):
        with pytest.raises(ValueError):
            summarize(labels, controls, bad)


def test_actual_assessment_preserves_trial_and_invalid_quote_raw_decision():
    from revenue_integrity.evidence_selection import interpretation_request, selection_request
    from revenue_integrity.paired_quality import assess
    from test_semantic_alignment import response, value

    v = value()
    r = response(quotes=("not in source",))
    out, proof = assess(v, interpretation_request(v), r, "task_wording", "trial-2", 1.0)
    assert out.trial_id == "trial-2" and out.raw_decision == "accept"
    assert out.decision is None and not out.evidence_valid and proof is None
    selected = response().model_copy(
        update={
            "output": __import__("agent_harness.contracts", fromlist=["ModelMessage"]).ModelMessage(
                role="assistant", content='{"decision":"accept","evidence_ids":["s0"]}'
            )
        }
    )
    out, proof = assess(v, selection_request(v), selected, "evidence_selection", "trial-1", 1.0)
    assert (
        out.decision == "accept"
        and out.evidence_valid
        and proof["semantic_support"] == "not_assessed"
    )
    with pytest.raises(ValueError):
        assess(v, selection_request(v), selected, "baseline", "trial-1", 1.0)
