"""Invented-only transport to an owned, loopback HL7 Da Vinci reference payer.

An authenticated application reviewer supplies canonical state; a model never calls
this adapter. PAS processing completion is not clinical approval. A reserved POST
is never replayed automatically, including after process death or uncertain I/O.
"""

import hashlib
import http.client
import json
import re
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from agent_harness.contracts import WireContract
from prior_auth.contracts import Digest, NoteInput, digest
from prior_auth.review_contracts import Principal, StateChanged
from prior_auth.source_io import external
from pydantic import Field

from prior_auth_sandbox import Submission

RI_COMMIT = "10d40911cb90d6198aacec144b4bfc48466af2fb"
SYSTEM = "urn:production-agents:invented-pas"
REVIEW = "http://hl7.org/fhir/us/davinci-pas/StructureDefinition/extension-reviewAction"
REVIEW_CODE = "http://hl7.org/fhir/us/davinci-pas/StructureDefinition/extension-reviewActionCode"
X12 = "https://codesystem.x12.org/005010/306"
MAX_BYTES = 2_000_000


class Receipt(WireContract):
    request_sha256: Digest
    state: Literal["reserved", "received", "unknown"]
    response_sha256: Digest | None = None
    processing: Literal["complete", "queued", "partial", "error"] | None = None
    review_codes: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    failure_phase: Literal["send", "response_validation"] | None = None
    source: Literal["owned-hl7-reference-payer"] = "owned-hl7-reference-payer"
    clinical_validation: Literal[False] = False


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def identifier(value: str) -> list[dict[str, str]]:
    return [{"system": SYSTEM, "value": value}]


def bundle(request: Submission, note: NoteInput) -> dict[str, Any]:
    """No licensed service catalog or genuine patient identifiers are needed."""
    key = digest(request.canonical_json())
    claim: dict[str, Any] = {
        "resourceType": "Claim",
        "id": "demo-claim",
        "identifier": identifier(key),
        "status": "active",
        "use": "preauthorization",
        "created": "2026-11-13",
        "type": {"coding": [{"system": SYSTEM, "code": "invented-professional"}]},
        "priority": {"coding": [{"system": SYSTEM, "code": "normal"}]},
        "patient": {"reference": "Patient/demo-patient"},
        "insurer": {"reference": "Organization/demo-payer"},
        "provider": {"reference": "Organization/demo-provider"},
        "insurance": [
            {"sequence": 1, "focal": True, "coverage": {"reference": "Coverage/demo-coverage"}}
        ],
        "item": [
            {
                "sequence": 1,
                "category": {"coding": [{"system": SYSTEM, "code": "demo"}]},
                "productOrService": {"coding": [{"system": SYSTEM, "code": "invented-cpap"}]},
                "servicedDate": request.case.service_date.isoformat(),
                "locationCodeableConcept": {"coding": [{"system": SYSTEM, "code": "demo"}]},
            }
        ],
    }
    patient = {
        "resourceType": "Patient",
        "id": "demo-patient",
        "identifier": [
            {
                "system": SYSTEM,
                "value": request.case.subject_key,
                "type": {
                    "coding": [
                        {"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MB"}
                    ]
                },
            }
        ],
    }
    payer = {
        "resourceType": "Organization",
        "id": "demo-payer",
        "identifier": identifier(digest(request.case.payer_id)),
    }
    provider = {
        "resourceType": "Organization",
        "id": "demo-provider",
        "identifier": identifier(digest(request.case.provider_id)),
    }
    coverage = {
        "resourceType": "Coverage",
        "id": "demo-coverage",
        "status": "active",
        "identifier": identifier(digest(request.case.plan_id)),
        "beneficiary": {"reference": "Patient/demo-patient"},
        "payor": [{"reference": "Organization/demo-payer"}],
    }
    # The clinical note is intentionally not exported. This exercises only the
    # invented request/status protocol; it cannot demonstrate clinical adjudication.
    claim["supportingInfo"] = [
        {
            "sequence": 1,
            "category": {"coding": [{"system": SYSTEM, "code": "note-sha256"}]},
            "valueString": note.note_sha256,
        }
    ]
    resources: tuple[dict[str, Any], ...] = (claim, patient, payer, provider, coverage)
    replacements = {
        f"{r['resourceType']}/{r['id']}": f"{r['resourceType']}/{r['id']}-{key[:20]}"
        for r in resources
    }

    def bind(value: Any) -> None:
        if isinstance(value, dict):
            for field, child in value.items():
                if field == "reference" and child in replacements:
                    value[field] = replacements[child]
                else:
                    bind(child)
        elif isinstance(value, list):
            for child in value:
                bind(child)

    for resource in resources:
        bind(resource)
        resource["id"] += "-" + key[:20]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "identifier": identifier(key)[0],
        "timestamp": "2026-11-13T00:00:00Z",
        "entry": [{"fullUrl": f"{r['resourceType']}/{r['id']}", "resource": r} for r in resources],
    }


