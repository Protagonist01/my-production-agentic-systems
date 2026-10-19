"""Invented complaints exercise mechanics; no real narratives or identifiers are fixtures."""

import csv
import io
import json
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

import pytest
from cfpb_triage.source import (
    case_key,
    group_key,
    inspect_prepared,
    prepare_snapshot,
    read_inputs,
    read_targets,
    verify_prepared,
)
from cfpb_triage.source_cli import main
from cfpb_triage.source_contracts import (
    ARCHIVE_MEMBER,
    COLUMNS,
    ComplaintInput,
    SourcePin,
    temporal_split,
)
from cfpb_triage.source_io import (
    OfficialRedirect,
    acquire_file,
    acquire_sources,
    digest_file,
    external_path,
)
from pydantic import ValidationError


def invented_row(
    identity: int, received: str, narrative: str = "Invented fee disputed."
) -> dict[str, str]:
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        {
            "Complaint ID": str(identity),
            "Date received": received,
            "Consumer complaint narrative": narrative,
            "Product": "INVENTED PRODUCT TARGET",
            "Issue": "INVENTED ISSUE TARGET",
            "Company": "COMPANY CANARY",
            "Company response to consumer": "RESPONSE CANARY",
            "ZIP code": "00000",
        }
    )
    return row


def invented_source(tmp_path: Path, rows: list[dict[str, str]]) -> tuple[Path, Path, SourcePin]:
    archive, taxonomy = tmp_path / "source.zip", tmp_path / "taxonomy.pdf"
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(archive, "w") as source:
        source.writestr(ARCHIVE_MEMBER, text.getvalue().encode())
    taxonomy.write_bytes(b"%PDF-1.4\nInvented taxonomy fixture, not an official source")
    return (
        archive,
        taxonomy,
        SourcePin(archive_sha256=digest_file(archive), taxonomy_sha256=digest_file(taxonomy)),
    )


def build(tmp_path: Path, rows: list[dict[str, str]]) -> tuple[Path, dict]:
    archive, taxonomy, pin = invented_source(tmp_path, rows)
    output = tmp_path / "prepared"
    return output, prepare_snapshot(archive, taxonomy, pin, output, code_revision="invented-v1")


def test_physical_and_typed_target_isolation(tmp_path: Path) -> None:
    output, manifest = build(tmp_path, [invented_row(1, "2023-09-01")])
    inputs = list(read_inputs(output / "agent.sqlite"))
    assert len(inputs) == 1
    visible = inputs[0].model_dump_json()
    assert inputs[0].narrative == "Invented fee disputed."
    for canary in (
        "INVENTED PRODUCT TARGET",
        "INVENTED ISSUE TARGET",
        "COMPANY CANARY",
        "RESPONSE CANARY",
        "00000",
    ):
        assert canary not in visible
        assert canary.encode() not in (output / "agent.sqlite").read_bytes()
    targets = list(read_targets(output / "evaluator.sqlite"))
    assert targets[0].product == "INVENTED PRODUCT TARGET"
    assert targets[0].issue == "INVENTED ISSUE TARGET"
    assert set(inputs[0].model_dump()) == {"schema_version", "case_id", "narrative"}
    with pytest.raises(ValidationError):
        ComplaintInput(case_id=inputs[0].case_id, narrative="invented", product="hidden")
    assert manifest["prepared"]["prepared_rows"] == 1
    assert "Invented fee disputed." not in json.dumps(manifest)
    assert not (output / "staging.sqlite").exists()


@pytest.mark.parametrize(
    ("received", "expected"),
    [
        ("2023-08-31", None),
        ("2023-09-01", "development"),
        ("2023-12-31", "development"),
        ("2024-01-01", "regression"),
        ("2024-02-29", "regression"),
        ("2024-03-01", "holdout"),
        ("2024-03-31", "holdout"),
        ("2024-04-01", None),
    ],
)
def test_closed_temporal_boundaries(received: str, expected: str | None) -> None:
    assert temporal_split(date.fromisoformat(received)) == expected


def test_group_crossing_quarantined_without_promoting_future_rows(tmp_path: Path) -> None:
    rows = [
        invented_row(1, "2023-09-01", "Same   NARRATIVE"),
        invented_row(2, "2024-03-01", "same narrative"),
        invented_row(3, "2023-10-01", "Development only"),
        invented_row(4, "2023-12-01", "development ONLY"),
        invented_row(5, "2024-01-01", "Regression only"),
        invented_row(6, "2024-03-02", "Holdout only"),
    ]
    output, manifest = build(tmp_path, rows)
    assert manifest["profile"]["counts"]["cross_partition_groups"] == 1
    assert manifest["profile"]["counts"]["cross_partition_rows"] == 2
    assert manifest["prepared"]["split_counts"] == {"development": 2, "regression": 1, "holdout": 1}
    assert manifest["prepared"]["group_count"] == 3
    assert {target.case_id for target in read_targets(output / "evaluator.sqlite")} == {
        case_key(str(i)) for i in (3, 4, 5, 6)
    }
    assert group_key("Ａ  B") == group_key("a b")


