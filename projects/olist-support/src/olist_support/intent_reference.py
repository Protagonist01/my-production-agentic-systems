"""Limited publisher-intent references and complete development comparison denominators.

Caller-supplied acceptance records are trusted provenance, not authenticated identities.
No legacy review gate, full service reference, provider dispatcher or release approval.
"""

from collections import Counter
from typing import Annotated, Literal, Self

from agent_harness.contracts import AgentInput, Contract, NonEmpty
from agent_harness.release_contracts import Sha256, pin, sha256
from pydantic import AwareDatetime, Field, model_validator

from olist_support.utterance_reference import UtteranceAudit, UtteranceFrame, mapping_pin


class IntentMethodAcceptance(Contract):
    version: Literal["olist-native-intent-method-acceptance-v1"] = (
        "olist-native-intent-method-acceptance-v1"
    )
    proposal_sha256: Sha256
    source_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    source_csv_sha256: Sha256
    mapping_sha256: Sha256
    accepted_at: AwareDatetime
    owner_reply_reference: NonEmpty
    exact_reply: Literal["Accept this limited reference method"]
    scope: Literal["development_calibration_intent_only"] = "development_calibration_intent_only"
    qualifies_individual_labels: Literal[False] = False
    replaces_release_review: Literal[False] = False
    provider_calls_authorized: Literal[0] = 0
    release_allowed: Literal[False] = False


class IntentReference(Contract):
    case_id: Sha256
    frame: UtteranceFrame
    input: AgentInput
    expected_intent: Literal["refund", "status", "unsupported"]
    reference_basis: Literal["conditional_native_instruction_mapping"] = (
        "conditional_native_instruction_mapping"
    )
    partition: Literal["exposed_development"] = "exposed_development"
    applicability: Literal["native_label_conditional_not_individually_validated"] = (
        "native_label_conditional_not_individually_validated"
    )
    amount_reference_established: Literal[False] = False
    semantic_gold_validated: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def projection(self) -> Self:
        if (
            self.frame.proposed_route != self.expected_intent
            or self.input != self.frame.input
            or self.case_id != sha256(("olist-native-intent|" + pin(self.frame)).encode())
            or any(r != "previously_exposed_normalized_text" for r in self.frame.exclusions)
        ):
            raise ValueError("intent reference source/input/mapping is inapplicable or changed")
        return self


class IntentBundle(Contract):
    version: Literal["olist-native-intent-development-v1"] = "olist-native-intent-development-v1"
    audit_sha256: Sha256
    acceptance_sha256: Sha256
    cases: Annotated[tuple[IntentReference, ...], Field(min_length=1)]
    qualifies_full_service: Literal[False] = False
    frozen_for_provider: Literal[False] = False
    release_allowed: Literal[False] = False

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({c.case_id for c in self.cases}) != len(self.cases) or len(
            {c.frame.source_ordinal for c in self.cases}
        ) != len(self.cases):
            raise ValueError("duplicate native intent reference")
        return self


def prepare(
    audit: UtteranceAudit,
    acceptance: IntentMethodAcceptance,
    ordinals: tuple[int, ...],
    *,
    expected_audit_sha256: str,
    expected_acceptance_sha256: str,
) -> IntentBundle:
    """Use a recomputed audit plus separately pinned owner record; no identity authentication."""
    audit = UtteranceAudit.model_validate_json(audit.canonical_json())
    acceptance = IntentMethodAcceptance.model_validate_json(acceptance.canonical_json())
    if (
        pin(audit) != expected_audit_sha256
        or pin(acceptance) != expected_acceptance_sha256
        or acceptance.source_revision != audit.source_revision
        or acceptance.source_csv_sha256 != audit.source_csv_sha256
        or acceptance.mapping_sha256 != audit.mapping_sha256
        or acceptance.mapping_sha256 != mapping_pin()
        or not ordinals
        or len(set(ordinals)) != len(ordinals)
        or any(type(i) is not int or not 1 <= i <= len(audit.frames) for i in ordinals)
    ):
        raise ValueError("accepted method/source/mapping/selection binding differs")
    cases = []
    for ordinal in ordinals:
        frame = audit.frames[ordinal - 1]
        if frame.proposed_route is None:
            raise ValueError("unmapped native intent cannot become a reference")
        cases.append(
            IntentReference(
                case_id=sha256(("olist-native-intent|" + pin(frame)).encode()),
                frame=frame,
                input=frame.input,
                expected_intent=frame.proposed_route,
            )
        )
    return IntentBundle(
        audit_sha256=pin(audit), acceptance_sha256=pin(acceptance), cases=tuple(cases)
    )


