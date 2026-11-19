"""Bounded samples of public CFPB metadata for the operations exercise."""

import argparse
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cfpb_triage.source import case_key
from cfpb_triage.source_io import external_path

ENDPOINT = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
MAX_BYTES = 2_000_000
JOURNAL_ID = 0x43465042


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def sample(start: date, end: date, limit: int) -> tuple[dict[str, str], int, str]:
    if not 0 <= (end - start).days < 60 or not 1 <= limit <= 100:
        raise ValueError("bounded receipt-date window and sample size required")
    query = urlencode(
        {
            "no_aggs": "true",
            "sort": "created_date_desc",
            "date_received_min": start.isoformat(),
            "date_received_max": end.isoformat(),
            "size": limit,
        }
    )
    request = Request(ENDPOINT + "?" + query, headers={"Accept": "application/json"})
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ValueError("unexpected CFPB response")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("response exceeds byte limit")
    return project(raw, start, end, limit)


def project(raw: bytes, start: date, end: date, limit: int) -> tuple[dict[str, str], int, str]:
    page = json.loads(raw)
    if page.get("timed_out") is not False or page["_shards"]["failed"] != 0:
        raise ValueError("partial CFPB search response")
    hits = page["hits"]
    total, relation = hits["total"]["value"], hits["total"]["relation"]
    rows = hits["hits"]
    if type(total) is not int or relation not in ("eq", "gte") or not isinstance(rows, list):
        raise ValueError("unexpected CFPB count")
    if total < 0 or len(rows) != min(total, limit):
        raise ValueError("unexpected CFPB page length")
    projected = {}
    for row in rows:
        source = row["_source"]
        identity = source["complaint_id"]
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9]{1,24}", identity):
            raise ValueError("unexpected public complaint identifier")
        received = date.fromisoformat(source["date_received"][:10])
        key = case_key(identity)
        if not start <= received <= end or key in projected:
            raise ValueError("public complaint outside requested window or duplicated")
        projected[key] = received.isoformat()
    return projected, total, relation


def poll(path: Path, start: date, end: date, limit: int) -> dict[str, object]:
    if path.is_symlink():
        raise ValueError("private feed database symlink refused")
    path = external_path(path)
    rows, total, relation = sample(start, end, limit)
    with closing(sqlite3.connect(path)) as database, database:
        database.execute("BEGIN IMMEDIATE")
        app_id = database.execute("PRAGMA application_id").fetchone()[0]
        if app_id != JOURNAL_ID:
            if app_id != 0 or database.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone():
                raise ValueError("public intake requires its own journal")
            database.execute("PRAGMA application_id = 1128681538")
        database.execute(
            "CREATE TABLE IF NOT EXISTS public_intake (case_id TEXT PRIMARY KEY, received TEXT)"
        )
        database.execute(
            "CREATE TABLE IF NOT EXISTS public_polls (checked_at TEXT, start_day TEXT, "
            "end_day TEXT, sampled INTEGER, inserted INTEGER, reported_total INTEGER, "
            "total_relation TEXT)"
        )
        before = database.total_changes
        database.executemany(
            "INSERT INTO public_intake VALUES (?,?) ON CONFLICT(case_id) DO NOTHING",
            rows.items(),
        )
        added = database.total_changes - before
        database.execute(
            "INSERT INTO public_polls VALUES (?,?,?,?,?,?,?)",
            (
                datetime.now(UTC).isoformat(),
                start.isoformat(),
                end.isoformat(),
                len(rows),
                added,
                total,
                relation,
            ),
        )
    return {
        "source": "cfpb_public_metadata_sample",
        "received_from": start.isoformat(),
        "received_through": end.isoformat(),
        "sampled": len(rows),
        "added": added,
        "deduplicated": len(rows) - added,
        "reported_total": total,
        "total_relation": relation,
        "window_complete": total == len(rows) and relation == "eq",
        "narratives_stored": 0,
        "model_calls": 0,
    }


def replay_ids(path: Path, limit: int) -> tuple[str, ...]:
    if not 1 <= limit <= 10 or path.is_symlink():
        raise ValueError("bounded private journal replay required")
    uri = external_path(path).as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        if database.execute("PRAGMA application_id").fetchone()[0] != JOURNAL_ID:
            raise ValueError("public intake journal identity differs")
        return tuple(
            row[0]
            for row in database.execute(
                "SELECT case_id FROM public_intake ORDER BY received DESC, case_id LIMIT ?",
                (limit,),
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--size", type=int, default=25)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    args = parser.parse_args()
    if (args.start is None) != (args.end is None):
        parser.error("--start and --end must be supplied together")
    end = args.end or datetime.now(UTC).date()
    start = args.start or end - timedelta(days=29)
    try:
        print(json.dumps(poll(args.journal, start, end, args.size), sort_keys=True))
        return 0
    except (OSError, URLError, sqlite3.Error, ValueError, LookupError, TypeError, AttributeError):
        print('{"error":"cfpb_public_sample_failed"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
