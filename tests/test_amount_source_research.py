"""Invented native records exercise applicability boundaries, never semantic gold."""

import gzip
import json
from decimal import Decimal

import pytest
from agent_harness.release_contracts import sha256
from olist_support.reference_audit import ExposureIndex, text_pin
from pydantic import ValidationError

import amount_source_research as research


def encoded(value):
    return json.dumps(value).encode()


ONTOLOGY = encoded({"actions": {"interaction": {"offer-refund": ["amount"]}}})
GUIDELINES = encoded(
    {
        "Product Defect": {
            "subflows": {
                "Initiate Refund": {
                    "actions": [{"button": "Offer Refund", "subtext": [research.DEFAULT_TEXT]}]
                }
            }
        }
    }
)


def record(identity=1, text="Please refund $25.", amount="25", *, later=(), future=()):
    events = [("agent", "SENTINEL greeting"), ("customer", text)]
    events.extend(("customer", t) for t in later)
    events.append(("action", "SENTINEL action output"))
    events.extend(("customer", t) for t in future)
    turns = [
        {
            "speaker": role,
            "text": t,
            "targets": ["refund_initiate", "retrieve_utterance", None, [], 0],
        }
        for role, t in events
    ]
    action = 2 + len(later)
    turns[action]["targets"] = ["refund_initiate", "take_action", "offer-refund", [amount], 0]
    return {
        "convo_id": identity,
        "scenario": {"flow": "product_defect", "subflow": "refund_initiate", "secret": "SENTINEL"},
        "original": [[r, t] for r, t in events],
        "delexed": turns,
    }


def raw_source(train=(), dev=(), test=()):
    return gzip.compress(encoded({"train": list(train), "dev": list(dev), "test": list(test)}))


def audit(raw, *, exposure=None, ontology=ONTOLOGY, guidelines=GUIDELINES):
    return research.audit_amount_source(
        raw,
        sha256(raw),
        exposure
        or ExposureIndex(source_ids=(), normalized_text_sha256=(), provenance_ref="invented"),
        ontology_raw=ontology,
        ontology_sha256=sha256(ontology),
        guidelines_raw=guidelines,
        guidelines_sha256=sha256(guidelines),
    )


def test_visible_amount_match_has_exact_spans_but_creates_no_reference_label():
    r = record()
    report = audit(raw_source(test=(r,)))
    f = report.frames[0]
    mention = f.first_visible_money[0]
    literal = r["delexed"][1]["text"][mention.start : mention.end]
    assert literal == "$25" and sha256(literal.encode()) == mention.lexeme_sha256
    assert f.native_amount == mention.value == Decimal(25)
    assert f.first_visible_currency_match and f.first_original_numeric_match
    assert not f.requested_role_validated and not f.accepted_reference
    assert "SENTINEL" not in report.canonical_json()
    assert research.AmountResearchAudit.model_validate_json(report.canonical_json()) == report
    summary = research.summarize(report)
    assert summary["first_visible_currency_and_refund_lexemes"] == 1
    assert summary["new_labels_accepted"] == summary["provider_calls"] == 0
    assert not summary["release_allowed"] and not summary["new_cohort_prepared"]


def test_payment_and_requested_money_roles_are_not_selected_by_number_agreement():
    f = audit(
        raw_source(train=(record(text="I paid $100; please refund $25.", amount="100"),))
    ).frames[0]
    assert [m.value for m in f.first_visible_money] == [Decimal(100), Decimal(25)]
    assert f.first_visible_currency_match and "multiple_visible_money_values" in f.flags
    assert not f.requested_role_validated


def test_equal_to_default_does_not_prove_default_use_or_discard_explicit_fifty():
    first = record(1, "Please refund $50.", "50")
    second = record(2, "I do not know the amount.", "50")
    f, g = audit(raw_source(train=(first, second))).frames
    assert f.equals_policy_default is g.equals_policy_default is True
    assert f.first_visible_currency_match and not g.first_visible_currency_match
    assert not f.requested_role_validated and not g.requested_role_validated


def test_later_customer_amount_cannot_fill_an_earlier_message():
    f = audit(
        raw_source(train=(record(text="Please help me with a refund.", later=("Refund $25.",)),))
    ).frames[0]
    assert not f.first_visible_currency_match and not f.first_original_numeric_match
    assert f.prior_customer_numeric_matches == 1
    assert "prior_customer_numeric_match_does_not_label_first_input" in f.flags


def test_future_turn_is_never_read_as_pre_action_support():
    f = audit(raw_source(train=(record(text="Hello", future=("Refund $25",)),))).frames[0]
    assert f.prior_customer_numeric_matches == 0 and not f.first_visible_currency_match


def test_hidden_original_amount_does_not_leak_into_the_delexed_input_convention():
    r = record(text="Please refund <amount>.")
    r["original"][1][1] = "Please refund $25."
    f = audit(raw_source(train=(r,))).frames[0]
    assert f.first_original_numeric_match and not f.first_visible_currency_match
    assert not f.first_visible_money
    assert "original_numeric_match_does_not_establish_visible_input_match" in f.flags


