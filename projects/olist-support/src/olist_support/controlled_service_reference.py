"""Explicit development adapter; the loader verifies original accepted packet bytes.

Wrapper pins are documentary provenance, not authenticated owner identity. A future
study must verify its whole prepared package/source bindings before admitting evidence.
"""

import json
from typing import Final, Literal, Self

from agent_harness.contracts import Contract
from agent_harness.release_contracts import sha256
from pydantic import TypeAdapter, model_validator

from olist_support.controlled_reference import ControlledReference, draft
from olist_support.routing_contracts import RoutingPlan

ACCEPTANCE: Final = "e6c1da143e18e8d80ba133585480beda453ccfbc6f3311e67846a44891b78979"
METHOD: Final = "6bcd0d9541217af327381a5bdf7367c06c2fa277f3e84d0e6624dbb1c6275ccc"
REFERENCES: Final = "9c611469e4428126870f735608d0cd1c4a2fd6613036736d0c552f0707dd1140"


class ControlledServiceReference(Contract):
    version: Literal["olist-controlled-service-reference-v1"] = (
        "olist-controlled-service-reference-v1"
    )
    source: ControlledReference
    acceptance_sha256: Literal[
        "e6c1da143e18e8d80ba133585480beda453ccfbc6f3311e67846a44891b78979"
    ] = ACCEPTANCE
    method_sha256: Literal["6bcd0d9541217af327381a5bdf7367c06c2fa277f3e84d0e6624dbb1c6275ccc"] = (
        METHOD
    )
    reference_file_sha256: Literal[
        "9c611469e4428126870f735608d0cd1c4a2fd6613036736d0c552f0707dd1140"
    ] = REFERENCES
    provenance: Literal["accepted_constructed_development"] = "accepted_constructed_development"
    qualification_allowed: Literal[False] = False
    release_allowed: Literal[False] = False

    @property
    def text(self) -> str:
        return self.source.input.request

    @property
    def expected(self) -> RoutingPlan:
        return self.source.expected

    @model_validator(mode="after")
    def known_meaning(self) -> Self:
        if self.source not in draft():
            raise ValueError("only the original twelve accepted development meanings apply")
        return self


def bind_accepted(
    acceptance_raw: bytes, method_raw: bytes, references_raw: bytes
) -> tuple[ControlledServiceReference, ...]:
    """Exact original file pins; no rewriting history or promoting other generated amounts."""
    if tuple(map(sha256, (acceptance_raw, method_raw, references_raw))) != (
        ACCEPTANCE,
        METHOD,
        REFERENCES,
    ):
        raise ValueError("accepted constructed packet bytes differ")
    owner = json.loads(acceptance_raw)
    if (
        owner["exact_reply"] != "Accept this constructed development method"
        or owner["method_proposal_sha256"] != METHOD
        or owner["reference_file_sha256"] != REFERENCES
        or owner["provider_calls_authorized"] != 0
        or owner["release_allowed"] is not False
    ):
        raise ValueError("accepted development scope differs")
    sources = TypeAdapter(tuple[ControlledReference, ...]).validate_json(references_raw)
    if sources != draft():
        raise ValueError("current generator differs from original accepted references")
    return tuple(ControlledServiceReference(source=source) for source in sources)
