"""Pinned independent DataCo/NWS preparation; no weather/shipment causal join."""

import csv
import hashlib
import io
import json
import sqlite3
import urllib.request
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from itertools import zip_longest
from pathlib import Path
from typing import Any, Literal

from supply_chain.source_contracts import AlertFact, ShipmentFact, ShipmentTarget, SourcePin, aware

HEADERS = (
    "Type",
    "Days for shipping (real)",
    "Days for shipment (scheduled)",
    "Benefit per order",
    "Sales per customer",
    "Delivery Status",
    "Late_delivery_risk",
    "Category Id",
    "Category Name",
    "Customer City",
    "Customer Country",
    "Customer Email",
    "Customer Fname",
    "Customer Id",
    "Customer Lname",
    "Customer Password",
    "Customer Segment",
    "Customer State",
    "Customer Street",
    "Customer Zipcode",
    "Department Id",
    "Department Name",
    "Latitude",
    "Longitude",
    "Market",
    "Order City",
    "Order Country",
    "Order Customer Id",
    "order date (DateOrders)",
    "Order Id",
    "Order Item Cardprod Id",
    "Order Item Discount",
    "Order Item Discount Rate",
    "Order Item Id",
    "Order Item Product Price",
    "Order Item Profit Ratio",
    "Order Item Quantity",
    "Sales",
    "Order Item Total",
    "Order Profit Per Order",
    "Order Region",
    "Order State",
    "Order Status",
    "Order Zipcode",
    "Product Card Id",
    "Product Category Id",
    "Product Description",
    "Product Image",
    "Product Name",
    "Product Price",
    "Product Status",
    "shipping date (DateOrders)",
    "Shipping Mode",
)
TABLE_SQL = (
    "CREATE TABLE {} (ordinal INTEGER PRIMARY KEY, source_key TEXT UNIQUE NOT NULL, "
    "document TEXT NOT NULL)"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def external(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any((p / ".git").exists() for p in (path, *path.parents)):
        raise ValueError("source, private stores and outputs must remain outside Git")
    return path


def pinned(path: Path, sha: str, size: int) -> bytes:
    with external(path).open("rb") as handle:
        raw = handle.read(size + 1)
    if len(raw) != size or digest(raw) != sha:
        raise ValueError("source size or digest differs from reviewed pin")
    return raw


def load_pin(path: Path, sha: str) -> tuple[SourcePin, bytes]:
    with external(path).open("rb") as handle:
        raw = handle.read(10001)
    if len(raw) > 10000 or digest(raw) != sha:
        raise ValueError("source pin differs from independently retained digest")
    return SourcePin.model_validate_json(raw), raw


def _flag(value: str) -> Literal[0, 1]:
    if value == "0":
        return 0
    if value == "1":
        return 1
    raise ValueError("late-delivery reference is not binary")


def shipping(
    raw: bytes | Iterable[str], observed_at: datetime
) -> Iterator[tuple[ShipmentFact, ShipmentTarget]]:
    reader = csv.DictReader(
        io.StringIO(raw.decode("latin-1"), newline="") if isinstance(raw, bytes) else raw
    )
    if tuple(reader.fieldnames or ()) != HEADERS:
        raise ValueError("unexpected DataCo columns or order")
    seen: set[str] = set()
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed DataCo row")
        key = digest(("dataco-v5:" + row["Order Item Id"]).encode())
        if key in seen:
            raise ValueError("duplicate source item")
        seen.add(key)
        fact = ShipmentFact(
            source_key=key,
            observed_at=aware(observed_at),
            recorded_order_time=datetime.strptime(row["order date (DateOrders)"], "%m/%d/%Y %H:%M"),
            destination_country=row["Order Country"],
            destination_region=row["Order Region"],
            shipping_mode=row["Shipping Mode"],
            scheduled_days=int(row["Days for shipment (scheduled)"]),
            quantity=int(row["Order Item Quantity"]),
            category=row["Category Name"],
        )
        target = ShipmentTarget(
            source_key=key,
            source_order_id=row["Order Id"],
            source_item_id=row["Order Item Id"],
            recorded_shipping_time=datetime.strptime(
                row["shipping date (DateOrders)"], "%m/%d/%Y %H:%M"
            ),
            actual_shipping_days=int(row["Days for shipping (real)"]),
            delivery_status=row["Delivery Status"],
            late_delivery_flag=_flag(row["Late_delivery_risk"]),
            order_status=row["Order Status"],
        )
        yield fact, target
    if not seen:
        raise ValueError("empty shipment source")


def shipping_file(path: Path, pin: SourcePin) -> Iterator[tuple[ShipmentFact, ShipmentTarget]]:
    """Hash the exact raw lines consumed by csv, without retaining the 96 MB input."""
    with external(path).open("rb") as handle:
        hasher = hashlib.sha256()
        size = 0

        def lines() -> Iterator[str]:
            nonlocal size
            for raw in handle:
                size += len(raw)
                if size > pin.dataco_bytes:
                    raise ValueError("shipment source exceeds pinned size")
                hasher.update(raw)
                yield raw.decode("latin-1")

        yield from shipping(lines(), pin.dataco_observed_at)
        if size != pin.dataco_bytes or hasher.hexdigest() != pin.dataco_sha256:
            raise ValueError("shipment source differs from reviewed pin")


def alerts(raw: bytes, captured_at: datetime) -> tuple[list[AlertFact], datetime]:
    data = json.loads(raw)
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("not a GeoJSON alert collection")
    if (data.get("pagination") or {}).get("next"):
        raise ValueError("incomplete paginated alert capture")
    updated = aware(datetime.fromisoformat(data["updated"]))
    if updated > aware(captured_at):
        raise ValueError("collection update is after capture")
    output = []
    seen: set[str] = set()
    for feature in data["features"]:
        p = feature["properties"]
        if not isinstance(feature["id"], str) or not feature["id"]:
            raise ValueError("alert needs a source identity")
        key = digest(feature["id"].encode())
        if key in seen:
            raise ValueError("duplicate alert")
        seen.add(key)
        value = AlertFact.model_validate_json(
            json.dumps(
                {
                    "source_key": key,
                    "captured_at": captured_at.isoformat(),
                    "sent": p["sent"],
                    "effective": p["effective"],
                    "onset": p.get("onset"),
                    "expires": p["expires"],
                    "ends": p.get("ends"),
                    "status": p["status"],
                    "message_type": p["messageType"],
                    "event": p["event"],
                    "area": p["areaDesc"],
                    "severity": p["severity"],
                    "urgency": p["urgency"],
                    "certainty": p["certainty"],
                }
            )
        )
        if (
            value.sent > captured_at
            or value.expires <= value.sent
            or value.expires <= value.effective
        ):
            raise ValueError("invalid alert validity interval")
        output.append(value)
    return output, updated


def visible_alerts(
    values: list[AlertFact],
    clock: datetime,
    captured_at: datetime,
    updated_at: datetime,
    max_snapshot_age: timedelta,
) -> tuple[AlertFact, ...]:
    clock, captured_at, updated_at = aware(clock), aware(captured_at), aware(updated_at)
    if max_snapshot_age <= timedelta(0) or max_snapshot_age > timedelta(days=7):
        raise ValueError("explicit freshness allowance must be positive and at most seven days")
    if clock < captured_at or updated_at > captured_at or clock - updated_at > max_snapshot_age:
        return ()
    output = []
    for item in values:
        item = AlertFact.model_validate_json(item.canonical_json())
        if item.captured_at != captured_at:
            raise ValueError("alert belongs to another snapshot")
        if (
            item.status == "Actual"
            and item.message_type in {"Alert", "Update"}
            and item.sent <= clock
            and item.effective <= clock < item.expires
            and (item.ends is None or clock < item.ends)
        ):
            output.append(item)
    return tuple(output)


def _database(path: Path, tables: tuple[str, ...]) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    for table in tables:
        con.execute(TABLE_SQL.format(table))
    return con


def _check_schema(con: sqlite3.Connection, tables: tuple[str, ...]) -> None:
    expected: set[tuple[str, str, str | None]] = {
        (name, "table", TABLE_SQL.format(name)) for name in tables
    }
    expected |= {(f"sqlite_autoindex_{name}_1", "index", None) for name in tables}
    actual = set(con.execute("SELECT name,type,sql FROM sqlite_master"))
    if actual != expected or con.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise ValueError("private store schema or integrity differs")


def _rows(con: sqlite3.Connection, table: str) -> Iterator[tuple[int, str, str]]:
    for row in con.execute(f"SELECT ordinal,source_key,document FROM {table} ORDER BY ordinal"):
        yield int(row[0]), str(row[1]), str(row[2])


def capture_weather(output: Path, user_agent: str) -> dict[str, Any]:
    """Explicit one-request acquisition, separate from network-free source readers."""
    if not user_agent.strip() or len(user_agent) > 512 or any(c in user_agent for c in "\r\n"):
        raise ValueError("an identifying bounded User-Agent is required")
    output = external(output)
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(UTC)
    request = urllib.request.Request(
        "https://api.weather.gov/alerts/active",
        headers={"User-Agent": user_agent, "Accept": "application/geo+json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 200 or not response.url.startswith("https://api.weather.gov/"):
            raise ValueError("unexpected weather source response")
        raw = response.read(30_000_001)
        if len(raw) > 30_000_000:
            raise ValueError("weather response exceeds source limit")
        headers = {name.lower(): value for name, value in response.headers.items()}
        final_url = response.url
    captured = datetime.now(UTC)
    values, updated = alerts(raw, captured)
    receipt = {
        "request_url": request.full_url,
        "response_url": final_url,
        "started_at": started.isoformat(),
        "captured_at": captured.isoformat(),
        "sha256": digest(raw),
        "bytes": len(raw),
        "alerts": len(values),
        "updated_at": updated.isoformat(),
        "headers": {
            key: headers.get(key)
            for key in ("date", "cache-control", "expires", "last-modified", "etag")
        },
    }
    (output / "alerts.json").write_bytes(raw)
    (output / "receipt.json").write_bytes(canonical(receipt))
    return receipt


def prepare(
    dataco: Path,
    description: Path,
    nws: Path,
    pin_path: Path,
    pin_sha: str,
    output: Path,
) -> dict[str, Any]:
    pin, pin_raw = load_pin(pin_path, pin_sha)
    desc = pinned(description, pin.description_sha256, pin.description_bytes)
    if not desc.decode("utf-8-sig").startswith("FIELDS,DESCRIPTION"):
        raise ValueError("unexpected DataCo description")
    weather = pinned(nws, pin.nws_sha256, pin.nws_bytes)
    weather_rows, updated = alerts(weather, pin.weather_captured_at)
    output = external(output)
    output.mkdir(parents=True, exist_ok=False)
    counts: Counter[str] = Counter()
    dates: list[datetime] = []
    order_ids: set[str] = set()
    with (
        _database(output / "inputs.sqlite", ("shipments", "alerts")) as public,
        _database(output / "evaluator.sqlite", ("targets",)) as targets,
    ):
        for index, (fact, target) in enumerate(shipping_file(dataco, pin)):
            public.execute(
                "INSERT INTO shipments VALUES(?,?,?)",
                (index, fact.source_key, fact.canonical_json()),
            )
            targets.execute(
                "INSERT INTO targets VALUES(?,?,?)",
                (index, target.source_key, target.canonical_json()),
            )
            counts["shipment_lines"] += 1
            counts["late_flag_" + str(target.late_delivery_flag)] += 1
            order_ids.add(target.source_order_id)
            dates.append(fact.recorded_order_time)
        for index, alert in enumerate(weather_rows):
            public.execute(
                "INSERT INTO alerts VALUES(?,?,?)",
                (index, alert.source_key, alert.canonical_json()),
            )
    (output / "source-pin.json").write_bytes(pin_raw)
    result = {
        "source_version": pin.source_version,
        "source_pin_sha256": pin_sha,
        "counts": dict(counts),
        "distinct_orders": len(order_ids),
        "source_columns": len(HEADERS),
        "recorded_order_min": min(dates).isoformat(),
        "recorded_order_max": max(dates).isoformat(),
        "original_timezone": "unverified",
        "alerts": len(weather_rows),
        "weather_updated_at": updated.isoformat(),
        "dataco_observed_at": pin.dataco_observed_at.isoformat(),
        "weather_captured_at": pin.weather_captured_at.isoformat(),
        "store_sha256": {
            name: file_digest(output / name) for name in ("inputs.sqlite", "evaluator.sqlite")
        },
        "causal_join": False,
        "hidden_outcomes_in_public_view": False,
    }
    (output / "manifest.json").write_bytes(canonical(result))
    return result


def verify(
    output: Path,
    manifest_sha: str,
    dataco: Path,
    description: Path,
    nws: Path,
) -> dict[str, Any]:
    output = external(output)
    raw_manifest = (output / "manifest.json").read_bytes()
    if digest(raw_manifest) != manifest_sha:
        raise ValueError("manifest differs from independently retained pin")
    manifest = json.loads(raw_manifest)
    pin, _ = load_pin(output / "source-pin.json", manifest["source_pin_sha256"])
    pinned(description, pin.description_sha256, pin.description_bytes)
    weather, updated = alerts(pinned(nws, pin.nws_sha256, pin.nws_bytes), pin.weather_captured_at)
    for name, expected in manifest["store_sha256"].items():
        if (
            name not in {"inputs.sqlite", "evaluator.sqlite"}
            or file_digest(output / name) != expected
        ):
            raise ValueError("derived store differs from pin")
    if set(manifest["store_sha256"]) != {"inputs.sqlite", "evaluator.sqlite"}:
        raise ValueError("incomplete store inventory")
    with (
        sqlite3.connect(
            f"file:{(output / 'inputs.sqlite').as_posix()}?mode=ro", uri=True
        ) as public,
        sqlite3.connect(
            f"file:{(output / 'evaluator.sqlite').as_posix()}?mode=ro", uri=True
        ) as targets,
    ):
        _check_schema(public, ("shipments", "alerts"))
        _check_schema(targets, ("targets",))
        n = 0
        counts: Counter[str] = Counter()
        dates: list[datetime] = []
        orders: set[str] = set()
        expected = shipping_file(dataco, pin)
        for source, fact_row, target_row in zip_longest(
            expected, _rows(public, "shipments"), _rows(targets, "targets")
        ):
            if source is None or fact_row is None or target_row is None:
                raise ValueError("derived shipment population differs")
            fact, target = source
            if fact_row != (n, fact.source_key, fact.canonical_json()) or target_row != (
                n,
                target.source_key,
                target.canonical_json(),
            ):
                raise ValueError("derived row differs from pinned original source")
            n += 1
            counts["shipment_lines"] += 1
            counts["late_flag_" + str(target.late_delivery_flag)] += 1
            dates.append(fact.recorded_order_time)
            orders.add(target.source_order_id)
        expected_weather = [
            (i, item.source_key, item.canonical_json()) for i, item in enumerate(weather)
        ]
        if list(_rows(public, "alerts")) != expected_weather:
            raise ValueError("derived weather population differs")
    checks = {
        "counts": dict(counts),
        "distinct_orders": len(orders),
        "source_columns": len(HEADERS),
        "recorded_order_min": min(dates).isoformat(),
        "recorded_order_max": max(dates).isoformat(),
        "alerts": len(weather),
        "weather_updated_at": updated.isoformat(),
        "dataco_observed_at": pin.dataco_observed_at.isoformat(),
        "weather_captured_at": pin.weather_captured_at.isoformat(),
        "source_version": pin.source_version,
        "original_timezone": "unverified",
        "causal_join": False,
        "hidden_outcomes_in_public_view": False,
    }
    if any(manifest.get(key) != value for key, value in checks.items()):
        raise ValueError("manifest aggregate differs from original source")
    return {"verified": True, "shipment_lines": n, "alerts": len(weather), "causal_join": False}


def _public_store(output: Path, manifest_sha: str) -> tuple[sqlite3.Connection, dict[str, Any]]:
    output = external(output)
    raw_manifest = (output / "manifest.json").read_bytes()
    if digest(raw_manifest) != manifest_sha:
        raise ValueError("manifest differs from independently retained pin")
    manifest = json.loads(raw_manifest)
    hasher = hashlib.sha256()
    with (output / "inputs.sqlite").open("rb") as handle:
        while chunk := handle.read(65536):
            hasher.update(chunk)
    if hasher.hexdigest() != manifest["store_sha256"]["inputs.sqlite"]:
        raise ValueError("public store differs from manifest")
    con = sqlite3.connect(f"file:{(output / 'inputs.sqlite').as_posix()}?mode=ro", uri=True)
    try:
        _check_schema(con, ("shipments", "alerts"))
    except BaseException:
        con.close()
        raise
    return con, manifest


def read_shipments(output: Path, manifest_sha: str, clock: datetime) -> Iterator[ShipmentFact]:
    """Only pinned public facts; no authenticated remote endpoint or evaluator access."""
    clock = aware(clock)
    con, manifest = _public_store(output, manifest_sha)
    try:
        observed = aware(datetime.fromisoformat(manifest["dataco_observed_at"]))
        if observed > clock:
            return
        for _, key, document in _rows(con, "shipments"):
            value = ShipmentFact.model_validate_json(document)
            if key != value.source_key or value.observed_at != observed:
                raise ValueError("shipment identity or observation clock differs")
            yield value
    finally:
        con.close()


def read_alerts(
    output: Path,
    manifest_sha: str,
    clock: datetime,
    max_snapshot_age: timedelta,
) -> tuple[AlertFact, ...]:
    con, manifest = _public_store(output, manifest_sha)
    try:
        values = []
        for _, key, document in _rows(con, "alerts"):
            value = AlertFact.model_validate_json(document)
            if key != value.source_key:
                raise ValueError("weather identity differs")
            values.append(value)
        return visible_alerts(
            values,
            clock,
            datetime.fromisoformat(manifest["weather_captured_at"]),
            datetime.fromisoformat(manifest["weather_updated_at"]),
            max_snapshot_age,
        )
    finally:
        con.close()
