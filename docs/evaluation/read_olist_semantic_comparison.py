"""Independent capture readback and field-specific development scoring, never release."""

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Literal

from agent_harness.contracts import ModelRequest, ModelResponse, WireContract
from agent_harness.cost_accounting import verify_accounting
from agent_harness.isolated_transport import AttemptTiming
from agent_harness.release_contracts import Sha256

from docs.evaluation.olist_semantic_candidate import SemanticOutput, parse, request
from docs.evaluation.olist_semantic_controls import Scope, canonical, historical_anchor, pin


class Reference(WireContract):
    case_id: str
    input_sha256: Sha256
    stratum: Literal[
        "native_direct_proposed",
        "native_intent_accepted",
        "price_role_unresolved",
        "constructed_accepted",
    ]
    intent: Literal["refund", "status", "reship", "clarify", "unsupported", "review"] | None
    amount_status: Literal["explicit", "no_explicit_amount", "not_applicable"] | None
    requested_minor: int | None
    currency: Literal["SIM", "dollar_unspecified", "unspecified"] | None


def score_rows(
    scope: Scope,
    requests: tuple[ModelRequest, ...],
    rows: list[dict],
    references: tuple[Reference, ...],
) -> dict:
    refs = {r.case_id: r for r in references}
    if (
        pin(canonical([r.model_dump(mode="json") for r in references]))
        != scope.reference_packet_sha256
    ):
        raise ValueError("separately frozen reference packet differs")
    if len(refs) != 24 or len(references) != 24 or len(requests) != 74:
        raise ValueError("complete separate reference/request inventory required")
    by_slot = {row["ordinal"]: row for row in rows}
    if len(by_slot) != len(rows) or sorted(by_slot) != list(range(1, len(rows) + 1)):
        raise ValueError("capture rows are not an ordered unique prefix")
    counts: dict[str, Counter] = {}
    for slot, req in zip(scope.slots[2:], requests[2:], strict=True):
        ref = refs.get(slot.case_id)
        if (
            ref is None
            or hashlib.sha256(req.messages[-1].content.encode()).hexdigest() != ref.input_sha256
        ):
            raise ValueError("reference does not bind the actual candidate input")
        c = counts.setdefault(ref.stratum, Counter())
        c["scheduled"] += 1
        c["intent_reference" if ref.intent is not None else "intent_unknown"] += 1
        c["amount_reference" if ref.amount_status is not None else "amount_unknown"] += 1
        row = by_slot.get(slot.ordinal)
        if row is None:
            c["missing"] += 1
            continue
        c["observed"] += 1
        if row["extracted"] is None or row["timing"]["parent_failure"] is not None:
            c["failed"] += 1
            continue
        actual = SemanticOutput.model_validate_json(json.dumps(row["extracted"]))
        if ref.intent is not None:
            c["intent_match"] += int(actual.intent == ref.intent)
        if ref.amount_status is not None:
            c["amount_match"] += int(
                (actual.amount_status, actual.requested_minor, actual.currency)
                == (ref.amount_status, ref.requested_minor, ref.currency)
            )
    fields = (
        "scheduled",
        "observed",
        "missing",
        "failed",
        "intent_reference",
        "intent_unknown",
        "amount_reference",
        "amount_unknown",
        "intent_match",
        "amount_match",
    )
    strata = {s: {k: c[k] for k in fields} for s, c in counts.items()}
    total = {k: sum(c[k] for c in counts.values()) for k in fields}
    return {
        "domain": total,
        "strata": strata,
        "trials_are_independent_language_families": False,
        "development_only": True,
        "qualification": False,
        "release_allowed": False,
    }


