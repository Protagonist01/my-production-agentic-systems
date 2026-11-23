"""Offline continuation admission: preserve failures, never resend, bound unknown usage."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import Usage
from agent_harness.gateway import failed_response
from test_olist_demo_study import Scripted, history

from olist_demo_acceptance import digest
from olist_demo_continuation import (
    Continuation,
    ContinuationScope,
    accounted_tokens,
    prefix_pin,
    prepare,
    responses,
)
from olist_demo_study import OwnerGrant, initialize


def server_failure(wire):
    return failed_response(
        wire, "unavailable", "Gemini HTTP request failed", dispatched=True, retryable=True
    )


def seeded(tmp_path, origin="mock"):
    path, parent = history(tmp_path)
    if origin == "provider":
        parent = parent.model_copy(update={"origin": "provider"})
        grant = OwnerGrant(
            scope_sha256=digest(parent.canonical_json().encode()),
            approval_ref="invented-parent-test-only",
            configured_project_still_free=True,
            accepts_authored_demo_references=True,
            authorizes_only_this_study=True,
        )
        ledger = initialize(
            path, parent, grant, trusted_grant_sha256=digest(grant.canonical_json().encode())
        )
    else:
        ledger = initialize(path, parent)
    script = Scripted()
    for ordinal in (1, 2, 3):
        wire = parent.schedule[ordinal - 1].request
        ledger.reserve(ordinal, wire, now=datetime.now(UTC), origin=origin)
        ledger.settle(
            ordinal,
            script.generate(wire, timeout_seconds=110) if ordinal <= 2 else server_failure(wire),
            1,
        )
    with ledger.connect() as db:
        prefix = prefix_pin(db, 3)
    scope = ContinuationScope(
        parent_scope_sha256=ledger.pin,
        parent_prefix_sha256=prefix,
        parent_attempts=3,
        source_sha256=parent.source_sha256,
        environment_sha256=parent.environment_sha256,
        starts_at=parent.starts_at,
        expires_at=parent.expires_at,
    )
    return path, ledger, scope


def test_complete_remaining_slots_preserves_parent_failure_stop_and_denominator(tmp_path):
    path, ledger, scope = seeded(tmp_path)
    continuation = Continuation(path, scope)
    script = Scripted()
    result = continuation.capture(script, pause=False)
    assert len(script.calls) == 143 and result["reserved_attempts"] == 146
    assert script.calls[0] == ledger.scope(ledger.connect()).schedule[3].request
    assert result["domain"]["counts"]["joint_correct"] == 143
    assert result["domain"]["counts"]["provider_failure"] == 1
    assert result["domain"]["all_scheduled_domain_observations_present"]
    assert result["domain"]["computed_suite_target_met"]
    assert not result["domain"]["proposed_demo_language_target_met"]
    assert result["parent_stop_preserved"] and result["observed_usage_unknown_rows"] == 1
    assert result["conservatively_accounted_tokens"] >= GEMINI_TOKEN_CEILING
    with ledger.connect() as db:
        assert prefix_pin(db, 3) == scope.parent_prefix_sha256
        assert db.execute("SELECT count(*) FROM olist_demo_stop").fetchone()[0] == 1
    assert continuation.capture(Scripted(), pause=False) == result


def test_new_provider_authority_required_before_continuation(tmp_path):
    path, _, scope = seeded(tmp_path, "provider")
    with pytest.raises(PermissionError, match="new exact owner grant"):
        Continuation(path, scope)
    grant = OwnerGrant(
        scope_sha256=digest(scope.canonical_json().encode()),
        approval_ref="invented-new-continuation-only",
        configured_project_still_free=True,
        accepts_authored_demo_references=True,
        authorizes_only_this_study=True,
    )
    with pytest.raises(PermissionError, match="new exact owner grant"):
        Continuation(path, scope, grant, trusted_grant_sha256="0" * 64)
    current = Continuation(
        path, scope, grant, trusted_grant_sha256=digest(grant.canonical_json().encode())
    )
    with pytest.raises(PermissionError, match="real SDK"):
        current.capture(Scripted(), pause=False)


def test_outstanding_attempt_and_parallel_reserver_never_resend(tmp_path):
    path, _, scope = seeded(tmp_path)
    first, second = Continuation(path, scope), Continuation(path, scope)
    first.reserve(4, now=datetime.now(UTC))
    with pytest.raises(PermissionError, match="outstanding"):
        second.reserve(4, now=datetime.now(UTC))
    script = Scripted()
    with pytest.raises(PermissionError, match="outstanding"):
        second.capture(script, pause=False)
    assert not script.calls


def test_copied_ledger_cannot_spend(tmp_path):
    path, _, scope = seeded(tmp_path)
    copied = tmp_path / "copied.sqlite"
    copied.write_bytes(path.read_bytes())
    with pytest.raises(PermissionError, match="same approved ledger"):
        Continuation(copied, scope)


def test_three_consecutive_http_failures_stop_without_retry(tmp_path):
    path, _, scope = seeded(tmp_path)
    current = Continuation(path, scope)

    class Fails:
        calls = []

        def generate(self, wire, *, timeout_seconds):
            self.calls.append(wire)
            return server_failure(wire)

    script = Fails()
    result = current.capture(script, pause=False)
    assert len(script.calls) == 2 and result["reserved_attempts"] == 5
    assert result["continuation_halt_reason"] == "http_failure_circuit"
    assert result["conservatively_accounted_tokens"] >= 3 * GEMINI_TOKEN_CEILING
    with pytest.raises(PermissionError, match="stopped"):
        current.reserve(6, now=datetime.now(UTC))


def test_cooldown_before_next_slots_preserves_failed_occurrences(tmp_path, monkeypatch):
    path, _, scope = seeded(tmp_path)
    current = Continuation(path, scope)
    pauses = []
    monkeypatch.setattr("olist_demo_continuation.time.sleep", pauses.append)

    class OneMoreFailure(Scripted):
        def generate(self, wire, *, timeout_seconds):
            if not self.calls:
                self.calls.append(wire)
                return server_failure(wire)
            return super().generate(wire, timeout_seconds=timeout_seconds)

    script = OneMoreFailure()
    result = current.capture(script)
    assert pauses == [60, 60]
    assert len(script.calls) == 143 and result["reserved_attempts"] == 146
    assert result["domain"]["counts"]["provider_failure"] == 2
    assert result["domain"]["counts"]["joint_correct"] == 142


def test_eighth_nonconsecutive_http_failure_stops_even_with_tokens_remaining(tmp_path):
    path, _, scope = seeded(tmp_path)
    current = Continuation(path, scope)

    class Alternating(Scripted):
        def generate(self, wire, *, timeout_seconds):
            if len(self.calls) % 2 == 0:
                self.calls.append(wire)
                return server_failure(wire)
            return super().generate(wire, timeout_seconds=timeout_seconds)

    script = Alternating()
    result = current.capture(script, pause=False)
    assert len(script.calls) == 13
    assert result["observed_usage_unknown_rows"] == 8
    assert result["continuation_halt_reason"] == "http_failure_circuit"
    assert result["conservatively_accounted_tokens"] < scope.max_accounted_tokens


def test_known_usage_invalid_domain_output_is_scored_without_retry(tmp_path):
    path, _, scope = seeded(tmp_path)
    current = Continuation(path, scope)

    class OneInvalid(Scripted):
        def generate(self, wire, *, timeout_seconds):
            result = super().generate(wire, timeout_seconds=timeout_seconds)
            if len(self.calls) == 1:
                return failed_response(
                    wire,
                    "invalid_response",
                    "Invented shape error",
                    dispatched=True,
                    usage=result.usage,
                )
            return result

    script = OneInvalid()
    result = current.capture(script, pause=False)
    assert len(script.calls) == 143 and result["settled_attempts"] == 146
    assert result["domain"]["counts"]["invalid_output"] == 1
    assert result["domain"]["counts"]["joint_correct"] == 142


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("timeout", "Gemini request timed out"),
        ("rate_limited", "Gemini HTTP 429"),
        ("unavailable", "Gemini transport failed"),
        ("unavailable", "Worker failed; usage unknown"),
        ("invalid_response", "Unsupported or invalid Gemini request"),
    ],
)
def test_other_failures_remain_stops(tmp_path, code, message):
    path, ledger, scope = seeded(tmp_path)
    current = Continuation(path, scope)
    current.reserve(4, now=datetime.now(UTC))
    wire = ledger.scope(ledger.connect()).schedule[3].request
    ledger.settle(4, failed_response(wire, code, message, dispatched=True), 1)
    assert current.readback()["continuation_halt_reason"] is not None
    with pytest.raises(PermissionError, match="stopped"):
        current.reserve(5, now=datetime.now(UTC))


def test_unknown_tokens_are_fully_reserved_and_next_quote_must_fit(tmp_path):
    path, _, scope = seeded(tmp_path)
    current = Continuation(path, scope)

    class LargeUsage(Scripted):
        def generate(self, wire, *, timeout_seconds):
            result = super().generate(wire, timeout_seconds=timeout_seconds)
            return result.model_copy(
                update={
                    "usage": Usage(
                        model_calls=1,
                        input_tokens=GEMINI_TOKEN_CEILING - 1,
                        output_tokens=1,
                        cost=None,
                        cost_currency=None,
                    )
                }
            )

    script = LargeUsage()
    result = current.capture(script, pause=False)
    assert len(script.calls) == 7
    # The two preserved canaries each reported 100 input plus 20 output tokens.
    assert result["conservatively_accounted_tokens"] == 8 * GEMINI_TOKEN_CEILING + 240
    assert result["continuation_halt_reason"] == "conservative_token_limit"
    with current.ledger.connect() as db:
        assert accounted_tokens(responses(db)) == 8 * GEMINI_TOKEN_CEILING + 240


def test_original_window_and_history_cannot_be_amended_silently(tmp_path):
    path, ledger, scope = seeded(tmp_path)
    with pytest.raises(PermissionError, match="expiry differs"):
        Continuation(
            path, scope.model_copy(update={"expires_at": scope.expires_at + timedelta(days=1)})
        )
    with pytest.raises(PermissionError, match="expired"):
        Continuation(path, scope).reserve(4, now=scope.expires_at)
    with ledger.connect() as db:
        db.execute("INSERT INTO attempts VALUES(2,'invented-unrelated-change')")
    with pytest.raises(PermissionError, match="historical ledger changed"):
        Continuation(path, scope)


def test_prefix_binds_ddl_even_if_update_trigger_removed(tmp_path):
    path, ledger, scope = seeded(tmp_path)
    with ledger.connect() as db:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE olist_demo_attempts SET created='changed' WHERE ordinal=3")
        db.execute("DROP TRIGGER immutable_olist_demo_attempts_UPDATE")
        db.execute("UPDATE olist_demo_attempts SET created='changed' WHERE ordinal=3")
    with pytest.raises(PermissionError, match="parent history"):
        Continuation(path, scope)


def test_preparation_grants_no_calls_and_preserves_expiry(tmp_path, monkeypatch):
    path, ledger, scope = seeded(tmp_path)
    monkeypatch.setattr("olist_demo_continuation.environment_pin", lambda: scope.environment_sha256)
    result = prepare(tmp_path / "packet", path, ledger.pin, now=datetime.now(UTC))
    assert result["provider_calls_authorized"] == 0
    assert result["remaining_original_slots"] == 143
    assert result["ceiling_unchanged"] == 160 and result["retained_unchanged"] == 10
    assert result["expires_at_unchanged"] == scope.expires_at.isoformat()
