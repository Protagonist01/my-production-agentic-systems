"""Hand-invented CSVs with explicit multiplicity, future facts and missing values."""

import csv
import json

from olist_support.source import digest_file
from test_olist_snapshot import snapshot


def dataset(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    tables = {
        "olist_orders_dataset.csv": [
            dict(
                order_id="order-1",
                customer_id="customer-1",
                order_status="delivered",
                order_purchase_timestamp="2020-01-01 09:00:00",
                order_approved_at="2020-01-01 10:00:00",
                order_delivered_carrier_date="2020-01-03 10:00:00",
                order_delivered_customer_date="2020-01-05 10:00:00",
                order_estimated_delivery_date="2020-01-07 00:00:00",
            ),
            dict(
                order_id="order-empty",
                customer_id="customer-1",
                order_status="unavailable",
                order_purchase_timestamp="2020-01-01 09:00:00",
            ),
        ],
        "olist_customers_dataset.csv": [
            dict(
                customer_id="customer-1",
                customer_unique_id="PRIVATE-CUSTOMER",
                customer_zip_code_prefix="00123",
                customer_city="São Paulo",
                customer_state="SP",
            )
        ],
        "olist_order_items_dataset.csv": [
            dict(
                order_id="order-1",
                order_item_id=str(i),
                product_id="product-1",
                seller_id="seller-1",
                shipping_limit_date="2020-01-04 00:00:00",
                price="10.01" if i == 1 else "20.02",
                freight_value="1.00",
            )
            for i in (1, 2)
        ],
        "olist_order_payments_dataset.csv": [
            dict(
                order_id="order-1",
                payment_sequential=str(i),
                payment_type="credit_card",
                payment_installments="1",
                payment_value=value,
            )
            for i, value in ((1, "12.00"), (2, "20.03"))
        ],
        "olist_order_reviews_dataset.csv": [
            dict(
                order_id="order-1",
                review_id="review-" + str(i),
                review_score="5",
                review_comment_title="Ótimo",
                review_comment_message="FUTURE-REVIEW-" + str(i),
                review_creation_date="2020-01-04 00:00:00",
                review_answer_timestamp=date,
            )
            for i, date in ((1, "2020-01-06 10:00:00"), (2, "2020-01-08 10:00:00"))
        ],
        "olist_products_dataset.csv": [
            dict(product_id="product-1", product_category_name="cama_mesa_banho")
        ],
        "olist_sellers_dataset.csv": [dict(seller_id="seller-1")],
        "product_category_name_translation.csv": [
            dict(
                product_category_name="cama_mesa_banho",
                product_category_name_english="bed_bath_table",
            )
        ],
    }
    for name, columns in snapshot.REQUIRED.items():
        write_rows(source / name, columns, tables.get(name, []))
    return source


def write_rows(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in columns})


def manifest(source, root):
    payload = {
        "dataset_handle": snapshot.HANDLE,
        "source_version": 7,
        "currency": {"source_declared_unit": None, "status": "unverified"},
        "timestamp_timezone": None,
        "language": "Portuguese retained; source categories separate",
        "files": snapshot.profile_snapshot(source),
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path, digest_file(path)
