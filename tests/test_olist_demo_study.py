"""Same-file admission/capture tests with invented ledgers and no outbound requests."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.gateway import failed_response
from test_olist_demo import response

from docs.evaluation.olist_semantic_candidate import SemanticOutput
from olist_demo_acceptance import canonical, cases, digest
from olist_demo_budget_readback import historical_hash, inspect
from olist_demo_capture import capture, readback
from olist_demo_study import OwnerGrant, Scope, canaries, initialize, slots


def history(tmp_path):
    path = tmp_path / "shared.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE attempts(serial INTEGER,response_pin TEXT)")
        db.execute("INSERT INTO attempts VALUES(1,'invented-settled')")
        for name in (
            "olist_semantic_attempts",
            "olist_semantic_observations",
            "pa_reservations",
            "pa_settlements",
            "pa_live_attempts",
            "pa_live_settlements",
        ):
            db.execute("CREATE TABLE " + name + "(ordinal INTEGER)")
            db.execute("INSERT INTO " + name + " VALUES(1)")
        db.execute("CREATE TABLE authorization(document TEXT)")
        db.execute(
            "INSERT INTO authorization VALUES(?)", (json.dumps({"project_sha256": "a" * 64}),)
        )
        db.execute("CREATE TABLE pa_live_grant(document TEXT)")
        db.execute(
            "INSERT INTO pa_live_grant VALUES(?)",
            (
                json.dumps(
                    {
                        "lifetime_ceiling": 20,
                        "old_slots_preserved": 10,
                        "historical_consumed": 2,
                    }
                ),
            ),
        )
    report = inspect(path)
    now = datetime.now(UTC)
    scope = Scope(
        origin="mock",
        ledger_reference=str(path.resolve()),
        historical_sha256=report["historical_snapshot_sha256"],
        historical_consumed=4,
        retained_bound_slots=10,
        lifetime_ceiling=160,
        source_sha256="b" * 64,
        environment_sha256="c" * 64,
        reference_sha256=digest(canonical([c.model_dump(mode="json") for c in cases()])),
        project_sha256="a" * 64,
        starts_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(days=1),
        schedule=slots(),
    )
    return path, scope


def oracle():
    values = {text: value for text, value in canaries()}
    for case in cases():
        amount = case.requested_minor
        values[case.text] = SemanticOutput(
            intent=case.acceptable_intents[0],
            amount_status="explicit"
            if amount is not None
            else ("no_explicit_amount" if case.bucket == "refund" else "not_applicable"),
            requested_minor=amount,
            currency="SIM" if amount is not None else "unspecified",
            amount_evidence=(
                "SIM 100.00" if "SIM 100.00" in case.text else f"{amount / 100:.2f} SIM"
            )
            if amount is not None
            else None,
        )
    return values


class Scripted:
    """Explicit test oracle, not a candidate model or model-quality observation."""

    def __init__(self):
        self.calls = []
        self.values = oracle()

    def generate(self, wire, *, timeout_seconds):
        self.calls.append(wire)
        output = response().model_copy(
            update={
                "output": response().output.model_copy(
                    update={
                        "content": self.values[wire.messages[-1].content].canonical_json(),
                    }
                ),
            }
        )
        return output


def test_full146_capture_preserves_history_and_does_not_claim_mock_quality(tmp_path):
    path, scope = history(tmp_path)
    ledger = initialize(path, scope)
    transport = Scripted()
    report = capture(ledger, transport, origin="mock", verify=False)
    assert len(transport.calls) == 146
    assert report == readback(ledger)
    assert report["both_canaries_passed"] and report["missing_attempts"] == 0
    assert report["actual_provider_attempts"] == 0 and not report["model_quality_observed"]
    assert report["domain"]["scheduled_joint_agreement"] == 1
    assert not report["domain"]["proposed_demo_language_target_met"]
    assert not report["demo_release_accepted"]
    with ledger.connect() as db:
        assert (
            historical_hash(
                db,
                frozenset(
                    {
                        "olist_demo_scope",
                        "olist_demo_attempts",
                        "olist_demo_results",
                        "olist_demo_stop",
                    }
                ),
            )
            == scope.historical_sha256
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM olist_demo_attempts")
    current = inspect(path)
    assert current["total_consumed"] == 150 and current["latest_recorded_ceiling"] == 160
    with pytest.raises(PermissionError):
        ledger.reserve(1, slots()[0].request, now=datetime.now(UTC), origin="mock")


def test_reserved_unknown_request_cannot_be_sent_again(tmp_path):
    path, scope = history(tmp_path)
    ledger = initialize(path, scope)
    ledger.reserve(1, slots()[0].request, now=datetime.now(UTC), origin="mock")
    with pytest.raises(PermissionError):
        ledger.reserve(1, slots()[0].request, now=datetime.now(UTC), origin="mock")
    assert readback(ledger)["unsettled_attempts"] == 1
    assert inspect(path)["total_consumed"] == 5


def test_failed_canary_stops_without_retry_or_domain_dispatch(tmp_path):
    path, scope = history(tmp_path)
    ledger = initialize(path, scope)

    class Failed:
        calls = 0

        def generate(self, wire, *, timeout_seconds):
            self.calls += 1
            return failed_response(wire, "unavailable", "Invented failure", dispatched=True)

    transport = Failed()
    result = capture(ledger, transport, origin="mock", verify=False)
    assert transport.calls == 1 and result["stopped"]
    assert result["reserved_attempts"] == 1 and result["missing_attempts"] == 145
    assert result["domain"]["counts"]["missing"] == 144
    with pytest.raises(PermissionError):
        ledger.reserve(2, slots()[1].request, now=datetime.now(UTC), origin="mock")


def test_scope_and_provider_grant_are_separate_and_expiry_cannot_expand(tmp_path):
    path, scope = history(tmp_path)
    real = scope.model_copy(update={"origin": "provider"})
    before = path.read_bytes()
    with pytest.raises(PermissionError, match="separate exact owner"):
        initialize(path, real)
    assert path.read_bytes() == before
    grant = OwnerGrant(
        scope_sha256=digest(real.canonical_json().encode()),
        approval_ref="invented-owner-test-only",
        configured_project_still_free=True,
        accepts_authored_demo_references=True,
        authorizes_only_this_study=True,
    )
    with pytest.raises(PermissionError):
        initialize(path, real, grant, trusted_grant_sha256="0" * 64)
    ledger = initialize(
        path, real, grant, trusted_grant_sha256=digest(grant.canonical_json().encode())
    )
    with pytest.raises(PermissionError):
        ledger.reserve(1, slots()[0].request, now=scope.expires_at, origin="provider")
    with pytest.raises(PermissionError):
        capture(ledger, Scripted(), origin="provider", verify=False)


def test_historical_change_blocks_new_admission(tmp_path):
    path, scope = history(tmp_path)
    ledger = initialize(path, scope)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO attempts VALUES(2,'invented-new-history')")
    with pytest.raises(PermissionError, match="historical ledger changed"):
        ledger.reserve(1, slots()[0].request, now=datetime.now(UTC), origin="mock")


def test_actual_spawned_sdk_canaries_with_network_denied():
    from agent_harness.isolated_transport import IsolatedTransport

    from docs.evaluation.olist_semantic_candidate import parse
    from olist_demo_worker import SDKWorker

    outputs = {
        slot.request.fingerprint(): expected.canonical_json()
        for slot, (_, expected) in zip(slots()[:2], canaries(), strict=True)
    }
    worker = SDKWorker("invented-private-readiness-value", "a" * 64, fake_outputs=outputs)
    assert worker.origin == "mock" and worker.api_key not in repr(worker)
    transport = IsolatedTransport(worker)
    for slot, (text, expected) in zip(slots()[:2], canaries(), strict=True):
        result = transport.generate(slot.request, timeout_seconds=110)
        assert result.failure is None
        assert parse(text, result.output.content) == expected
        assert result.usage.model_calls == 1 and result.usage.input_tokens == 100
        assert transport.last_timing.exit_code == 0 and not transport.last_timing.timed_out


def test_copy_of_approved_ledger_cannot_spend(tmp_path):
    from olist_demo_study import Ledger

    path, scope = history(tmp_path)
    ledger = initialize(path, scope)
    copied = tmp_path / "copied.sqlite"
    copied.write_bytes(path.read_bytes())
    with pytest.raises(PermissionError, match="same approved ledger"):
        Ledger(copied, ledger.pin).reserve(
            1, slots()[0].request, now=datetime.now(UTC), origin="mock"
        )


def test_domain_predispatch_failure_remains_in_denominator_and_unknown_usage(tmp_path):
    path, scope = history(tmp_path)
    ledger = initialize(path, scope)
    scripted = Scripted()

    class ThirdFails:
        def generate(self, wire, *, timeout_seconds):
            if len(scripted.calls) == 2:
                return failed_response(
                    wire, "unavailable", "Invented pre-dispatch failure", dispatched=False
                )
            return scripted.generate(wire, timeout_seconds=timeout_seconds)

    result = capture(ledger, ThirdFails(), origin="mock", verify=False)
    assert result["reserved_attempts"] == 3 and result["both_canaries_passed"] and result["stopped"]
    assert result["domain"]["counts"]["attempted"] == 1
    assert result["domain"]["counts"]["provider_failure"] == 1
    assert result["domain"]["counts"]["missing"] == 143
    assert result["domain"]["counts"]["unknown_token_usage"] == 1


def test_known_usage_invalid_domain_output_is_scored_without_retry_or_early_stop(tmp_path):
    path, scope = history(tmp_path)
    ledger = initialize(path, scope)
    scripted = Scripted()

    class OneInvalid:
        def generate(self, wire, *, timeout_seconds):
            if len(scripted.calls) == 2:
                scripted.calls.append(wire)
                return failed_response(
                    wire,
                    "invalid_response",
                    "Invented generated shape error",
                    dispatched=True,
                    usage=response().usage,
                )
            return scripted.generate(wire, timeout_seconds=timeout_seconds)

    result = capture(ledger, OneInvalid(), origin="mock", verify=False)
    assert len(scripted.calls) == 146 and not result["stopped"]
    assert result["domain"]["counts"]["invalid_output"] == 1
    assert result["domain"]["counts"]["joint_correct"] == 143
    assert result["domain"]["counts"].get("missing", 0) == 0
