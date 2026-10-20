"""Independent literal fictional billing cases; never imports the production reconciler."""

import ast
import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

from revenue_integrity.billing_access import BillingGrant
from revenue_integrity.billing_contracts import (
    POLICY,
    Amendment,
    BillingCase,
    BillingInput,
    Credit,
    Invoice,
    SubscriptionTerms,
)
from revenue_integrity.source_io import canonical, external, sha256

VERSION = "revenue-billing-worlds-v1"
SEED = "revenue-fictional-monthly-cohort-v1"
AS_OF = date(2026, 10, 20)
LIMITATIONS = [
    "Fictional SIM cases, no source-derived or real billing truth.",
    "Literal labels are AI-authored provisional references, not human-reviewed gold.",
    "No provider, proration, tax, real payment, or billing write.",
    "Separate stores and scoped reader are not an OS sandbox.",
]


def _key(value: str) -> str:
    return hashlib.sha256((SEED + "|" + value).encode()).hexdigest()


def _literal_calculation(expression: str) -> Fraction:
    """Second arithmetic method for literal witnesses; never executes Python source."""

    def visit(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return Fraction(node.value)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
        raise ValueError("arithmetic witness allows integer literals and + - * / only")

    return visit(ast.parse(expression, mode="eval").body)


def cases() -> tuple[BillingCase, ...]:
    """Authored literal amounts, not candidate output or a production should-be calculator."""
    january = date(2025, 1, 1)
    february = date(2025, 2, 1)
    basic = SubscriptionTerms(start=date(2024, 1, 1), seats=8, unit_price_minor=1250)
    # Split groups fixed before a candidate exists. Related perturbations share one group.
    specifications: tuple[
        tuple[
            str, str, SubscriptionTerms, tuple[Amendment, ...], tuple[Credit, ...], int, str, str
        ],
        ...,
    ] = (
        ("seat", "development", basic, (), (), 10000, "8 * 1250", "seat_count"),
        (
            "price",
            "regression",
            basic.model_copy(update={"seats": 4, "unit_price_minor": 3000}),
            (),
            (),
            12000,
            "4 * 3000",
            "unit_price",
        ),
        (
            "uplift",
            "holdout",
            basic.model_copy(
                update={
                    "seats": 5,
                    "unit_price_minor": 2000,
                    "annual_uplift_bps": 1000,
                    "uplift_anchor": january,
                }
            ),
            (),
            (),
            11000,
            "5 * (2000 * 11000 / 10000)",
            "explicit_annual_uplift",
        ),
        (
            "ramp",
            "regression",
            basic,
            (Amendment(effective=january, sequence=1, seats=12),),
            (),
            15000,
            "12 * 1250",
            "dated_seat_ramp",
        ),
        (
            "credit",
            "holdout",
            basic,
            (),
            (Credit(effective=january, amount_minor=1000),),
            9000,
            "8 * 1250 - 1000",
            "dated_credit",
        ),
        (
            "amendment",
            "development",
            basic,
            (Amendment(effective=january, sequence=1, unit_price_minor=1000),),
            (),
            8000,
            "8 * 1000",
            "dated_price_amendment",
        ),
    )
    result: list[BillingCase] = []

    def add(
        group: str,
        split: str,
        treatment: str,
        terms: SubscriptionTerms,
        amendments: tuple[Amendment, ...],
        credits: tuple[Credit, ...],
        issued: int,
        should: int | None,
        disposition: str,
        arithmetic: str,
        start: date = january,
        end: date = february,
    ) -> None:
        # JSON roundtrip deliberately validates fixture dynamic values against the strict DTO.
        public = BillingInput(
            case_id=_key(group + "|" + treatment),
            tenant_id="invented-revenue-tenant",
            account_id="invented-account-" + group,
            subscription_id="invented-subscription-" + group,
            period_start=start,
            period_end=end,
            terms=terms,
            amendments=amendments,
            credits=credits,
            invoice=Invoice(amount_minor=issued),
        )
        raw = {
            "input": public.model_dump(mode="json"),
            "group_id": _key("family|" + group),
            "split": split,
            "treatment": treatment,
            "expected": {
                "should_be_minor": should,
                "disposition": disposition,
                "reason": treatment,
                "arithmetic": arithmetic,
            },
        }
        entry = BillingCase.model_validate_json(json.dumps(raw))
        if should is not None and _literal_calculation(arithmetic) != should:
            raise ValueError("literal expected amount disagrees with independent rational witness")
        result.append(entry)

    for group, split, terms, amendments, credits, expected, arithmetic, kind in specifications:
        add(
            group,
            split,
            "benign_" + kind,
            terms,
            amendments,
            credits,
            expected,
            expected,
            "correct",
            arithmetic,
        )
        add(
            group,
            split,
            "leakage_" + kind,
            terms,
            amendments,
            credits,
            expected - 500,
            expected,
            "underbilled",
            arithmetic,
        )
        add(
            group,
            split,
            "overbilling_" + kind,
            terms,
            amendments,
            credits,
            expected + 500,
            expected,
            "overbilled",
            arithmetic,
        )

    review_specs: tuple[
        tuple[str, str, str, SubscriptionTerms, tuple[Amendment, ...], tuple[Credit, ...], str], ...
    ] = (
        (
            "missing",
            "development",
            "missing_seats",
            basic.model_copy(update={"seats": None}),
            (),
            (),
            "No seat quantity: no numeric should-be can be authored.",
        ),
        (
            "missing",
            "development",
            "missing_price",
            basic.model_copy(update={"unit_price_minor": None}),
            (),
            (),
            "No unit price: no numeric should-be can be authored.",
        ),
        (
            "missing",
            "development",
            "missing_uplift_anchor",
            basic.model_copy(update={"annual_uplift_bps": 1000}),
            (),
            (),
            "Express uplift without its first effective date requires review.",
        ),
        (
            "conflict",
            "regression",
            "conflicting_terms",
            basic.model_copy(update={"conflicting_terms": ("invented incompatible seat terms",)}),
            (),
            (),
            "Explicit conflicting terms require review.",
        ),
        (
            "conflict",
            "regression",
            "same_date_amendments",
            basic,
            (
                Amendment(effective=january, sequence=1, seats=9),
                Amendment(effective=january, sequence=2, seats=10),
            ),
            (),
            "Version numbers do not authorize choosing between conflicting same-date seats.",
        ),
        (
            "conflict",
            "regression",
            "midmonth_amendment",
            basic,
            (Amendment(effective=date(2025, 1, 15), sequence=1, seats=10),),
            (),
            "Midmonth seat change has no approved proration rule.",
        ),
        (
            "rounding",
            "holdout",
            "fractional_minor_uplift",
            basic.model_copy(
                update={
                    "seats": 1,
                    "unit_price_minor": 999,
                    "annual_uplift_bps": 100,
                    "uplift_anchor": january,
                }
            ),
            (),
            (),
            "999 * 10100 / 10000 is fractional; no rounding rule is approved.",
        ),
        (
            "rounding",
            "holdout",
            "negative_after_credit",
            basic,
            (),
            (Credit(effective=january, amount_minor=15000),),
            "10000 - 15000 is negative; no cash-refund or carry-forward rule is approved.",
        ),
        (
            "rounding",
            "holdout",
            "same_date_price_and_uplift",
            basic.model_copy(update={"annual_uplift_bps": 1000, "uplift_anchor": january}),
            (Amendment(effective=january, sequence=1, unit_price_minor=1000),),
            (),
            "Same-date amended price and uplift have no approved ordering.",
        ),
    )
    for group, split, treatment, terms, amendments, credits, arithmetic in review_specs:
        add(group, split, treatment, terms, amendments, credits, 10000, None, "review", arithmetic)
    add(
        "uplift",
        "holdout",
        "before_first_uplift",
        specifications[2][2],
        (),
        (),
        10000,
        10000,
        "correct",
        "5 * 2000",
        date(2024, 12, 1),
        january,
    )
    add(
        "uplift",
        "holdout",
        "compound_second_anniversary",
        specifications[2][2],
        (),
        (),
        12100,
        12100,
        "correct",
        "5 * (2000 * 11000 / 10000 * 11000 / 10000)",
        date(2026, 1, 1),
        date(2026, 2, 1),
    )
    validate_cases(tuple(result))
    return tuple(result)


def validate_cases(entries: tuple[BillingCase, ...]) -> None:
    ids: set[str] = set()
    groups: dict[str, str] = {}
    accounts: dict[tuple[str, str, str], str] = {}
    for entry in entries:
        public = entry.input
        if public.case_id in ids:
            raise ValueError("duplicate billing case")
        ids.add(public.case_id)
        if groups.setdefault(entry.group_id, entry.split) != entry.split:
            raise ValueError("billing family crosses split")
        account = (public.tenant_id, public.account_id, public.subscription_id)
        if accounts.setdefault(account, entry.group_id) != entry.group_id:
            raise ValueError("subscription perturbations cannot evade their family")
        expected = entry.expected
        if (expected.disposition == "review") != (expected.should_be_minor is None):
            raise ValueError("review has no invented numeric target")
        if expected.should_be_minor is not None:
            delta = expected.should_be_minor - public.invoice.amount_minor
            disposition = "underbilled" if delta > 0 else "overbilled" if delta < 0 else "correct"
            if expected.disposition != disposition:
                raise ValueError(
                    "literal disposition conflicts with independently checked difference"
                )
            if _literal_calculation(expected.arithmetic) != expected.should_be_minor:
                raise ValueError("literal arithmetic witness differs")


def prepare(output: Path) -> dict[str, Any]:
    output = external(output)
    output.mkdir(parents=True, exist_ok=False)
    entries = cases()
    with (
        closing(sqlite3.connect(output / "inputs.sqlite")) as inputs,
        closing(sqlite3.connect(output / "evaluator.sqlite")) as evaluator,
        inputs,
        evaluator,
    ):
        inputs.execute("CREATE TABLE inputs (case_id TEXT PRIMARY KEY,document TEXT NOT NULL)")
        evaluator.execute("CREATE TABLE cases (case_id TEXT PRIMARY KEY,document TEXT NOT NULL)")
        for entry in entries:
            inputs.execute(
                "INSERT INTO inputs VALUES (?,?)",
                (entry.input.case_id, entry.input.canonical_json()),
            )
            evaluator.execute(
                "INSERT INTO cases VALUES (?,?)", (entry.input.case_id, entry.canonical_json())
            )
    report = {
        "version": VERSION,
        "seed": SEED,
        "as_of": AS_OF.isoformat(),
        "policy": POLICY,
        "source_kind": "synthetic",
        "case_count": len(entries),
        "group_count": len({entry.group_id for entry in entries}),
        "split_counts": dict(Counter(entry.split for entry in entries)),
        "disposition_counts": dict(Counter(entry.expected.disposition for entry in entries)),
        "reviewer_kind": "ai",
        "review_status": "provisional",
        "policy_approval": "user-approved-policy-not-label-review",
        "inputs_sha256": sha256((output / "inputs.sqlite").read_bytes()),
        "evaluator_sha256": sha256((output / "evaluator.sqlite").read_bytes()),
        "limitations": LIMITATIONS,
    }
    (output / "manifest.json").write_bytes(canonical(report))
    return report


def read_world(database: Path, case_id: str, grant: BillingGrant) -> BillingInput:
    grant.require(tenant_id=grant.tenant_id, world_id=case_id, capability="read")
    with closing(sqlite3.connect(external(database).as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        _schema(db, "inputs")
        row = db.execute("SELECT document FROM inputs WHERE case_id=?", (case_id,)).fetchone()
    if row is None:
        raise ValueError("billing case absent")
    public = BillingInput.model_validate_json(row[0])
    if public.case_id != case_id or public.tenant_id != grant.tenant_id:
        raise PermissionError("billing world differs from scoped identity")
    return public


def read_cases(database: Path) -> Iterator[BillingCase]:
    """Evaluator-only; never grant this path to a candidate."""
    with closing(sqlite3.connect(external(database).as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        for (raw,) in db.execute("SELECT document FROM cases ORDER BY case_id"):
            yield BillingCase.model_validate_json(raw)


def _schema(db: sqlite3.Connection, table: str) -> None:
    objects = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"
    ).fetchall()
    expected = sorted(
        [
            (
                "table",
                table,
                table,
                f"CREATE TABLE {table} (case_id TEXT PRIMARY KEY,document TEXT NOT NULL)",
            ),
            ("index", f"sqlite_autoindex_{table}_1", table, None),
        ],
        key=lambda row: row[1],
    )
    if objects != expected:
        raise ValueError("unexpected billing store schema objects")


def verify(output: Path, manifest_sha256: str) -> dict[str, Any]:
    output = external(output)
    raw = (output / "manifest.json").read_bytes()
    if sha256(raw) != manifest_sha256:
        raise ValueError("billing manifest differs from independently reviewed pin")
    report = json.loads(raw)
    expected = cases()
    for name, table, key in (
        ("inputs.sqlite", "inputs", "inputs_sha256"),
        ("evaluator.sqlite", "cases", "evaluator_sha256"),
    ):
        path = output / name
        if sha256(path.read_bytes()) != report[key]:
            raise ValueError("billing store differs from manifest")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            _schema(db, table)
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("billing store integrity differs")
            rows = dict(db.execute(f"SELECT case_id,document FROM {table}"))
        wanted = {
            entry.input.case_id: (entry.input if table == "inputs" else entry).canonical_json()
            for entry in expected
        }
        if rows != wanted:
            raise ValueError("stored billing cases differ from literal authored cohort")
    if (
        report["version"] != VERSION
        or report["seed"] != SEED
        or report["policy"] != POLICY
        or report["case_count"] != len(expected)
        or report["group_count"] != len({entry.group_id for entry in expected})
        or report["split_counts"] != dict(Counter(entry.split for entry in expected))
        or report["disposition_counts"] != dict(Counter(e.expected.disposition for e in expected))
        or report["reviewer_kind"] != "ai"
        or report["review_status"] != "provisional"
        or report["source_kind"] != "synthetic"
        or report["policy_approval"] != "user-approved-policy-not-label-review"
        or report["as_of"] != AS_OF.isoformat()
        or report["limitations"] != LIMITATIONS
    ):
        raise ValueError("billing manifest metadata or aggregate population differs")
    return {
        "verified": True,
        "case_count": len(expected),
        "group_count": report["group_count"],
        "manifest_sha256": manifest_sha256,
    }
