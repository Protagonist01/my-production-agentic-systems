"""Aggregate original publisher labels; never turn clause spans into billing/meaning gold."""

from collections import defaultdict

from agent_harness.release_contracts import Sha256

from revenue_integrity.source_contracts import PublishedTarget


def reference_coverage(
    targets: tuple[PublishedTarget, ...], *, source_manifest_sha256: Sha256
) -> dict[str, object]:
    """Caller must verify source/store bytes separately; only return safe aggregate counts."""
    targets = tuple(PublishedTarget.model_validate_json(t.canonical_json()) for t in targets)
    if not targets or len({t.case_id for t in targets}) != len(targets):
        raise ValueError("empty or duplicate publisher reference population")
    # A digest supplied to this pure aggregator is a provenance label, not a verification.
    if len(source_manifest_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in source_manifest_sha256
    ):
        raise ValueError("invalid source manifest digest")
    families: dict[str, set[str]] = defaultdict(set)
    categories: dict[str, list[PublishedTarget]] = defaultdict(list)
    for target in targets:
        families[target.family_id].add(target.split)
        categories[target.category].append(target)
    if any(len(splits) > 1 for splits in families.values()):
        raise ValueError("publisher reference family crosses splits")

    def counts(members: list[PublishedTarget]) -> dict[str, int]:
        return {
            "questions": len(members),
            "answerable": sum(not t.impossible for t in members),
            "no_answer": sum(t.impossible for t in members),
            "spans": sum(len(t.answers) for t in members),
            "families": len({t.family_id for t in members}),
            "answerable_families": len({t.family_id for t in members if not t.impossible}),
            "no_answer_families": len({t.family_id for t in members if t.impossible}),
        }

    return {
        "version": "cuad-reference-applicability-v1",
        "source_manifest_sha256": source_manifest_sha256,
        "totals": counts(list(targets)),
        "categories": {
            category: {
                "all": counts(members),
                "development": counts([t for t in members if t.split == "development"]),
                "holdout": counts([t for t in members if t.split == "holdout"]),
            }
            for category, members in sorted(categories.items())
        },
        "applicable_reference_metrics": [
            "publisher_relative_span_precision",
            "answerable_span_recall",
            "no_answer_agreement",
        ],
        "not_established": [
            "unseen_model_training_data",
            "general_contract_meaning",
            "normalized_billing_terms",
            "sim_invoice_delta",
            "authorization",
            "state_recovery",
            "clinical_validity",
        ],
        "source_verification_performed_by_aggregator": False,
        "release_allowed": False,
    }
