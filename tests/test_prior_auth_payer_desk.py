"""The desk serializer disambiguates packets without changing legacy wire bytes."""

from prior_auth.contracts import digest
from test_prior_auth_release_readiness import fixture, payer_response
from test_prior_auth_review import actor

from prior_auth_pas import PasClient, bundle, encoded
from prior_auth_payer_desk import traced_bundle


def test_trace_is_stable_packet_specific_and_legacy_serializer_is_unchanged():
    request, note = fixture()
    original = bundle(request, note)
    traced = traced_bundle(request, note)
    assert "extension" not in original["entry"][0]["resource"]["item"][0]
    trace = traced["entry"][0]["resource"]["item"][0]["extension"][0]
    assert trace["valueIdentifier"]["value"] == digest(request.canonical_json())
    assert traced_bundle(request, note) == traced
    other = traced_bundle(request.model_copy(update={"request_id": "another"}), note)
    assert other["entry"][0]["resource"]["item"][0]["extension"][0] != trace
    assert bundle(request, note) == original
    assert note.text not in encoded(traced).decode()


def test_injected_serializer_is_used_before_submit_and_keeps_independent_readback(tmp_path):
    request, note = fixture()
    calls = []
    response, stored = payer_response(traced_bundle(request, note))

    def transport(method, path, payload):
        calls.append((method, path, payload))
        return encoded(response if method == "POST" else stored)

    client = PasClient(tmp_path / "trace.sqlite", transport, builder=traced_bundle)
    receipt = client.submit(actor("demo-case"), request, note, current_version=1)
    assert receipt.state == "received"
    assert calls[0] == ("POST", "Claim/$submit", traced_bundle(request, note))
    assert calls[1] == ("GET", "Claim/server-claim", None)
