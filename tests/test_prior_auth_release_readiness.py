"""Independent constructed boundaries and payer transport failure witnesses."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from prior_auth.contracts import digest
from prior_auth.review_contracts import StateChanged
from test_prior_auth_review import actor

from prior_auth_demo import demo_request
from prior_auth_pas import (
    REVIEW,
    REVIEW_CODE,
    X12,
    Loopback,
    PasClient,
    bundle,
    checked_inquiry,
    checked_response,
    encoded,
    object_from,
)
from prior_auth_pipeline import prepare
from prior_auth_profiling import Profiler
from prior_auth_reference_method import Index, reference
from prior_auth_sandbox import Submission
from prior_auth_study_draft import population


def fixture():
    raw = b"AHI: 18 events/hour."
    request = demo_request(raw)
    prepared = prepare(raw, request, Profiler())
    note = prepared.note
    assert note is not None
    submission = Submission(
        request_id="demo-send",
        case=request.case,
        case_version=1,
        note_sha256=note.note_sha256,
        policy_sha256=note.policy_sha256,
    )
    return submission, note


def payer_response(payload, code="A3"):
    resources = copy.deepcopy(payload["entry"])
    claim = resources[0]["resource"]
    claim["id"] = "server-claim"
    cr = {
        "resourceType": "ClaimResponse",
        "id": "response",
        "outcome": "complete",
        "request": {"reference": "Claim/server-claim"},
        "patient": claim["patient"],
        "insurer": claim["insurer"],
        "requestor": claim["provider"],
        "item": [
            {
                "itemSequence": 1,
                "adjudication": [
                    {
                        "extension": [
                            {
                                "url": REVIEW,
                                "extension": [
                                    {
                                        "url": REVIEW_CODE,
                                        "valueCodeableConcept": {
                                            "coding": [{"system": X12, "code": code}]
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                ],
            }
        ],
    }
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "identifier": {"value": "unrelated-random"},
        "entry": [{"resource": cr}, *resources[1:]],
    }, claim


def test_same_study_measure_semantics_are_separate_from_candidate():
    rows = {r.case_id: r.facts for r in population()}
    assert reference(rows["same-measure-conflict"])["severity"] == "conflict"
    assert reference(rows["different-measures"])["severity"] == "met"
    assert reference(rows["fractional-boundary"])["severity"] == "insufficient"
    assert reference(rows["moderate-without-symptom"])["severity"] == "not_met"
    assert reference(rows["moderate-with-symptom"])["severity"] == "met"
    assert reference(rows["type-iv-two-channels"])["sleep_test"] == "not_met"


def test_local_counts_never_become_a_national_reference_implicitly():
    facts = next(r.facts for r in population() if r.case_id == "short-study")
    # A rate of 18 does NOT require 36 events under the proposed local 30-event branch.
    assert reference(facts)["event_count"] == "insufficient"
    assert reference(facts, short_study="local-30-10-proposal")["event_count"] == "met"
    fewer = facts.model_copy(update={"recorded_events": 29})
    assert reference(fewer, short_study="local-30-10-proposal")["event_count"] == "not_met"
    low = facts.model_copy(
        update={
            "indices": (Index(measure="RDI", value=Decimal("5")),),
            "qualifying_symptom": True,
            "recorded_events": 10,
        }
    )
    assert reference(low, short_study="local-30-10-proposal")["event_count"] == "met"
    with pytest.raises(ValueError):
        reference(facts, short_study="typo")


def test_one_post_and_independent_correlation_then_durable_replay(tmp_path):
    request, note = fixture()
    calls = []
    response, stored = payer_response(bundle(request, note))

    def transport(method, path, payload):
        calls.append((method, path))
        return encoded(response if method == "POST" else stored)

    database = tmp_path / "payer.sqlite"
    client = PasClient(database, transport)
    first = client.submit(actor("demo-case"), request, note, current_version=1)
    second = PasClient(database, transport).submit(
        actor("demo-case"), request, note, current_version=1
    )
    assert first == second
    assert first.state == "received" and first.review_codes == ("A3",)
    assert first.processing == "complete" and first.clinical_validation is False
    assert calls == [("POST", "Claim/$submit"), ("GET", "Claim/server-claim")]
    assert "approve" not in first.canonical_json()
    assert note.text not in encoded(bundle(request, note)).decode()


@pytest.mark.parametrize(
    "change", ["wrong-claim", "wrong-patient", "absolute-url", "no-action", "duplicate-action"]
)
def test_untrusted_payer_response_cannot_become_approval_or_trigger_foreign_get(change):
    request, note = fixture()
    response, stored = payer_response(bundle(request, note))
    cr = response["entry"][0]["resource"]
    if change == "wrong-claim":
        stored["identifier"][0]["value"] = "different"
    elif change == "wrong-patient":
        response["entry"][1]["resource"]["identifier"][0]["value"] = "different"
    elif change == "absolute-url":
        cr["request"]["reference"] = "https://foreign.invalid/Claim/foo"
    elif change == "no-action":
        cr["item"] = []
    else:
        cr["item"] *= 2
    gets = []

    def read(method, path, payload):
        gets.append(path)
        return encoded(stored)

    with pytest.raises(ValueError):
        checked_response(encoded(response), digest(request.canonical_json()), request, read)
    assert not gets if change == "absolute-url" else len(gets) == 1


def test_lost_response_is_unknown_and_concurrent_callers_never_resend(tmp_path):
    request, note = fixture()
    calls = []

    def lost(*args):
        calls.append(1)
        raise TimeoutError("body containing private details")

    database = tmp_path / "payer.sqlite"
    client = PasClient(database, lost)

    def send(_):
        return client.submit(actor("demo-case"), request, note, current_version=1)

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(send, range(8)))
    assert len(calls) == 1
    assert all(r.state in {"unknown", "reserved"} for r in rows)
    assert "private details" not in database.read_bytes().decode(errors="ignore")
    assert (
        PasClient(database, lost).submit(actor("demo-case"), request, note, current_version=1).state
        == "unknown"
    )


def test_crash_after_reservation_preserves_uncertainty_without_second_post(tmp_path):
    request, note = fixture()

    def death(*args):
        raise SystemExit("simulated process death")

    client = PasClient(tmp_path / "payer.sqlite", death)
    with pytest.raises(SystemExit):
        client.submit(actor("demo-case"), request, note, current_version=1)
    assert client.submit(actor("demo-case"), request, note, current_version=1).state == "reserved"


def test_authority_and_current_state_checked_before_network_or_reservation(tmp_path):
    request, note = fixture()
    calls = []
    client = PasClient(tmp_path / "payer.sqlite", lambda *args: calls.append(args))
    for user, version, value in (
        (actor("demo-case", role="viewer"), 1, note),
        (actor("other"), 1, note),
        (actor("demo-case"), 2, note),
        (actor("demo-case"), 1, note.model_copy(update={"provenance": "published_illustrative"})),
    ):
        with pytest.raises((PermissionError, StateChanged)):
            client.submit(user, request, value, current_version=version)
    assert not calls
    with client.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM pas_attempts").fetchone()[0] == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8081/fhir",
        "http://localhost:8081/fhir",
        "http://127.0.0.1:8081/fhir?x=1",
        "http://user@127.0.0.1:8081/fhir",
        "http://169.254.169.254:80/fhir",
    ],
)
def test_only_owned_literal_loopback_is_accepted(url):
    with pytest.raises(ValueError):
        Loopback(url)


def test_ambiguous_json_and_nonobjects_are_refused():
    for raw in (b'{"resourceType":"Bundle","resourceType":"Claim"}', b"[]", b"x" * 2_000_001):
        with pytest.raises(ValueError):
            object_from(raw)


def test_inquiry_parameters_need_unique_match_and_independent_identity_readback():
    request, note = fixture()
    response, stored = payer_response(bundle(request, note))
    resources = {
        f"{e['resource']['resourceType']}/{e['resource']['id']}": e["resource"]
        for e in response["entry"][1:]
    }
    response["entry"] = response["entry"][:1]
    wrapper = {
        "resourceType": "Parameters",
        "parameter": [{"name": "responseBundle", "resource": response}],
    }
    gets = []

    def read(method, path, payload):
        gets.append(path)
        return encoded(stored if path == "Claim/server-claim" else resources[path])

    result = checked_inquiry(encoded(wrapper), digest(request.canonical_json()), request, read)
    assert result.review_codes == ("A3",) and len(gets) == 4
    for parameters in ([], wrapper["parameter"] * 2):
        with pytest.raises(ValueError):
            checked_inquiry(
                encoded({"resourceType": "Parameters", "parameter": parameters}),
                digest(request.canonical_json()),
                request,
                read,
            )


def test_proposal_has_separate_labels_and_no_false_qualification(tmp_path):
    from prior_auth_study_draft import prepare as draft

    directory = tmp_path / "draft"
    report = draft(directory)
    assert report["attempts_max"] == 170 and report["provider_authorized"] is False
    inputs = json.loads((directory / "inputs.json").read_text())
    labels = json.loads((directory / "proposed-references.json").read_text())
    assert len(inputs) == len(labels) == 12
    assert all("states" not in row and "facts" not in row for row in inputs)
    assert all(row["clinical_qualified"] is False for row in labels)
    with pytest.raises(FileExistsError):
        draft(directory)
