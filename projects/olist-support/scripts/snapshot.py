# /// script
# requires-python = ">=3.12"
# dependencies = ["kagglehub==1.0.2"]
# ///
"""Acquire or verify Olist v7; publish aggregate provenance, never source rows."""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

HANDLE = "olistbr/brazilian-ecommerce/versions/7"
REPO = Path(__file__).resolve().parents[3]
REQUIRED = {
    "olist_customers_dataset.csv": [
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ],
    "olist_geolocation_dataset.csv": [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ],
    "olist_order_items_dataset.csv": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ],
    "olist_order_payments_dataset.csv": [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
    "olist_order_reviews_dataset.csv": [
        "review_id",
        "order_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ],
    "olist_orders_dataset.csv": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "olist_products_dataset.csv": [
        "product_id",
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ],
    "olist_sellers_dataset.csv": [
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ],
    "product_category_name_translation.csv": [
        "product_category_name",
        "product_category_name_english",
    ],
}


def outside_repository(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(REPO):
        raise ValueError("Raw source snapshots must be outside the repository.")
    return resolved


def profile_file(path: Path, columns: list[str]) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    missing = dict.fromkeys(columns, 0)
    count = 0
    earliest = latest = None
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != columns:
            raise ValueError(f"Unexpected schema: {path.name}")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row in {path.name}, record {count + 1}")
            count += 1
            for column in columns:
                missing[column] += row[column] == ""
            timestamp = row.get("order_purchase_timestamp")
            if timestamp:
                datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                earliest = timestamp if earliest is None else min(earliest, timestamp)
                latest = timestamp if latest is None else max(latest, timestamp)
    result = {
        "name": path.name,
        "sha256": digest,
        "bytes": path.stat().st_size,
        "row_count": count,
        "columns": columns,
        "empty_value_counts": missing,
    }
    if earliest is not None:
        result["purchase_timestamp_range"] = {"min": earliest, "max": latest, "timezone": None}
    return result


def profile_snapshot(source: Path) -> list[dict]:
    source = outside_repository(source)
    observed = {path.name for path in source.glob("*.csv")}
    if observed != set(REQUIRED):
        raise ValueError(
            f"Snapshot file mismatch: missing={sorted(set(REQUIRED) - observed)}, "
            f"unexpected={sorted(observed - set(REQUIRED))}"
        )
    for name in REQUIRED:
        outside_repository(source / name)
    return [profile_file(source / name, columns) for name, columns in sorted(REQUIRED.items())]


def verify_snapshot(source: Path, manifest: dict) -> list[dict]:
    if manifest.get("dataset_handle") != HANDLE or manifest.get("source_version") != 7:
        raise ValueError("Manifest does not identify the pinned Olist version 7.")
    actual = profile_snapshot(source)
    if actual != manifest["files"]:
        raise ValueError(
            "Snapshot differs from the pinned manifest; do not overwrite the baseline."
        )
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["acquire", "profile", "verify"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "acquire":
        import kagglehub

        source = Path(kagglehub.dataset_download(HANDLE))
    else:
        if args.source is None:
            parser.error("--source is required for profile/verify")
        source = args.source
    if args.mode == "verify" or (args.mode == "acquire" and args.manifest.exists()):
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        files = verify_snapshot(source, manifest)
    else:
        if args.manifest.exists():
            parser.error("Manifest already exists. Verify it or choose a new output; no overwrite.")
        files = profile_snapshot(source)
        manifest = {
            "schema_version": 1,
            "dataset_handle": HANDLE,
            "source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
            "publisher": "Olist",
            "source_version": 7,
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "download_library": "kagglehub==1.0.2",
            "license": {
                "identifier": "CC-BY-NC-SA-4.0",
                "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                "handling": (
                    "Local noncommercial development; no raw rows exported to Git or telemetry."
                ),
            },
            "currency": {
                "source_declared_unit": None,
                "status": "Unverified; do not infer from country.",
            },
            "timestamp_timezone": None,
            "language": "Portuguese fields/text retained; category translation is source supplied.",
            "source_kind": "Original anonymized historical commerce records",
            "evaluation_status": (
                "Not an evaluation case set; no support policy or gold actions exist."
            ),
            "files": files,
        }
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    total_records = sum(item["row_count"] for item in files)
    print(f"{args.mode}: {len(files)} files, {total_records:,} records checked")
    print(f"Source directory (local only): {outside_repository(source)}")


if __name__ == "__main__":
    main()
