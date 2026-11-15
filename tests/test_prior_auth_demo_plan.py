"""The runnable missing-document scenario binds both sides before any fake work."""

import json

import pytest
from prior_auth.assessment import assess
from prior_auth.contracts import NoteInput, digest
from test_prior_auth_complete_citations import context
from test_prior_auth_review import NOW, policy

from prior_auth_complete_citations import extract_complete
from prior_auth_demo_console import plan
from prior_auth_demo_fixtures import EDUCATION, ScriptedGateway, requests
from prior_auth_pipeline import ImportRequest, prepare
from prior_auth_profiling import Profiler


def test_education_wait_plan_freezes_supplement_and_actual_resume_requests():
    imported, scope, files = plan(policy(), now=NOW, scenario="education-wait")
    initial = prepare(files["source.txt"].encode(), imported, Profiler()).note
    assert initial is not None and EDUCATION not in initial.text
    result = assess(
        initial, policy(), extract_complete(ScriptedGateway(), context(initial), initial, policy())
    )
    assert next(c for c in result.claims if c.criterion_id == "education").state == "insufficient"
    supplement = ImportRequest.model_validate_json(files["supplement-request.json"])
    assert supplement.expected_version == 2 and supplement.case == imported.case
    assert supplement.document.kind == "education_record"
    assert prepare(files["supplement.txt"].encode(), supplement, Profiler()).decision.admitted
    text = initial.text + "\n\n--- Reviewed supplemental evidence ---\n" + EDUCATION
    resumed = NoteInput.model_validate_json(
        initial.model_copy(update={"text": text, "note_sha256": digest(text)}).canonical_json()
    )
    request = next(
        r
        for r in requests((resumed,), policy())
        if json.loads(r.messages[1].content)["criterion"]["criterion_id"] == "education"
    )
    assert request.fingerprint() in scope.request_sha256s
    gateway = ScriptedGateway()
    proposed = extract_complete(gateway, context(resumed), resumed, policy(), ("education",))
    assert proposed.claims[0].evidence[0].quote == EDUCATION
    assert proposed.claims[0].evidence[0].start == text.rindex(EDUCATION)
    assert scope.mode == "offline_fake" and scope.provider_scope_sha256 is None


def test_complete_plan_has_no_implicit_supplement_and_unknown_scenario_is_refused():
    _, scope, files = plan(policy(), now=NOW, scenario="complete")
    assert set(files) == {"request.json", "policy.json", "source.txt", "scope.json"}
    assert scope.max_attempts == 7
    with pytest.raises(ValueError):
        plan(policy(), now=NOW, scenario="guess")
