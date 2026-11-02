"""Durable scoped cases and exact-action decisions on the existing SIM backend."""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from agent_harness.contracts import RunContext
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from olist_support.business import BusinessStore, ConnectionFactory, FaultHook, identity_hash, sha
from olist_support.business_contracts import BusinessReview, RefundCommand, RefundReceipt
from olist_support.console_contracts import CaseRecord, Decision, Principal, Submission
from olist_support.policy import POLICY_VERSION, SupportRequest, propose
from olist_support.routing_contracts import RoutingPlan
from olist_support.workflow import (
    FixedPlanner,
    IntentDecision,
    IntentPlan,
    Planner,
    SupportWorkflow,
    WorkflowRequest,
    WorkflowResult,
)
from olist_support.workflow_postgres import saver

MODEL_SERVICE_CANDIDATE = "olist-customer-confirmed-routing-v1"
MODEL_SERVICE_AGENT = "olist-customer-confirmed-routing-sim"


class CaseStore:
    def __init__(self, connect: ConnectionFactory, *, planner: Planner | None = None) -> None:
        self.connect = connect
        self.business = BusinessStore(connect)
        # Trusted composition only; never selectable through an HTTP request body.
        self.planner = planner

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        with self.connect() as connection:
            connection.autocommit = True
            connection.row_factory = dict_row
            connection.execute("SET statement_timeout=5000")
            connection.execute("SET lock_timeout=2000")
            yield connection

    @staticmethod
    def event(
        connection: Connection[Any], case: CaseRecord, actor: str, kind: str, **detail: Any
    ) -> None:
        connection.execute(
            "INSERT INTO olist_app.events VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                uuid.uuid4().hex,
                case.tenant_id,
                case.case_id,
                actor,
                kind,
                datetime.now(UTC),
                Jsonb(detail),
            ),
        )

    @staticmethod
    def load(
        connection: Connection[Any], principal: Principal, case_id: str, *, lock: bool = False
    ) -> CaseRecord:
        row = connection.execute(
            "SELECT document FROM olist_app.cases WHERE tenant_id=%s AND case_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (principal.tenant_id, case_id),
        ).fetchone()
        if row is None:
            raise LookupError("case unavailable")
        case = CaseRecord.model_validate_json(json.dumps(row["document"]))
        principal.grant(case.order_id)
        return case

    @staticmethod
    def save(connection: Connection[Any], case: CaseRecord) -> None:
        case = CaseRecord.model_validate_json(case.canonical_json())
        result = connection.execute(
            (
                "UPDATE olist_app.cases SET version=%s,status=%s,document=%s WHERE "
                "tenant_id=%s AND case_id=%s AND version=%s"
            ),
            (
                case.version,
                case.status,
                Jsonb(case.model_dump(mode="json")),
                case.tenant_id,
                case.case_id,
                case.version - 1,
            ),
        )
        if result.rowcount != 1:
            raise BusinessReview("case_version_changed")

    def detail(self, principal: Principal, case_id: str) -> tuple[CaseRecord, list[dict[str, Any]]]:
        with self.connection() as connection:
            case = self.load(connection, principal, case_id)
            events = connection.execute(
                (
                    "SELECT actor_id,kind,at,detail FROM olist_app.events WHERE "
                    "tenant_id=%s AND case_id=%s ORDER BY at,event_id"
                ),
                (principal.tenant_id, case_id),
            ).fetchall()
        if case.result and case.result.receipt:
            if not self.business.verify_receipt(
                principal.grant(case.order_id), case.result.receipt
            ):
                raise BusinessReview("saved_completion_not_verified")
        return case, events

    def listing(self, principal: Principal) -> list[CaseRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                (
                    "SELECT document FROM olist_app.cases WHERE tenant_id=%s AND "
                    "order_id=ANY(%s) ORDER BY document->>'updated_at' DESC LIMIT 100"
                ),
                (principal.tenant_id, list(principal.order_ids)),
            ).fetchall()
        cases = [CaseRecord.model_validate_json(json.dumps(row["document"])) for row in rows]
        for case in cases:
            if case.result and case.result.receipt:
                if not self.business.verify_receipt(
                    principal.grant(case.order_id), case.result.receipt
                ):
                    raise BusinessReview("listed_completion_not_verified")
        return cases

    def _snapshot(self, principal: Principal, case: CaseRecord) -> dict[str, Any]:
        view, facts, version = self.business.order(
            principal.grant(case.order_id), case.tenant_id, case.order_id
        )
        intent: str = case.request.intent
        requested_minor: int | None = None
        decision = case.intent_decision
        if case.intent_source == "planner":
            intent = decision.plan.intent if decision and not decision.failure_code else "review"
            requested_minor = decision.plan.requested_minor if decision else None
        policy_intent = (
            intent
            if case.intent_source == "planner"
            else "reship"
            if case.request.intent == "reship"
            else "refund"
        )
        proposal = (
            propose(
                view,
                SupportRequest(
                    intent="reship" if policy_intent == "reship" else "refund",
                    message=case.request.text,
                    requested_minor=requested_minor,
                ),
                facts,
            )
            if policy_intent in ("refund", "reship")
            else None
        )
        record_pin = identity_hash(
            "approval-record",
            view.canonical_json(),
            facts.canonical_json() if facts else "null",
            str(version),
        )
        command = None
        if (
            intent == "refund"
            and proposal is not None
            and proposal.action == "propose_full_refund"
            and proposal.amount_minor is not None
        ):
            command = RefundCommand(
                tenant_id=case.tenant_id,
                order_id=case.order_id,
                business_operation_id=sha("olist-full-refund-v1|" + case.context.business_event_id),
                amount_minor=proposal.amount_minor,
                expected_version=version,
            )
        digest = (
            identity_hash(
                "approval-action",
                command.canonical_json(),
                record_pin,
                POLICY_VERSION,
                case.submitted_actor,
            )
            if command
            else None
        )
        if digest and case.intent_source == "planner":
            if decision is None:
                raise BusinessReview("saved_planner_decision_missing")
            digest = identity_hash(
                "planner-confirmed-action-v1", digest, decision.plan.canonical_json()
            )
        return {
            "evidence": view,
            "confirmation": facts,
            "proposal": proposal,
            "command": command,
            "record_pin": record_pin,
            "action_digest": digest,
            "approved_by": None,
            "approval_version": None,
        }

    def submit(
        self,
        principal: Principal,
        request: Submission,
        context: RunContext,
        *,
        run_limit_minor: int,
    ) -> CaseRecord:
        principal.require("operator")
        principal.grant(request.order_id)
        request = Submission.model_validate_json(request.canonical_json())
        if context.tenant_id != principal.tenant_id or context.versions.policy != POLICY_VERSION:
            raise PermissionError("context scope/policy mismatch")
        source: Literal["operator", "planner"] = (
            "planner" if self.planner is not None else "operator"
        )
        if source == "planner" and (
            context.agent_id != MODEL_SERVICE_AGENT
            or context.versions.candidate != MODEL_SERVICE_CANDIDATE
        ):
            raise PermissionError("explicit customer-confirmed routing candidate required")
        case_id = identity_hash(
            "console-case", principal.tenant_id, principal.actor_id, request.event_key
        )
        context = context.model_copy(update={"business_event_id": case_id, "case_id": case_id})
        pin = identity_hash("console-request", request.canonical_json(), principal.actor_id)
        if source == "planner":
            pin = identity_hash("console-planner-request-v1", pin, MODEL_SERVICE_CANDIDATE)
        now = datetime.now(UTC)
        initial = CaseRecord(
            case_id=case_id,
            tenant_id=principal.tenant_id,
            order_id=request.order_id,
            submitted_actor=principal.actor_id,
            status="processing",
            version=0,
            request=request,
            context=context,
            created_at=now,
            updated_at=now,
            intent_source=source,
        )
        with self.connection() as connection:
            with connection.transaction():
                row = connection.execute(
                    (
                        "INSERT INTO olist_app.cases "
                        "VALUES(%s,%s,%s,%s,%s,0,'processing',%s) ON CONFLICT DO "
                        "NOTHING RETURNING case_id"
                    ),
                    (
                        principal.tenant_id,
                        case_id,
                        pin,
                        principal.actor_id,
                        request.order_id,
                        Jsonb(initial.model_dump(mode="json")),
                    ),
                ).fetchone()
                old = connection.execute(
                    "SELECT request_hash FROM olist_app.cases WHERE tenant_id=%s AND case_id=%s",
                    (principal.tenant_id, case_id),
                ).fetchone()
                if old is None or old["request_hash"] != pin:
                    raise BusinessReview("event_payload_changed")
                if row:
                    self.event(connection, initial, principal.actor_id, "submitted")
        return self.run_request(principal, case_id, run_limit_minor=run_limit_minor)

    def run_request(
        self, principal: Principal, case_id: str, *, run_limit_minor: int
    ) -> CaseRecord:
        principal.require("operator")
        case, _ = self.detail(principal, case_id)
        if case.status not in ("processing", "needs_recovery"):
            return case
        if (case.intent_source == "planner") != (self.planner is not None):
            raise BusinessReview("case_planner_composition_changed")
        with self.business.session(
            principal.grant(case.order_id),
            tenant=case.tenant_id,
            order=case.order_id,
            event_id="console-run:" + case_id,
            request_pin=case.request.canonical_json(),
        ):
            case, _ = self.detail(principal, case_id)
            if case.status not in ("processing", "needs_recovery"):
                return case
            now = datetime.now(UTC)
            context = (
                case.context
                if case.intent_source == "planner"
                else case.context.model_copy(
                    update={
                        "run_id": uuid.uuid4().hex,
                        "clock": now,
                        "deadline": now + timedelta(minutes=2),
                    }
                )
            )
            intent = "review" if case.request.require_review else case.request.intent
            try:
                with saver(self.connect) as checkpoints:
                    from olist_support.customer_intent import ConfirmationRequiredStore

                    result = SupportWorkflow(
                        ConfirmationRequiredStore(self.connect),
                        self.planner
                        if self.planner is not None
                        else FixedPlanner(IntentPlan(intent=intent)),
                    ).run(
                        context,
                        WorkflowRequest(order_id=case.order_id, text=case.request.text),
                        principal.grant(case.order_id),
                        checkpoints,
                        run_limit_minor=run_limit_minor,
                    )
                    decision = None
                    if case.intent_source == "planner":
                        checkpoint = checkpoints.get_tuple(
                            {
                                "configurable": {
                                    "thread_id": identity_hash(
                                        "thread", context.tenant_id, context.business_event_id
                                    )
                                }
                            }
                        )
                        if checkpoint is None:
                            raise BusinessReview("saved_planner_checkpoint_missing")
                        decision = IntentDecision.model_validate_json(
                            json.dumps(checkpoint.checkpoint["channel_values"]["decision"])
                        )
                        if not decision.failure_code and not isinstance(decision.plan, RoutingPlan):
                            raise BusinessReview("explicit_routing_plan_required")
                        if case.request.require_review and result.outcome != "review_required":
                            result = WorkflowResult(
                                outcome="review_required",
                                reason="operator_requires_review",
                                message="This request requires review. No new refund is confirmed.",
                                usage=result.usage,
                                usage_run_id=result.usage_run_id,
                            )
                updates: dict[str, Any] = {
                    "result": result,
                    "status": "committed" if result.outcome == "refunded" else result.outcome,
                    "error_code": None,
                    "intent_decision": decision,
                }
                if result.outcome == "review_required":
                    updates.update(
                        self._snapshot(
                            principal, case.model_copy(update={"intent_decision": decision})
                        )
                    )
            except Exception:
                # The commit may already exist. Preserve recovery, never assert rollback.
                updates = {
                    "status": "needs_recovery",
                    "error_code": "request_execution_interrupted",
                }
            current = case.model_copy(
                update={**updates, "version": case.version + 1, "updated_at": datetime.now(UTC)}
            )
            with self.connection() as connection:
                with connection.transaction():
                    self.save(connection, current)
                    self.event(connection, current, principal.actor_id, current.status)
            return current

    def decide(self, principal: Principal, case_id: str, decision: Decision) -> CaseRecord:
        principal.require("reviewer")
        with self.connection() as connection:
            with connection.transaction():
                case = self.load(connection, principal, case_id, lock=True)
                if principal.actor_id == case.submitted_actor:
                    raise PermissionError("submitter cannot review own request")
                if (
                    case.status not in ("review_required", "stale")
                    or case.version != decision.expected_version
                    or case.action_digest != decision.action_digest
                ):
                    raise BusinessReview("decision_does_not_match_current_case")
                if decision.decision == "approve":
                    fresh = self._snapshot(principal, case)
                    if case.command is None or fresh["action_digest"] != case.action_digest:
                        raise BusinessReview("refund_not_eligible_or_evidence_changed")
                status = "approved" if decision.decision == "approve" else "rejected"
                current = case.model_copy(
                    update={
                        "status": status,
                        "version": case.version + 1,
                        "updated_at": datetime.now(UTC),
                        "approved_by": principal.actor_id if status == "approved" else None,
                        "approval_version": case.version + 1 if status == "approved" else None,
                    }
                )
                self.save(connection, current)
                self.event(
                    connection,
                    current,
                    principal.actor_id,
                    status,
                    action_digest=case.action_digest,
                    case_version=case.version,
                    rationale=decision.rationale,
                )
                return current

    def reevaluate(self, principal: Principal, case_id: str) -> CaseRecord:
        with self.connection() as connection:
            with connection.transaction():
                case = self.load(connection, principal, case_id, lock=True)
                if case.status not in ("review_required", "stale", "approved"):
                    raise BusinessReview("case_cannot_be_reevaluated")
                current = case.model_copy(
                    update={
                        **self._snapshot(principal, case),
                        "status": "review_required",
                        "version": case.version + 1,
                        "updated_at": datetime.now(UTC),
                        "error_code": None,
                    }
                )
                self.save(connection, current)
                self.event(
                    connection,
                    current,
                    principal.actor_id,
                    "reevaluated",
                    action_digest=current.action_digest,
                )
                return current

    def resume(
        self,
        principal: Principal,
        case_id: str,
        digest: str | None,
        *,
        run_limit_minor: int,
        fault: FaultHook | None = None,
    ) -> CaseRecord:
        principal.require("reviewer")
        case, _ = self.detail(principal, case_id)
        if case.action_digest != digest or case.approved_by != principal.actor_id:
            raise PermissionError("approval does not belong to this action/reviewer")
        if case.status == "committed":
            return case
        if case.status != "approved" or case.command is None:
            raise BusinessReview("case_is_not_approved")

        from olist_support.customer_intent import confirmation_deadline, consume

        try:
            customer_deadline = confirmation_deadline(self.connect, case)
        except BusinessReview:
            latest = self.detail(principal, case_id)[0]
            if (
                latest.status == "committed"
                and latest.action_digest == digest
                and latest.approved_by == principal.actor_id
            ):
                return latest
            raise

        def record(connection: Connection[Any], receipt: RefundReceipt) -> None:
            locked = self.load(connection, principal, case_id, lock=True)
            if locked.status == "committed" and locked.result and locked.result.receipt == receipt:
                return
            if (
                locked.status != "approved"
                or locked.action_digest != digest
                or locked.approved_by != principal.actor_id
                or locked.command != case.command
            ):
                raise BusinessReview("approval_changed_before_commit")
            # Fresh policy/version enforcement already ran under the business order lock.
            fresh = self._snapshot_pin_from_locked_order(connection, locked)
            if fresh != locked.record_pin:
                raise BusinessReview("approval_evidence_changed")
            consume(connection, locked, receipt)
            result = WorkflowResult(
                outcome="refunded",
                reason="approved_ledger_and_state_verified",
                message=(
                    "Approved refund committed in the SIM ledger: "
                    f"{receipt.amount_minor // 100}.{receipt.amount_minor % 100:02d} SIM."
                ),
                receipt=receipt,
                usage=locked.result.usage if locked.result else None,
                usage_run_id=locked.result.usage_run_id if locked.result else None,
            )
            current = locked.model_copy(
                update={
                    "status": "committed",
                    "result": result,
                    "version": locked.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            self.save(connection, current)
            self.event(
                connection,
                current,
                principal.actor_id,
                "committed",
                action_digest=digest,
                ledger_id=receipt.ledger_id,
            )

        try:
            self.business.refund(
                principal.grant(case.order_id),
                case.command,
                run_id=uuid.uuid4().hex,
                run_limit_minor=run_limit_minor,
                expires_at=min(customer_deadline, datetime.now(UTC) + timedelta(minutes=2)),
                fault=fault,
                record_commit=record,
            )
        except BusinessReview:
            with self.connection() as connection:
                with connection.transaction():
                    current = self.load(connection, principal, case_id, lock=True)
                    if current.status == "approved":
                        current = current.model_copy(
                            update={
                                "status": "stale",
                                "error_code": "approval_requires_reevaluation",
                                "version": current.version + 1,
                                "updated_at": datetime.now(UTC),
                            }
                        )
                        self.save(connection, current)
                        self.event(connection, current, principal.actor_id, "stale")
            return self.detail(principal, case_id)[0]
        return self.detail(principal, case_id)[0]

    def _snapshot_pin_from_locked_order(self, connection: Connection[Any], case: CaseRecord) -> str:
        row = connection.execute(
            "SELECT * FROM olist.orders WHERE tenant_id=%s AND order_id=%s",
            (case.tenant_id, case.order_id),
        ).fetchone()
        if row is None or case.command is None:
            raise BusinessReview("approval_order_unavailable")
        # The business write in this transaction has already advanced balance/version.
        # Reconstruct the exact pre-write snapshot solely from the locked row and command.
        original = dict(row)
        original["refunded_minor"] -= case.command.amount_minor
        original["version"] -= 1
        view, facts, version = self.business._order(original)
        return identity_hash(
            "approval-record",
            view.canonical_json(),
            facts.canonical_json() if facts else "null",
            str(version),
        )
