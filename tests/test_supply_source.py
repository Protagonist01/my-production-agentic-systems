"""Invented source fixtures prove isolation, pins and conservative source clocks."""

import csv
import io
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from supply_chain.source import (
    HEADERS,
    alerts,
    canonical,
    digest,
    prepare,
    read_alerts,
    read_shipments,
    shipping,
    verify,
    visible_alerts,
)
from supply_chain.source_cli import main
from supply_chain.source_contracts import SourcePin

NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)


def shipment_bytes(**changes):
    row = dict.fromkeys(HEADERS, "invented")
    row.update(
        {
            "Order Item Id": "invented-item",
            "Order Id": "invented-order",
            "order date (DateOrders)": "1/1/2017 10:00",
            "shipping date (DateOrders)": "1/3/2017 10:00",
            "Days for shipment (scheduled)": "2",
            "Days for shipping (real)": "2",
            "Order Item Quantity": "1",
            "Late_delivery_risk": "0",
            "Customer Email": "PRIVATE-EMAIL-CANARY",
        }
    )
    row.update(changes)
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, HEADERS)
    writer.writeheader()
    writer.writerow(row)
    return out.getvalue().encode("latin-1")


def weather_bytes(**changes):
    p = {
        "sent": (NOW - timedelta(minutes=2)).isoformat(),
        "effective": (NOW - timedelta(minutes=2)).isoformat(),
        "onset": None,
        "expires": (NOW + timedelta(hours=2)).isoformat(),
        "ends": None,
        "status": "Actual",
        "messageType": "Alert",
        "event": "Invented warning",
        "areaDesc": "Invented area",
        "severity": "Moderate",
        "urgency": "Expected",
        "certainty": "Likely",
    }
    p.update(changes)
    return canonical(
        {
            "type": "FeatureCollection",
            "updated": (NOW - timedelta(minutes=1)).isoformat(),
            "features": [{"id": "invented-alert", "properties": p}],
        }
    )


def bundle(tmp_path):
    paths = [tmp_path / n for n in ("shipping.csv", "description.csv", "weather.json", "pin.json")]
    raw, desc, weather = shipment_bytes(), b"FIELDS,DESCRIPTION\nType,Invented\n", weather_bytes()
    pin = SourcePin(
        dataco_sha256=digest(raw),
        dataco_bytes=len(raw),
        description_sha256=digest(desc),
        description_bytes=len(desc),
        nws_sha256=digest(weather),
        nws_bytes=len(weather),
        dataco_observed_at=NOW,
        weather_captured_at=NOW,
    )
    for path, data in zip(paths, (raw, desc, weather, pin.canonical_json().encode()), strict=True):
        path.write_bytes(data)
    output = tmp_path / "prepared"
    result = prepare(*paths[:3], paths[3], digest(paths[3].read_bytes()), output)
    return paths, output, result, digest((output / "manifest.json").read_bytes())


def repin(output, store):
    manifest = json.loads((output / "manifest.json").read_bytes())
    manifest["store_sha256"][store] = digest((output / store).read_bytes())
    (output / "manifest.json").write_bytes(canonical(manifest))
    return digest((output / "manifest.json").read_bytes())


def test_prepare_verify_public_projection_and_real_observation_clock(tmp_path):
    paths, output, report, pin = bundle(tmp_path)
    assert verify(output, pin, *paths[:3]) == {
        "verified": True,
        "shipment_lines": 1,
        "alerts": 1,
        "causal_join": False,
    }
    assert report["original_timezone"] == "unverified"
    assert list(read_shipments(output, pin, NOW - timedelta(seconds=1))) == []
    facts = list(read_shipments(output, pin, NOW))
    assert len(facts) == 1
    fields = facts[0].model_dump()
    assert fields["recorded_order_time"].tzinfo is None
    assert not any(
        key in fields
        for key in (
            "actual_shipping_days",
            "delivery_status",
            "late_delivery_flag",
            "order_status",
            "source_order_id",
            "source_item_id",
        )
    )
    assert b"PRIVATE-EMAIL-CANARY" not in (output / "inputs.sqlite").read_bytes()
    assert b"PRIVATE-EMAIL-CANARY" not in (output / "evaluator.sqlite").read_bytes()
    assert len(read_alerts(output, pin, NOW, timedelta(minutes=30))) == 1
    assert read_alerts(output, pin, NOW - timedelta(seconds=1), timedelta(minutes=30)) == ()


