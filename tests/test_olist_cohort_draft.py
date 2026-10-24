"""Draft grouping and literal labels, with invented source views only."""

import json

import pytest
from olist_support import cohort_draft
from olist_support.cohort_draft import build_draft
from olist_support.policy import propose
from test_olist_policy import invented_view


def test_draft_keeps_parent_and_wording_families_together_and_covers_boundaries():
    views = tuple(
        invented_view().model_copy(
            update={"order_id": f"invented-{i}", "source_manifest_sha256": "b" * 64}
        )
        for i in range(6)
    )
    cases, metadata = build_draft(views, "a" * 64)
    assert len(cases.entries) == 12
    assert len({e.input.request.message for e in cases.entries}) == 12
    for i in range(0, 12, 2):
        left, right = cases.entries[i : i + 2]
        assert left.group_id == right.group_id and left.split == right.split
        assert metadata[i]["language_family"] == metadata[i + 1]["language_family"]
    assert {e.input.order.payment.total_minor for e in cases.entries} == {9999, 10000, 10001}
    # Runtime is only a consistency cross-check here, never the label constructor.
    for entry in cases.entries:
        actual = propose(entry.input.order, entry.input.request, entry.input.confirmation)
        assert (actual.action, actual.amount_minor, actual.reason) == (
            entry.expected.action,
            entry.expected.amount_minor,
            entry.expected.reason,
        )
    holdout_slices = {
        s
        for e, m in zip(cases.entries, metadata, strict=True)
        if e.split == "holdout"
        for s in m["slices"]
    }
    assert {
        "eligible_refund",
        "required_review",
        "missing_facts",
        "conflicting_facts",
        "cap_boundary",
        "unseen_wording",
        "prompt_injection",
        "crash_restart",
    } <= holdout_slices
    assert sum(m["recovery_required"] for m in metadata) == 1


def test_duplicate_source_groups_refused():
    with pytest.raises(ValueError, match="distinct source"):
        build_draft((invented_view(),) * 6, "a" * 64)


def test_provider_export_excludes_intent_labels_and_source_facts(monkeypatch, tmp_path):
    class Database:
        def execute(self, query):
            return [{"order_id": f"invented-{i}"} for i in range(6)]

    class Store:
        db = Database()
        observed_at = None

        def __init__(self, *args, **kwargs):
            pass

        def view(self, scope, *, tenant_id, order_id, as_of):
            return invented_view().model_copy(
                update={"order_id": order_id, "source_manifest_sha256": "b" * 64}
            )

        def close(self):
            pass

    monkeypatch.setattr(cohort_draft, "OrderStore", Store)
    result = cohort_draft.prepare(
        tmp_path / "unused.sqlite",
        "a" * 64,
        tmp_path / "new-draft",
        excluded_groups=frozenset({"c" * 64}),
    )
    exported = json.loads((tmp_path / "new-draft/inputs.json").read_bytes())
    assert result["provider_calls"] == 0
    assert len(exported) == 12 and all(set(row) == {"case_id", "text"} for row in exported)
    assert all("invented-" not in row["text"] for row in exported)
