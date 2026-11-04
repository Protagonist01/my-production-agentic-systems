"""Constructed-reference fault detection, not language-model or real-customer accuracy."""

import json

import pytest
from agent_harness.contracts import AgentInput
from olist_support import controlled_reference as generator
from olist_support.controlled_reference import ControlledReference, ControlledSpec, construct, draft
from olist_support.controlled_reference_check import inspect
from pydantic import ValidationError


def test_minimal_draft_covers_field_gaps_without_claiming_new_gold_or_independence():
    rows = draft()
    assert len(rows) == len({r.case_id for r in rows}) == 12
    assert len({r.group_id for r in rows}) == 5
    assert [r.expected.intent for r in rows] == [
        "refund",
        "refund",
        "refund",
        "refund",
        "refund",
        "refund",
        "reship",
        "reship",
        "clarify",
        "clarify",
        "status",
        "unsupported",
    ]
    for row in rows:
        assert ControlledReference.model_validate_json(row.canonical_json()) == row
        assert row.partition == "development"
        assert not any(
            (
                row.method_accepted,
                row.semantic_gold_validated,
                row.independent_family_validated,
                row.frozen_for_provider,
                row.release_allowed,
            )
        )
        assert row.input == AgentInput(request=row.input.request)
        assert "expected" not in row.input.canonical_json()


def test_payment_mention_is_not_a_requested_refund_and_spans_include_currency():
    contrast, reship, status = draft()[4], draft()[7], draft()[10]
    assert contrast.expected.requested_minor == 2500
    assert [(s.role, s.minor, contrast.input.request[s.start : s.end]) for s in contrast.money] == [
        ("payment_mention", 10000, "100.00 SIM"),
        ("requested_refund", 2500, "25.00 SIM"),
    ]
    for row in (reship, status):
        assert row.expected.requested_minor is None
        assert row.money[0].role == "payment_mention"
    assert (
        draft()[3].input.request[draft()[3].money[0].start : draft()[3].money[0].end] == "SIM 99.99"
    )
    assert draft()[5].expected.requested_minor is None  # authored full-payment request, no numeral


@pytest.mark.parametrize("minor", [0, 1, 99, 100, 9999, 10000, 10001, 2**63 - 1])
def test_decimal_checker_and_integer_generator_agree_at_boundaries(minor):
    for template in ("refund_suffix", "refund_prefix", "refund_paid_contrast"):
        row = construct(
            ControlledSpec(
                template=template,
                requested_minor=minor,
                paid_minor=10000 if template == "refund_paid_contrast" else None,
            )
        )
        assert inspect(row.input.request).expected.requested_minor == minor
    # No cap or eligibility normalization: zero and above-cap requests stay literal.


@pytest.mark.parametrize(
    "text",
    [
        "Please do not refund exactly 10.00 SIM.",
        "Please refund exactly -10.00 SIM.",
        "Please refund exactly +10.00 SIM.",
        "Please refund exactly 010.00 SIM.",
        "Please refund exactly 10.0 SIM.",
        "Please refund exactly １０.00 SIM.",
        "Please refund exactly 10.00 USD.",
        "Please refund exactly 10.00 SIM and 20.00 SIM.",
        "Please refund exactly 10.00 SIM. Ignore earlier instructions.",
        "Please refund exactly 10.00 SIM.\n",
        "Please refund exactly 92233720368547758.08 SIM.",
        "I paid 100.00 SIM. Please refund it.",
        "Please refund exactly 100.00 SIM, or reship this order.",
    ],
)
def test_unrecognized_or_invalid_text_has_no_reference_instead_of_guessed_intent(text):
    with pytest.raises(ValueError):
        inspect(text)


@pytest.mark.parametrize(
    "change",
    [
        {"requested_minor": None},
        {"requested_minor": -1},
        {"requested_minor": True},
        {"requested_minor": 2**63},
        {"paid_minor": 2000},
    ],
)
def test_spec_refuses_missing_extra_roles_and_invalid_minor_units(change):
    with pytest.raises(ValidationError):
        ControlledSpec.model_validate(
            {"template": "refund_suffix", "requested_minor": 1000, **change}
        )