@pytest.mark.parametrize(
    "change",
    [
        {"status": "Test"},
        {"messageType": "Cancel"},
        {"effective": (NOW + timedelta(seconds=1)).isoformat()},
        {"expires": NOW.isoformat()},
        {"ends": NOW.isoformat()},
    ],
)
def test_alert_not_visible_for_invalid_status_future_issue_or_finished_validity(change):
    values, updated = alerts(weather_bytes(**change), NOW)
    assert visible_alerts(values, NOW, NOW, updated, timedelta(minutes=30)) == ()


def test_explicit_snapshot_freshness_and_naive_clocks():
    values, updated = alerts(weather_bytes(), NOW)
    assert (
        visible_alerts(values, NOW + timedelta(hours=1), NOW, updated, timedelta(minutes=30)) == ()
    )
    for maxage in (timedelta(0), timedelta(days=8)):
        with pytest.raises(ValueError):
            visible_alerts(values, NOW, NOW, updated, maxage)
    with pytest.raises(ValueError):
        visible_alerts(values, NOW.replace(tzinfo=None), NOW, updated, timedelta(minutes=30))
    # An issued alert may describe future onset without claiming an event already happened.
    values, updated = alerts(weather_bytes(onset=(NOW + timedelta(hours=1)).isoformat()), NOW)
    assert len(visible_alerts(values, NOW, NOW, updated, timedelta(minutes=30))) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"sent": "bad"},
        {"sent": (NOW + timedelta(seconds=1)).isoformat()},
        {"expires": "2026-10-21T13:00:00"},
        {"expires": (NOW - timedelta(hours=1)).isoformat()},
    ],
)
def test_malformed_or_inverted_alert_time_rejected(change):
    with pytest.raises(ValueError):
        alerts(weather_bytes(**change), NOW)


def test_pagination_duplicates_and_future_collection_rejected():
    x = json.loads(weather_bytes())
    x["pagination"] = {"next": "https://api.weather.gov/next"}
    with pytest.raises(ValueError):
        alerts(canonical(x), NOW)
    x.pop("pagination")
    x["features"] *= 2
    with pytest.raises(ValueError):
        alerts(canonical(x), NOW)
    x["features"] = x["features"][:1]
    x["updated"] = (NOW + timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError):
        alerts(canonical(x), NOW)


@pytest.mark.parametrize("store", ["inputs.sqlite", "evaluator.sqlite"])
def test_repinned_unexpected_sql_objects_rejected(tmp_path, store):
    paths, output, _, _ = bundle(tmp_path)
    with sqlite3.connect(output / store) as con:
        con.execute("CREATE VIEW extra AS SELECT 1")
    pin = repin(output, store)
    with pytest.raises(ValueError):
        verify(output, pin, *paths[:3])


def test_repinned_target_and_profile_cannot_redefine_source_truth(tmp_path):
    paths, output, _, pin = bundle(tmp_path)
    with sqlite3.connect(output / "evaluator.sqlite") as con:
        x = json.loads(con.execute("SELECT document FROM targets").fetchone()[0])
        x["actual_shipping_days"] = 99
        con.execute("UPDATE targets SET document=?", (json.dumps(x),))
    pin = repin(output, "evaluator.sqlite")
    with pytest.raises(ValueError):
        verify(output, pin, *paths[:3])
    manifest = json.loads((output / "manifest.json").read_bytes())
    manifest["counts"]["shipment_lines"] = 99
    (output / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ValueError):
        verify(output, digest((output / "manifest.json").read_bytes()), *paths[:3])