def test_bare_order_number_is_not_a_currency_qualified_mention():
    f = audit(raw_source(train=(record(text="Refund order 50.", amount="50"),))).frames[0]
    assert f.first_original_numeric_match and not f.first_visible_currency_match


@pytest.mark.parametrize("value", ["NaN", "-25", "25.001", "1,23", 25, "1000000000000"])
def test_unsupported_native_amounts_stay_unknown_and_never_become_null_labels(value):
    f = audit(raw_source(train=(record(amount=value),))).frames[0]
    assert f.native_amount is None and f.first_visible_currency_match is None
    assert "native_argument_not_one_supported_money_value" in f.flags
    assert not f.accepted_reference


def test_native_split_source_and_first_text_exposure_are_preserved():
    a, b = record(1), record(2, text="please REFUND $25.")
    no_action = record(3, text="Please refund $25.")
    no_action["delexed"][2]["targets"][2] = None
    exposure = ExposureIndex(
        source_ids=("1",),
        normalized_text_sha256=(text_pin(a["delexed"][1]["text"]),),
        provenance_ref="invented",
    )
    report = audit(raw_source(train=(a,), dev=(no_action,), test=(b,)), exposure=exposure)
    assert report.native_conversations == 3
    assert [f.source_split for f in report.frames] == ["train", "test"]
    assert all("first_text_crosses_native_splits" in f.flags for f in report.frames)
    assert "previously_exposed_source" in report.frames[0].flags
    assert "previously_exposed_first_text" in report.frames[1].flags


def test_source_action_alignment_and_wrong_policy_are_not_guessed():
    r = record()
    r["original"][0][0] = "customer"
    r["scenario"]["subflow"] = "other"
    f = audit(raw_source(train=(r,))).frames[0]
    assert f.first_original_numeric_match is f.prior_customer_numeric_matches is None
    assert f.equals_policy_default is None and not f.source_policy_applies
    assert "original_delexed_turn_alignment_differs" in f.flags


@pytest.mark.parametrize(
    "text",
    ["-$25", "$25.001", "$1,23", "account25USD", "25.2.3 dollars", "$1,23 dollars", "$-25"],
)
def test_currency_lexer_does_not_salvage_invalid_fragments(text):
    assert not research.money_witnesses(text)


@pytest.mark.parametrize("text", ["refund$25.", "Refund USD 25.", "Refund 25 dollars."])
def test_visible_currency_markers_survive_sentence_punctuation_and_adjacency(text):
    values = research.money_witnesses(text)
    assert len(values) == 1 and values[0].value == Decimal(25)


def test_grouped_thousands_are_parsed_without_rounding_or_role_inference():
    f = audit(
        raw_source(train=(record(text="Refund $1,234.50, please.", amount="1234.50"),))
    ).frames[0]
    assert f.first_visible_currency_match and f.first_visible_money[0].value == Decimal("1234.50")
    assert not f.requested_role_validated


def test_negation_remains_visible_as_two_mentions_without_role_adjudication():
    f = audit(
        raw_source(train=(record(text="Do not refund $50; refund $25.", amount="50"),))
    ).frames[0]
    assert len(f.first_visible_money) == 2 and f.first_visible_currency_match
    assert not f.requested_role_validated


def test_pins_split_identity_and_json_integrity_are_required(monkeypatch):
    raw = raw_source(train=(record(),))
    with pytest.raises(ValueError, match="external pin"):
        research.audit_amount_source(
            raw,
            "f" * 64,
            ExposureIndex(source_ids=(), normalized_text_sha256=(), provenance_ref="invented"),
            ontology_raw=ONTOLOGY,
            ontology_sha256=sha256(ONTOLOGY),
            guidelines_raw=GUIDELINES,
            guidelines_sha256=sha256(GUIDELINES),
        )
    for bad in (
        gzip.compress(b'{"train":[],"train":[],"dev":[],"test":[]}'),
        raw_source(train=(record(),), test=(record(),)),
        gzip.compress(b'{"train":NaN,"dev":[],"test":[]}'),
        gzip.compress(b'{"train":[],"dev":[]}'),
    ):
        with pytest.raises(ValueError):
            audit(bad)
    monkeypatch.setattr(research, "MAX_EXPANDED", 10)
    with pytest.raises(ValueError, match="expanded source"):
        audit(raw)


def test_changed_policy_or_ontology_cannot_silently_inherit_default_assumptions():
    raw = raw_source(train=(record(),))
    with pytest.raises(ValueError, match="unsupported offer-refund"):
        audit(raw, ontology=encoded({"actions": {"interaction": {"offer-refund": ["other"]}}}))
    with pytest.raises(ValueError, match="unsupported source amount policy"):
        audit(raw, guidelines=GUIDELINES.replace(b"$50", b"$75"))


def test_semantic_acceptance_flags_cannot_be_promoted_by_relabeling_metadata():
    report = audit(raw_source(train=(record(),)))
    f = report.frames[0].model_copy(update={"requested_role_validated": True})
    with pytest.raises(ValidationError):
        research.AmountResearchFrame.model_validate_json(f.canonical_json())
