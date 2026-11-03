"""Accepted method mechanics and complete intent-only development denominators."""

from datetime import UTC, datetime

import pytest
from agent_harness.contracts import AgentInput
from agent_harness.release_contracts import pin
from olist_support.intent_reference import (
    IntentBundle,
    IntentMethodAcceptance,
    IntentObservation,
    IntentReference,
    compare,
    prepare,
)
from olist_support.utterance_reference import audit_csv, mapping_pin
from test_olist_utterance_reference import exposure, payload, row


def source():
    from agent_harness.release_contracts import sha256

    raw = payload(row("Refund {{Refund Amount}}"), row("Track order", "track_order", "ORDER"))
    audit = audit_csv(raw, sha256(raw), "a" * 40, exposure("Track order"))
    accepted = IntentMethodAcceptance(
        proposal_sha256="b" * 64,
        source_revision=audit.source_revision,
        source_csv_sha256=audit.source_csv_sha256,
        mapping_sha256=mapping_pin(),
        accepted_at=datetime(2026, 11, 4, tzinfo=UTC),
        owner_reply_reference="invented acceptance; not a real owner identity",
        exact_reply="Accept this limited reference method",
    )
    return audit, accepted


def bundle():
    audit, accepted = source()
    return prepare(
        audit,
        accepted,
        (1, 2),
        expected_audit_sha256=pin(audit),
        expected_acceptance_sha256=pin(accepted),
    )


def test_accepted_intent_scope_preserves_slots_unknown_amounts_and_exposure():
    value = bundle()
    assert [c.expected_intent for c in value.cases] == ["refund", "status"]
    assert value.cases[0].input.request == "Refund {{Refund Amount}}"
    assert "unresolved_source_slots" in value.cases[0].frame.full_service_reference_blockers
    assert value.cases[1].frame.exclusions == ("previously_exposed_normalized_text",)
    assert all(c.partition == "exposed_development" for c in value.cases)
    assert "requested_minor" not in value.canonical_json()
    assert not value.qualifies_full_service and not value.frozen_for_provider


def test_stale_pins_changed_method_or_unscheduled_selection_refuse():
    audit, accepted = source()
    for ordinals in ((), (1, 1), (0,), (3,), (True,)):
        with pytest.raises(ValueError, match="binding"):
            prepare(
                audit,
                accepted,
                ordinals,
                expected_audit_sha256=pin(audit),
                expected_acceptance_sha256=pin(accepted),
            )
    for field in ("source_revision", "source_csv_sha256", "mapping_sha256"):
        changed = accepted.model_copy(
            update={field: "c" * (40 if field == "source_revision" else 64)}
        )
        with pytest.raises(ValueError, match="binding"):
            prepare(
                audit,
                changed,
                (1,),
                expected_audit_sha256=pin(audit),
                expected_acceptance_sha256=pin(changed),
            )
    with pytest.raises(ValueError, match="binding"):
        prepare(
            audit,
            accepted,
            (1,),
            expected_audit_sha256="c" * 64,
            expected_acceptance_sha256=pin(accepted),
        )
    with pytest.raises(ValueError, match="binding"):
        prepare(
            audit,
            accepted,
            (1,),
            expected_audit_sha256=pin(audit),
            expected_acceptance_sha256="c" * 64,
        )


def test_individual_conflicts_and_edited_inputs_cannot_borrow_method_acceptance():
    audit, accepted = source()
    frame = audit.frames[0]
    value = bundle()
    for change in ({"input": AgentInput(request="Edited refund")}, {"expected_intent": "status"}):
        with pytest.raises(ValueError, match="inapplicable or changed"):
            IntentReference.model_validate_json(
                value.cases[0].model_copy(update=change).canonical_json()
            )
    changed = frame.model_copy(update={"exclusions": ("conflicting_native_text_labels",)})
    altered = audit.model_copy(update={"frames": (changed, audit.frames[1])})
    with pytest.raises(ValueError, match="inapplicable"):
        prepare(
            altered,
            accepted,
            (1,),
            expected_audit_sha256=pin(altered),
            expected_acceptance_sha256=pin(accepted),
        )
    with pytest.raises(ValueError, match="duplicate"):
        IntentBundle.model_validate_json(
            value.model_copy(update={"cases": (value.cases[0],) * 2}).canonical_json()
        )


def test_reference_acceptance_does_not_grant_release_or_qualified_label_authority():
    _, accepted = source()
    for key, item in (
        ("qualifies_individual_labels", True),
        ("replaces_release_review", True),
        ("provider_calls_authorized", 1),
        ("release_allowed", True),
    ):
        with pytest.raises(ValueError):
            IntentMethodAcceptance.model_validate_json(
                accepted.model_copy(update={key: item}).canonical_json()
            )


def observation(value, variant, case, trial, intent, failure=None):
    item = value.cases[case]
    return IntentObservation(
        variant=variant,
        case_id=item.case_id,
        trial_id=trial,
        input_sha256=pin(item.input),
        observed_intent=intent,
        failure_code=failure,
    )


def test_absent_candidate_failures_and_abstentions_remain_in_complete_denominators():
    value = bundle()
    rows = (
        observation(value, "rules", 0, "1", "refund"),
        observation(value, "rules", 1, "1", None, "invented_failure"),
        observation(value, "always-review", 0, "1", "review"),
    )
    report = compare(value, ("1", "2", "3"), rows)
    assert (report["scheduled"], report["observed"], report["missing"]) == (18, 3, 15)
    candidate = report["variants"]["candidate"]
    assert candidate["missing"] == 6 and candidate["scheduled_agreement_fraction"] == 0
    rules = report["variants"]["rules"]
    assert rules["failed"] == 1 and rules["native_reference_agreements"] == 1
    assert rules["all_repetitions_agree_cases"] == 0
    assert rules["confusions"]["status:failed"] == 1
    assert report["variants"]["always-review"]["review_abstentions"] == 1
    assert not report["amount_and_full_service_assessed"] and not report["qualification_met"]


def test_repetition_is_not_independence_and_forged_schedules_inputs_refuse():
    value = bundle()
    rows = tuple(
        observation(value, "rules", i, t, c.expected_intent)
        for i, c in enumerate(value.cases)
        for t in ("1", "2", "3")
    )
    report = compare(value, ("1", "2", "3"), rows)
    assert report["variants"]["rules"]["all_repetitions_agree_cases"] == 2
    assert report["normalized_text_buckets_not_independent"] == 2
    assert not report["population_confidence_established"]
    for altered in (
        (*rows, rows[0]),
        (rows[0].model_copy(update={"trial_id": "unknown"}),),
        (rows[0].model_copy(update={"input_sha256": "c" * 64}),),
    ):
        with pytest.raises(ValueError):
            compare(value, ("1", "2", "3"), altered)
    with pytest.raises(ValueError):
        compare(value, ("1", "1"), ())
    with pytest.raises(ValueError):
        observation(value, "rules", 0, "1", None)
