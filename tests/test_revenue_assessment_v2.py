"""Authored mechanics only: no provider requests, qualified semantics or billing effects."""

import json

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.offline_example import example_context
from agent_harness.release_contracts import sha256

from revenue_assessment import (
    FIELDS,
    Citation,
    Meaning,
    ModelAssessment,
    ScopeAssessment,
    TermClaim,
    assess,
    decide_scope,
    preflight,
    screen_without_document,
)
from revenue_diagnostics import fixtures, rules
from revenue_profiling import Recorder


class Gateway:
    def __init__(self, content, *, provider="fake", error=None):
        self.content, self.provider, self.error = content, provider, error
        self.requests = []

    def generate(self, context, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return ModelResponse(
            provider=self.provider,
            model="fixture",
            output=ModelMessage(role="assistant", content=self.content),
            usage=Usage(
                model_calls=1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
            ),
        )


def invoke(gateway, *, fixture=None, tenant="invented"):
    fixture = fixture or fixtures()[0]
    context = example_context("authored", "locked").model_copy(
        update={"case_id": fixture.input.case_id, "tenant_id": tenant}
    )
    route = ModelRequest(
        provider="fake",
        model="fixture",
        endpoint="in-process",
        messages=(ModelMessage(role="user", content="replaced"),),
        parameters={},
    )
    return assess(
        context,
        fixture.input,
        fixture.request,
        fixture.binding,
        fixture.grant,
        gateway=gateway,
        route=route,
        recorder=Recorder(),
    )


def positive():
    fixture = fixtures()[0]
    meaning = rules(fixture, Recorder()).meaning
    return ModelAssessment(
        scope=ScopeAssessment(
            request="revenue", document="billing_agreement", sufficiency="sufficient"
        ),
        outcome="supported",
        spans=({"start": 0, "text": "unit_price_minor=1000"},),
        meaning=meaning,
    )


def test_read_only_positive_separates_literal_integrity_from_semantic_authority():
    gateway = Gateway(positive().canonical_json())
    result = invoke(gateway)
    assert result.decision.action == "analyze" and result.failure is None
    assert result.meaning.meaning_status == "reference_or_qualified_evaluator_required"
    assert result.meaning.billing_write_authorized is False
    assert result.decision.write_authorized is False and result.release_allowed is False
    wire = gateway.requests[0]
    assert not wire.tools and wire.tool_choice is None
    public = json.loads(wire.messages[1].content)
    assert set(public) == {"context", "question"}
    assert "expected_action" not in wire.canonical_json()


@pytest.mark.parametrize(
    "index,action",
    [(6, "review"), (7, "deny"), (8, "review"), (9, "review"), (10, "deny"), (13, "review")],
)
def test_trusted_scope_blocks_before_any_model(index, action):
    gateway = Gateway("unused")
    result = invoke(gateway, fixture=fixtures()[index])
    assert result.decision.action == action and gateway.requests == []


def test_request_tenant_and_read_grant_are_checked_before_content():
    gateway = Gateway("unused")
    assert invoke(gateway, tenant="wrong").decision.action == "deny"
    fixture = fixtures()[0]
    fixture = fixture.model_copy(
        update={"grant": fixture.grant.model_copy(update={"capabilities": ()})}
    )
    assert invoke(gateway, fixture=fixture).decision.action == "deny"
    assert gateway.requests == []


def test_pin_mismatch_and_forged_boundaries_fail_closed():
    fixture = fixtures()[0]
    binding = fixture.binding.model_copy(update={"document_sha256": "a" * 64})
    assert (
        preflight(fixture.request, fixture.input, binding, fixture.grant).reason
        == "document_pin_mismatch"
    )
    with pytest.raises(ValueError):
        preflight(
            fixture.request.model_copy(update={"period_end": fixture.request.period_start}),
            fixture.input,
            fixture.binding,
            fixture.grant,
        )


@pytest.mark.parametrize(
    "assessment,action",
    [
        (
            {"request": "unrelated", "document": "billing_agreement", "sufficiency": "sufficient"},
            "outside_scope",
        ),
        (
            {"request": "revenue", "document": "other_agreement", "sufficiency": "uncertain"},
            "request_information",
        ),
        (
            {"request": "revenue", "document": "billing_agreement", "sufficiency": "conflicting"},
            "review",
        ),
        ({"request": "uncertain", "document": "uncertain", "sufficiency": "uncertain"}, "review"),
    ],
)
def test_specific_scope_dispositions(assessment, action):
    assert decide_scope(ScopeAssessment.model_validate(assessment)).action == action


def test_no_document_screen_never_invents_contract_or_zero_amount():
    f = fixtures()[0]
    assert screen_without_document(f.request, f.grant, "unrelated").action == "outside_scope"
    assert screen_without_document(f.request, f.grant, "revenue").reason == "document_required"
    assert screen_without_document(f.request, f.grant, "uncertain").action == "review"
    with pytest.raises(ValueError):
        ScopeAssessment(request="revenue", document="billing_agreement", sufficiency="missing")


@pytest.mark.parametrize("text", ["{}", '{"scope":null,"scope":null}', "NaN", "[]", "not JSON"])
def test_invalid_duplicate_or_nonfinite_responses_are_not_success(text):
    result = invoke(Gateway(text))
    assert result.failure == "invalid_response" and result.decision.action == "review"


def test_timeout_identity_and_citation_mismatch_have_distinct_failures():
    assert invoke(Gateway("", error=TimeoutError("private"))).failure == "timeout"
    assert (
        invoke(Gateway(positive().canonical_json(), provider="wrong")).failure == "invalid_identity"
    )
    bad = positive().model_dump(mode="json")
    bad["meaning"]["terms"][0]["evidence"][0]["quote"] = "fabricated"
    assert invoke(Gateway(json.dumps(bad))).failure == "invalid_response"


def test_valid_quote_does_not_prove_its_asserted_numeric_meaning():
    bad = positive().model_dump(mode="json")
    bad["meaning"]["terms"][0]["value"] = 9000
    result = invoke(Gateway(json.dumps(bad)))
    assert result.failure is None  # literal checks cannot resolve semantic entailment
    assert result.meaning.terms[0].value == 9000
    assert result.meaning.billing_write_authorized is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", True),
        ("unit_price_minor", -1),
        ("currency", "usd"),
        ("effective_from", "tomorrow"),
        ("conditions", ""),
    ],
)
def test_typed_terms_refuse_invalid_values(field, value):
    with pytest.raises(ValueError):
        TermClaim(
            field=field,
            value=value,
            state="supported",
            evidence=(Citation(document_sha256=sha256(b"x"), start=0, quote="x"),),
        )


def test_all_fields_and_resolved_status_required_for_analysis():
    with pytest.raises(ValueError):
        Meaning(terms=tuple(TermClaim(field=f, state="missing", value=None) for f in FIELDS[:-1]))
    value = positive().model_dump(mode="json")
    value["meaning"]["terms"][0] = {"field": "unit_price_minor", "state": "missing", "value": None}
    assert invoke(Gateway(json.dumps(value))).failure == "invalid_response"