Variant = Literal["candidate", "rules", "always-review"]
Intent = Literal["refund", "status", "reship", "review", "clarify", "unsupported"]
VARIANTS: tuple[Variant, ...] = ("candidate", "rules", "always-review")


class IntentObservation(Contract):
    variant: Variant
    case_id: Sha256
    trial_id: NonEmpty
    input_sha256: Sha256
    observed_intent: Intent | None
    failure_code: NonEmpty | None = None

    @model_validator(mode="after")
    def complete(self) -> Self:
        if (self.observed_intent is None) != (self.failure_code is not None):
            raise ValueError("failed intent observation requires a code and no prediction")
        return self


def compare(
    bundle: IntentBundle, trial_ids: tuple[str, ...], rows: tuple[IntentObservation, ...]
) -> dict[str, object]:
    """Descriptive agreement with conditional native references; never population inference."""
    bundle = IntentBundle.model_validate_json(bundle.canonical_json())
    if not trial_ids or len(set(trial_ids)) != len(trial_ids) or any(not t for t in trial_ids):
        raise ValueError("explicit unique trial schedule required")
    expected = {(v, c.case_id, t) for v in VARIANTS for c in bundle.cases for t in trial_ids}
    lookup = {c.case_id: c for c in bundle.cases}
    observed: dict[tuple[str, str, str], IntentObservation] = {}
    for raw in rows:
        row = IntentObservation.model_validate_json(raw.canonical_json())
        key = row.variant, row.case_id, row.trial_id
        if key not in expected or key in observed:
            raise ValueError("duplicate or unscheduled intent observation")
        if row.input_sha256 != pin(lookup[row.case_id].input):
            raise ValueError("intent input projection pin differs")
        observed[key] = row
    variants = {}
    for variant in VARIANTS:
        keys = sorted(k for k in expected if k[0] == variant)
        confusions: Counter[str] = Counter()
        for key in keys:
            observation = observed.get(key)
            predicted = (
                "missing" if observation is None else observation.observed_intent or "failed"
            )
            confusions[lookup[key[1]].expected_intent + ":" + predicted] += 1
        correct = sum(
            key in observed and observed[key].observed_intent == lookup[key[1]].expected_intent
            for key in keys
        )
        variants[variant] = {
            "scheduled": len(keys),
            "observed": sum(k in observed for k in keys),
            "missing": sum(k not in observed for k in keys),
            "failed": sum(observed[k].failure_code is not None for k in keys if k in observed),
            "review_abstentions": sum(
                observed[k].observed_intent == "review" for k in keys if k in observed
            ),
            "native_reference_agreements": correct,
            "scheduled_agreement_fraction": correct / len(keys),
            "confusions": dict(sorted(confusions.items())),
            "all_repetitions_agree_cases": sum(
                all(
                    (variant, c.case_id, t) in observed
                    and observed[(variant, c.case_id, t)].observed_intent == c.expected_intent
                    for t in trial_ids
                )
                for c in bundle.cases
            ),
        }
    return {
        "version": "olist-native-intent-development-comparison-v1",
        "bundle_sha256": pin(bundle),
        "trial_ids": trial_ids,
        "scheduled": len(expected),
        "observed": len(observed),
        "missing": len(expected) - len(observed),
        "cases": len(bundle.cases),
        "normalized_text_buckets_not_independent": len(
            {c.frame.normalized_text_sha256 for c in bundle.cases}
        ),
        "variants": variants,
        "claim_scope": "exposed_development_conditional_native_intent_agreement",
        "amount_and_full_service_assessed": False,
        "population_confidence_established": False,
        "semantic_gold_validated": False,
        "qualification_met": False,
        "release_allowed": False,
    }