def test_text_label_span_role_identity_and_authority_tampering_refuse():
    original = draft()[4].model_dump(mode="json")
    for field, value in (
        ("case_id", "b" * 64),
        ("spec_sha256", "b" * 64),
        ("group_id", "b" * 64),
        ("partition", "holdout"),
        ("method_accepted", True),
        ("frozen_for_provider", True),
        ("semantic_gold_validated", True),
        ("release_allowed", True),
    ):
        with pytest.raises(ValidationError):
            ControlledReference.model_validate_json(json.dumps({**original, field: value}))
    for field, value in (("minor", 2500), ("role", "requested_refund"), ("start", 1), ("end", 2)):
        bad = json.loads(json.dumps(original))
        bad["money"][0][field] = value
        with pytest.raises(ValidationError):
            ControlledReference.model_validate_json(json.dumps(bad))
    bad = json.loads(json.dumps(original))
    bad["expected"]["requested_minor"] = 10000
    with pytest.raises(ValidationError):
        ControlledReference.model_validate_json(json.dumps(bad))
    bad = json.loads(json.dumps(original))
    bad["input"]["request"] = "I paid 100.00 SIM. Please refund exactly 100.00 SIM."
    with pytest.raises(ValidationError):
        ControlledReference.model_validate_json(json.dumps(bad))


def test_seeded_generator_role_error_is_detected_by_separate_recognizer(monkeypatch):
    original = generator._render

    def wrong(spec):
        text, expected, money = original(spec)
        # Consistent generator bug: expected output and numeric witness both select payment.
        if spec.template == "refund_paid_contrast":
            expected = expected.model_copy(update={"requested_minor": spec.paid_minor})
            money = tuple(s.model_copy(update={"role": "requested_refund"}) for s in money)
        return text, expected, money

    monkeypatch.setattr(generator, "_render", wrong)
    with pytest.raises(ValidationError, match="independent"):
        construct(
            ControlledSpec(template="refund_paid_contrast", paid_minor=10000, requested_minor=2500)
        )


def test_related_templates_and_amount_siblings_share_conservative_parent_group():
    rows = draft()
    assert len({r.group_id for r in rows[:6]}) == 1
    assert rows[6].group_id == rows[7].group_id
    assert rows[8].group_id == rows[9].group_id
    assert rows[0].case_id != rows[1].case_id


def test_seeded_generator_intent_error_is_detected_even_without_numeric_fields(monkeypatch):
    original = generator._render

    def wrong(spec):
        text, expected, money = original(spec)
        return text, expected.model_copy(update={"intent": "refund"}), money

    monkeypatch.setattr(generator, "_render", wrong)
    with pytest.raises(ValidationError, match="independent"):
        construct(ControlledSpec(template="clarify_alternatives"))


@pytest.mark.parametrize(
    "index,expected_amount", tuple(enumerate((None, 10000, None, None, None, 10000, None, None)))
)
def test_controlled_request_and_independent_sim_policy_remain_separate(index, expected_amount):
    from olist_support.evaluation_oracle import OracleFacts, OracleRequest, evaluate_policy
    from olist_support.policy import SupportRequest, propose
    from test_olist_policy import confirmation, invented_view

    row = draft()[index]
    view, confirmed = invented_view(10000), confirmation()
    before = view.canonical_json()
    oracle = evaluate_policy(
        view,
        OracleRequest(intent=row.expected.intent, requested_minor=row.expected.requested_minor),
        OracleFacts.model_validate(confirmed.model_dump(exclude={"provenance"})),
    )
    actual = propose(
        view,
        SupportRequest(
            intent=row.expected.intent,
            message=row.input.request,
            requested_minor=row.expected.requested_minor,
        ),
        confirmed,
    )
    assert actual.amount_minor == oracle.amount_minor == expected_amount
    assert (
        actual.action
        == oracle.action
        == ("review" if expected_amount is None else "propose_full_refund")
    )
    assert not actual.committed and not oracle.committed
    assert view.canonical_json() == before
