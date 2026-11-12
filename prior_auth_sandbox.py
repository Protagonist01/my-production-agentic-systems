"""Local synthetic payer emulator. No insurer endpoint, PHI or clinical adjudication.

An operator chooses an invented payer scenario. The model cannot select the scenario,
submit a request, or turn an assessment into a clinical approval. SQLite owns replay
receipts; this is a demo transport, not an HL7 PAS conformance implementation.
"""

import json
import sqlite3
from pathlib import Path
from typing import Annotated, Literal, get_args

from agent_harness.contracts import WireContract
from prior_auth.contracts import Digest, Id, NoteInput, digest
from prior_auth.review_contracts import Principal, StateChanged
from pydantic import Field

from prior_auth_intake import CaseBinding
from prior_auth_profiling import Profiler

PayerStatus = Literal["approved", "denied", "additional_information"]


class Submission(WireContract):
    request_id: Id
    case: CaseBinding
    case_version: Annotated[int, Field(ge=1)]
    note_sha256: Digest
    policy_sha256: Digest
    mode: Literal["synthetic-demo"] = "synthetic-demo"


class PayerResponse(WireContract):
    request_id: Id
    case_id: Id
    payer_id: Id
    case_version: Annotated[int, Field(ge=1)]
    status: PayerStatus
    source: Literal["local-synthetic-payer"] = "local-synthetic-payer"
    clinical_validation: Literal[False] = False


class SyntheticPayer:
    def __init__(self, database: Path, *, payer_id: str, scenario: PayerStatus) -> None:
        if not payer_id.startswith("demo-") or scenario not in get_args(PayerStatus):
            raise ValueError("explicit invented payer/scenario required")
        self.database, self.payer_id, self.scenario = database, payer_id, scenario
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS payer_receipts ("
                "tenant_id TEXT, request_id TEXT, payload_sha TEXT NOT NULL, "
                "response TEXT NOT NULL, PRIMARY KEY(tenant_id,request_id))"
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def submit(
        self,
        user: Principal,
        request: Submission,
        current_note: NoteInput,
        *,
        current_version: int,
        profiler: Profiler,
    ) -> PayerResponse:
        request = Submission.model_validate_json(request.canonical_json())
        current_note = NoteInput.model_validate_json(current_note.canonical_json())
        user.require(request.case.case_id, write=True)
        if user.tenant_id != request.case.tenant_id or (
            current_note.tenant_id,
            current_note.case_id,
        ) != (request.case.tenant_id, request.case.case_id):
            raise PermissionError("synthetic payer case scope differs")
        if (
            current_note.provenance != "invented"
            or request.case.payer_id != self.payer_id
            or not request.case.provider_id.startswith("demo-")
            or not request.case.plan_id.startswith("demo-")
        ):
            raise PermissionError("synthetic identities and invented note required")
        if (
            current_version != request.case_version
            or request.note_sha256 != current_note.note_sha256
            or request.policy_sha256 != current_note.policy_sha256
        ):
            raise StateChanged("submission must match current case/version/pins")
        with profiler.span("sandbox_submit"), self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT payload_sha,response FROM payer_receipts "
                "WHERE tenant_id=? AND request_id=?",
                (user.tenant_id, request.request_id),
            ).fetchone()
            pin = digest(request.canonical_json())
            if prior:
                if prior[0] != pin:
                    raise StateChanged("payer request identity reused")
                return PayerResponse.model_validate_json(prior[1])
            response = PayerResponse(
                request_id=request.request_id,
                case_id=request.case.case_id,
                payer_id=self.payer_id,
                case_version=request.case_version,
                status=self.scenario,
            )
            connection.execute(
                "INSERT INTO payer_receipts VALUES(?,?,?,?)",
                (user.tenant_id, request.request_id, pin, response.canonical_json()),
            )
            return response

    def count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM payer_receipts").fetchone()[0])


def response_preview(response: PayerResponse) -> str:
    # Never claim that our checker approved/denied treatment or contacted a real insurer.
    labels = {
        "approved": "approved",
        "denied": "denied",
        "additional_information": "requested additional information",
    }
    return (
        "DEMO: the local synthetic payer " + labels[response.status] + ". No insurer was contacted."
    )


def response_bytes(response: PayerResponse) -> bytes:
    return json.dumps(response.model_dump(mode="json"), sort_keys=True).encode()
