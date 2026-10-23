"""Private fresh experiment contracts and complete state-based comparison; no release approval."""

import re
from collections import Counter
from decimal import Decimal
from typing import Annotated, Literal, Self

from agent_harness.admission import GEMINI_TOKEN_CEILING
from agent_harness.contracts import Contract, RunContext
from agent_harness.release_contracts import AttemptReceipt, CandidateSpec
from pydantic import Field, model_validator

from olist_support.policy_cases import Digest, PolicyCases, digest
from olist_support.release import Observation, ScheduledTrial, score
from olist_support.workflow import IntentDecision, IntentPlan, WorkflowRequest

Mode = Literal["gemini", "rules", "review"]
MODES: tuple[Mode, ...] = ("rules", "review", "gemini")


class TextInput(Contract):
    case_id: Digest
    text: Annotated[str, Field(min_length=1, max_length=8192)]


class ExperimentPlan(Contract):
    version: Literal["olist-fresh-plan-v1"] = "olist-fresh-plan-v1"
    cases_sha256: Digest
    inputs_sha256: Digest
    candidate: CandidateSpec
    trial_ids: tuple[str, str, str]
    tasks: tuple[ScheduledTrial, ...]
    max_live_calls: Literal[36] = 36
    label_status: Literal["ai_provisional"] = "ai_provisional"

    @model_validator(mode="after")
    def schedule(self) -> Self:
        if len(set(self.trial_ids)) != 3 or any(not t for t in self.trial_ids):
            raise ValueError("three distinct nonempty trials required")
        keys = {t.key for t in self.tasks}
        cases = {t.case_id for t in self.tasks}
        if (
            not cases
            or len(keys) != len(self.tasks)
            or keys != {(c, t) for c in cases for t in self.trial_ids}
        ):
            raise ValueError("whole population requires exactly three trials")
        if len(self.tasks) > self.max_live_calls:
            raise ValueError("fresh pilot exceeds approved live call cap")
        if len({t.run_id for t in self.tasks}) != len(self.tasks):
            raise ValueError("isolated trials require unique run identities")
        if self.candidate.execution.max_attempts != 1:
            raise ValueError("first pilot permits one provider attempt per trial")
        budget = self.candidate.recording_budget
        if (
            not len(self.tasks) <= budget.max_model_calls <= self.max_live_calls
            or budget.max_tokens < len(self.tasks) * GEMINI_TOKEN_CEILING
            or budget.max_cost != 0
            or budget.cost_currency != "USD"
        ):
            raise ValueError("recording budget must reserve every Free-only scheduled attempt")
        return self


def validate_population(
    plan: ExperimentPlan, cases: PolicyCases, inputs: tuple[TextInput, ...]
) -> None:
    if digest(cases.canonical_json()) != plan.cases_sha256:
        raise ValueError("case pin mismatch")
    ids = {e.input.case_id for e in cases.entries}
    if {t.case_id for t in plan.tasks} != ids or {r.case_id for r in inputs} != ids:
        raise ValueError("experiment population differs")
    if len(inputs) != len(ids):
        raise ValueError("duplicate input identity")
    canonical = "\n".join(r.canonical_json() for r in sorted(inputs, key=lambda r: r.case_id))
    if digest(canonical) != plan.inputs_sha256:
        raise ValueError("input pin mismatch")
    lookup = {e.input.case_id: e for e in cases.entries}
    if any(r.text != lookup[r.case_id].input.request.message for r in inputs):
        raise ValueError("provider text differs from reviewed request")


class RulesPlanner:
    """Declared template-aware baseline; no labels, source facts or provider access."""

    def plan(self, context: RunContext, request: WorkflowRequest) -> IntentDecision:
        primary = request.text.split(" Untrusted quoted note:", 1)[0]
        if primary.startswith("Primary request: please arrange a replacement shipment"):
            return IntentDecision(plan=IntentPlan(intent="reship"))
        if primary.startswith("Primary request: please refund the full paid amount"):
            return IntentDecision(plan=IntentPlan(intent="refund"))
        match = re.fullmatch(
            r"Primary request: please refund exactly ([0-9]+\.[0-9]{2}) SIM for this order, "
            r"not the full paid amount\.",
            primary,
        )
        if match:
            amount = int(Decimal(match.group(1)) * 100)
            if amount <= 2**63 - 1:
                return IntentDecision(plan=IntentPlan(intent="refund", requested_minor=amount))
        return IntentDecision(plan=IntentPlan(intent="review"))


class FreshRow(Contract):
    case_id: Digest
    trial_id: str
    mode: Mode
    observation: Observation | None
    decision: IntentDecision | None
    receipts: tuple[AttemptReceipt, ...] = ()
    elapsed_seconds: Annotated[float, Field(ge=0)]
    duplicate_delivery_unchanged: bool
    cleanup_ok: bool
    errors: tuple[str, ...] = ()

    @model_validator(mode="after")
    def identity(self) -> Self:
        if self.observation and (self.case_id, self.trial_id) != (
            self.observation.case_id,
            self.observation.trial_id,
        ):
            raise ValueError("observation scope mismatch")
        if self.mode != "gemini" and self.receipts:
            raise ValueError("deterministic baseline cannot claim provider receipts")
        if len(self.receipts) > 1:
            raise ValueError("pilot row exceeded its single-attempt bound")
        if (
            self.mode == "gemini"
            and self.decision is not None
            and self.decision.failure_code is None
            and not self.receipts
        ):
            raise ValueError("successful model decision requires a fresh attempt receipt")
        if (not self.cleanup_ok or not self.duplicate_delivery_unchanged) and not self.errors:
            raise ValueError("incomplete cleanup/recovery needs explicit error accounting")
        return self


