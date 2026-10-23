"""Invented classifier boundaries and hand-counted calibration witnesses."""

from datetime import timedelta

import pytest
from agent_harness.admission import GeminiFreeAdmission
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from agent_harness.gateway import failed_response
from agent_harness.offline_example import example_context
from cfpb_triage.calibration import EvaluatedCase, fit, measure
from cfpb_triage.classifier import route
from cfpb_triage.review import EvidenceSpan
from cfpb_triage.source_contracts import ComplaintInput
from cfpb_triage.triage_contracts import (
    Attempt,
    Prediction,
    RouterPolicy,
    Taxonomy,
    digest_text,
)


def taxonomy():
    return Taxonomy(
        version="invented", source_manifest="a" * 64, pairs={"Credit card": ("Billing dispute",)}
    )


def complaint():
    return ComplaintInput(case_id="b" * 64, narrative="Invented credit card billing dispute.")


def prediction(**changes):
    p = Prediction(
        product="Credit card",
        issue="Billing dispute",
        priority="routine",
        ambiguity="clear",
        confidence=0.9,
        evidence=(EvidenceSpan(start=9, end=20, text="credit card"),),
    )
    return p.model_copy(update=changes)


def policy():
    return RouterPolicy(
        taxonomy_sha256=taxonomy().digest(),
        cheap_threshold=0.8,
        strong_threshold=0.8,
        fit_manifest_sha256="c" * 64,
        fit_cases=2,
    )


def context():
    c = example_context("invented", "invented")
    return c.model_copy(
        update={
            "case_id": complaint().case_id,
            "deadline": c.clock + timedelta(minutes=2),
            "versions": c.versions.model_copy(
                update={
                    "policy": digest_text(policy().canonical_json()),
                    "data_snapshot": digest_text(complaint().narrative),
                }
            ),
        }
    )


def extracted_json(value):
    import json

    try:
        data = json.loads(value)
    except ValueError:
        return value
    data["quotes"] = [span["text"] for span in data.pop("evidence", [])]
    return json.dumps(data)


class Gateway:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def generate(self, context, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if response == "budget":
            return failed_response(request, "budget_exhausted", "invented", dispatched=False)
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content=extracted_json(response)),
            usage=Usage(
                model_calls=1, input_tokens=10, output_tokens=5, cost=None, cost_currency=None
            ),
        )


def test_real_pydantic_ai_custom_model_uses_bounded_gateway_once_and_hides_targets():
    g = Gateway(prediction().canonical_json())
    result = route(g, context(), complaint(), taxonomy(), policy())
    assert result.outcome == "classified" and len(g.requests) == 1
    assert g.requests[0].tools == () and g.requests[0].output_schema
    assert '"case_id"' not in g.requests[0].messages[-1].content
    assert result.attempts[0].usage.input_tokens == 10


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        prediction(product="Unknown product").canonical_json(),
        prediction(evidence=(EvidenceSpan(start=0, end=4, text="fake"),)).canonical_json(),
        prediction(
            evidence=(EvidenceSpan(start=9, end=999, text="not in narrative"),)
        ).canonical_json(),
        prediction(product=None, issue="Billing dispute").canonical_json(),
    ],
)
def test_invalid_schema_taxonomy_or_spans_routes_review_without_retry(output):
    g = Gateway(output)
    result = route(g, context(), complaint(), taxonomy(), policy())
    assert result.outcome == "review_required" and result.reason == "model_failure"
    assert len(g.requests) == 1


def test_budget_failure_and_elevated_priority_do_not_dispatch_strong():
    for output in ["budget", prediction(priority="elevated").canonical_json()]:
        g = Gateway(output)
        result = route(g, context(), complaint(), taxonomy(), policy())
        assert result.outcome == "review_required" and len(g.requests) == 1


def test_low_confidence_routes_once_to_distinct_strong_model():
    g = Gateway(prediction(confidence=0.5).canonical_json(), prediction().canonical_json())
    result = route(g, context(), complaint(), taxonomy(), policy())
    assert result.outcome == "classified" and len(g.requests) == 2
    assert g.requests[0].model != g.requests[1].model


def row(n, split="development", **changes):
    p = prediction()
    a = Attempt(
        route="cheap",
        model="invented-cheap",
        prediction=p,
        usage=Usage(
            model_calls=1, input_tokens=None, output_tokens=None, cost=None, cost_currency=None
        ),
    )
    b = a.model_copy(update={"route": "strong", "model": "invented-strong"})
    r = EvaluatedCase(
        case_id=digest_text(str(n)),
        group_id=digest_text("group" + str(n)),
        split=split,
        reference_product="Credit card",
        reference_issue="Billing dispute",
        provisional_priority="routine",
        provisional_ambiguity="clear",
        cheap=a,
        strong=b,
    )
    return r.model_copy(update=changes)


def test_calibration_rejects_holdout_and_preserves_error_review_denominators():
    rows = (row(1), row(2, reference_issue="Other"))
    fitted = fit(rows, taxonomy())
    assert fitted.cheap_threshold == 1.01 and fitted.strong_threshold == 1.01
    with pytest.raises(ValueError, match="development"):
        fit((row(3, split="holdout"),), taxonomy())
    metrics = measure(rows, fitted, "cheap_first")
    assert metrics.cases == 2 and metrics.review_required == 2 and metrics.classified == 0
    assert metrics.selective_error is None and metrics.elevated_review_recall is None
    assert metrics.usage_unknown_attempts == 4 and metrics.model_calls == 4


def test_exact_quotes_locate_unicode_and_refuse_ambiguous_occurrences():
    from cfpb_triage.triage_contracts import ExtractedPrediction

    item = complaint().model_copy(update={"narrative": "é🙂 credit card problem"})
    extracted = ExtractedPrediction(
        product="Credit card",
        issue="Billing dispute",
        priority="routine",
        ambiguity="clear",
        confidence=0.8,
        quotes=("credit card",),
    )
    assert extracted.locate(item, taxonomy()).evidence[0].start == 3
    for text in ["credit card credit card", "missing quotation"]:
        with pytest.raises(ValueError, match="one exact occurrence"):
            extracted.locate(item.model_copy(update={"narrative": text}), taxonomy())


def test_strong_free_route_requires_explicit_comparison_opt_in():
    from agent_harness.gemini import request_payload

    g = Gateway(prediction().canonical_json(), prediction().canonical_json())
    route(g, context(), complaint(), taxonomy(), policy(), mode="always_strong")
    request = g.requests[0]
    with pytest.raises(ValueError):
        GeminiFreeAdmission(free_tier_confirmed=True).quote(request)
    assert (
        GeminiFreeAdmission(free_tier_confirmed=True, flash_comparison=True).quote(request).max_cost
        == 0
    )
    with pytest.raises(ValueError):
        request_payload(request)
    request_payload(request, flash_comparison=True)
