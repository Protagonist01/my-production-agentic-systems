"""Exact original packet bytes reconstructed from public JSON for portable test fixtures."""

import json
from pathlib import Path

from olist_support.controlled_service_reference import bind_accepted

ROOT = Path(__file__).resolve().parents[1]


def packet_bytes():
    data = json.loads(
        (ROOT / "docs/data/olist-controlled-field-draft-v1.json").read_text(encoding="utf-8")
    )
    owner = json.loads(
        (ROOT / "docs/data/olist-controlled-field-acceptance-v1.json").read_text(encoding="utf-8")
    )
    return (
        (json.dumps(owner, indent=2, ensure_ascii=False) + "\n").encode(),
        json.dumps(data["method"], indent=2, ensure_ascii=False).replace("\n", "\r\n").encode(),
        json.dumps(data["references"], indent=2, ensure_ascii=False).replace("\n", "\r\n").encode(),
    )


def references():
    return bind_accepted(*packet_bytes())
