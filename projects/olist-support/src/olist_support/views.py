"""Read-only scoped effective-time projections; unknown observation times stay unknown."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from agent_harness.contracts import Contract, NonEmpty

from olist_support.source import digest_file, source_time


@dataclass(frozen=True)
class OrderScope:
    """Trusted caller grants source orders; this is not an authentication service."""

    tenant_id: str
    order_ids: frozenset[str]


class AmountTotal(Contract):
    known_minor: int | None
    total_minor: int | None
    missing_rows: int
    scale: Literal[2] = 2


class Event(Contract):
    kind: NonEmpty
    source_local_time: NonEmpty


class Item(Contract):
    item_id: NonEmpty
    product_id: NonEmpty
    seller_id: NonEmpty
    price_source: str | None
    freight_source: str | None
    category_portuguese: str | None
    category_english_source_translation: str | None


class Review(Contract):
    review_id: NonEmpty
    score: int | None
    title_portuguese: str | None
    message_portuguese: str | None
    answered_at_source_local: NonEmpty


class Payment(Contract):
    sequence: NonEmpty
    type: str | None
    installments_source: str | None
    value_source: str | None


class OrderView(Contract):
    tenant_id: NonEmpty
    order_id: NonEmpty
    as_of_source_local: NonEmpty
    clock_basis: Literal["source_local_timezone_unverified"] = "source_local_timezone_unverified"
    visibility_policy: Literal["conservative-effective-time-v1"] = "conservative-effective-time-v1"
    source_manifest_sha256: NonEmpty
    currency_unit: str | None
    snapshot_details_visible: bool
    events: tuple[Event, ...]
    final_source_status: str | None
    estimated_delivery_source_local: str | None
    customer_city: str | None
    customer_state: str | None
    items: tuple[Item, ...] | None
    payments: tuple[Payment, ...] | None
    reviews: tuple[Review, ...]
    item_count: int | None
    payment_count: int | None
    price: AmountTotal | None
    freight: AmountTotal | None
    payment: AmountTotal | None


class OrderStore:
    def __init__(self, database: Path, *, expected_sha256: str) -> None:
        def no_sidecars() -> None:
            if any(
                Path(str(database) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")
            ):
                raise ValueError("sealed database has an active journal or WAL sidecar")

        no_sidecars()
        if database.is_symlink() or digest_file(database) != expected_sha256:
            raise ValueError("database differs from independently pinned derived snapshot")
        self.db = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA query_only=ON")
            self.db.execute("BEGIN")
            # Reading acquires a retained rollback-journal shared lock. A writer cannot
            # commit different pages between view queries while this store remains open.
            self.meta: dict[str, Any] = {
                row["key"]: json.loads(row["value"])
                for row in self.db.execute("SELECT * FROM metadata")
            }
            no_sidecars()
            if digest_file(database) != expected_sha256:
                raise ValueError("database changed while establishing the pinned read snapshot")
            if self.meta["visibility_policy"] != "conservative-effective-time-v1":
                raise ValueError("unsupported visibility policy")
            self.observed_at = datetime.fromisoformat(self.meta["observed_at"])
            if self.observed_at.tzinfo is not None:
                raise ValueError("source observation clock must remain explicit and unspecified")
        except BaseException:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def view(
        self, scope: OrderScope, *, tenant_id: str, order_id: str, as_of: datetime
    ) -> OrderView:
        if not tenant_id or scope.tenant_id != tenant_id or order_id not in scope.order_ids:
            raise PermissionError("order is outside the caller's explicit tenant scope")
        if as_of.tzinfo is not None:
            raise ValueError(
                "as_of must use the declared source-local clock; no timezone inference"
            )
        order = self.db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if order is None or source_time(order["order_purchase_timestamp"]) > as_of:
            raise LookupError("order is unavailable at the requested time")
        visible = as_of >= self.observed_at
        events = tuple(
            Event(kind=kind, source_local_time=order[name])
            for kind, name in (
                ("purchased", "order_purchase_timestamp"),
                ("approved", "order_approved_at"),
                ("carrier_handoff", "order_delivered_carrier_date"),
                ("customer_delivery", "order_delivered_customer_date"),
            )
            if order[name] is not None and source_time(order[name]) <= as_of
        )
        reviews = []
        for row in self.db.execute(
            "SELECT * FROM reviews WHERE order_id=? ORDER BY review_id", (order_id,)
        ):
            # Creation is a survey-send date, not proof that a comment/score existed then.
            answered = row["review_answer_timestamp"]
            # Final text/score has no revision history; do not backdate it to survey creation
            # or answer time. Only the observed snapshot plus its answer cutoff is sufficient.
            if visible and answered is not None and source_time(answered) <= as_of:
                reviews.append(
                    Review(
                        review_id=row["review_id"],
                        score=int(row["review_score"]) if row["review_score"] is not None else None,
                        title_portuguese=row["review_comment_title"],
                        message_portuguese=row["review_comment_message"],
                        answered_at_source_local=answered,
                    )
                )
        items = None
        payments = None
        customer = None
        aggregate = None
        if visible:
            customer = self.db.execute(
                "SELECT customer_city,customer_state FROM customers WHERE customer_id=?",
                (order["customer_id"],),
            ).fetchone()
            aggregate = self.db.execute(
                "SELECT * FROM orders_360 WHERE order_id=?", (order_id,)
            ).fetchone()
            items = tuple(
                Item(
                    item_id=row["order_item_id"],
                    product_id=row["product_id"],
                    seller_id=row["seller_id"],
                    price_source=row["price"],
                    freight_source=row["freight_value"],
                    category_portuguese=row["product_category_name"],
                    category_english_source_translation=row["product_category_name_english"],
                )
                for row in self.db.execute(
                    """SELECT i.*,p.product_category_name,
                    t.product_category_name_english FROM items i
                    LEFT JOIN products p ON i.product_id=p.product_id
                    LEFT JOIN translations t ON p.product_category_name=t.product_category_name
                    WHERE i.order_id=? ORDER BY i.order_item_id""",
                    (order_id,),
                )
            )
            payments = tuple(
                Payment(
                    sequence=row["payment_sequential"],
                    type=row["payment_type"],
                    installments_source=row["payment_installments"],
                    value_source=row["payment_value"],
                )
                for row in self.db.execute(
                    "SELECT * FROM payments WHERE order_id=? ORDER BY payment_sequential",
                    (order_id,),
                )
            )

        def total(name: str) -> AmountTotal | None:
            if aggregate is None:
                return None
            value, missing = aggregate[name + "_known_minor"], aggregate[name + "_missing"]
            return AmountTotal(
                known_minor=value,
                total_minor=value if not missing else None,
                missing_rows=missing or 0,
            )

        return OrderView(
            tenant_id=tenant_id,
            order_id=order_id,
            as_of_source_local=as_of.isoformat(),
            source_manifest_sha256=self.meta["source_manifest_sha256"],
            currency_unit=self.meta["currency"].get("source_declared_unit"),
            snapshot_details_visible=visible,
            events=events,
            final_source_status=order["order_status"] if visible else None,
            estimated_delivery_source_local=order["order_estimated_delivery_date"]
            if visible
            else None,
            customer_city=customer["customer_city"] if customer is not None else None,
            customer_state=customer["customer_state"] if customer is not None else None,
            items=items,
            payments=payments,
            reviews=tuple(reviews),
            item_count=(aggregate["item_count"] or 0) if aggregate is not None else None,
            payment_count=(aggregate["payment_count"] or 0) if aggregate is not None else None,
            price=total("price"),
            freight=total("freight_value"),
            payment=total("payment_value"),
        )
