"""Hand-counted authored contract/readback and adapter boundaries; no real provider."""

import json
import sqlite3
from collections import Counter
from pathlib import Path

import pytest
from agent_harness.contracts import ModelMessage, ModelResponse, Usage
from olist_support.workflow import WorkflowRequest
from test_olist_workflow import context

from docs.evaluation.olist_semantic_candidate import SemanticOutput, request
from olist_demo_acceptance import cases, digest, prepare
from olist_demo_evaluation import Observation, schedule, summarize
from olist_demo_planner import DemoPlanner, project


def test_all_namespace_readback_counts_separate_semantic_attempt_and_never_mutates(tmp_path):
    from olist_demo_budget_readback import inspect

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
    before = path.read_bytes()
    report = inspect(path)
    assert path.read_bytes() == before
    assert report["total_consumed"] == 4 and report["legacy_pa_reported_total"] == 3
    assert report["proposed_required_ceiling"] == 160
    assert report["new_attempts_authorized"] == 0
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO olist_semantic_attempts VALUES(2)")
    assert inspect(path)["unsettled_by_namespace"]["olist_semantic_attempts"] == 1
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE unknown_attempts(ordinal INTEGER)")
    with pytest.raises(ValueError, match="explicit audited mapping"):
        inspect(path)


def test_revenue_namespace_counts_calls_and_preserves_unused_allocation(tmp_path):
    from test_olist_demo_study import history

    from olist_demo_budget_readback import inspect

    path, _ = history(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE pa_live_grant SET document=?",
            (
                json.dumps(
                    {
                        "lifetime_ceiling": 793,
                        "old_slots_preserved": 169,
                        "historical_consumed": 2,
                    }
                ),
            ),
        )
        db.execute(
            "CREATE TABLE revenue_scope_843(ordinal INTEGER PRIMARY KEY "
            "CHECK(ordinal BETWEEN 0 AND 49), request_pin TEXT NOT NULL, result TEXT)"
        )
        for i in range(18):
            db.execute("INSERT INTO revenue_scope_843 VALUES(?,?,?)", (i, "a" * 64, "{}"))
    before = path.read_bytes()
    report = inspect(path)
    assert path.read_bytes() == before
    assert report["reservation_counts"]["revenue_scope_843"] == 18
    assert report["total_consumed"] == 22
    assert report["latest_recorded_ceiling"] == 843
    assert report["retained_bound_slots"] == 201
    assert report["revenue_unspent_slots_preserved"] == 32
    assert report["proposed_required_ceiling"] == 369
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO revenue_scope_843 VALUES(18,?,NULL)", ("b" * 64,))
    report = inspect(path)
    assert report["total_consumed"] == 23
    assert report["unsettled_by_namespace"]["revenue_scope_843"] == 1
    assert report["retained_bound_slots"] == 200
    assert report["proposed_required_ceiling"] == 369
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE plausible_future_scope(ordinal INTEGER)")
    with pytest.raises(ValueError, match="explicit audited mapping"):
        inspect(path)


def test_revenue_namespace_schema_change_fails_closed(tmp_path):
    from test_olist_demo_study import history

    from olist_demo_budget_readback import inspect

    path, _ = history(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE revenue_scope_843(ordinal INTEGER PRIMARY KEY, "
            "request_pin TEXT NOT NULL,result TEXT)"
        )
    with pytest.raises(ValueError, match="Revenue reservation schema"):
        inspect(path)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://invented:invented@example.test/demo?sslmode=require",
        "postgresql://invented:invented@localhost/demo?sslmode=verify-full",
        "postgresql://invented@example.test/demo?sslmode=verify-full",
        "not a connection string",
    ],
)
def test_host_configuration_refuses_weak_or_missing_tls_without_echoing_secret(dsn):
    from olist_demo_host import DatabaseConfiguration

    config = DatabaseConfiguration(dsn=dsn)
    with pytest.raises(ValueError) as failure:
        config.verify_transport()
    assert dsn not in str(failure.value) and "invented" not in str(config)


def test_host_configuration_accepts_verified_remote_dsn_without_connecting():
    from olist_demo_host import DatabaseConfiguration

    DatabaseConfiguration(
        dsn="postgresql://invented:invented@db.example.test/demo?sslmode=verify-full"
    ).verify_transport()


def response(intent="status", **changes):
    output = {
        "intent": intent,
        "amount_status": "not_applicable",
        "requested_minor": None,
        "currency": "unspecified",
        "amount_evidence": None,
        **changes,
    }
    return ModelResponse(
        provider="google-gemini-developer-api",
        model="gemini-3.5-flash-lite",
        output=ModelMessage(role="assistant", content=json.dumps(output)),
        usage=Usage(
            model_calls=1, input_tokens=100, output_tokens=20, cost=None, cost_currency=None
        ),
    )


