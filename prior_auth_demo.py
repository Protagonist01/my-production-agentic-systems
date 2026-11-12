"""Reproducible invented PA intake → assessment → local payer demo. No provider calls."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from prior_auth.assessment import CRITERIA
from prior_auth.contracts import Criterion, Policy, Span, digest
from prior_auth.review_contracts import Principal

from prior_auth_documents import normalize
from prior_auth_intake import CaseBinding, DocumentBinding, PolicyEntry, Registry
from prior_auth_pipeline import ImportRequest, checked, prepare
from prior_auth_profiling import Profiler
from prior_auth_sandbox import Submission, SyntheticPayer, response_preview
from prior_auth_scorecards import rules


def demo_policy() -> Policy:
    return Policy(
        policy_id="cms-ncd-240-4-v3",
        source_url="https://example.invalid/invented",
        source_sha256=digest("Invented"),
        text_sha256=digest("Invented"),
        effective_from=date(2008, 3, 13),
        review_status="ai_provisional",
        review_ref="invented-mechanism-demo-not-policy-validation",
        criteria=tuple(
            Criterion(
                criterion_id=k,
                description="Invented mechanism requirement",
                source=Span(start=0, end=8, quote="Invented"),
            )
            for k in CRITERIA
        ),
    )


def demo_request(raw: bytes, *, case_id: str = "demo-case") -> ImportRequest:
    policy = demo_policy()
    pin = digest(policy.canonical_json())
    case = CaseBinding(
        tenant_id="demo",
        case_id=case_id,
        subject_key=digest("invented-subject"),
        provider_id="demo-clinic",
        payer_id="demo-payer",
        plan_id="demo-plan",
        service="initial-cpap",
        service_date=date(2026, 11, 12),
        purpose="initial_evidence",
    )
    binding = DocumentBinding(
        document_id="demo-document",
        tenant_id=case.tenant_id,
        case_id=case.case_id,
        subject_key=case.subject_key,
        provider_id="demo-sleep-lab",
        kind="sleep_report",
        service=case.service,
        binding_review_ref="invented-binding",
        relevance="relevant",
        relevance_review_ref="invented-relevance",
        redaction_review_ref="invented-redaction",
    )
    registry = Registry(
        entries=(
            PolicyEntry(
                payer_id=case.payer_id,
                plan_id=case.plan_id,
                service=case.service,
                effective_from=date(2008, 3, 13),
                policy_sha256=pin,
                configuration_ref="invented-demo",
            ),
        )
    )
    return ImportRequest(
        case=case,
        document=binding,
        registry=registry,
        policy=policy,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        format="text",
        normalization_sha256=normalize(raw, "text").text_sha256,
    )


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    raw = b"AHI: 18 events/hour. Study duration: 2 hours."
    request, profiler = demo_request(raw), Profiler()
    with profiler.span("total"):
        prepared = prepare(raw, request, profiler)
        assert prepared.note is not None
        result = checked(
            prepared.note, prepared.policy, rules(prepared.note, prepared.policy), profiler
        )
        user = Principal(
            username="demo-reviewer",
            tenant_id="demo",
            actor_id="demo-operator",
            role="reviewer",
            case_ids=(request.case.case_id,),
        )
        payer = SyntheticPayer(
            output / "synthetic-payer.sqlite",
            payer_id="demo-payer",
            scenario="additional_information",
        )
        submission = Submission(
            request_id="demo-submission",
            case=request.case,
            case_version=1,
            note_sha256=prepared.note.note_sha256,
            policy_sha256=prepared.note.policy_sha256,
        )
        response = payer.submit(
            user, submission, prepared.note, current_version=1, profiler=profiler
        )
    report = {
        "mode": "invented-development-demo",
        "provider_calls": 0,
        "clinical_validation": False,
        "intake": prepared.decision.model_dump(mode="json"),
        "assessment": result.model_dump(mode="json"),
        "payer_preview": response_preview(response),
        "durable_payer_receipts": payer.count(),
        "timing": profiler.report(),
        "limits": [
            "no real insurer/EHR connected",
            "no clinical reference validation",
            "Postgres intake handoff is tested separately, not exercised in this demo",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps({k: report[k] for k in ("mode", "provider_calls", "durable_payer_receipts")}))


if __name__ == "__main__":
    main()
