"""Billing-world expectations are checked without importing the production engine."""

import ast
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError
from revenue_integrity.billing_access import BillingGrant
from revenue_integrity.billing_contracts import BillingInput
from revenue_integrity.billing_worlds import (
    _literal_calculation,
    cases,
    prepare,
    read_cases,
    read_world,
    validate_cases,
    verify,
)
from revenue_integrity.billing_worlds_cli import main
from revenue_integrity.source_io import canonical, sha256


def grant(entry, **updates):
    fields = dict(
        tenant_id=entry.input.tenant_id,
        actor_id="invented-reader",
        world_ids=(entry.input.case_id,),
        capabilities=("read",),
    )
    fields.update(updates)
    return BillingGrant(**fields)


def test_literal_cohort_has_benign_examples_and_independent_arithmetic():
    entries = cases()
    assert len(entries) == 29
    assert len({entry.group_id for entry in entries}) == 9
    expected = {
        "benign_seat_count": 10000,
        "benign_unit_price": 12000,
        "benign_explicit_annual_uplift": 11000,
        "benign_dated_seat_ramp": 15000,
        "benign_dated_credit": 9000,
        "benign_dated_price_amendment": 8000,
        "before_first_uplift": 10000,
        "compound_second_anniversary": 12100,
    }
    actual = {
        e.treatment: e.expected.should_be_minor
        for e in entries
        if e.expected.disposition == "correct"
    }
    assert actual == expected
    assert sum(e.expected.disposition == "review" for e in entries) == 9
    assert all(
        e.expected.should_be_minor is None for e in entries if e.expected.disposition == "review"
    )
    assert all(e.reviewer_kind == "ai" and e.review_status == "provisional" for e in entries)
    families = {}
    for entry in entries:
        families.setdefault(entry.group_id, set()).add(entry.split)
    assert all(len(splits) == 1 for splits in families.values())
    assert {e.split for e in entries} == {"development", "regression", "holdout"}


def test_rational_witness_is_distinct_exact_arithmetic_and_never_executes():
    assert _literal_calculation("5 * (2000 * 11000 / 10000 * 11000 / 10000)") == 12100
    assert _literal_calculation("999 * 10100 / 10000") != 1009
    for source in ("__import__('os').getcwd()", "True", "1 ** 5", "1.5"):
        with pytest.raises(ValueError):
            _literal_calculation(source)
    tree = ast.parse(
        Path(__file__)
        .parents[1]
        .joinpath("projects/revenue-integrity/src/revenue_integrity/billing_worlds.py")
        .read_text()
    )
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(
        name and any(term in name for term in ("reconciliation", "engine")) for name in imports
    )


def test_expected_mutation_split_and_identity_evasion_are_rejected():
    entries = cases()
    first = entries[0]
    with pytest.raises(ValueError, match="duplicate"):
        validate_cases((first, first))
    changed = entries[1].model_copy(update={"split": "holdout"})
    with pytest.raises(ValueError, match="crosses split"):
        validate_cases((first, changed))
    changed = entries[1].model_copy(update={"group_id": "invented-evaded-family"})
    with pytest.raises(ValueError, match="evade"):
        validate_cases((first, changed))
    changed = first.model_copy(
        update={"expected": first.expected.model_copy(update={"should_be_minor": 1})}
    )
    with pytest.raises(ValueError):
        validate_cases((changed,))


def test_prepare_stores_only_public_input_and_verifies_literal_population(tmp_path):
    output = tmp_path / "worlds"
    report = prepare(output)
    assert report["split_counts"] == {"development": 9, "regression": 9, "holdout": 11}
    assert report["disposition_counts"] == {
        "correct": 8,
        "underbilled": 6,
        "overbilled": 6,
        "review": 9,
    }
    stored = tuple(read_cases(output / "evaluator.sqlite"))
    assert {e.input.case_id for e in stored} == {e.input.case_id for e in cases()}
    for entry in stored:
        public = read_world(output / "inputs.sqlite", entry.input.case_id, grant(entry))
        assert public == entry.input
        assert {"expected", "split", "group_id", "arithmetic", "reviewer_kind"}.isdisjoint(
            public.model_dump()
        )
    with sqlite3.connect(output / "inputs.sqlite") as db:
        assert {
            name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        } == {"inputs"}
        for (raw,) in db.execute("SELECT document FROM inputs"):
            assert "should_be_minor" not in raw and "provisional" not in raw
    pin = sha256((output / "manifest.json").read_bytes())
    assert verify(output, pin) == {
        "verified": True,
        "case_count": 29,
        "group_count": 9,
        "manifest_sha256": pin,
    }
    with pytest.raises(FileExistsError):
        prepare(output)