def test_missingness_masks_and_outside_rows_have_explicit_denominators(tmp_path: Path) -> None:
    missing_target = invented_row(3, "2024-01-02", "Present unlabelled invented narrative")
    missing_target["Issue"] = " "
    output, manifest = build(
        tmp_path,
        [
            invented_row(1, "2023-09-01", "XXXX paid XX."),
            invented_row(2, "2023-09-02", "  "),
            missing_target,
            invented_row(4, "2024-04-01", "Outside window"),
        ],
    )
    counts = manifest["profile"]["counts"]
    assert counts == {
        "archive_rows": 4,
        "outside_cohort": 1,
        "cohort_rows": 3,
        "missing_narrative": 1,
        "missing_required_consumer_target": 1,
        "masked_narrative_rows": 1,
        "mask_tokens": 2,
        "cross_partition_groups": 0,
        "cross_partition_rows": 0,
    }
    assert list(read_inputs(output / "agent.sqlite"))[0].narrative == "XXXX paid XX."


def test_modified_source_and_taxonomy_refused_before_output_creation(tmp_path: Path) -> None:
    archive, taxonomy, pin = invented_source(tmp_path, [invented_row(1, "2023-09-01")])
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Archive differs"):
        prepare_snapshot(archive, taxonomy, pin, tmp_path / "out", code_revision="x")
    assert not (tmp_path / "out").exists()
    pin = pin.model_copy(update={"archive_sha256": digest_file(archive)})
    taxonomy.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Taxonomy differs"):
        prepare_snapshot(archive, taxonomy, pin, tmp_path / "out", code_revision="x")


@pytest.mark.parametrize(
    "mutation", ["duplicate", "date", "identity", "width", "schema", "extra-member"]
)
def test_invalid_source_fails_closed(tmp_path: Path, mutation: str) -> None:
    rows = [invented_row(1, "2023-09-01")]
    if mutation == "duplicate":
        rows *= 2
    elif mutation == "date":
        rows[0]["Date received"] = "not-a-date"
    elif mutation == "identity":
        rows[0]["Complaint ID"] = "not-numeric"
    archive, taxonomy, pin = invented_source(tmp_path, rows)
    if mutation in ("width", "schema", "extra-member"):
        with zipfile.ZipFile(archive, "w") as source:
            if mutation == "width":
                content = ",".join(COLUMNS) + "\nshort,row\n"
            elif mutation == "schema":
                content = "wrong,columns\n"
            else:
                content = ",".join(COLUMNS) + "\n"
                source.writestr("extra.txt", "invented")
            source.writestr(ARCHIVE_MEMBER, content)
        pin = pin.model_copy(update={"archive_sha256": digest_file(archive)})
    with pytest.raises(ValueError):
        prepare_snapshot(archive, taxonomy, pin, tmp_path / "out", code_revision="invented")


def test_prepared_hashes_inventory_and_group_validation_detect_tamper(tmp_path: Path) -> None:
    output, _ = build(
        tmp_path,
        [
            invented_row(1, "2023-09-01", "first narrative"),
            invented_row(2, "2024-03-01", "other narrative"),
        ],
    )
    pin = digest_file(output / "manifest.json")
    assert verify_prepared(output, pin)["prepared"]["prepared_rows"] == 2
    with pytest.raises(ValueError, match="externally supplied"):
        verify_prepared(output, "0" * 64)
    (output / "extra.txt").touch()
    with pytest.raises(ValueError, match="inventory"):
        verify_prepared(output, pin)
    (output / "extra.txt").unlink()
    with sqlite3.connect(output / "evaluator.sqlite") as database:
        database.execute("UPDATE targets SET split='holdout' WHERE received='2023-09-01'")
    with pytest.raises(ValueError, match="database differs"):
        verify_prepared(output, pin)
    with pytest.raises(ValueError, match="temporal/group"):
        inspect_prepared(output)


def test_no_overwrite_and_no_checkout_source_storage(tmp_path: Path) -> None:
    archive, taxonomy, pin = invented_source(tmp_path, [invented_row(1, "2023-09-01")])
    output = tmp_path / "prepared"
    prepare_snapshot(archive, taxonomy, pin, output, code_revision="invented")
    with pytest.raises(FileExistsError):
        prepare_snapshot(archive, taxonomy, pin, output, code_revision="invented")
    with pytest.raises(ValueError, match="outside Git"):
        external_path(Path(__file__).parent / "raw")
    repository = tmp_path / "different-checkout"
    repository.mkdir()
    (repository / ".git").touch()
    with pytest.raises(ValueError, match="outside Git"):
        external_path(repository / "nested" / "not-created")


