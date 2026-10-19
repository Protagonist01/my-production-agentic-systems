"""Invented grain, historical visibility, scope and immutable import witnesses."""

import csv
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from olist_fixtures import dataset, manifest, write_rows
from olist_support import source_cli
from olist_support.source import digest_file, import_snapshot, minor_units
from olist_support.views import OrderScope, OrderStore

OBSERVED = datetime(2020, 1, 10)
SCOPE = OrderScope("tenant-1", frozenset(("order-1", "order-empty")))
ROOT = Path(__file__).resolve().parents[1]


def build(tmp_path, mutate=None, observed=OBSERVED):
    source = dataset(tmp_path)
    if mutate:
        mutate(source)
    pin_path, pin = manifest(source, tmp_path)
    database = tmp_path / "orders.sqlite"
    result = import_snapshot(source, pin_path, pin, database, observed_at=observed, repository=ROOT)
    return database, result


def view(store, at, order_id="order-1"):
    return store.view(SCOPE, tenant_id="tenant-1", order_id=order_id, as_of=at)


def test_separate_child_grains_prevent_eightfold_join_inflation(tmp_path):
    database, result = build(tmp_path)
    assert result["totals"]["orders"] == 2
    assert result["totals"]["child_counts"] == {"items": 2, "payments": 2, "reviews": 2}
    assert result["totals"]["amounts"]["price"]["known_minor"] == 3003
    assert result["totals"]["amounts"]["payment_value"]["known_minor"] == 3203
    with sqlite3.connect(database) as db:
        # Witness the wrong implementation: 2x2x2 multiplies each item's price four times.
        count, inflated = db.execute(
            "SELECT COUNT(*),SUM(i.price_minor) FROM items i "
            "JOIN payments p USING(order_id) JOIN reviews r USING(order_id)"
        ).fetchone()
        assert (count, inflated) == (8, 12012)
    store = OrderStore(database, expected_sha256=result["database_sha256"])
    try:
        actual = view(store, OBSERVED)
        assert actual.item_count == actual.payment_count == 2
        assert actual.price.total_minor == 3003 and actual.payment.total_minor == 3203
        assert len(actual.reviews) == 2
        assert actual.items[0].category_portuguese == "cama_mesa_banho"
        assert actual.items[0].category_english_source_translation == "bed_bath_table"
        assert actual.reviews[0].title_portuguese == "Ótimo"
        assert actual.currency_unit is None
        assert "PRIVATE-CUSTOMER" not in actual.canonical_json()
        empty = view(store, OBSERVED, "order-empty")
        assert empty.items == () and empty.item_count == 0
        assert empty.price.total_minor is None  # no rows is not observed zero money
    finally:
        store.close()


@pytest.mark.parametrize(
    "at,event_kinds",
    [
        (datetime(2020, 1, 1, 9), ("purchased",)),
        (datetime(2020, 1, 2), ("purchased", "approved")),
        (datetime(2020, 1, 4), ("purchased", "approved", "carrier_handoff")),
        (datetime(2020, 1, 9), ("purchased", "approved", "carrier_handoff", "customer_delivery")),
    ],
)
def test_future_events_and_unknown_availability_never_leak(tmp_path, at, event_kinds):
    database, result = build(tmp_path)
    store = OrderStore(database, expected_sha256=result["database_sha256"])
    try:
        actual = view(store, at)
        assert tuple(e.kind for e in actual.events) == event_kinds
        assert all(datetime.fromisoformat(e.source_local_time) <= at for e in actual.events)
        assert actual.items is actual.payments is actual.price is None
        assert actual.item_count is actual.payment_count is None
        assert actual.final_source_status is actual.estimated_delivery_source_local is None
        assert actual.customer_city is None and not actual.snapshot_details_visible
        assert actual.reviews == () and "FUTURE-REVIEW" not in actual.canonical_json()
    finally:
        store.close()


def test_scope_unpurchased_orders_and_unknown_timezone_fail_closed(tmp_path):
    database, result = build(tmp_path)
    store = OrderStore(database, expected_sha256=result["database_sha256"])
    try:
        with pytest.raises(PermissionError):
            store.view(SCOPE, tenant_id="another-tenant", order_id="order-1", as_of=OBSERVED)
        with pytest.raises(PermissionError):
            store.view(SCOPE, tenant_id="tenant-1", order_id="ungranted", as_of=OBSERVED)
        with pytest.raises(LookupError):
            view(store, datetime(2019, 1, 1))
        with pytest.raises(ValueError):
            view(store, datetime(2020, 1, 10, tzinfo=UTC))
        with pytest.raises(sqlite3.OperationalError):
            store.db.execute("DELETE FROM orders")
    finally:
        store.close()


@pytest.mark.parametrize(
    "table,key",
    [
        ("olist_orders_dataset.csv", "order_id"),
        ("olist_order_items_dataset.csv", "order_item_id"),
        ("olist_order_payments_dataset.csv", "payment_sequential"),
        ("olist_order_reviews_dataset.csv", "review_id"),
        ("product_category_name_translation.csv", "product_category_name"),
    ],
)
def test_duplicate_grain_is_rejected_instead_of_silently_deduplicated(tmp_path, table, key):
    def duplicate(source):
        path = source / table
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames
            rows = list(reader)
        write_rows(path, columns, [*rows, rows[0]])

    with pytest.raises(sqlite3.IntegrityError):
        build(tmp_path, duplicate)