def test_scope_rejection_happens_before_open_and_mismatched_tenant_is_hidden(tmp_path):
    first = cases()[0]
    with pytest.raises(PermissionError):
        read_world(tmp_path / "absent.sqlite", first.input.case_id, grant(first, world_ids=()))
    output = tmp_path / "worlds"
    prepare(output)
    with pytest.raises(PermissionError):
        read_world(
            output / "inputs.sqlite",
            first.input.case_id,
            grant(first, tenant_id="another-invented-tenant"),
        )
    with pytest.raises(PermissionError):
        read_world(
            output / "inputs.sqlite", first.input.case_id, grant(first, capabilities=("reconcile",))
        )
    with pytest.raises(ValueError, match="absent"):
        read_world(output / "inputs.sqlite", "absent", grant(first, world_ids=("absent",)))
    with sqlite3.connect(output / "inputs.sqlite") as db:
        value = first.input.model_dump(mode="json")
        value["case_id"] = "different-invented-case"
        db.execute(
            "UPDATE inputs SET document=? WHERE case_id=?", (json.dumps(value), first.input.case_id)
        )
    with pytest.raises(PermissionError, match="scoped identity"):
        read_world(output / "inputs.sqlite", first.input.case_id, grant(first))


@pytest.mark.parametrize("change", ["target", "public", "view", "trigger", "extra_case", "count"])
def test_repin_cannot_hide_changed_cases_or_schema(tmp_path, change):
    output = tmp_path / "worlds"
    report = prepare(output)
    if change == "count":
        report["case_count"] = 1
    elif change == "target":
        with sqlite3.connect(output / "evaluator.sqlite") as db:
            key, raw = db.execute("SELECT case_id,document FROM cases LIMIT 1").fetchone()
            value = json.loads(raw)
            value["expected"]["should_be_minor"] = 777
            db.execute("UPDATE cases SET document=? WHERE case_id=?", (json.dumps(value), key))
    else:
        with sqlite3.connect(output / "inputs.sqlite") as db:
            if change == "view":
                db.execute("CREATE VIEW targets AS SELECT 'invented answer' AS gold")
            elif change == "trigger":
                db.execute("CREATE TRIGGER leak AFTER INSERT ON inputs BEGIN SELECT 'gold'; END")
            elif change == "extra_case":
                db.execute("INSERT INTO inputs VALUES ('extra','{}')")
            else:
                key, raw = db.execute("SELECT case_id,document FROM inputs LIMIT 1").fetchone()
                value = json.loads(raw)
                value["invoice"]["amount_minor"] = 777
                db.execute("UPDATE inputs SET document=? WHERE case_id=?", (json.dumps(value), key))
    for name, key in (("inputs.sqlite", "inputs_sha256"), ("evaluator.sqlite", "evaluator_sha256")):
        report[key] = sha256((output / name).read_bytes())
    (output / "manifest.json").write_bytes(canonical(report))
    with pytest.raises(ValueError):
        verify(output, sha256((output / "manifest.json").read_bytes()))


def test_tampered_manifest_and_store_hash_fail_before_semantic_compare(tmp_path):
    output = tmp_path / "worlds"
    prepare(output)
    with pytest.raises(ValueError, match="independently reviewed"):
        verify(output, "0" * 64)
    pin = sha256((output / "manifest.json").read_bytes())
    path = output / "inputs.sqlite"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="differs from manifest"):
        verify(output, pin)


def test_cli_private_git_guard_and_generic_validation_errors(tmp_path, capsys):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").write_text("invented")
    assert main(["prepare", "--output", str(checkout / "worlds")]) == 1
    assert not (checkout / "worlds").exists()
    assert "outside Git" not in capsys.readouterr().out
    first = cases()[0].input.model_dump(mode="json")
    first["should_be_minor"] = 10000
    with pytest.raises(ValidationError):
        BillingInput.model_validate_json(json.dumps(first))
