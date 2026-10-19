"""Pinned private Olist import, exact source grains and independent order aggregates."""

import csv
import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

TABLES = {
    "customers": ("olist_customers_dataset.csv", ("customer_id",)),
    "orders": ("olist_orders_dataset.csv", ("order_id",)),
    "items": ("olist_order_items_dataset.csv", ("order_id", "order_item_id")),
    "payments": ("olist_order_payments_dataset.csv", ("order_id", "payment_sequential")),
    "reviews": ("olist_order_reviews_dataset.csv", ("order_id", "review_id")),
    "products": ("olist_products_dataset.csv", ("product_id",)),
    "sellers": ("olist_sellers_dataset.csv", ("seller_id",)),
    "translations": ("product_category_name_translation.csv", ("product_category_name",)),
}
REQUIRED_FILES = {v[0] for v in TABLES.values()} | {"olist_geolocation_dataset.csv"}
MONEY = {"items": ("price", "freight_value"), "payments": ("payment_value",)}
TIME_COLUMNS = {
    "orders": (
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
    "items": ("shipping_limit_date",),
    "reviews": ("review_creation_date", "review_answer_timestamp"),
}


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_path(path: Path, repository: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_relative_to(repository.resolve()):
        raise ValueError("source and derived row storage must be outside the repository")
    return path


def source_time(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if parsed.strftime("%Y-%m-%d %H:%M:%S") != value:
        raise ValueError("noncanonical source timestamp")
    return parsed


def minor_units(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    if len(value) > 24 or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value) is None:
        raise ValueError("source amount must be a nonnegative two-decimal text amount")
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid source amount") from error
    if not amount.is_finite() or amount > Decimal("92233720368547758.07"):
        raise ValueError("source amount must be finite nonnegative with at most two decimals")
    result = int(amount * 100)
    if result > 2**63 - 1:
        raise ValueError("amount exceeds storage range")
    return result


def quoted(name: str) -> str:
    if not name or not name.replace("_", "").isalnum() or not name.isascii():
        raise ValueError("unsupported source identifier")
    return '"' + name + '"'


def verify_source(source: Path, manifest_path: Path, expected_sha256: str) -> dict[str, Any]:
    if digest_file(manifest_path) != expected_sha256:
        raise ValueError("source manifest differs from independently reviewed pin")
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("dataset_handle"), manifest.get("source_version")) != (
        "olistbr/brazilian-ecommerce/versions/7",
        7,
    ):
        raise ValueError("expected pinned Olist v7 source")
    files = manifest["files"]
    if len(files) != len(REQUIRED_FILES) or {f["name"] for f in files} != REQUIRED_FILES:
        raise ValueError("manifest source inventory differs")
    if {p.name for p in source.glob("*.csv")} != REQUIRED_FILES:
        raise ValueError("raw source inventory differs")
    for entry in files:
        path = source / entry["name"]
        if path.is_symlink() or digest_file(path) != entry["sha256"]:
            raise ValueError("raw source differs from reviewed manifest")
    return manifest


def _import_table(db: sqlite3.Connection, table: str, source: Path, entry: dict[str, Any]) -> int:
    columns = entry["columns"]
    filename, keys = TABLES[table]
    if len(set(columns)) != len(columns) or not set(keys).issubset(columns):
        raise ValueError("invalid source columns")
    extras = [name + "_minor" for name in MONEY.get(table, ())]
    declarations = [quoted(n) + " TEXT" for n in columns]
    declarations += [quoted(n) + " INTEGER" for n in extras]
    declarations.append("PRIMARY KEY (" + ",".join(quoted(k) for k in keys) + ")")
    db.execute("CREATE TABLE " + quoted(table) + " (" + ",".join(declarations) + ")")
    placeholders = ",".join("?" for _ in [*columns, *extras])
    insert = "INSERT INTO " + quoted(table) + " VALUES (" + placeholders + ")"
    count = 0
    missing = dict.fromkeys(columns, 0)
    with (source / filename).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != columns:
            raise ValueError("source header mismatch")
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("source row width mismatch")
            if any(not row[k] for k in keys):
                raise ValueError("missing source key")
            for name in TIME_COLUMNS.get(table, ()):
                if row[name]:
                    source_time(row[name])
            if table == "orders" and not row["order_purchase_timestamp"]:
                raise ValueError("purchase time is required")
            if table == "reviews" and row["review_score"] not in ("1", "2", "3", "4", "5", ""):
                raise ValueError("invalid review score")
            for name in columns:
                missing[name] += int(row[name] == "")
            values = [row[n] if row[n] != "" else None for n in columns]
            values += [minor_units(row[n]) for n in MONEY.get(table, ())]
            db.execute(insert, values)
            count += 1
    if count != entry["row_count"] or missing != entry["empty_value_counts"]:
        raise ValueError("source row count or missingness differs")
    return count


def _references(db: sqlite3.Connection) -> None:
    for child, key, parent in (
        ("orders", "customer_id", "customers"),
        ("items", "order_id", "orders"),
        ("payments", "order_id", "orders"),
        ("reviews", "order_id", "orders"),
        ("items", "product_id", "products"),
        ("items", "seller_id", "sellers"),
    ):
        query = (
            f"SELECT COUNT(*) FROM {child} c LEFT JOIN {parent} p ON c.{key}=p.{key} "
            f"WHERE c.{key} IS NULL OR p.{key} IS NULL"
        )
        if db.execute(query).fetchone()[0]:
            raise ValueError("orphan or missing source reference")


def _aggregates(db: sqlite3.Connection) -> dict[str, Any]:
    # Each child is reduced to one row per order BEFORE joining any other child.
    for table, prefix in (("items", "item"), ("payments", "payment"), ("reviews", "review")):
        fields = [f"COUNT(*) AS {prefix}_count"]
        for name in MONEY.get(table, ()):
            fields += [
                f"SUM({name}_minor) AS {name}_known_minor",
                f"SUM({name}_minor IS NULL) AS {name}_missing",
            ]
        db.execute(
            f"CREATE TABLE {table}_by_order AS SELECT order_id,"
            + ",".join(fields)
            + f" FROM {table} GROUP BY order_id"
        )
        db.execute(f"CREATE UNIQUE INDEX {table}_grain ON {table}_by_order(order_id)")
    db.execute("""CREATE TABLE orders_360 AS
        SELECT o.order_id, i.item_count, i.price_known_minor, i.price_missing,
          i.freight_value_known_minor, i.freight_value_missing,
          p.payment_count, p.payment_value_known_minor, p.payment_value_missing, r.review_count
        FROM orders o LEFT JOIN items_by_order i ON o.order_id=i.order_id
        LEFT JOIN payments_by_order p ON o.order_id=p.order_id
        LEFT JOIN reviews_by_order r ON o.order_id=r.order_id""")
    db.execute("CREATE UNIQUE INDEX orders_360_grain ON orders_360(order_id)")
    rows = db.execute("SELECT COUNT(*) FROM orders_360").fetchone()[0]
    if rows != db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]:
        raise ValueError("order grain changed")
    result: dict[str, Any] = {"orders": rows, "child_counts": {}, "amounts": {}}
    for table, prefix in (("items", "item"), ("payments", "payment"), ("reviews", "review")):
        direct = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        joined = db.execute(f"SELECT COALESCE(SUM({prefix}_count),0) FROM orders_360").fetchone()[0]
        if direct != joined:
            raise ValueError("child join count inflation")
        result["child_counts"][table] = direct
        for name in MONEY.get(table, ()):
            direct_amount = db.execute(f"SELECT SUM({name}_minor) FROM {table}").fetchone()[0]
            aggregate = db.execute(f"SELECT SUM({name}_known_minor) FROM orders_360").fetchone()[0]
            if direct_amount != aggregate:
                raise ValueError("joined source totals changed")
            result["amounts"][name] = {
                "known_minor": direct_amount,
                "missing": db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {name}_minor IS NULL"
                ).fetchone()[0],
            }
    return result


