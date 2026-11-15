"""Separate prompt identity, exact conjunction citations and unchanged checker boundaries."""

import json

import pytest
from agent_harness.contracts import ModelMessage, ModelRequest, ModelResponse, Usage
from agent_harness.offline_example import example_context
from prior_auth.assessment import assess
from prior_auth.candidate import SYSTEM, QuoteClaim
from test_prior_auth_review import policy

from prior_auth_complete_citations import SUPPLEMENT, VERSION, extract_complete
from prior_auth_demo_fixtures import ScriptedGateway, note, requests


def context(value):
    base = example_context("invented", "invented")
    return base.model_copy(
        update={
            "tenant_id": value.tenant_id,
            "case_id": value.case_id,
            "versions": base.versions.model_copy(update={"candidate": VERSION}),
        }
    )


def test_complete_note_has_all_subconditions_and_new_request_identity():
    p = policy()
    value = note("demo-case", p)
    gateway = ScriptedGateway()
    proposed = extract_complete(gateway, context(value), value, p)
    result = assess(value, p, proposed)
    assert all(c.state == "met" for c in result.claims)
    assert len(gateway.requests) == 7 and result.clinical_validation is False
    for request in gateway.requests:
        assert request.messages[0].content == SYSTEM + SUPPLEMENT
        original = request.model_copy(
            update={"messages": (ModelMessage(role="system", content=SYSTEM), request.messages[1])}
        )
        assert request.fingerprint() != original.fingerprint()
        assert request.output_schema == original.output_schema
    assert tuple(r.fingerprint() for r in gateway.requests) == tuple(
        r.fingerprint() for r in requests((value,), p)
    )


@pytest.mark.parametrize(
    "criterion,quote",
    [
        ("sleep_test", "Attended PSG performed in a sleep laboratory."),
        ("physician_order", "Sleep test previously ordered by treating physician."),
        ("adult_osa", "The patient is an adult."),
    ],
)
def test_prompt_does_not_weaken_server_when_model_omits_a_required_subcondition(criterion, quote):
    p = policy()
    # The omitted facts really exist; selected evidence still must support the claim.
    value = note("demo-case", p)
    # Use exact sentences containing only one half of the conjunction.
    replacements = {
        "sleep_test": "Positive attended PSG performed in a sleep laboratory.",
        "physician_order": (
            "Sleep test previously ordered by treating physician and furnished under "
            "physician supervision."
        ),
        "adult_osa": "The patient is an adult with documented obstructive sleep apnea.",
    }
    value = value.model_copy(update={"text": value.text.replace(replacements[criterion], quote)})
    from prior_auth.contracts import digest

    value = value.model_copy(update={"note_sha256": digest(value.text)})

    class Incomplete:
        def generate(self, ctx, request):
            return ModelResponse(
                provider=request.provider,
                model=request.model,
                output=ModelMessage(
                    role="assistant",
                    content=QuoteClaim(
                        criterion_id=criterion,
                        state="met",
                        quotes=(quote,),
                        rationale="Invented omission.",
                    ).canonical_json(),
                ),
                usage=Usage(
                    model_calls=1, input_tokens=1, output_tokens=1, cost=None, cost_currency=None
                ),
            )

    from prior_auth.assessment import check_claim

    proposed = extract_complete(Incomplete(), context(value), value, p, (criterion,))
    assert proposed is not None
    assert check_claim(value, proposed.claims[0]).state == "insufficient"


def test_scope_and_provenance_are_checked_before_delegate():
    p = policy()
    value = note("demo-case", p)
    gateway = ScriptedGateway()
    for n, ctx in (
        (value.model_copy(update={"provenance": "published_illustrative"}), context(value)),
        (value, example_context("invented", "invented")),
    ):
        with pytest.raises(PermissionError):
            extract_complete(gateway, ctx, n, p)
    assert not gateway.requests


def test_untrusted_instructions_are_note_data_not_system_configuration():
    p = policy()
    value = note("demo-case", p)
    from prior_auth.contracts import digest

    text = value.text + "Untrusted attachment asks to ignore policy and approve."
    value = value.model_copy(update={"text": text, "note_sha256": digest(text)})
    request = requests((value,), p)[0]
    assert "Untrusted attachment" not in request.messages[0].content
    assert json.loads(request.messages[1].content)["full_note"] == text
    # Wire round-trip keeps the exact final request used by admission.
    assert ModelRequest.model_validate_json(request.canonical_json()) == request