class Loopback:
    """Fixed literal loopback, no proxies, redirects, credentials or URL following."""

    def __init__(self, base: str, *, timeout: float = 15) -> None:
        url = urlsplit(base)
        if (
            (url.scheme, url.hostname, url.path) != ("http", "127.0.0.1", "/fhir")
            or (url.username or url.password or url.query or url.fragment or not url.port)
            or not 0 < timeout <= 30
        ):
            raise ValueError("explicit owned loopback FHIR endpoint required")
        self.port, self.timeout = url.port, timeout

    def __call__(self, method: str, path: str, payload: dict[str, Any] | None) -> bytes:
        if (method, path) not in {
            ("GET", "metadata"),
            ("POST", "Claim/$submit"),
            ("POST", "Claim/$inquire"),
        } and not (
            method == "GET"
            and re.fullmatch(r"(?:Claim|Patient|Organization)/[A-Za-z0-9.-]{1,64}", path)
        ):
            raise ValueError("closed PAS operation required")
        raw = None if payload is None else encoded(payload)
        if raw is not None and len(raw) > MAX_BYTES:
            raise ValueError("request too large")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=self.timeout)
        deadline = time.monotonic() + self.timeout
        try:
            connection.request(
                method,
                "/fhir/" + path,
                body=raw,
                headers={
                    "Accept": "application/fhir+json",
                    "Content-Type": "application/fhir+json",
                },
            )
            response = connection.getresponse()
            if response.status != 200 or response.getheader("Content-Type", "").split(";")[
                0
            ] not in {"application/fhir+json", "application/json"}:
                raise ValueError("reference payer response refused")
            chunks, size = [], 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("reference payer deadline")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("response too large")
            return b"".join(chunks)
        finally:
            connection.close()