def import_snapshot(
    source: Path,
    manifest_path: Path,
    expected_sha256: str,
    output: Path,
    *,
    observed_at: datetime,
    repository: Path,
) -> dict[str, Any]:
    source = private_path(source, repository)
    output = private_path(output, repository)
    if observed_at.tzinfo is not None:
        raise ValueError("observed_at must explicitly use the source's unspecified local clock")
    manifest = verify_source(source, manifest_path, expected_sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Claim a new file before SQLite opens it. Partial failure is retained, never overwritten.
    with output.open("xb"):
        pass
    if os.name != "nt":
        os.chmod(output, 0o600)
    with closing(sqlite3.connect(output)) as db, db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        entries = {entry["name"]: entry for entry in manifest["files"]}
        counts = {
            table: _import_table(db, table, source, entries[filename])
            for table, (filename, _) in TABLES.items()
        }
        observed_text = observed_at.strftime("%Y-%m-%d %H:%M:%S")
        for table, names in (
            ("orders", TIME_COLUMNS["orders"][:-1]),
            ("reviews", TIME_COLUMNS["reviews"]),
        ):
            for name in names:
                latest = db.execute(f"SELECT MAX({name}) FROM {table}").fetchone()[0]
                if latest is not None and latest > observed_text:
                    raise ValueError("snapshot observation precedes a recorded actual event")
        _references(db)
        totals = _aggregates(db)
        for table in ("items", "payments", "reviews"):
            db.execute(f"CREATE INDEX {table}_order_lookup ON {table}(order_id)")
        # Recheck bytes so a concurrent source edit cannot be sealed as the reviewed snapshot.
        verify_source(source, manifest_path, expected_sha256)
        meta = {
            "source_manifest_sha256": expected_sha256,
            "source_version": 7,
            "observed_at": observed_at.isoformat(),
            "currency": manifest["currency"],
            "timestamp_timezone": manifest["timestamp_timezone"],
            "language": manifest["language"],
            "counts": counts,
            "totals": totals,
            "visibility_policy": "conservative-effective-time-v1",
        }
        db.executemany(
            "INSERT INTO metadata VALUES (?,?)",
            [(key, json.dumps(value, ensure_ascii=False)) for key, value in meta.items()],
        )
    return {**meta, "database_sha256": digest_file(output), "quality_evaluation": False}
