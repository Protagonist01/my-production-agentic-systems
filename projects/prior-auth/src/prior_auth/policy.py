"""Explicit reviewed national-policy slice; no silent LCD or code-catalog substitution."""

import json
from datetime import date

from prior_auth.contracts import Criterion, Policy, digest
from prior_auth.source import unique_span
from prior_auth.source_io import SourcePin


def compile_policy(text: str, pin: SourcePin) -> Policy:
    if pin.provenance != "government_policy" or "ncdid=226" not in pin.url.lower():
        raise ValueError("selected national policy source required")
    lines = text.splitlines()

    def containing(prefix: str) -> str:
        found = [line for line in lines if line.startswith(prefix)]
        if len(found) != 1:
            raise ValueError("selected policy prose changed; review source mapping")
        return found[0]

    mappings = (
        (
            "adult_osa",
            "Adult with documented obstructive sleep apnea.",
            containing("The use of CPAP is covered"),
        ),
        (
            "education",
            "CPAP use education completed before device use.",
            containing("The provider of CPAP must conduct education"),
        ),
        (
            "clinical_evaluation",
            "Clinical evaluation documents the positive OSA diagnosis.",
            containing("A positive diagnosis of OSA"),
        ),
        (
            "sleep_test",
            "Positive attended PSG or permitted Type II/III/IV home study; "
            "Type IV needs at least three channels.",
            text[text.index("attended PSG performed") : text.index("The sleep test must")].strip(),
        ),
        (
            "physician_order",
            "Sleep study previously ordered by treating physician and appropriately supervised.",
            containing("The sleep test must"),
        ),
        (
            "severity",
            "AHI/RDI at least 15 events/hour, or 5 through 14 "
            "with a listed symptom or comorbidity.",
            text[
                text.index("AHI or RDI greater") : text.index("The AHI or RDI is calculated")
            ].strip(),
        ),
        (
            "event_count",
            "A study shorter than two hours must include the events required "
            "for two hours at its reported rate.",
            containing("The AHI or RDI is calculated"),
        ),
    )
    criteria = tuple(
        Criterion.model_validate_json(
            '{"criterion_id":'
            + json.dumps(key)
            + ',"description":'
            + json.dumps(description)
            + ',"source":'
            + unique_span(text, quote).canonical_json()
            + "}"
        )
        for key, description, quote in mappings
    )
    return Policy(
        policy_id="cms-ncd-240-4-v3",
        source_url=pin.url,
        source_sha256=pin.sha256,
        text_sha256=digest(text),
        effective_from=date(2008, 3, 13),
        criteria=criteria,
        review_status="ai_provisional",
        review_ref="AI-provisional-P1-v1; no qualified review",
    )
