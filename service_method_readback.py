"""Separate control-plane verifier for pinned Olist development service baselines.

Keep this outside the frozen runtime packages. Read actual artifacts before producing
claim pins; serialized reports and submitted claims are never verification inputs.
No scope authority, semantic qualification or release permission is created here.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, Literal

from agent_harness.cases import LoadedManifest
from agent_harness.contracts import Contract, ModelRequest, NonEmpty
from agent_harness.release_contracts import Sha256, pin, sha256
from olist_support.evidence_methods import FieldName, MethodCase, MethodClaim, MethodScope
from olist_support.service_h10 import private_scenario, read_comparator
from pydantic import AwareDatetime, Field

# These are existing scorer fields and accepted method parts, not new metrics.
PARTS: Final = {
    "truthful_confirmation": ("message_consistency", "fixed_template"),
    "exact_state": ("authoritative_state", "state_observation"),
    "duplicate_delivery": ("repeated_effect", "state_observation"),
}


class ObjectiveFact(Contract):
    case_id: Sha256
    field: Literal["truthful_confirmation", "exact_state", "duplicate_delivery", "recovery"]
    trial_ids: Annotated[tuple[NonEmpty, ...], Field(min_length=3, max_length=3)]
    row_sha256: Annotated[tuple[Sha256, ...], Field(min_length=3, max_length=3)]
    values: Annotated[tuple[bool | None, ...], Field(min_length=3, max_length=3)]

    @property
    def disposition(self) -> Literal["supported", "contradicted", "unresolved"]:
        if False in self.values:
            return "contradicted"
        return "supported" if all(v is True for v in self.values) else "unresolved"


class ObjectiveReadback(Contract):
    version: Literal["olist-development-objective-readback-v1"] = (
        "olist-development-objective-readback-v1"
    )
    baseline_sha256: Sha256
    candidate_sha256: Sha256
    manifest_sha256: Sha256
    evaluator_sha256: Sha256
    started_at: AwareDatetime
    finished_at: AwareDatetime
    checked_at: AwareDatetime
    cases: tuple[MethodCase, ...]
    facts: tuple[ObjectiveFact, ...]
    scope: Literal["development_only"] = "development_only"
    recovery_scope: Literal["response_loss_only_not_process_death"] = (
        "response_loss_only_not_process_death"
    )
    semantic_reference_authenticated: Literal[False] = False
    independent_groups_authenticated: Literal[False] = False
    release_allowed: Literal[False] = False


@dataclass(frozen=True)
class VerifiedObjectives:
    readback: ObjectiveReadback
    claims: tuple[MethodClaim, ...]

    @property
    def verified_claim_pins(self) -> frozenset[str]:
        # Contradictions retain their hash too; audit_methods separately rejects them.
        return frozenset(pin(c) for c in self.claims)


def _claims(
    report: ObjectiveReadback,
    scopes: tuple[MethodScope, ...],
    trusted_scope_pins: frozenset[str],
) -> tuple[MethodClaim, ...]:
    cases = {(c.input_sha256, c.reference_sha256): c for c in report.cases}
    facts: dict[tuple[str, str], ObjectiveFact] = {(f.case_id, f.field): f for f in report.facts}
    claims = []
    seen: set[tuple[str, str]] = set()
    for supplied in scopes:
        scope = MethodScope.model_validate_json(supplied.canonical_json())
        if pin(scope) not in trusted_scope_pins:
            raise ValueError("scope must be separately trusted before domain verification")
        case = cases.get((scope.input_sha256, scope.reference_sha256))
        if case is None or scope.field not in PARTS:
            raise ValueError("scope is not an available objective case/part")
        part, method = PARTS[scope.field]
        if (
            scope.permitted_use != "development"
            or scope.part != part
            or scope.method != method
            or scope.source_sha256 != report.baseline_sha256
            or scope.evaluator_sha256 != report.evaluator_sha256
            or not set(case.slices).issubset(scope.slices)
            or not scope.granted_at <= report.started_at <= report.finished_at
            or not report.finished_at <= report.checked_at < scope.expires_at
        ):
            raise ValueError("scope differs from development objective evidence or interval")
        key = case.case_id, scope.field
        if key in seen:
            raise ValueError("duplicate objective scope cannot vote away contradiction")
        seen.add(key)
        fact = facts[key]
        claims.append(
            MethodClaim(
                case_id=case.case_id,
                field=scope.field,
                part=part,
                scope_sha256=pin(scope),
                input_sha256=case.input_sha256,
                reference_sha256=case.reference_sha256,
                source_sha256=scope.source_sha256,
                evaluator_sha256=scope.evaluator_sha256,
                evidence_sha256=sha256((pin(report) + pin(fact)).encode()),
                observed_at=report.finished_at,
                disposition=fact.disposition,
            )
        )
    return tuple(sorted(claims, key=lambda c: (c.case_id, c.field, c.part)))


def read_method_evidence(
    root: Path,
    loaded: LoadedManifest,
    *,
    route: ModelRequest,
    selected: Literal["rules", "always-review"],
    evidence_sha256: str,
    candidate_sha256: str,
    checked_at: AwareDatetime,
    scopes: tuple[MethodScope, ...] = (),
    trusted_scope_pins: frozenset[str] = frozenset(),
) -> VerifiedObjectives:
    """Recheck externally pinned artifacts, then derive only admitted objective claims.

    Expected pins and scope authority are control-plane inputs. Do not obtain them from
    an untrusted submission. This accepts neither a preverified object nor a proof bundle.
    The unchanged domain reader still verifies the complete frozen runtime inventory.
    """
    if checked_at.tzinfo is None:
        raise ValueError("an aware readback clock is required")
    verified = read_comparator(
        root,
        loaded,
        route=route,
        selected=selected,
        evidence_sha256=evidence_sha256,
        candidate_sha256=candidate_sha256,
    )
    manifest, batch = verified.manifest, verified.batch
    if manifest.finished_at > checked_at or manifest.started_at > manifest.finished_at:
        raise ValueError("capture interval is in the future or reversed")
    if any(e.split != "development" for e in loaded.manifest.entries):
        raise ValueError("this reader supports development evidence only")
    trial_ids = batch.schedule.trial_ids
    if len(trial_ids) != 3 or len(set(trial_ids)) != 3:
        raise ValueError("three distinct scheduled repetitions required")
    rows = {(r.task.context.case_id, r.task.context.trial_id): r for r in batch.rows}
    expected = {(c, t) for c in loaded.manifest.case_ids for t in trial_ids}
    if len(rows) != len(batch.rows) or set(rows) != expected:
        raise ValueError("objective readback requires the exact complete trial schedule")
    cases, facts = [], []
    for entry in loaded.manifest.entries:
        scenario = private_scenario(entry.case)
        label = scenario.reference
        cases.append(
            MethodCase(
                case_id=entry.case.case_id,
                input_sha256=sha256(entry.case.input.request.encode()),
                reference_sha256=pin(scenario),
                source_keys=(
                    "reference:" + label.case_id,
                    "group:" + label.group_id,
                    "language:" + label.language_family,
                    "order:"
                    + sha256(json.dumps([label.order.tenant_id, label.order.order_id]).encode()),
                    "normalized_text:"
                    + sha256(" ".join(label.reference.text.casefold().split()).encode()),
                ),
                slices=entry.case.slices,
                split="development",
            )
        )
        selected_rows = [rows[entry.case.case_id, trial] for trial in trial_ids]
        score_maps = []
        for row in selected_rows:
            if row.errors or row.report is None:
                raise ValueError("objective readback cannot admit missing or failed trials")
            scores = row.report.report.scores
            if len({s.metric for s in scores}) != len(scores):
                raise ValueError("duplicate objective score")
            score_maps.append({s.metric: s for s in scores})
        fields: tuple[FieldName, ...] = (
            "truthful_confirmation",
            "exact_state",
            "duplicate_delivery",
            *(("recovery",) if label.recovery_required else ()),
        )
        for field in fields:
            values: list[bool | None] = []
            for metrics in score_maps:
                metric = metrics.get(field)
                if metric is None or not metric.eligible or metric.failure is not None:
                    values.append(None)
                elif metric.value in (0.0, 1.0):
                    values.append(metric.value == 1.0)
                else:
                    raise ValueError("objective metric must be boolean or explicitly unknown")
            facts.append(
                ObjectiveFact.model_validate(
                    {
                        "case_id": entry.case.case_id,
                        "field": field,
                        "trial_ids": trial_ids,
                        "row_sha256": tuple(pin(r) for r in selected_rows),
                        "values": tuple(values),
                    }
                )
            )
    # The separate adapter and recorded domain scorer are both bound, not the path alone.
    evaluator = sha256(Path(__file__).read_bytes() + manifest.candidate.scorer_sha256.encode())
    report = ObjectiveReadback(
        baseline_sha256=pin(manifest),
        candidate_sha256=pin(manifest.candidate),
        manifest_sha256=loaded.pin.sha256,
        evaluator_sha256=evaluator,
        started_at=manifest.started_at,
        finished_at=manifest.finished_at,
        checked_at=checked_at,
        cases=tuple(cases),
        facts=tuple(facts),
    )
    return VerifiedObjectives(report, _claims(report, scopes, trusted_scope_pins))
