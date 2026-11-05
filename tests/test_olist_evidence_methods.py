"""Invented trust grants test coverage logic, never real semantic qualification."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from agent_harness.evaluation_standards import Review, StandardProfile, _reviewed
from agent_harness.evaluator_qualification import (
    QualificationCase,
    QualificationDataset,
    QualificationObservation,
    QualificationProtocol,
    QualificationStudy,
    qualification_report,
)
from agent_harness.release_contracts import pin, sha256
from olist_support.evidence_methods import (
    CLAIMS,
    PROPOSAL,
    MethodCase,
    MethodClaim,
    MethodDesignAcceptance,
    MethodScope,
    QualificationMaterial,
    audit_methods,
    qualification_pin,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 6, tzinfo=UTC)
RAW = (ROOT / "docs/data/olist-v2-method-design-acceptance-v1.json").read_bytes()
ACCEPTANCE_PIN = "fb39d0589b5f11dff9aeaf68f3efc51272635b95de8d684f65fac4fdf21fd8dc"


def sample():
    profile = StandardProfile.model_validate_json(
        (ROOT / "docs/evaluation/profiles/olist.json").read_bytes()
    )
    case = MethodCase(
        case_id=sha256(b"invented-case"),
        input_sha256=sha256(b"invented-input"),
        reference_sha256=sha256(b"invented-reference"),
        source_keys=("invented-parent",),
        slices=profile.required_holdout_slices,
        split="holdout",
    )
    scopes, claims = [], []
    for field, parts in CLAIMS.items():
        for part, methods in parts.items():
            scope = MethodScope(
                field=field,
                part=part,
                method=methods[0],
                input_sha256=case.input_sha256,
                reference_sha256=case.reference_sha256,
                source_sha256=sha256(b"invented-source"),
                evaluator_sha256=sha256(b"invented-evaluator"),
                slices=case.slices,
                permitted_use="qualification",
                authority_reference="invented-test-only-grant-not-real-qualification",
                granted_at=NOW - timedelta(hours=1),
                expires_at=NOW + timedelta(hours=1),
            )
            scopes.append(scope)
            claims.append(
                MethodClaim(
                    case_id=case.case_id,
                    field=field,
                    part=part,
                    scope_sha256=pin(scope),
                    input_sha256=case.input_sha256,
                    reference_sha256=case.reference_sha256,
                    source_sha256=scope.source_sha256,
                    evaluator_sha256=scope.evaluator_sha256,
                    evidence_sha256=sha256((field + part).encode()),
                    observed_at=NOW,
                    disposition="supported",
                )
            )
    return dict(
        profile=profile,
        cases=(case,),
        claims=tuple(claims),
        scopes=tuple(scopes),
        acceptance_raw=RAW,
        expected_acceptance_sha256=ACCEPTANCE_PIN,
        trusted_scope_pins=frozenset(pin(s) for s in scopes),
        verified_claim_pins=frozenset(pin(c) for c in claims),
        qualifications={},
        now=NOW,
    )


def changed_scope(values, index, **changes):
    """Explicitly invent a new external grant and a newly admitted claim for a test."""
    scopes, claims = list(values["scopes"]), list(values["claims"])
    scopes[index] = scopes[index].model_copy(update=changes)
    claims[index] = claims[index].model_copy(update={"scope_sha256": pin(scopes[index])})
    return dict(
        values,
        scopes=tuple(scopes),
        claims=tuple(claims),
        trusted_scope_pins=frozenset(pin(s) for s in scopes),
        verified_claim_pins=frozenset(pin(c) for c in claims),
    )


def test_full_invented_coverage_is_neither_factual_authentication_nor_release():
    result = audit_methods(**sample())
    assert result["method_coverage_met"] and result["required_claims"] == 11
    assert result["admitted_supported_claims"] == 11 and not result["blockers"]
    assert not result["qualification_allowed"] and not result["release_allowed"]
    assert not result["human_review_supplied"] and not result["factual_source_io_performed"]
    assert result["provider_calls_authorized"] == 0
    assert result["domain_readers_and_external_trust_required"]


def test_arithmetic_does_not_establish_requested_amount_meaning():
    values = sample()
    claims = tuple(c for c in values["claims"] if c.part != "requested_meaning")
    result = audit_methods(**dict(values, claims=claims))
    assert not result["method_coverage_met"]
    assert any(
        "claim_missing:" in b and "amount:requested_meaning" in b for b in result["blockers"]
    )
    semantic = next(s for s in values["scopes"] if s.part == "requested_meaning")
    with pytest.raises(ValidationError, match="cannot establish"):
        MethodScope.model_validate_json(
            semantic.model_copy(update={"method": "independent_program"}).canonical_json()
        )


@pytest.mark.parametrize(
    "kind", ["development_case", "development_scope", "no_grants", "no_proofs"]
)
def test_self_description_and_development_acceptance_cannot_qualify(kind):
    values = sample()
    if kind == "development_case":
        values["cases"] = (values["cases"][0].model_copy(update={"split": "development"}),)
    elif kind == "development_scope":
        values = changed_scope(values, 0, permitted_use="development")
    elif kind == "no_grants":
        values["trusted_scope_pins"] = frozenset()
    else:
        values["verified_claim_pins"] = frozenset()
    assert not audit_methods(**values)["method_coverage_met"]


@pytest.mark.parametrize(
    "name", ["input_sha256", "reference_sha256", "source_sha256", "evaluator_sha256"]
)
def test_admitted_claim_still_requires_exact_case_and_grant_binding(name):
    values = sample()
    row = values["claims"][0].model_copy(update={name: "f" * 64})
    values["claims"] = (row, *values["claims"][1:])
    values["verified_claim_pins"] = frozenset(pin(c) for c in values["claims"])
    assert not audit_methods(**values)["method_coverage_met"]


def test_duplicate_support_cannot_vote_away_a_contradiction():
    values = sample()
    bad = values["claims"][0].model_copy(update={"disposition": "contradicted"})
    values["claims"] = (bad, *values["claims"][1:])
    result = audit_methods(**values)
    assert any("claim_contradicted" in b for b in result["blockers"])
    assert any("not_independently_admitted" in b for b in result["blockers"])
    with pytest.raises(ValueError, match="vote away"):
        audit_methods(**dict(values, claims=(*values["claims"], sample()["claims"][0])))


@pytest.mark.parametrize("kind", ["expired", "before_grant", "future", "missing_slice"])
def test_scope_and_observation_intervals_and_slices(kind):
    values = sample()
    if kind == "expired":
        values = changed_scope(values, 0, expires_at=NOW)
    elif kind == "missing_slice":
        values = changed_scope(values, 0, slices=("eligible_refund",))
    else:
        time = NOW - timedelta(hours=2) if kind == "before_grant" else NOW + timedelta(seconds=1)
        values["claims"] = (
            values["claims"][0].model_copy(update={"observed_at": time}),
            *values["claims"][1:],
        )
        values["verified_claim_pins"] = frozenset(pin(c) for c in values["claims"])
    assert not audit_methods(**values)["method_coverage_met"]


def test_transitive_source_groups_cannot_cross_splits_or_be_counted_independently():
    values = sample()
    a = values["cases"][0].model_copy(update={"source_keys": ("A", "B")})
    b = a.model_copy(
        update={"case_id": "b" * 64, "input_sha256": "b" * 64, "source_keys": ("C", "D")}
    )
    c = a.model_copy(
        update={
            "case_id": "c" * 64,
            "input_sha256": "c" * 64,
            "source_keys": ("B", "C"),
            "split": "development",
        }
    )
    result = audit_methods(**dict(values, cases=(a, b, c)))
    assert result["declared_connected_groups_not_authenticated"] == 1
    assert "connected_source_or_input_crosses_splits" in result["blockers"]


def test_exact_acceptance_bytes_profile_and_clock_are_required():
    values = sample()
    assert sha256(RAW) == ACCEPTANCE_PIN
    assert (
        sha256((ROOT / "docs/data/olist-evidence-method-design-proposal-v2.json").read_bytes())
        == PROPOSAL
    )
    for change in (
        {"acceptance_raw": RAW + b" "},
        {"profile": values["profile"].model_copy(update={"required_fields": ("intent",)})},
        {"now": NOW.replace(tzinfo=None)},
    ):
        with pytest.raises(ValueError):
            audit_methods(**dict(values, **change))
    with pytest.raises(ValidationError):
        Review.model_validate_json(RAW)
    review = Review(
        reviewer="invented", reference="invented", reviewed_at=NOW, kind="human_retrospective"
    )
    assert not _reviewed(review, NOW + timedelta(seconds=1))
    assert not MethodDesignAcceptance.model_validate_json(RAW).qualification_cohort_approved


def model_material(values, field="intent.meaning", wrong=False):
    """Small permissive invented test; these thresholds are not an accepted study."""
    slices = values["cases"][0].slices
    data = QualificationDataset(
        version="invented-only",
        agent="olist",
        field=field,
        frozen_at=NOW - timedelta(days=1),
        cases=tuple(
            QualificationCase(
                case_id=str(i),
                input_sha256=sha256(str(i).encode()),
                independence_keys=(str(i),),
                split="calibration" if i < 2 else "holdout",
                slices=slices,
                expected_accept=i % 2 == 0,
                reference_sha256="a" * 64,
                reference_kind="independent_program",
                applicability_ref="invented-only",
                exposure="withheld_from_tuning",
            )
            for i in range(6)
        ),
    )
    protocol = QualificationProtocol(
        dataset_sha256=pin(data),
        evaluator_sha256=values["claims"][0].evaluator_sha256,
        frozen_at=data.frozen_at,
        trial_ids=("t1",),
        required_slices=slices,
        min_holdout_groups=4,
        min_groups_per_slice=4,
        min_groups_per_class=2,
        min_decision_coverage=1,
        min_scheduled_accuracy=1,
        max_false_accept_rate=0,
        max_false_reject_rate=0,
        max_group_error_upper_bound=1,
        reference_validation_ref="invented-only",
        sample_size_ref="invented-only",
    )
    study = QualificationStudy(
        protocol_sha256=pin(protocol),
        started_at=data.frozen_at,
        finished_at=data.frozen_at,
        rows=tuple(
            QualificationObservation(
                case_id=c.case_id,
                trial_id="t1",
                input_sha256=c.input_sha256,
                evaluator_sha256=protocol.evaluator_sha256,
                observed_at=data.frozen_at,
                decision="accept" if c.expected_accept != wrong else "reject",
            )
            for c in data.cases
        ),
    )
    return QualificationMaterial(data, protocol, study)


@pytest.mark.parametrize("kind", ["bound", "missing", "wrong_field", "failed", "late"])
def test_model_pointer_requires_recomputed_qualification_for_exact_claim(kind):
    values = sample()
    material = model_material(
        values,
        "amount.requested_meaning" if kind == "wrong_field" else "intent.meaning",
        kind == "failed",
    )
    if kind == "late":
        material = QualificationMaterial(
            material.dataset,
            material.protocol,
            material.study.model_copy(update={"finished_at": NOW}),
        )
    report = qualification_report(material.dataset, material.protocol, material.study, now=NOW)
    digest = qualification_pin(report)
    values = changed_scope(values, 0, method="qualified_model", qualification_report_sha256=digest)
    values["qualifications"] = {} if kind == "missing" else {digest: material}
    result = audit_methods(**values)
    assert result["method_coverage_met"] == (kind == "bound")
    assert not result["release_allowed"]


def test_current_development_evidence_with_no_admitted_claims_stays_blocked():
    values = sample()
    values.update(
        cases=(values["cases"][0].model_copy(update={"split": "development"}),),
        claims=(),
        scopes=(),
        trusted_scope_pins=frozenset(),
        verified_claim_pins=frozenset(),
    )
    result = audit_methods(**values)
    assert result["required_claims"] == 11 and result["admitted_supported_claims"] == 0
    assert not result["method_coverage_met"]
    assert len([b for b in result["blockers"] if b.startswith("holdout_slice_missing:")]) == 8
