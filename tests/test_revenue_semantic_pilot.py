"""Invented sources test publisher-label isolation, not real semantic quality."""

import json
from datetime import UTC, datetime

import pytest
from agent_harness.baseline_recording import zero_usage
from agent_harness.contracts import ModelMessage, ModelResponse
from agent_harness.release_contracts import pin, sha256
from revenue_integrity.release_evaluation import ExtractionCase
from revenue_integrity.semantic_pilot import model_request, parse_judgment, prepare_pilot
from revenue_integrity.source_contracts import ExtractionInput, PublishedTarget, Span


def cases():
    return tuple(
        ExtractionCase(
            input=ExtractionInput(
                case_id=sha256(str(i).encode()),
                context="Invented term: annual.",
                question=f"What term for invented case {i}?",
            ),
            target=PublishedTarget(
                case_id=sha256(str(i).encode()),
                category="invented-category",
                answers=(Span(start=15, text="annual"),) if i % 2 == 0 else (),
                impossible=i % 2 != 0,
                family_id=sha256(("family" + str(i)).encode()),
                split="development",
            ),
        )
        for i in range(12)
    )


def test_preparation_balances_and_separates_calibration_families_without_relabeling():
    original = cases()
    pilot = prepare_pilot(original, source_manifest_sha256="a" * 64, frozen_at=datetime.now(UTC))
    assert len(pilot.cases) == 12 and pilot.provider_attempt_cap == 24
    assert sum(c.expected_accept for c in pilot.dataset.cases) == 6
    assert sum(c.split == "calibration" for c in pilot.dataset.cases) == 4
    assert len({k for c in pilot.dataset.cases for k in c.independence_keys}) == 12
    assert {pin(c.target) for c in pilot.cases} == {pin(c.target) for c in original}
    assert all(
        c.input_sha256
        == pin(model_request(next(x.input for x in pilot.cases if x.input.case_id == c.case_id)))
        for c in pilot.dataset.cases
    )


def test_projection_never_sends_label_family_case_id_or_category():
    case = cases()[0]
    request = model_request(case.input)
    public = json.loads(request.messages[1].content)
    assert public == {"context": case.input.context, "question": case.input.question}
    assert case.input.case_id not in request.canonical_json()
    for marker in (
        case.target.family_id,
        case.target.category,
        "impossible",
        "expected_accept",
        "answers",
    ):
        assert marker not in request.canonical_json()


def test_duplicate_source_bad_span_and_insufficient_families_refuse():
    source = cases()
    kwargs = dict(source_manifest_sha256="a" * 64, frozen_at=datetime.now(UTC))
    with pytest.raises(ValueError, match="duplicate"):
        prepare_pilot((*source, source[0]), **kwargs)
    with pytest.raises(ValueError, match="insufficient"):
        prepare_pilot(
            source, excluded_families=frozenset(c.target.family_id for c in source), **kwargs
        )
    bad = source[0].model_copy(
        update={
            "target": source[0].target.model_copy(
                update={"answers": (Span(start=0, text="absent"),)}
            )
        }
    )
    with pytest.raises(ValueError, match="span differs"):
        prepare_pilot((bad, *source[1:]), **kwargs)


def response(payload):
    return ModelResponse(
        provider="google-gemini-developer-api",
        model="gemini-3.5-flash-lite",
        output=ModelMessage(role="assistant", content=payload),
        usage=zero_usage("USD"),
    )


def test_parser_refuses_fabricated_quotes_inconsistent_decisions_and_duplicate_keys():
    value = cases()[0].input
    assert (
        parse_judgment(value, response('{"decision":"accept","quotes":["annual"]}')).decision
        == "accept"
    )
    assert (
        parse_judgment(value, response('{"decision":"abstain","quotes":[]}')).decision == "abstain"
    )
    for payload in (
        '{"decision":"accept","quotes":["fabricated"]}',
        '{"decision":"accept","quotes":[]}',
        '{"decision":"reject","quotes":["annual"]}',
        '{"decision":"accept","decision":"reject","quotes":[]}',
        '{"decision":"reject","quotes":[],"expected_accept":false}',
    ):
        with pytest.raises(ValueError):
            parse_judgment(value, response(payload))