def test_packet_separates_only_inputs_and_marks_unknowns_without_fabricated_gold(tmp_path):
    result = prepare(tmp_path / "draft")
    assert result["cases"] == 48 and result["provider_calls"] == 0
    packet = tmp_path / "draft"
    manifest = json.loads((packet / "manifest.json").read_text())
    for name, pin in manifest["files"].items():
        assert digest((packet / name).read_bytes()) == pin
    inputs = json.loads((packet / "inputs.json").read_text())
    assert all(set(row) == {"case_id", "input"} and set(row["input"]) == {"text"} for row in inputs)
    refs = json.loads((packet / "references.json").read_text())
    assert Counter(r["bucket"] for r in refs) == dict.fromkeys(
        ("refund", "status", "reship", "clarify", "unrelated", "adversarial"), 8
    )
    assert not any(r["independent_language_gold"] for r in refs)
    assert sum(not r["amount_reference_known"] for r in refs) == 16
    with pytest.raises(FileExistsError):
        prepare(packet)


def test_packet_refuses_git_checkouts():
    with pytest.raises(ValueError, match="outside Git"):
        prepare(Path(__file__).resolve().parents[1] / "artifacts" / "must-not-create")


def test_missing_attempts_and_cost_cannot_become_success():
    result = summarize(())
    assert result["counts"] == {
        "scheduled": 144,
        "known_amount_scheduled": 96,
        "explicit_amount_scheduled": 18,
        "missing": 144,
    }
    assert result["scheduled_joint_agreement"] == 0
    assert result["known_cost_sum"] is None
    assert result["latency_p95_ms_attempted"] is None
    assert not result["proposed_demo_language_target_met"] and not result["demo_release_accepted"]


def test_actual_rows_have_scheduled_denominator_and_reject_duplicates_or_wrong_request():
    case = next(c for c in cases() if c.bucket == "status")
    row = Observation(
        case_id=case.case_id,
        trial=1,
        request_sha256=request(case.text).fingerprint(),
        response=response(),
        elapsed_ms=12.0,
    )
    report = summarize((row,))
    assert report["scheduled_joint_agreement"] == 1 / 144
    assert report["counts"]["missing"] == 143
    assert report["counts"]["unknown_cost"] == 1
    assert report["all_trials_consistent_cases"] == 0
    assert report["known_cost_sum"] is None
    for rows in ((row, row), (row.model_copy(update={"request_sha256": "0" * 64}),)):
        with pytest.raises(ValueError):
            summarize(rows)
    assert len(schedule()) == 144 and len(set(schedule())) == 144


@pytest.mark.parametrize("currency", ["dollar_unspecified", "other"])
def test_non_sim_requested_money_never_becomes_implicit_full_refund(currency):
    value = SemanticOutput(
        intent="refund",
        amount_status="explicit",
        requested_minor=2500,
        currency=currency,
        amount_evidence="$25",
    )
    assert project(value).intent == "review"
    assert project(value).requested_minor is None


def test_unclear_money_goes_to_review_and_explicit_absence_can_use_policy_total():
    value = SemanticOutput(
        intent="refund",
        amount_status="unclear",
        requested_minor=None,
        currency="unspecified",
        amount_evidence=None,
    )
    assert project(value).intent == "review"
    assert (
        project(value.model_copy(update={"amount_status": "no_explicit_amount"})).intent == "refund"
    )


def test_planner_sends_exact_text_and_fails_closed_on_bad_output():
    calls = []

    class Gateway:
        def generate(self, ctx, wire):
            calls.append(wire)
            return response(
                "refund",
                amount_status="explicit",
                requested_minor=3725,
                currency="SIM",
                amount_evidence="37.25 SIM",
            )

    planner = DemoPlanner(Gateway())
    text = "Please refund 37.25 SIM."
    actual = planner.plan(context(), WorkflowRequest(order_id="invented-order", text=text))
    assert actual.plan.requested_minor == 3725
    assert calls == [request(text)]
    wrong = planner.plan(context(), WorkflowRequest(order_id="invented-order", text="Where is it?"))
    assert wrong.plan.intent == "review" and wrong.failure_code == "invalid_semantic_response"


def test_verbatim_price_quote_can_pass_mechanics_but_still_fail_semantic_scoring():
    case = next(c for c in cases() if c.case_id == "olist-demo-status-5")
    row = Observation(
        case_id=case.case_id,
        trial=1,
        request_sha256=request(case.text).fingerprint(),
        response=response(
            "refund",
            amount_status="explicit",
            requested_minor=4500,
            currency="SIM",
            amount_evidence="45.00 SIM",
        ),
        elapsed_ms=10.0,
    )
    result = summarize((row,))
    assert result["counts"]["parsed"] == 1
    assert result["counts"]["false_refund_route"] == 1
    assert result["scheduled_joint_agreement"] == 0


def test_fixed_baselines_are_real_outputs_and_always_review_has_eight_matches():
    from olist_demo_evaluation import baselines

    result = baselines()
    assert result["always-review"]["joint_correct"] == 8
    assert all(value["model_calls"] == 0 and len(value["rows"]) == 48 for value in result.values())
    assert result == baselines()


def test_unknown_money_role_is_not_scored_as_known_absence():
    case = next(c for c in cases() if c.case_id == "olist-demo-refund-7")
    row = Observation(
        case_id=case.case_id,
        trial=1,
        request_sha256=request(case.text).fingerprint(),
        response=response("refund", amount_status="unclear"),
        elapsed_ms=1.0,
    )
    result = summarize((row,))
    assert result["counts"]["intent_correct"] == 1
    assert result["counts"]["known_amount_correct"] == 0
    assert result["counts"]["joint_correct"] == 0