def test_source_and_public_reader_pins_fail_closed(tmp_path):
    paths, output, _, pin = bundle(tmp_path)
    with pytest.raises(ValueError):
        list(read_shipments(output, "0" * 64, NOW))
    with sqlite3.connect(output / "inputs.sqlite") as con:
        con.execute("UPDATE shipments SET document='{}'")
    with pytest.raises(ValueError):
        list(read_shipments(output, pin, NOW))
    paths[0].write_bytes(paths[0].read_bytes() + b"x")
    with pytest.raises(ValueError):
        verify(output, pin, *paths[:3])


def test_header_duplicates_and_bad_dates_rejected():
    raw = shipment_bytes()
    with pytest.raises(ValueError):
        list(shipping(raw.replace(b"Customer Email", b"Unknown Column"), NOW))
    with pytest.raises(ValueError):
        list(shipping(raw + raw.splitlines(keepends=True)[1], NOW))
    with pytest.raises(ValueError):
        list(shipping(shipment_bytes(**{"order date (DateOrders)": "bad"}), NOW))


def test_cli_does_not_print_private_invalid_values(tmp_path, capsys):
    paths, output, _, pin = bundle(tmp_path)
    with pytest.raises(SystemExit):
        main(
            [
                "prepare",
                "--dataco",
                str(paths[0]),
                "--description",
                str(paths[1]),
                "--nws",
                str(paths[2]),
                "--source-pin",
                str(paths[3]),
                "--source-pin-sha256",
                "0" * 64,
                "--output",
                str(output),
            ]
        )
    captured = capsys.readouterr()
    assert "PRIVATE-EMAIL-CANARY" not in captured.err and not captured.out
    main(
        [
            "verify",
            "--dataco",
            str(paths[0]),
            "--description",
            str(paths[1]),
            "--nws",
            str(paths[2]),
            "--output",
            str(output),
            "--manifest-sha256",
            pin,
        ]
    )
    assert json.loads(capsys.readouterr().out)["verified"] is True


def test_streaming_byte_pin_external_paths_and_exclusive_output(tmp_path):
    from supply_chain.source import external, load_pin, shipping_file

    paths, output, _, _ = bundle(tmp_path)
    pin, _ = load_pin(paths[3], digest(paths[3].read_bytes()))
    assert len(list(shipping_file(paths[0], pin))) == 1
    paths[0].write_bytes(paths[0].read_bytes().replace(b"invented-order", b"changed-order"))
    with pytest.raises(ValueError):
        list(shipping_file(paths[0], pin))
    repo = tmp_path / "checkout"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: invented")
    with pytest.raises(ValueError):
        external(repo / "source.csv")
    with pytest.raises(FileExistsError):
        prepare(*paths[:3], paths[3], digest(paths[3].read_bytes()), output)


def test_explicit_weather_capture_is_exclusive_identified_and_bounded(tmp_path, monkeypatch):
    from supply_chain.source import capture_weather

    calls = []

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr("supply_chain.source.datetime", FrozenDateTime)

    class Response:
        status = 200
        url = "https://api.weather.gov/alerts/active"
        headers = {"Cache-Control": "public, max-age=4"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, maximum):
            assert maximum == 30_000_001
            return weather_bytes()

    def opened(request, timeout):
        assert request.full_url == "https://api.weather.gov/alerts/active" and timeout == 60
        assert request.get_header("User-agent") == "invented-test-app"
        calls.append(request)
        return Response()

    monkeypatch.setattr("supply_chain.source.urllib.request.urlopen", opened)
    receipt = capture_weather(tmp_path / "capture", "invented-test-app")
    assert receipt["alerts"] == 1 and len(calls) == 1
    assert receipt["headers"]["cache-control"] == "public, max-age=4"
    assert (tmp_path / "capture" / "alerts.json").read_bytes() == weather_bytes()
    with pytest.raises(FileExistsError):
        capture_weather(tmp_path / "capture", "invented-test-app")
    with pytest.raises(ValueError):
        capture_weather(tmp_path / "blank", "  ")
    with pytest.raises(ValueError):
        capture_weather(tmp_path / "inject", "app\r\ninvalid")
    assert len(calls) == 1
