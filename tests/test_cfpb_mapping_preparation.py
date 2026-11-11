"""The approved draft reads training records without decoding source test utterances."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "docs/evaluation/prepare_cfpb_mapping_draft.py"


def helper():
    spec = importlib.util.spec_from_file_location("cfpb_mapping_prepare", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mixed_container_skips_unrelated_split_without_utf8_decoding():
    raw = b'{"test":[["\xffhidden test text", "test"]], "train":[["training only","weather"]]}'
    assert helper().training_member(raw) == [["training only", "weather"]]


def test_stops_after_training_and_handles_escaped_braces_in_other_members():
    raw = b'{"other":["}\\"[{}]"],"train":[["training","recipe"]],"test":["\xff"]}'
    assert helper().training_member(raw) == [["training", "recipe"]]


def test_never_substitutes_oos_train_or_test_for_required_train_member():
    with pytest.raises(ValueError, match="unavailable"):
        helper().training_member(b'{"oos_train":[["not approved","oos"]],"test":[]}')


def test_selection_is_stable_and_preserves_original_text_and_labels():
    rows = [("source typo unchanged", "weather"), ("another query", "weather")]
    assert helper().choose(rows, ("weather",)) == helper().choose(
        tuple(reversed(rows)), ("weather",)
    )
    assert helper().choose(rows[:1], ("weather",)) == rows[:1]
    with pytest.raises(ValueError, match="missing"):
        helper().choose(rows, ("recipe",))