def test_review_id_can_belong_to_distinct_orders_without_data_loss(tmp_path):
    def edit(source):
        path = source / "olist_order_reviews_dataset.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames
            rows = list(reader)
        rows[1]["review_id"] = rows[0]["review_id"]
        rows[1]["order_id"] = "order-empty"
        write_rows(path, columns, rows)

    _, result = build(tmp_path, edit)
    assert result["totals"]["child_counts"]["reviews"] == 2


def test_orphan_child_blocks_import(tmp_path):
    def edit(source):
        p = source / "olist_order_items_dataset.csv"
        p.write_text(p.read_text().replace("order-1", "orphan"), encoding="utf-8")

    with pytest.raises(ValueError, match="reference"):
        build(tmp_path, edit)


def test_missing_amount_stays_unknown_and_exact_known_subtotal_is_preserved(tmp_path):
    def edit(source):
        p = source / "olist_order_items_dataset.csv"
        p.write_text(p.read_text().replace("10.01", ""), encoding="utf-8")

    database, result = build(tmp_path, edit)
    store = OrderStore(database, expected_sha256=result["database_sha256"])
    try:
        actual = view(store, OBSERVED)
        assert actual.price.total_minor is None
        assert actual.price.known_minor == 2002 and actual.price.missing_rows == 1
    finally:
        store.close()


@pytest.mark.parametrize(
    "value", ["-1.00", "NaN", "Infinity", "1.001", "1E999999999", "92233720368547758.08"]
)
def test_invalid_amounts_are_not_rounded_or_coerced(value):
    with pytest.raises(ValueError):
        minor_units(value)
    assert minor_units("0.00") == 0 and minor_units("0.01") == 1


def test_wrong_pins_modified_source_existing_output_and_backdated_observation_fail(tmp_path):
    source = dataset(tmp_path)
    path, pin = manifest(source, tmp_path)
    output = tmp_path / "orders.sqlite"
    with pytest.raises(ValueError, match="manifest"):
        import_snapshot(source, path, "0" * 64, output, observed_at=OBSERVED, repository=ROOT)
    with pytest.raises(ValueError, match="precedes"):
        import_snapshot(
            source, path, pin, output, observed_at=datetime(2020, 1, 2), repository=ROOT
        )
    assert output.exists()  # failed artifacts are retained and never resumed
    with pytest.raises(FileExistsError):
        import_snapshot(source, path, pin, output, observed_at=OBSERVED, repository=ROOT)
    (source / "olist_orders_dataset.csv").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="source differs"):
        import_snapshot(
            source, path, pin, tmp_path / "new.sqlite", observed_at=OBSERVED, repository=ROOT
        )


def test_database_pin_and_repository_boundary_are_enforced(tmp_path):
    database, result = build(tmp_path)
    with pytest.raises(ValueError):
        OrderStore(database, expected_sha256="0" * 64)
    source = tmp_path / "source"
    path = tmp_path / "manifest.json"
    with pytest.raises(ValueError, match="outside"):
        import_snapshot(
            source,
            path,
            digest_file(path),
            ROOT / "artifacts/raw.sqlite",
            observed_at=OBSERVED,
            repository=ROOT,
        )


def test_cli_writes_only_aggregate_report_and_fails_nonzero(tmp_path, capsys):
    source = dataset(tmp_path)
    path, pin = manifest(source, tmp_path)
    report = tmp_path / "aggregate.json"
    args = [
        "--source",
        str(source),
        "--source-manifest",
        str(path),
        "--source-manifest-sha256",
        pin,
        "--output",
        str(tmp_path / "db.sqlite"),
        "--observed-at",
        "2020-01-10 00:00:00",
        "--repository-root",
        str(ROOT),
        "--aggregate-report",
        str(report),
    ]
    assert source_cli.main(args) == 0
    text = report.read_text() + capsys.readouterr().out
    assert "order-1" not in text and "FUTURE-REVIEW" not in text
    assert source_cli.main(args) == 1


def test_pinned_reader_retains_snapshot_and_blocks_concurrent_commit(tmp_path):
    database, result = build(tmp_path)
    store = OrderStore(database, expected_sha256=result["database_sha256"])
    writer = sqlite3.connect(database, timeout=0.05)
    try:
        before = view(store, OBSERVED)
        writer.execute("UPDATE orders SET order_status='changed-after-pin'")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            writer.commit()
        assert view(store, OBSERVED) == before
        assert digest_file(database) == result["database_sha256"]
    finally:
        writer.rollback()
        writer.close()
        store.close()


def test_active_wal_changes_outside_main_hash_are_rejected(tmp_path):
    database, _ = build(tmp_path)
    writer = sqlite3.connect(database)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        unchanged_main_pin = digest_file(database)
        writer.execute("UPDATE orders SET order_status='wal-only-change'")
        writer.commit()
        assert digest_file(database) == unchanged_main_pin
        assert Path(str(database) + "-wal").exists()
        with pytest.raises(ValueError, match="sidecar"):
            OrderStore(database, expected_sha256=unchanged_main_pin)
    finally:
        writer.close()


def test_import_closes_connection_before_returning_sealed_digest(tmp_path, monkeypatch):
    from olist_support import source

    opened = []
    original_connect = sqlite3.connect

    def capture_connection(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(source.sqlite3, "connect", capture_connection)
    database, result = build(tmp_path)
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
    assert digest_file(database) == result["database_sha256"]