def experiment_report(
    plan: ExperimentPlan,
    cases: PolicyCases,
    inputs: tuple[TextInput, ...],
    rows: tuple[FreshRow, ...],
) -> dict[str, object]:
    validate_population(plan, cases, inputs)
    keys = [(r.mode, r.case_id, r.trial_id) for r in rows]
    expected = {(m, t.case_id, t.trial_id) for m in MODES for t in plan.tasks}
    if len(set(keys)) != len(keys) or not set(keys).issubset(expected):
        raise ValueError("duplicate or unexpected experiment row")
    lookup = {(r.mode, r.case_id, r.trial_id): r for r in rows}
    nonces = [p.nonce for r in rows for p in r.receipts]
    if len(set(nonces)) != len(nonces):
        raise ValueError("attempt receipt was reused")
    executions = {p.execution_id for r in rows for p in r.receipts}
    if len(executions) > 1:
        raise ValueError("attempt receipts belong to different executions")
    texts = {r.case_id: r.text for r in inputs}
    by_case = {e.input.case_id: e for e in cases.entries}
    result: dict[str, object] = {
        "version": "olist-fresh-comparison-v1",
        "release_allowed": False,
        "label_status": "ai_provisional",
        "human_validation": False,
        "candidate_sha256": digest(plan.candidate.canonical_json()),
        "plan_sha256": digest(plan.canonical_json()),
        "blockers": [
            "independent_label_review_pending",
            "baseline_and_threshold_approval_pending",
            "representative_production_validation_pending",
        ],
    }
    modes: dict[str, object] = {}
    for mode in MODES:
        splits: dict[str, object] = {}
        for split in ("development", "regression", "holdout", "all"):
            tasks = [t for t in plan.tasks if split == "all" or by_case[t.case_id].split == split]
            categories: Counter[str] = Counter()
            eligible = completed = reviews = required = required_correct = 0
            intent_correct = failures = calls = input_tokens = output_tokens = unknown = 0
            cost_unknown = duplicate_ok = cleanup_ok = 0
            elapsed: list[float] = []
            all_correct: dict[str, list[bool]] = {}
            for task in tasks:
                case = by_case[task.case_id]
                is_eligible = case.expected.action == "propose_full_refund"
                eligible += is_eligible
                required += not is_eligible
                row = lookup.get((mode, *task.key))
                category = "missing"
                if row:
                    elapsed.append(row.elapsed_seconds)
                    duplicate_ok += row.duplicate_delivery_unchanged
                    cleanup_ok += row.cleanup_ok
                    if row.observation:
                        category = score(case, task, row.observation).category
                        reviews += row.observation.outcome == "review_required"
                    else:
                        category = "unresolved"
                    if row.errors and category != "unsafe":
                        category = "unresolved"
                    failures += bool(row.errors or (row.decision and row.decision.failure_code))
                    if row.decision:
                        intent_correct += (
                            row.decision.failure_code is None
                            and row.decision.plan.intent == case.input.request.intent
                            and row.decision.plan.requested_minor
                            == case.input.request.requested_minor
                        )
                    for receipt in row.receipts:
                        if receipt.exchange.context.run_id != task.run_id:
                            raise ValueError("receipt run identity differs")
                        if receipt.exchange.context.mode != "fresh_candidate":
                            raise ValueError("receipt is not a fresh candidate attempt")
                        c, request = receipt.exchange.context, receipt.exchange.request
                        if (
                            c.case_id != task.case_id
                            or c.trial_id != task.trial_id
                            or c.tenant_id != task.grant.tenant_id
                            or c.versions.candidate != plan.candidate.candidate
                            or c.versions.code_revision != plan.candidate.code_revision
                            or c.versions.environment_lock != plan.candidate.environment_lock
                            or request.provider != "google-gemini-developer-api"
                            or request.model != "gemini-3.5-flash-lite"
                            or request.tools
                            or len(request.messages) != 2
                            or request.messages[1].content != texts[task.case_id]
                        ):
                            raise ValueError("receipt differs from pinned scope/provider input")
                        u = receipt.exchange.response.usage
                        calls += u.model_calls
                        input_tokens += u.input_tokens or 0
                        output_tokens += u.output_tokens or 0
                        unknown += u.input_tokens is None or u.output_tokens is None
                        cost_unknown += u.cost is None
                completed += is_eligible and category == "correct"
                required_correct += not is_eligible and category == "correct"
                categories[category] += 1
                all_correct.setdefault(task.case_id, []).append(category == "correct")
            n = len(tasks)
            splits[split] = {
                "scheduled_trials": n,
                "categories": dict(categories),
                "eligible_trials": eligible,
                "eligible_completed": completed,
                "eligible_completion": completed / eligible if eligible else None,
                "required_review_trials": required,
                "required_review_correct": required_correct,
                "review_trials": reviews,
                "review_fraction": reviews / n if n else None,
                "intent_exact_correct": intent_correct,
                "failed_trials": failures,
                "all_three_correct_cases": sum(all(v) for v in all_correct.values()),
                "case_denominator": len(all_correct),
                "duplicate_delivery_unchanged": duplicate_ok,
                "cleanup_ok": cleanup_ok,
                "reported_model_calls": calls,
                "observed_input_tokens": input_tokens,
                "observed_output_tokens": output_tokens,
                "usage_unknown_attempts": unknown,
                "cost_unknown_attempts": cost_unknown,
                "measured_trial_seconds": sum(elapsed),
                "max_trial_seconds": max(elapsed) if elapsed else None,
                "cost_per_safe_completion": None,
            }
        modes[mode] = splits
    result["modes"] = modes
    return result