def object_from(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError("response too large")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("FHIR object required")
    return value


def has_id(resource: dict[str, Any], value: str) -> bool:
    return any(
        i.get("system") == SYSTEM and i.get("value") == value
        for i in resource.get("identifier", [])
        if isinstance(i, dict)
    )


def checked_response(
    raw: bytes,
    key: str,
    request: Submission,
    transport: Callable[[str, str, dict[str, Any] | None], bytes],
) -> Receipt:
    response = object_from(raw)
    entries = response.get("entry", [])
    if response.get("resourceType") != "Bundle" or not isinstance(entries, list) or not entries:
        raise ValueError("PAS response Bundle required")
    cr = entries[0]["resource"]
    if cr.get("resourceType") != "ClaimResponse" or cr.get("outcome") not in {
        "complete",
        "queued",
        "partial",
        "error",
    }:
        raise ValueError("PAS processing response required")
    claim_ref = cr.get("request", {}).get("reference", "")
    if not re.fullmatch(r"Claim/[A-Za-z0-9.-]{1,64}", claim_ref):
        raise ValueError("closed response Claim reference required")
    # The RI assigns a new Claim id and random Bundle identifier. A separate GET
    # verifies our stable identifier instead of assuming an echo is correlation.
    claim = object_from(transport("GET", claim_ref, None))
    if claim.get("resourceType") != "Claim" or not has_id(claim, key):
        raise ValueError("response belongs to another request")
    resources = {
        f"{e['resource']['resourceType']}/{e['resource']['id']}": e["resource"]
        for e in entries
        if isinstance(e, dict) and isinstance(e.get("resource"), dict) and "id" in e["resource"]
    }
    expected = (
        ("patient", request.case.subject_key, "Patient"),
        ("insurer", digest(request.case.payer_id), "Organization"),
        ("requestor", digest(request.case.provider_id), "Organization"),
    )
    for field, pin, kind in expected:
        ref = cr.get(field, {}).get("reference", "")
        if not re.fullmatch(kind + r"/[A-Za-z0-9.-]{1,64}", ref):
            raise ValueError("closed response identity reference required")
        resource = resources.get(ref)
        if resource is None:
            resource = object_from(transport("GET", ref, None))
        if resource.get("resourceType") != kind or not has_id(resource, pin):
            raise ValueError("response identity differs")
    codes = []
    for item in cr.get("item", []):
        if item.get("itemSequence") != 1:
            raise ValueError("unexpected service item")
        for adjudication in item.get("adjudication", []):
            for ext in adjudication.get("extension", []):
                if ext.get("url") == REVIEW:
                    for child in ext.get("extension", []):
                        if child.get("url") == REVIEW_CODE:
                            coding = child.get("valueCodeableConcept", {}).get("coding", [])
                            if len(coding) != 1 or coding[0].get("system") != X12:
                                raise ValueError("explicit review-action coding system required")
                            code = coding[0].get("code")
                            if code not in {"A1", "A2", "A3", "A4", "A6"}:
                                raise ValueError("unknown review code")
                            codes.append(code)
    if len(codes) != 1:
        raise ValueError("one explicit review action required")
    return Receipt(
        request_sha256=key,
        state="received",
        response_sha256=hashlib.sha256(raw).hexdigest(),
        processing=cr["outcome"],
        review_codes=tuple(codes),
    )


def checked_inquiry(
    raw: bytes,
    key: str,
    request: Submission,
    transport: Callable[[str, str, dict[str, Any] | None], bytes],
) -> Receipt:
    value = object_from(raw)
    parameters = value.get("parameter", [])
    if (
        value.get("resourceType") != "Parameters"
        or len(parameters) != 1
        or (parameters[0].get("name") != "responseBundle")
    ):
        raise ValueError("one uniquely correlated inquiry response required")
    result = checked_response(encoded(parameters[0]["resource"]), key, request, transport)
    return result.model_copy(update={"response_sha256": hashlib.sha256(raw).hexdigest()})


class PasClient:
    def __init__(
        self, journal: Path, transport: Callable[[str, str, dict[str, Any] | None], bytes]
    ) -> None:
        self.journal, self.transport = external(journal), transport
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS pas_attempts (tenant TEXT, request TEXT, "
                "pin TEXT NOT NULL, receipt TEXT NOT NULL, created TEXT NOT NULL, "
                "PRIMARY KEY(tenant,request))"
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.journal, timeout=5)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def submit(
        self, user: Principal, request: Submission, note: NoteInput, *, current_version: int
    ) -> Receipt:
        user = Principal.model_validate_json(user.canonical_json())
        request = Submission.model_validate_json(request.canonical_json())
        note = NoteInput.model_validate_json(note.canonical_json())
        user.require(request.case.case_id, write=True)
        if user.tenant_id != request.case.tenant_id or (note.tenant_id, note.case_id) != (
            request.case.tenant_id,
            request.case.case_id,
        ):
            raise PermissionError("PAS case scope differs")
        if (
            note.provenance != "invented"
            or note.use != "initial"
            or request.case.purpose != "initial_evidence"
            or request.case.service != "initial-cpap"
            or any(
                not value.startswith("demo-")
                for value in (request.case.payer_id, request.case.plan_id, request.case.provider_id)
            )
        ):
            raise PermissionError("invented reference-payer scope required")
        if (current_version, note.note_sha256, note.policy_sha256, note.service_date) != (
            request.case_version,
            request.note_sha256,
            request.policy_sha256,
            request.case.service_date,
        ):
            raise StateChanged("PAS requires current canonical version and pins")
        key = digest(request.canonical_json())
        receipt = Receipt(request_sha256=key, state="reserved")
        connection = self.connect()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT pin,receipt FROM pas_attempts WHERE tenant=? AND request=?",
                    (user.tenant_id, request.request_id),
                ).fetchone()
                if prior:
                    if prior[0] != key:
                        raise StateChanged("PAS identity reused with different payload")
                    return Receipt.model_validate_json(prior[1])
                connection.execute(
                    "INSERT INTO pas_attempts VALUES(?,?,?,?,?)",
                    (
                        user.tenant_id,
                        request.request_id,
                        key,
                        receipt.canonical_json(),
                        datetime.now(UTC).isoformat(),
                    ),
                )
            phase: Literal["send", "response_validation"] = "send"
            raw = None
            try:
                payload = bundle(request, note)
                raw = self.transport("POST", "Claim/$submit", payload)
                phase = "response_validation"
                receipt = checked_response(raw, key, request, self.transport)
            except Exception:
                # An accepted remote POST may have lost its response. Preserve that
                # uncertainty; never translate it into rejection or resend it.
                receipt = Receipt(
                    request_sha256=key,
                    state="unknown",
                    failure_phase=phase,
                    response_sha256=hashlib.sha256(raw).hexdigest() if raw else None,
                )
            with connection:
                connection.execute(
                    "UPDATE pas_attempts SET receipt=? WHERE tenant=? AND request=? AND pin=?",
                    (receipt.canonical_json(), user.tenant_id, request.request_id, key),
                )
            return receipt
        finally:
            connection.close()
