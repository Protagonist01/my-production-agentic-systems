"""Private source provenance and closed narrative-only classifier inputs."""

from datetime import date
from typing import Annotated, Literal

from agent_harness.contracts import Contract
from pydantic import Field

ARCHIVE_URL = (
    "https://files.consumerfinance.gov/f/documents/"
    "CCDB_Export_5_September_2023_through_March_2024.zip"
)
ARCHIVE_MEMBER = "CCDB_Export_5_September_2023_through_March_2024.csv"
TAXONOMY_URL = (
    "https://files.consumerfinance.gov/f/documents/"
    "cfpb_consumer_complaint_form_product_issue_options_August_2023_FINAL.pdf"
)
TAXONOMY_VERSION = "cfpb-form-effective-2023-08-24"
POLICY_VERSION = "cfpb-archive-temporal-exact-groups-v1"
COLUMNS = (
    "Date received",
    "Product",
    "Sub-product",
    "Issue",
    "Sub-issue",
    "Consumer complaint narrative",
    "Company public response",
    "Company",
    "State",
    "ZIP code",
    "Tags",
    "Submitted via",
    "Date sent to company",
    "Company response to consumer",
    "Timely response?",
    "Complaint ID",
)
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Split = Literal["development", "regression", "holdout"]


class SourcePin(Contract):
    archive_sha256: Digest
    taxonomy_sha256: Digest


class ComplaintInput(Contract):
    """No target, source identifier, company, response, date or split field exists here."""

    case_id: Digest
    narrative: Annotated[str, Field(min_length=1)]


class ConsumerTarget(Contract):
    """Scorer-only consumer selections; these are not independently reviewed truth."""

    case_id: Digest
    product: Annotated[str, Field(min_length=1)]
    sub_product: str
    issue: Annotated[str, Field(min_length=1)]
    sub_issue: str
    received: date
    split: Split
    group_id: Digest


def temporal_split(received: date) -> Split | None:
    if date(2023, 9, 1) <= received <= date(2023, 12, 31):
        return "development"
    if date(2024, 1, 1) <= received <= date(2024, 2, 29):
        return "regression"
    if date(2024, 3, 1) <= received <= date(2024, 3, 31):
        return "holdout"
    return None
