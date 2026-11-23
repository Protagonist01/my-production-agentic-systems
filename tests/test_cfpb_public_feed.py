import json
import sqlite3
from contextlib import closing
from datetime import date

import pytest

import cfpb_public_feed as feed

DAY = date(2026, 11, 2)


def page(*, failed=0, ids=("123",), date_text="2026-11-02T23:59:58.000Z"):
    return json.dumps(
        {
            "timed_out": False,
            "_shards": {"failed": failed},
            "hits": {
                "total": {"value": len(ids), "relation": "eq"},
                "hits": [
                    {
                        "_source": {
                            "complaint_id": key,
                            "date_received": date_text,
                            "consumer_complaint_narrative": "Must never be stored",
                            "product": "Must never be passed to the exercise",
                        }
                    }
                    for key in ids
                ],
            },
        }
    ).encode()


def test_live_inclusive_end_day_and_repeat_poll_store_only_intake_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, "sample", lambda *args: feed.project(page(), DAY, DAY, 1))
    journal = tmp_path / "public.sqlite"
    assert feed.poll(journal, DAY, DAY, 1)["added"] == 1
    second = feed.poll(journal, DAY, DAY, 1)
    assert second["added"] == 0 and second["deduplicated"] == 1
    assert feed.replay_ids(journal, 1) == (feed.case_key("123"),)
    with closing(sqlite3.connect(journal)) as db:
        assert db.execute("SELECT * FROM public_intake").fetchall() == [
            (feed.case_key("123"), DAY.isoformat())
        ]
        assert db.execute("SELECT COUNT(*) FROM public_polls").fetchone() == (2,)


@pytest.mark.parametrize(
    "raw", [page(failed=1), page(ids=("123", "123")), page(date_text="2026-11-03")]
)
def test_out_of_window_duplicate_and_partial_pages_refuse(raw):
    with pytest.raises(ValueError):
        feed.project(raw, DAY, DAY, 2)


def test_poll_refuses_unrelated_existing_database(tmp_path, monkeypatch):
    monkeypatch.setattr(feed, "sample", lambda *args: feed.project(page(), DAY, DAY, 1))
    journal = tmp_path / "unrelated.sqlite"
    with closing(sqlite3.connect(journal)) as db:
        db.execute("CREATE TABLE unrelated (id INT)")
    with pytest.raises(ValueError, match="own journal"):
        feed.poll(journal, DAY, DAY, 1)
    with closing(sqlite3.connect(journal)) as db:
        assert db.execute("SELECT name FROM sqlite_schema").fetchall() == [("unrelated",)]
