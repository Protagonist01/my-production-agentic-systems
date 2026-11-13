"""Scoped fixed-metadata receipts and source locations; no note bodies in responses."""

import json
from datetime import datetime
from typing import Annotated, Literal

from agent_harness.contracts import WireContract
from prior_auth.contracts import Digest, Id, NoteInput
from prior_auth.review_contracts import Principal, StateChanged
from prior_auth.review_store import ConnectionFactory, ReviewStore
from pydantic import Field

from prior_auth_documents import Document, Format, Region
from prior_auth_intake import IntakeDecision


class Receipt(WireContract):
    document_id: Id
    request_sha256: Digest
    prepared_sha256: Digest
    source_sha256: Digest
    decision: IntakeDecision
    resulting_version: Annotated[int, Field(ge=1)] | None
    created_at: datetime


class NoteRegion(WireContract):
    source_region: Region
    note_start: Annotated[int, Field(ge=0)]
    note_end: Annotated[int, Field(gt=0)]


class SourceLocation(WireContract):
    document_id: Id
    source_sha256: Digest
    note_sha256: Digest
    document_text_sha256: Digest
    format: Format
    coordinate_units: Literal["pdf_points", "raster_pixels", "not_applicable"]
    imported_version: Annotated[int, Field(ge=1)]
    current_version: Annotated[int, Field(ge=1)]
    regions: tuple[NoteRegion, ...]


class IntakeReader:
    def __init__(self, connect: ConnectionFactory) -> None:
        self.store = ReviewStore(connect)

    def receipt(self, user: Principal, case_id: str, document_id: str) -> Receipt:
        user.require(case_id)
        with self.store.transaction() as c:
            row = c.execute(
                "SELECT * FROM prior_auth_intake.receipts "
                "WHERE tenant_id=%s AND case_id=%s AND document_id=%s",
                (user.tenant_id, case_id, document_id),
            ).fetchone()
        if row is None:
            raise LookupError("intake receipt unavailable")
        return Receipt(
            document_id=row["document_id"],
            request_sha256=row["request_sha256"],
            prepared_sha256=row["prepared_sha256"],
            source_sha256=row["source_sha256"],
            decision=IntakeDecision.model_validate_json(json.dumps(row["decision"])),
            resulting_version=row["resulting_version"],
            created_at=row["created_at"],
        )

    def locate(
        self,
        user: Principal,
        case_id: str,
        document_id: str,
        *,
        note_sha256: str,
        start: int,
        end: int,
    ) -> SourceLocation:
        user.require(case_id)
        with self.store.transaction() as c:
            # One statement snapshot: do not combine source metadata from one case
            # version with the current note read by another statement after a delivery.
            row = c.execute(
                "SELECT d.*,c.note,c.version AS current_version, "
                "r.source_sha256 AS receipt_source_sha,r.resulting_version AS receipt_version "
                "FROM prior_auth_intake.documents d JOIN prior_auth_app.cases c "
                "ON c.tenant_id=d.tenant_id AND c.case_id=d.case_id "
                "JOIN prior_auth_intake.receipts r ON r.tenant_id=d.tenant_id "
                "AND r.case_id=d.case_id AND r.document_id=d.document_id "
                "WHERE d.tenant_id=%s AND d.case_id=%s AND d.document_id=%s",
                (user.tenant_id, case_id, document_id),
            ).fetchone()
        if row is None:
            raise LookupError("source location unavailable")
        note = NoteInput.model_validate_json(json.dumps(row["note"]))
        document = Document.model_validate_json(json.dumps(row["normalized"]))
        offset = int(row["note_start"])
        if (
            note_sha256 != note.note_sha256
            or document.source_sha256 != row["receipt_source_sha"]
            or row["case_version"] != row["receipt_version"]
            or offset < 0
            or int(row["case_version"]) > int(row["current_version"])
            or note.text[offset : offset + len(document.text)] != document.text
        ):
            raise StateChanged("current note or saved document location differs")
        regions = document.locate(start - offset, end - offset)
        if not regions:
            raise ValueError("requested range has no source region")
        units: Literal["pdf_points", "raster_pixels", "not_applicable"] = "not_applicable"
        if document.format == "pdf_text":
            units = "pdf_points"
        elif document.format == "pdf_ocr":
            units = "raster_pixels"
        return SourceLocation(
            document_id=document_id,
            source_sha256=document.source_sha256,
            note_sha256=note.note_sha256,
            document_text_sha256=document.text_sha256,
            format=document.format,
            coordinate_units=units,
            imported_version=row["case_version"],
            current_version=row["current_version"],
            regions=tuple(
                NoteRegion(source_region=r, note_start=offset + r.start, note_end=offset + r.end)
                for r in regions
            ),
        )
