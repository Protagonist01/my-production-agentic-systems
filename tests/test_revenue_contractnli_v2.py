"""Authored tiny native schema witnesses; no publisher source labels are invented here."""

import json

import pytest

from revenue_contractnli import (
    NativePrediction,
    audit_archive,
    native_score,
    parse_training,
    strict_json,
)


def source():
    return {
        "labels": {k: {"hypothesis": k} for k in ("a", "b", "c")},
        "documents": [
            {
                "id": 1,
                "text": "An invented NDA.",
                "spans": [[0, 2], [3, 11]],
                "annotation_sets": [
                    {
                        "annotations": {
                            "a": {"choice": "Entailment", "spans": [0]},
                            "b": {"choice": "Contradiction", "spans": [1]},
                            "c": {"choice": "NotMentioned", "spans": []},
                        }
                    }
                ],
            }
        ],
    }


def test_native_projection_preserves_three_classes_all_spans_and_no_label_leakage():
    refs = parse_training(json.dumps(source()).encode())
    assert {r.choice for r in refs} == {"Entailment", "Contradiction", "NotMentioned"}
    assert set(refs[0].input.model_dump()) == {
        "schema_version",
        "case_id",
        "document",
        "hypothesis",
    }
    assert all(not r.billing_reference for r in refs)
    report = native_score(refs, ())
    assert report["missing"] == 3 and report["macro_f1"] == 0
    predictions = tuple(
        NativePrediction(case_id=r.input.case_id, choice=r.choice, evidence=r.evidence)
        for r in refs
    )
    assert native_score(refs, predictions)["macro_f1"] == 1
    assert native_score(refs, predictions)["exact_complete_evidence"] == {
        "numerator": 2,
        "denominator": 2,
    }


@pytest.mark.parametrize(
    "mutation", ["bounds", "duplicate", "neutral_evidence", "invalid_choice", "missing_annotation"]
)
def test_corrupt_native_source_is_refused_without_repairs(mutation):
    value = source()
    d = value["documents"][0]
    if mutation == "bounds":
        d["spans"][0] = [0, 999]
    elif mutation == "duplicate":
        value["documents"].append(d)
    elif mutation == "neutral_evidence":
        d["annotation_sets"][0]["annotations"]["c"]["spans"] = [0]
    elif mutation == "invalid_choice":
        d["annotation_sets"][0]["annotations"]["a"]["choice"] = "accept"
    else:
        del d["annotation_sets"][0]["annotations"]["a"]
    with pytest.raises(ValueError):
        parse_training(json.dumps(value).encode())


def test_unpinned_archive_duplicate_json_and_forged_predictions_are_refused():
    with pytest.raises(ValueError):
        audit_archive(b"not official", b"invented", train_member="train.json")
    for raw in (b'{"documents":[],"documents":[]}', b"NaN"):
        with pytest.raises(ValueError):
            strict_json(raw)
    refs = parse_training(json.dumps(source()).encode())
    p = NativePrediction(case_id=refs[0].input.case_id, choice="Entailment", evidence=((0, 999),))
    with pytest.raises(ValueError):
        native_score(refs, (p,))
