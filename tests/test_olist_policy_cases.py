"""Invented source-to-private-case pipeline; literal expected outputs stay evaluator-only."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from olist_fixtures import dataset, manifest, snapshot, write_rows
from olist_support.policy import propose
from olist_support.policy_case_cli import prepare
from olist_support.policy_cases import PolicyCases, digest, group_id
from olist_support.source import import_snapshot


def source(tmp_path, *, extra_population=False):
    raw = dataset(tmp_path)
    orders, payments = [], []
    values = ("10.00", "20.00", "30.00", "40.00", "101.00", "50.00")
    for i, value in enumerate(values * (2 if extra_population else 1)):
        orders.append(
            dict(
                order_id=f"invented-order-{i}",
                customer_id="customer-1",
                order_status="delivered" if i % 6 == 5 else "canceled",
                order_purchase_timestamp="2020-01-01 09:00:00",
                order_delivered_customer_date="2020-01-05 10:00:00" if i % 6 == 5 else "",
            )
        )
        payments.append(
            dict(order_id=f"invented-order-{i}", payment_sequential="1", payment_value=value)
        )
    for name, rows in (
        ("olist_orders_dataset.csv", orders),
        ("olist_order_payments_dataset.csv", payments),
        ("olist_order_items_dataset.csv", []),
        ("olist_order_reviews_dataset.csv", []),
    ):
        write_rows(raw / name, snapshot.REQUIRED[name], rows)
    pin, value = manifest(raw, tmp_path)
    database = tmp_path / "orders.sqlite"
    report = import_snapshot(
        raw,
        pin,
        value,
        database,
        observed_at=datetime(2026, 10, 18),
        repository=Path(__file__).resolve().parents[1],
    )
    return database, report["database_sha256"]


def test_private_hybrid_pilot_has_grouped_splits_and_literal_hidden_labels(tmp_path):
    database, pin = source(tmp_path)
    output = tmp_path / "pilot"
    report = prepare(database, pin, output, as_of=datetime(2026, 10, 19))
    cases = PolicyCases.model_validate_json((output / "evaluator.json").read_bytes())
    assert report["case_count"] == 12 and report["group_count"] == 6
    assert report["split_counts"] == {"development": 4, "regression": 4, "holdout": 4}
    assert report["treatment_counts"] == {"base": 6, "adversarial": 6}
    assert report["expected_action_counts"] == {"propose_full_refund": 3, "review": 9}
    assert report["evaluator_sha256"] == digest(
        (output / "evaluator.json").read_text(encoding="utf-8")
    )
    for entry in cases.entries:
        assert entry.group_id == group_id(entry.input.order.order_id)
        assert entry.source_kind == "hybrid" and entry.review_status == "provisional"
        assert entry.input.order.currency_unit is None
        actual = propose(entry.input.order, entry.input.request, entry.input.confirmation)
        assert (actual.action, actual.amount_minor, actual.reason) == (
            entry.expected.action,
            entry.expected.amount_minor,
            entry.expected.reason,
        )
        assert actual.committed is False
    public = json.loads((output / "inputs.json").read_text(encoding="utf-8"))
    for item in public:
        assert set(item) == {"schema_version", "case_id", "order", "request", "confirmation"}
    before = (output / "evaluator.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(database, pin, output, as_of=datetime(2026, 10, 19))
    assert (output / "evaluator.json").read_bytes() == before


def test_source_pin_clock_and_output_boundary_fail_before_publication(tmp_path):
    database, pin = source(tmp_path)
    with pytest.raises(ValueError, match="pinned"):
        prepare(database, "a" * 64, tmp_path / "bad", as_of=datetime(2026, 10, 19))
    with pytest.raises(ValueError, match="visible"):
        prepare(database, pin, tmp_path / "bad", as_of=datetime(2026, 10, 17))
    blocked = tmp_path / "checkout"
    blocked.mkdir()
    (blocked / ".git").mkdir()
    with pytest.raises(ValueError, match="outside"):
        prepare(database, pin, blocked / "bad", as_of=datetime(2026, 10, 19))
    assert not (tmp_path / "bad").exists()


def test_duplicate_or_cross_split_order_edits_cannot_change_population(tmp_path):
    database, pin = source(tmp_path)
    output = tmp_path / "pilot"
    prepare(database, pin, output, as_of=datetime(2026, 10, 19))
    payload = json.loads((output / "evaluator.json").read_text(encoding="utf-8"))
    payload["entries"].append(payload["entries"][0])
    with pytest.raises(ValueError, match="duplicate"):
        PolicyCases.model_validate_json(json.dumps(payload))
    payload["entries"].pop()
    payload["entries"][1]["split"] = (
        "holdout" if payload["entries"][0]["split"] != "holdout" else "development"
    )
    with pytest.raises(ValueError, match="crosses"):
        PolicyCases.model_validate_json(json.dumps(payload))


def test_new_seed_and_group_exclusion_preserve_old_pilot_and_source_labels(tmp_path):
    database, pin = source(tmp_path, extra_population=True)
    first, second = tmp_path / "first", tmp_path / "second"
    prepare(database, pin, first, as_of=datetime(2026, 10, 19))
    original = (first / "evaluator.json").read_bytes()
    old = PolicyCases.model_validate_json(original)
    excluded = frozenset(e.group_id for e in old.entries)
    result = prepare(
        database,
        pin,
        second,
        as_of=datetime(2026, 10, 19),
        selection_seed="invented-new-cohort",
        excluded_groups=excluded,
    )
    new = PolicyCases.model_validate_json((second / "evaluator.json").read_bytes())
    assert len(new.entries) == 12 and result["excluded_group_count"] == 6
    assert not excluded & {e.group_id for e in new.entries}
    assert (first / "evaluator.json").read_bytes() == original
    assert result["expected_action_counts"] == {"propose_full_refund": 3, "review": 9}
