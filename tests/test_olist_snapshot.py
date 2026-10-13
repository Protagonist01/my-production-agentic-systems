"""Offline source-integrity checks use invented records, not Olist rows."""

import csv
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "projects/olist-support/scripts/snapshot.py"
SPEC = importlib.util.spec_from_file_location("olist_snapshot_tool", SCRIPT)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


def synthetic_snapshot(tmp_path: Path) -> Path:
    source = tmp_path / "synthetic"
    source.mkdir()
    for name, columns in snapshot.REQUIRED.items():
        with (source / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            row = ["invented" for _ in columns]
            if "order_purchase_timestamp" in columns:
                row[columns.index("order_purchase_timestamp")] = "2020-01-01 00:00:00"
            row[-1] = ""
            writer.writerow(row)
    return source


def test_repeatable_profile_and_modified_bytes_fail_verification(tmp_path: Path) -> None:
    source = synthetic_snapshot(tmp_path)
    files = snapshot.profile_snapshot(source)
    assert len(files) == 9
    assert all(item["row_count"] == 1 for item in files)
    assert all(item["empty_value_counts"][item["columns"][-1]] == 1 for item in files)
    manifest = {"dataset_handle": snapshot.HANDLE, "source_version": 7, "files": files}
    assert snapshot.verify_snapshot(source, manifest) == files
    with pytest.raises(ValueError, match="pinned Olist version"):
        snapshot.verify_snapshot(source, {**manifest, "source_version": 6})
    path = source / "olist_orders_dataset.csv"
    path.write_text(path.read_text().replace("invented", "changed"), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        snapshot.verify_snapshot(source, manifest)


def test_missing_file_and_bad_schema_are_rejected(tmp_path: Path) -> None:
    source = synthetic_snapshot(tmp_path)
    path = source / "olist_sellers_dataset.csv"
    path.rename(source / "missing.txt")
    with pytest.raises(ValueError, match="file mismatch"):
        snapshot.profile_snapshot(source)
    (source / "missing.txt").rename(path)
    path.write_text("wrong_column\nvalue\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected schema"):
        snapshot.profile_snapshot(source)


def test_malformed_record_is_rejected(tmp_path: Path) -> None:
    source = synthetic_snapshot(tmp_path)
    with (source / "olist_sellers_dataset.csv").open("a", encoding="utf-8") as stream:
        stream.write("short,row\n")
    with pytest.raises(ValueError, match="Malformed CSV"):
        snapshot.profile_snapshot(source)


def test_raw_source_cannot_be_inside_checkout() -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        snapshot.outside_repository(SCRIPT.parent / "raw")
