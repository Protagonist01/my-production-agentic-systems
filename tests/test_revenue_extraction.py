"""Invented quotations prove integrity mechanisms, never model/legal quality."""

import json

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.gateway import failed_response
from agent_harness.offline_example import example_context
from revenue_integrity.extraction import (
    ExtractionClaim,
    GatewayExtractor,
    ParsedTerms,
    SyntheticDocument,
    abstain,
    extract,
    parse_synthetic,
    reconcile_extracted,
    synthetic_document,
    verify_extraction,
)
from revenue_integrity.reconcile_cli import main, reconcile_world
from revenue_integrity.source_contracts import ExtractionInput, Span
from test_revenue_reconcile import case


def original():
    return ExtractionInput(
        case_id="a" * 64,
        context="Invented α: renewal by agreement.",
        question="What is the renewal term?",
    )


def test_public_projection_only_candidate_and_citations_not_meaning():
    value = original()

    def candidate(public):
        assert set(public.model_dump()) == {"schema_version", "case_id", "context", "question"}
        return ExtractionClaim(
            case_id=public.case_id,
            outcome="supported",
            spans=(Span(start=12, text="renewal by agreement"),),
            rationale="Invented candidate output, not legal interpretation.",
        )

    result = extract(value, candidate)
    assert result.meaning_status == "not-validated"
    assert result.citation_integrity == "literal-spans-verified"
    assert extract(value, abstain).claim.outcome == "unsupported"


@pytest.mark.parametrize(
    ("case_id", "outcome", "spans"),
    [
        ("b" * 64, "supported", (Span(start=0, text="Invented"),)),
        ("a" * 64, "supported", (Span(start=0, text="Fabricated"),)),
        ("a" * 64, "supported", ()),
        ("a" * 64, "uncertain", (Span(start=0, text="Invented"),)),
        ("a" * 64, "supported", (Span(start=0, text="Invented"), Span(start=0, text="Invented"))),
    ],
)
def test_misbound_forged_and_contradictory_claims_fail(case_id, outcome, spans):
    claim = ExtractionClaim(case_id=case_id, outcome=outcome, spans=spans, rationale="Invented.")
    with pytest.raises(ValueError):
        verify_extraction(original(), claim)


def test_extracted_terms_path_uses_cited_text_instead_of_provided_gold():
    value = case()
    changed = value.terms.model_dump()
    changed["seats"] = 4
    from revenue_integrity.billing_contracts import SubscriptionTerms

    document = synthetic_document(value.case_id, SubscriptionTerms.model_validate(changed))
    parsed = parse_synthetic(document)
    assert reconcile_extracted(value, document, parsed).should_be_minor == 4000
    assert len(parsed.citations) == 7
    forged = parsed.model_dump()
    forged["terms"]["seats"] = 3
    with pytest.raises(ValueError, match="do not match"):
        reconcile_extracted(value, document, ParsedTerms.model_validate(forged))
    with pytest.raises(ValueError):
        reconcile_extracted(value, document.model_copy(update={"case_id": "other"}), parsed)


@pytest.mark.parametrize("text", ["seats=2", "seats=2\nseats=3", "unknown=2", "seats=true"])
def test_incomplete_duplicate_unknown_grammar_does_not_guess(text):
    with pytest.raises(ValueError):
        parse_synthetic(SyntheticDocument(case_id="invented", text=text))


def test_cli_offline_paths_and_private_input(tmp_path, capsys):
    value = case()
    path = tmp_path / "input.json"
    path.write_text(value.model_dump_json(), encoding="utf-8")
    output = tmp_path / "result.json"
    main(["reconcile", "--input", str(path), "--output", str(output)])
    assert json.loads(output.read_text())["should_be_minor"] == 3000
    assert json.loads(capsys.readouterr().out)["written"] is True
    path.write_text(original().model_dump_json(), encoding="utf-8")
    output = tmp_path / "extraction.json"
    main(["extract-original", "--input", str(path), "--output", str(output)])
    assert json.loads(output.read_text())["claim"]["outcome"] == "unsupported"
    assert "renewal" not in capsys.readouterr().out


def test_cli_invalid_private_payload_does_not_echo_source(tmp_path, capsys):
    path = tmp_path / "invalid.json"
    path.write_text('{"private":"CANARY_PRIVATE_SOURCE_R4"}', encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["reconcile", "--input", str(path), "--output", str(tmp_path / "out.json")])
    assert "CANARY" not in str(error.value)
    assert "CANARY" not in str(capsys.readouterr())
    assert not (tmp_path / "out.json").exists()


class ScriptedGateway:
    def __init__(self, text=None, failure=False):
        self.text, self.failure, self.requests = text, failure, []

    def generate(self, context, request):
        self.requests.append(request)
        if self.failure:
            return failed_response(request, "timeout", "Invented timeout", dispatched=True)
        return ModelResponse(
            provider=request.provider,
            model=request.model,
            output=ModelMessage(role="assistant", content=self.text),
            usage=Usage(
                model_calls=1, input_tokens=10, output_tokens=5, cost=None, cost_currency=None
            ),
        )


def gateway_extractor(gateway):
    route = ModelRequest(
        provider="invented",
        endpoint="in-process",
        model="invented-r4",
        messages=(ModelMessage(role="user", content="must disappear"),),
        parameters={"max_output_tokens": 999999},
    )
    return GatewayExtractor(gateway, route)


