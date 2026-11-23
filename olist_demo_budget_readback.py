"""Read all existing Gemini reservation namespaces without editing their history.

The older PA readers counted base+PA but omitted the additive semantic namespace.
This reader reports that defect instead of deleting a reservation or relabeling it
as free. It is an audit/proposal tool, never a provider grant or ledger provisioner.
"""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

ATTEMPTS = {
    "attempts": "response_pin IS NULL",
    "olist_semantic_attempts": ("ordinal NOT IN (SELECT ordinal FROM olist_semantic_observations)"),
    "pa_reservations": "ordinal NOT IN (SELECT ordinal FROM pa_settlements)",
    "pa_live_attempts": "ordinal NOT IN (SELECT ordinal FROM pa_live_settlements)",
}
KNOWN_TABLES = frozenset(ATTEMPTS) | frozenset(
    {
        "authorization",
        "amendments",
        "development_extensions",
        "development_slots",
        "paired_extensions",
        "paired_slots",
        "paired_canary_passes",
        "paired_availability",
        "model_extensions",
        "model_slots",
        "model_canary_passes",
        "routing_extensions",
        "routing_slots",
        "routing_settlements",
        "routing_stops",
        "routing_canary_receipts",
        "olist_semantic_scope",
        "olist_semantic_observations",
        "pa_scope",
        "pa_settlements",
        "pa_stops",
        "pa_live_grant",
        "pa_live_settlements",
        "pa_live_stop",
        "olist_demo_scope",
        "olist_demo_attempts",
        "olist_demo_results",
        "olist_demo_stop",
        "revenue_scope_843",
    }
)


def historical_hash(db: sqlite3.Connection, exclude: frozenset[str] = frozenset()) -> str:
    schema = [
        row
        for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        if row[2] not in exclude
    ]
    raw = hashlib.sha256(json.dumps(schema, separators=(",", ":")).encode())
    for name in sorted(row[1] for row in schema if row[0] == "table"):
        if not name.replace("_", "").isalnum():
            raise ValueError("unsupported ledger identifier")
        rows = sorted(
            json.dumps(row, separators=(",", ":"), allow_nan=False)
            for row in db.execute('SELECT * FROM "' + name + '"')
        )
        raw.update(json.dumps([name, rows], separators=(",", ":")).encode())
    return raw.hexdigest()


def inspect(path: Path) -> dict[str, Any]:
    with closing(sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        schema = db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        ).fetchall()
        tables = {r[1] for r in schema if r[0] == "table"}
        if not set(ATTEMPTS) <= tables:
            raise ValueError("all four historical reservation namespaces are required")
        mapped = dict(ATTEMPTS)
        revenue_reserved = 0
        if "revenue_scope_843" in tables:
            # Audited Revenue runner: fifty maximum attempts in this same table;
            # result NULL means consumed but unsettled, not a reusable slot.
            columns = db.execute("PRAGMA table_info(revenue_scope_843)").fetchall()
            definition = db.execute(
                "SELECT sql FROM sqlite_master WHERE name='revenue_scope_843'"
            ).fetchone()[0]
            if (
                [(r[1], r[2], r[3], r[5]) for r in columns]
                != [
                    ("ordinal", "INTEGER", 0, 1),
                    ("request_pin", "TEXT", 1, 0),
                    ("result", "TEXT", 0, 0),
                ]
                or "CHECK(ordinal BETWEEN 0 AND 49)" not in definition
                or db.execute(
                    "SELECT 1 FROM revenue_scope_843 WHERE ordinal NOT BETWEEN 0 AND 49 LIMIT 1"
                ).fetchone()
            ):
                raise ValueError("audited Revenue reservation schema differs")
            mapped["revenue_scope_843"] = "result IS NULL"
            revenue_reserved = int(
                db.execute("SELECT count(*) FROM revenue_scope_843").fetchone()[0]
            )
        if "olist_demo_attempts" in tables:
            mapped["olist_demo_attempts"] = (
                "ordinal NOT IN (SELECT ordinal FROM olist_demo_results)"
            )
        unknown = tables - KNOWN_TABLES
        if unknown:
            raise ValueError("new reservation namespace needs an explicit audited mapping")
        counts = {
            name: int(db.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0])
            for name in mapped
        }
        unsettled = {
            name: int(
                db.execute('SELECT count(*) FROM "' + name + '" WHERE ' + clause).fetchone()[0]
            )
            for name, clause in mapped.items()
        }
        # Include every historical schema/row, including stops, grants and receipts.
        snapshot = historical_hash(db)
        grant_rows = db.execute("SELECT document FROM pa_live_grant").fetchall()
        if len(grant_rows) != 1:
            raise ValueError("one latest historical live grant required")
        grant = json.loads(grant_rows[0][0])
        ceiling, retained = grant["lifetime_ceiling"], grant["old_slots_preserved"]
        if "revenue_scope_843" in tables:
            if ceiling != 793:
                raise ValueError("Revenue extension expects the recorded793parent allowance")
            ceiling = 843
            retained += 50 - revenue_reserved
        if "olist_demo_scope" in tables:
            scope_rows = db.execute("SELECT document FROM olist_demo_scope").fetchall()
            if len(scope_rows) != 1:
                raise ValueError("one demo scope required")
            demo_scope = json.loads(scope_rows[0][0])
            ceiling, retained = demo_scope["lifetime_ceiling"], demo_scope["retained_bound_slots"]
        if type(ceiling) is not int or type(retained) is not int or min(ceiling, retained) < 0:
            raise ValueError("invalid historical allowance")
        total = sum(counts.values())
        return {
            "version": "all-gemini-namespace-readback-v1",
            "reservation_counts": counts,
            "unsettled_by_namespace": unsettled,
            "total_consumed": total,
            "latest_recorded_ceiling": ceiling,
            "retained_bound_slots": retained,
            "unallocated_capacity": ceiling - total - retained,
            "legacy_pa_reported_total": grant["historical_consumed"] + counts["pa_live_attempts"],
            "omitted_semantic_reservations": counts["olist_semantic_attempts"],
            "revenue_reserved": revenue_reserved,
            "revenue_unspent_slots_preserved": 50 - revenue_reserved
            if "revenue_scope_843" in tables
            else 0,
            "historical_pa_slots_preserved": grant["old_slots_preserved"],
            "historical_snapshot_sha256": snapshot,
            "proposed_new_study_attempts": 146,
            "proposed_required_ceiling": total + retained + 146,
            "proposed_increase_from_recorded_ceiling": total + retained + 146 - ceiling,
            "new_attempts_authorized": 0,
            "prior_history_modified": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    print(json.dumps(inspect(parser.parse_args().ledger), sort_keys=True))


if __name__ == "__main__":
    main()