def read_capture(
    output: Path,
    ledger: Path,
    scope: Scope,
    expected_scope_pin: str,
    completion_sha256: str,
    references: tuple[Reference, ...],
    canary_expected: tuple[SemanticOutput, ...],
) -> dict:
    """Recompute all bindings, raw/derived usage, quotes and parent observations."""
    if pin(scope.canonical_json()) != expected_scope_pin:
        raise ValueError("external scope pin differs")
    if (
        len(canary_expected) != 2
        or pin(canonical([x.model_dump(mode="json") for x in canary_expected]))
        != scope.canary_expectations_sha256
    ):
        raise ValueError("frozen canary expectations differ")
    raw = (output / "completion.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != completion_sha256:
        raise ValueError("external completion pin differs")
    completion = json.loads(raw)
    capture_raw = (output / "capture.json").read_bytes()
    if hashlib.sha256(capture_raw).hexdigest() != completion["capture_sha256"]:
        raise ValueError("capture pin differs")
    captured = json.loads(capture_raw)
    request_raw = (output / "requests.json").read_bytes()
    before = json.loads((output / "before.json").read_bytes())
    if (
        before["scope_sha256"] != expected_scope_pin
        or completion["scope_sha256"] != expected_scope_pin
        or before["origin"] != scope.origin
        or completion["origin"] != scope.origin
        or hashlib.sha256(request_raw).hexdigest() != before["requests_sha256"]
    ):
        raise ValueError("capture/request/scope origin differs")
    requests = tuple(
        ModelRequest.model_validate_json(json.dumps(x)) for x in json.loads(request_raw)
    )
    if len(requests) != 74:
        raise ValueError("74 request inventory required")
    for slot, req in zip(scope.slots, requests, strict=True):
        if slot.request_sha256 != req.fingerprint() or req != request(req.messages[-1].content):
            raise ValueError("fixed candidate request differs")
    inputs = [
        {"case_id": scope.slots[i].case_id, "input": {"text": requests[i].messages[-1].content}}
        for i in range(2, 74, 3)
    ]
    if pin(canonical(inputs)) != scope.input_packet_sha256:
        raise ValueError("original input-only packet differs")
    with sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if historical_anchor(db) != scope.historical_anchor_sha256:
            raise ValueError("historical ledger changed")
        installed = db.execute("SELECT pin,document FROM olist_semantic_scope").fetchall()
        if installed != [(expected_scope_pin, scope.canonical_json())]:
            raise ValueError("installed scope differs")
        attempts = db.execute(
            "SELECT ordinal,request_pin FROM olist_semantic_attempts ORDER BY ordinal"
        ).fetchall()
        observations = db.execute(
            "SELECT ordinal,response,response_pin,timing,continue_allowed "
            "FROM olist_semantic_observations ORDER BY ordinal"
        ).fetchall()
    rows = captured["rows"]
    n = len(rows)
    if (
        len(attempts) != n
        or len(observations) != n
        or captured["consumed"] != n
        or captured["missing"] != 74 - n
        or captured["scheduled"] != 74
        or completion["consumed"] != n
        or captured["origin"] != scope.origin
        or captured["actual_provider_attempts"] != (n if scope.origin == "provider" else 0)
        or captured["business_effects_executed"] is not False
        or captured["semantic_accuracy_scored"] is not False
        or captured["qualification"] is not False
        or captured["release_allowed"] is not False
    ):
        raise ValueError("complete consumed/observed prefix or authority flags differ")
    for index, row in enumerate(rows):
        slot, req = scope.slots[index], requests[index]
        ordinal = slot.ordinal
        response = ModelResponse.model_validate_json(json.dumps(row["response"]))
        raw_response = ModelResponse.model_validate_json(
            (output / f"raw-{ordinal:02d}.json").read_bytes()
        )
        verify_accounting(req, response)
        if response.accounting is not None:
            saved = response.accounting
            if (
                saved["capture_scope_sha256"] != expected_scope_pin
                or saved["allowance_sha256"] != scope.allowance_sha256
                or saved["tariff"] != scope.tariff.model_dump(mode="json")
                or response.model_copy(update={"usage": raw_response.usage, "accounting": None})
                != raw_response
            ):
                raise ValueError("raw usage/tariff/control attachment differs")
        elif response != raw_response:
            raise ValueError("unaccounted raw response differs")
        ok = row["timing"]["parent_failure"] is None
        if (
            attempts[index] != (ordinal, req.fingerprint())
            or row["ordinal"] != ordinal
            or row["phase"] != slot.phase
            or row["request_sha256"] != req.fingerprint()
            or observations[index]
            != (
                ordinal,
                response.canonical_json(),
                pin(response.canonical_json()),
                canonical(row["timing"]),
                int(ok),
            )
            or (not ok and index != n - 1)
        ):
            raise ValueError("attempt/response/parent continuation binding differs")
        if row["timing"]["worker"] is None:
            raise ValueError("worker timing missing")
        AttemptTiming.model_validate_json(json.dumps(row["timing"]["worker"]))
        if ok:
            if (
                response.failure is not None
                or response.output is None
                or response.output.content is None
            ):
                raise ValueError("successful response missing")
            extracted = parse(req.messages[-1].content, response.output.content)
            if extracted.model_dump(mode="json") != row["extracted"]:
                raise ValueError("recomputed candidate output differs")
            if slot.phase == "canary" and extracted != canary_expected[index]:
                raise ValueError("canary did not pass its frozen expectation")
    report = score_rows(scope, requests, rows, references)
    report.update(
        {
            "origin": scope.origin,
            "consumed_attempts": n,
            "remaining_attempts": 74 - n,
            "provider_billing_observed": False,
        }
    )
    return report