def test_cli_offline_prepare_verify_and_safe_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive, taxonomy, pin = invented_source(tmp_path, [invented_row(1, "2023-09-01")])
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(pin.model_dump_json(), encoding="utf-8")
    output = tmp_path / "prepared"
    args = ["--source", str(tmp_path), "--source-pin", str(pin_path)]
    assert main(["prepare", *args, "--output", str(output), "--code-revision", "invented"]) == 0
    assert (
        main(
            [
                "verify",
                "--output",
                str(output),
                "--manifest-sha256",
                digest_file(output / "manifest.json"),
            ]
        )
        == 0
    )
    assert main(["verify-source", *args]) == 0
    assert "Invented fee disputed" not in capsys.readouterr().out
    taxonomy.write_bytes(b"changed")
    assert main(["verify-source", *args]) == 1
    assert "changed" not in capsys.readouterr().err


def test_existing_acquisition_only_verifies_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, pin = invented_source(tmp_path, [invented_row(1, "2023-09-01")])

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No network expected")

    monkeypatch.setattr("cfpb_triage.source_io.build_opener", forbidden)
    acquire_sources(tmp_path, pin)


def test_acquisition_pins_byte_cap_and_no_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"invented source bytes"
    source = tmp_path / "fixture"
    source.write_bytes(payload)
    digest = digest_file(source)

    class InventedOpener:
        def open(self, *args: object, **kwargs: object) -> io.BytesIO:
            return io.BytesIO(payload)

    monkeypatch.setattr("cfpb_triage.source_io.build_opener", lambda *args: InventedOpener())
    destination = tmp_path / "download"
    acquire_file("https://files.consumerfinance.gov/invented", destination, digest, 100)
    assert destination.read_bytes() == payload
    with pytest.raises(ValueError, match="no overwrite"):
        acquire_file("https://files.consumerfinance.gov/invented", destination, "0" * 64, 100)
    assert destination.read_bytes() == payload
    with pytest.raises(ValueError, match="byte cap"):
        acquire_file("https://files.consumerfinance.gov/invented", tmp_path / "too-big", digest, 1)
    with pytest.raises(ValueError, match="nothing published"):
        acquire_file(
            "https://files.consumerfinance.gov/invented", tmp_path / "bad-pin", "0" * 64, 100
        )
    assert not (tmp_path / "too-big").exists() and not (tmp_path / "bad-pin").exists()
    assert not list(tmp_path.glob("*.partial"))


@pytest.mark.parametrize("url", ["http://files.consumerfinance.gov/x", "https://example.com/x"])
def test_redirect_cannot_leave_official_https_host(url: str) -> None:
    from urllib.request import Request

    with pytest.raises(ValueError, match="official HTTPS"):
        OfficialRedirect().redirect_request(
            Request("https://files.consumerfinance.gov/x"), None, 302, "redirect", None, url
        )


def test_initial_url_cannot_leave_official_https_host(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="official HTTPS"):
        acquire_file("https://example.com/source", tmp_path / "source", "0" * 64, 10)


def test_active_sqlite_wal_is_not_part_of_a_sealed_snapshot(tmp_path: Path) -> None:
    output, _ = build(tmp_path, [invented_row(1, "2023-09-01")])
    pin = digest_file(output / "manifest.json")
    database = sqlite3.connect(output / "evaluator.sqlite")
    try:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("UPDATE targets SET product='INVENTED WAL TARGET'")
        database.commit()
        assert (output / "evaluator.sqlite-wal").exists()
        with pytest.raises(ValueError, match="inventory"):
            verify_prepared(output, pin)
    finally:
        database.close()


def test_change_during_semantic_verification_fails_second_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _ = build(tmp_path, [invented_row(1, "2023-09-01")])
    pin = digest_file(output / "manifest.json")
    original = inspect_prepared

    def change_after_inspection(directory: Path) -> dict:
        result = original(directory)
        with sqlite3.connect(directory / "agent.sqlite") as database:
            database.execute("UPDATE inputs SET narrative='Changed invented narrative'")
        return result

    monkeypatch.setattr("cfpb_triage.source.inspect_prepared", change_after_inspection)
    with pytest.raises(ValueError, match="database differs"):
        verify_prepared(output, pin)


def test_empty_usable_population_never_seals_manifest(tmp_path: Path) -> None:
    archive, taxonomy, pin = invented_source(tmp_path, [invented_row(1, "2023-09-01", " ")])
    output = tmp_path / "empty"
    with pytest.raises(ValueError, match="No usable"):
        prepare_snapshot(archive, taxonomy, pin, output, code_revision="invented")
    assert not (output / "manifest.json").exists()
