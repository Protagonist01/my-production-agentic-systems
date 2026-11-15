"""Operator-only reference-payer composition over canonical synthetic SQL cases."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from typing import Annotated, Any, Literal

from agent_harness.contracts import Contract
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prior_auth.contracts import NoteInput, digest
from prior_auth.review_auth import AuthStore
from prior_auth.review_contracts import Principal, StateChanged
from prior_auth.review_store import ReviewStore, contract
from pydantic import Field

from prior_auth_intake import CaseBinding
from prior_auth_pas import PasClient, Receipt, bundle, checked_inquiry
from prior_auth_sandbox import Submission


class PayerCommand(Contract):
    expected_version: Annotated[int, Field(ge=1)]
    confirm_synthetic_exchange: Literal[True]


class PayerDesk:
    def __init__(self, store: ReviewStore, client: PasClient, bindings: tuple[CaseBinding, ...]):
        self.store, self.client = store, client
        self.bindings = {
            (b.tenant_id, b.case_id): CaseBinding.model_validate_json(b.canonical_json())
            for b in bindings
        }
        if len(self.bindings) != len(bindings) or not bindings:
            raise ValueError("unique trusted case bindings required")
        with closing(client.connect()) as c, c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS pas_desk_inquiries(tenant TEXT, request TEXT, "
                "pin TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(tenant,request))"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS pas_desk_packets(tenant TEXT, case_id TEXT, "
                "version INTEGER, request TEXT, pin TEXT NOT NULL, PRIMARY KEY(tenant,request))"
            )

    @contextmanager
    def current(
        self, user: Principal, case_id: str, version: int, *, write: bool
    ) -> Iterator[tuple[Submission, NoteInput]]:
        user.require(case_id, write=write)
        binding = self.bindings.get((user.tenant_id, case_id))
        if binding is None:
            raise PermissionError("reference payer not configured for this case")
        # Keep the canonical row locked through the bounded exchange. A supplement
        # cannot change the packet between verification and POST. No model invokes it.
        with self.store.transaction() as c:
            row = self.store._row(c, user.tenant_id, case_id)
            saved = c.execute(
                "SELECT binding_sha256 FROM prior_auth_intake.bindings "
                "WHERE tenant_id=%s AND case_id=%s",
                (user.tenant_id, case_id),
            ).fetchone()
            if (
                row["version"] != version
                or not saved
                or saved["binding_sha256"] != digest(binding.canonical_json())
            ):
                raise StateChanged("canonical version or trusted binding differs")
            note = contract(row["note"], NoteInput)
            if note.provenance != "invented" or note.service_date != binding.service_date:
                raise PermissionError("current invented case required")
            identity = digest(
                json.dumps([user.tenant_id, case_id, version, note.note_sha256, note.policy_sha256])
            )
            request = Submission(
                request_id="desk-" + identity,
                case=binding,
                case_version=version,
                note_sha256=note.note_sha256,
                policy_sha256=note.policy_sha256,
            )
            yield request, note

    def saved(self, user: Principal, request: Submission) -> dict[str, Any]:
        pin = digest(request.canonical_json())
        with closing(self.client.connect()) as c:
            row = c.execute(
                "SELECT pin,receipt FROM pas_attempts WHERE tenant=? AND request=?",
                (user.tenant_id, request.request_id),
            ).fetchone()
            inquiry = c.execute(
                "SELECT pin,receipt FROM pas_desk_inquiries WHERE tenant=? AND request=?",
                (user.tenant_id, request.request_id),
            ).fetchone()
            previous = c.execute(
                "SELECT p.request,a.receipt FROM pas_desk_packets p LEFT JOIN pas_attempts a "
                "ON a.tenant=p.tenant AND a.request=p.request WHERE p.tenant=? AND p.case_id=?",
                (user.tenant_id, request.case.case_id),
            ).fetchall()
        if any(r and r[0] != pin for r in (row, inquiry)):
            raise StateChanged("payer journal binding differs")
        return {
            "configured": True,
            "source": "owned-hl7-reference-payer",
            "case_version": request.case_version,
            "request_sha256": pin,
            "submission": Receipt.model_validate_json(row[1]).model_dump(mode="json")
            if row
            else None,
            "inquiry": json.loads(inquiry[1]) if inquiry else None,
            "clinical_validation": False,
            "note_exported": False,
            "blocked_prior_unknown": any(
                (r[1] is None or Receipt.model_validate_json(r[1]).state != "received")
                and (r[0] != request.request_id or r[1] is None)
                for r in previous
            ),
        }

    def status(self, user: Principal, case_id: str, version: int) -> dict[str, Any]:
        user.require(case_id)
        if (user.tenant_id, case_id) not in self.bindings:
            return {"configured": False}
        with self.current(user, case_id, version, write=False) as (request, _):
            return self.saved(user, request)

    def exchange(
        self, user: Principal, case_id: str, command: PayerCommand, *, inquire: bool
    ) -> dict[str, Any]:
        command = PayerCommand.model_validate_json(command.canonical_json())
        with self.current(user, case_id, command.expected_version, write=True) as (request, note):
            if not inquire:
                if self.saved(user, request)["blocked_prior_unknown"]:
                    raise StateChanged("an earlier packet needs reconciliation; do not resubmit")
                with closing(self.client.connect()) as c, c:
                    c.execute(
                        "INSERT INTO pas_desk_packets VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (
                            user.tenant_id,
                            case_id,
                            command.expected_version,
                            request.request_id,
                            digest(request.canonical_json()),
                        ),
                    )
                self.client.submit(user, request, note, current_version=command.expected_version)
            else:
                saved = self.saved(user, request)
                if saved["submission"] is None:
                    raise StateChanged("submit explicitly before inquiry")
                try:
                    result = checked_inquiry(
                        self.client.transport("POST", "Claim/$inquire", bundle(request, note)),
                        digest(request.canonical_json()),
                        request,
                        self.client.transport,
                    ).model_dump(mode="json")
                except Exception:
                    result = {"state": "unavailable", "clinical_validation": False}
                with closing(self.client.connect()) as c, c:
                    c.execute(
                        "INSERT INTO pas_desk_inquiries VALUES(?,?,?,?) "
                        "ON CONFLICT(tenant,request) DO UPDATE SET receipt=excluded.receipt "
                        "WHERE pas_desk_inquiries.pin=excluded.pin",
                        (
                            user.tenant_id,
                            request.request_id,
                            digest(request.canonical_json()),
                            json.dumps(result, sort_keys=True),
                        ),
                    )
            return self.saved(user, request)


def install(app: FastAPI, desk: PayerDesk, auth: AuthStore, *, origin: str, trial_id: str) -> None:
    suffix = hashlib.sha256(trial_id.encode()).hexdigest()[:12]

    @app.exception_handler(sqlite3.Error)
    async def journal_unavailable(request: Request, error: sqlite3.Error) -> JSONResponse:
        return JSONResponse(
            {"error": "payer_journal_unavailable_inspect_before_retry"}, status_code=503
        )

    def actor(request: Request) -> Principal:
        # Same exact cookie and origin/CSRF requirements as the inherited review API.
        from urllib.parse import urlsplit

        if (
            request.headers.get("origin") != origin
            or request.headers.get("host") != urlsplit(origin).netloc
            or request.headers.get("sec-fetch-site") not in (None, "same-origin", "none")
            or not request.headers.get("x-csrf-token")
        ):
            raise PermissionError("same-origin verified operator action required")
        return auth.authenticate(
            request.cookies.get("prior_auth_session_" + suffix, ""), request.headers["x-csrf-token"]
        )

    @app.post("/api/cases/{case_id}/payer/submit")
    def submit(case_id: str, payload: PayerCommand, request: Request) -> JSONResponse:
        return JSONResponse(desk.exchange(actor(request), case_id, payload, inquire=False))

    @app.post("/api/cases/{case_id}/payer/inquire")
    def inquire(case_id: str, payload: PayerCommand, request: Request) -> JSONResponse:
        return JSONResponse(desk.exchange(actor(request), case_id, payload, inquire=True))