def test_gateway_extracts_only_public_context_and_question_with_bounded_output():
    gateway = ScriptedGateway(
        json.dumps(
            {
                "outcome": "supported",
                "spans": [{"start": 12, "text": "renewal by agreement"}],
                "rationale": "Invented scripted answer.",
            }
        )
    )
    context = example_context("invented-code", "invented-lock").model_copy(
        update={"case_id": original().case_id}
    )
    result = gateway_extractor(gateway).run(context, original())
    assert result.extraction.claim.outcome == "supported"
    assert result.extraction.claim.case_id == original().case_id
    assert result.extraction.meaning_status == "not-validated"
    request = gateway.requests[0]
    assert len(gateway.requests) == 1
    assert json.loads(request.messages[1].content) == {
        "context": original().context,
        "question": original().question,
    }
    assert request.parameters["max_output_tokens"] <= 2048
    assert not request.tools and request.tool_choice is None
    assert "must disappear" not in request.canonical_json()
    assert "case_id" not in request.output_schema["properties"]


@pytest.mark.parametrize(
    "text",
    [
        "not JSON",
        '{"outcome":"supported","spans":[],"rationale":"no evidence"}',
        '{"outcome":"supported","spans":[{"start":0,"text":"forged"}],"rationale":"x"}',
        '{"outcome":"unsupported","rationale":"x","case_id":"forged"}',
    ],
)
def test_malformed_or_forged_gateway_answer_requires_review(text):
    gateway = ScriptedGateway(text)
    context = example_context("invented-code", "invented-lock").model_copy(
        update={"case_id": original().case_id}
    )
    result = gateway_extractor(gateway).run(context, original())
    assert result.failure_code == "invalid_extraction_response"
    assert result.extraction.claim.outcome == "uncertain"
    assert len(gateway.requests) == 1 and result.usage.model_calls == 1


def test_gateway_failure_and_input_limits_never_fabricate_an_answer():
    gateway = ScriptedGateway(failure=True)
    context = example_context("invented-code", "invented-lock").model_copy(
        update={"case_id": original().case_id}
    )
    extractor = gateway_extractor(gateway)
    assert extractor.run(context, original()).failure_code == "timeout"
    long = original().model_copy(update={"context": "x" * 200001})
    assert extractor.run(context, long).failure_code == "input_too_large"
    assert len(gateway.requests) == 1
    with pytest.raises(ValueError, match="case differ"):
        extractor.run(example_context("invented-code", "invented-lock"), original())


def test_scoped_tool_requires_read_and_reconcile_before_disclosing_world(tmp_path):
    from revenue_integrity.billing_access import BillingGrant
    from revenue_integrity.billing_worlds import cases, prepare

    output = tmp_path / "worlds"
    prepare(output)
    value = cases()[0].input
    fields = dict(
        tenant_id=value.tenant_id, actor_id="invented-reviewer", world_ids=(value.case_id,)
    )
    for capabilities in (("read",), ("reconcile",), ()):
        with pytest.raises(PermissionError):
            reconcile_world(
                output / "inputs.sqlite",
                value.case_id,
                BillingGrant(**fields, capabilities=capabilities),
            )
    grant = BillingGrant(**fields, capabilities=("read", "reconcile"))
    assert reconcile_world(output / "inputs.sqlite", value.case_id, grant).case_id == value.case_id
    with pytest.raises(PermissionError):
        reconcile_world(output / "inputs.sqlite", "other-world", grant)
    with pytest.raises(PermissionError):
        reconcile_world(
            output / "inputs.sqlite",
            value.case_id,
            grant.model_copy(update={"tenant_id": "other-tenant"}),
        )


@pytest.mark.parametrize(
    "changed",
    [
        {"provider": "other-provider"},
        {"model": "other-model"},
        {"model_revision": "other-revision"},
    ],
)
def test_wrong_gateway_candidate_identity_never_becomes_supported(changed):
    class WrongIdentity(ScriptedGateway):
        def generate(self, context, request):
            response = super().generate(context, request)
            return response.model_copy(update={"model_revision": "pinned-revision", **changed})

    gateway = WrongIdentity(
        json.dumps(
            {
                "outcome": "supported",
                "spans": [{"start": 0, "text": "Invented"}],
                "rationale": "Invented identity mismatch test.",
            }
        )
    )
    extractor = gateway_extractor(gateway)
    extractor.route = extractor.route.model_copy(update={"model_revision": "pinned-revision"})
    context = example_context("invented-code", "invented-lock").model_copy(
        update={"case_id": original().case_id}
    )
    result = extractor.run(context, original())
    assert result.failure_code == "model_identity_mismatch"
    assert result.extraction.claim.outcome == "uncertain"
    assert result.usage.model_calls == 1


def test_unchecked_gateway_response_is_revalidated_before_content():
    class InvalidResponse(ScriptedGateway):
        def generate(self, context, request):
            response = super().generate(context, request)
            return response.model_copy(
                update={"usage": response.usage.model_copy(update={"model_calls": -1})}
            )

    gateway = InvalidResponse('{"outcome":"unsupported","rationale":"Invented."}')
    context = example_context("invented-code", "invented-lock").model_copy(
        update={"case_id": original().case_id}
    )
    result = gateway_extractor(gateway).run(context, original())
    assert result.failure_code == "invalid_model_response"
    assert result.extraction.claim.outcome == "uncertain"
    assert result.usage is None
