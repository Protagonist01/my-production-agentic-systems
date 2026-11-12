"""Only explicit trusted invented requests can enter the durable payer emulator."""

import pytest
from prior_auth.review_contracts import Principal, StateChanged

from prior_auth_demo import demo_request
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_sandbox import Submission, SyntheticPayer


@pytest.mark.parametrize("scenario", ["approved", "denied", "additional_information"])
def test_synthetic_response_restarts_replays_and_fences_versions(tmp_path, scenario):
    raw, profiler = b"AHI: 18 events/hour.", Profiler()
    request = demo_request(raw)
    note = prepare(raw, request, profiler).note
    user = Principal(
        username="demo-reviewer",
        tenant_id="demo",
        actor_id="operator",
        role="reviewer",
        case_ids=("demo-case",),
    )
    submission = Submission(
        request_id="request",
        case=request.case,
        case_version=1,
        note_sha256=note.note_sha256,
        policy_sha256=note.policy_sha256,
    )
    payer = SyntheticPayer(tmp_path / "payer.sqlite", payer_id="demo-payer", scenario=scenario)
    response = payer.submit(user, submission, note, current_version=1, profiler=profiler)
    rebuilt = SyntheticPayer(tmp_path / "payer.sqlite", payer_id="demo-payer", scenario="denied")
    assert rebuilt.submit(user, submission, note, current_version=1, profiler=profiler) == response
    assert response.status == scenario and not response.clinical_validation and rebuilt.count() == 1
    with pytest.raises(StateChanged):
        payer.submit(user, submission, note, current_version=2, profiler=profiler)
    with pytest.raises(StateChanged):
        payer.submit(
            user,
            submission.model_copy(update={"case_version": 2}),
            note,
            current_version=2,
            profiler=profiler,
        )
    with pytest.raises(PermissionError):
        payer.submit(
            user.model_copy(update={"role": "viewer"}),
            submission,
            note,
            current_version=1,
            profiler=profiler,
        )
    with pytest.raises(PermissionError):
        payer.submit(
            user,
            submission,
            note.model_copy(update={"provenance": "published_illustrative"}),
            current_version=1,
            profiler=profiler,
        )
